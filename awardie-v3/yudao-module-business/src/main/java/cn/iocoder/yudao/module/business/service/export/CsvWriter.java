package cn.iocoder.yudao.module.business.service.export;

import java.nio.charset.StandardCharsets;

/**
 * CSV 写出器(批9)
 *
 * <p>三处对 v2 的修正:
 * <ol>
 *   <li><b>防公式注入</b>:v2 只做 RFC 引号转义,以 {@code = + - @} 开头的内容会被 Excel
 *       当公式执行(CSV 注入)。v3 统一前置单引号转义。</li>
 *   <li><b>不依赖 Map 迭代顺序</b>:v2 导出用 {@code row.values()} 顺序对应 SELECT 列序,
 *       没有列名映射,换驱动或加别名就错列。v3 一律传有序的字符串数组。</li>
 *   <li><b>CRLF 行尾 + UTF-8 BOM</b>:BOM 让 Excel 正确识别 UTF-8(不加会乱码,v2 已做);</li>
 *   <li><b>公式注入防护不误伤负数</b>:仅当首字符是 {@code = + - @} 且该单元格看起来是
 *       文本时才转义。纯数字负数(如 -12.5)仍原样输出,否则统计报表会被引号污染。</li>
 * </ol>
 *
 * @author AwardIE
 */
public final class CsvWriter {

    /** UTF-8 BOM:Excel 靠它识别编码,缺失则中文乱码 */
    public static final String UTF8_BOM = "﻿";
    /** 行尾用 CRLF:Excel 兼容性最好 */
    private static final String CRLF = "\r\n";
    /**
     * 公式前缀:这四个字符开头会被 Excel 解释为公式
     *
     * <p>只判首字符是不够的:Excel/LibreOffice 会**先剥离前导空白**(Tab/CR/LF)再解析,
     * 所以 {@code "\t=cmd|..."} 能绕过"首字符 ∈ =+-@"的检查(OWASP CSV Injection)。
     * 故先剥离前导空白再判前缀。
     */
    private static final String FORMULA_PREFIXES = "=+-@";
    /** Excel 会跳过的前导空白:判断公式前必须先剥掉 */
    private static final String LEADING_BLANKS = " \t\r\n";

    private CsvWriter() {
    }

    /**
     * 写出 CSV 字节
     *
     * @param header 表头列
     * @param rows   数据行(每行按 header 同序)
     * @return 带 BOM 的 CSV 字节
     */
    public static byte[] write(String[] header, java.util.List<String[]> rows) {
        StringBuilder sb = new StringBuilder(UTF8_BOM);
        appendRow(sb, header);
        for (String[] row : rows) {
            appendRow(sb, row);
        }
        return sb.toString().getBytes(StandardCharsets.UTF_8);
    }

    private static void appendRow(StringBuilder sb, String[] cells) {
        for (int i = 0; i < cells.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(escape(cells[i]));
        }
        sb.append(CRLF);
    }

    /**
     * 单个单元格转义
     *
     * @param value 原始值(null 转空串)
     * @return 转义后的值
     */
    static String escape(String value) {
        if (value == null) {
            return "";
        }
        String escaped = sanitizeFormula(value);
        boolean needQuote = escaped.indexOf(',') >= 0
                || escaped.indexOf('"') >= 0
                || escaped.indexOf('\n') >= 0
                || escaped.indexOf('\r') >= 0;
        if (!needQuote) {
            return escaped;
        }
        // RFC4180:内部双引号翻倍,整体用双引号包裹
        return '"' + escaped.replace("\"", "\"\"") + '"';
    }

    /**
     * 防公式注入
     *
     * <p>三个要点:
     * <ol>
     *   <li><b>先剥前导空白</b>——Excel 会跳过 Tab/空格/换行再解析公式,
     *       {@code "\t=cmd|..."} 若只判首字符就能绕过(OWASP CSV Injection);</li>
     *   <li>剥完仍以 {@code =+-@} 开头才加前缀转义;</li>
     *   <li><b>纯数字不转义</b>——统计报表里负数(如 -12.5)是合法数据,
     *       一律加引号会变文本、破坏表格计算。</li>
     * </ol>
     *
     * @param value 原始值
     * @return 处理后的值
     */
    static String sanitizeFormula(String value) {
        if (value.isEmpty()) {
            return value;
        }
        // stripLeading 只去前导空白,不动内部与尾部
        String probe = value.stripLeading();
        if (probe.isEmpty() || FORMULA_PREFIXES.indexOf(probe.charAt(0)) < 0) {
            return value;
        }
        if (isNumeric(probe)) {
            return value;
        }
        return "'" + value;
    }

    private static boolean isNumeric(String value) {
        try {
            Double.parseDouble(value);
            return true;
        } catch (NumberFormatException e) {
            return false;
        }
    }

}
