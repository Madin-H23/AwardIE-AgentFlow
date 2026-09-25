package cn.iocoder.yudao.module.business.service.export;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 批9 CSV 写出单测
 *
 * <p>覆盖 v2 的三处缺陷对应的防护:BOM、公式注入、显式列序(不用 Map 迭代序)。
 *
 * @author AwardIE
 */
class CsvWriterTest {

    @Test
    void writesUtf8BomForExcel() {
        byte[] bytes = CsvWriter.write(new String[]{"学号", "姓名"}, List.of());
        // BOM 是 UTF-8 的 EF BB BF——Excel 靠它识别编码,缺失则中文乱码
        assertThat(bytes[0]).isEqualTo((byte) 0xEF);
        assertThat(bytes[1]).isEqualTo((byte) 0xBB);
        assertThat(bytes[2]).isEqualTo((byte) 0xBF);
    }

    @Test
    void writesHeaderWithCrlf() {
        byte[] bytes = CsvWriter.write(new String[]{"学号", "姓名"}, List.of());
        String text = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
        // 去掉 BOM 后应恰好是表头 + CRLF
        assertThat(text.substring(1)).isEqualTo("学号,姓名\r\n");
    }

    @Test
    void escapesCommaQuoteAndNewline() {
        assertThat(CsvWriter.escape("含,逗号")).isEqualTo("\"含,逗号\"");
        assertThat(CsvWriter.escape("含\"引号\"")).isEqualTo("\"含\"\"引号\"\"\"");
        assertThat(CsvWriter.escape("含\n换行")).isEqualTo("\"含\n换行\"");
        assertThat(CsvWriter.escape("含\r\n回车换行")).isEqualTo("\"含\r\n回车换行\"");
    }

    @Test
    void sanitizesFormulaInjection() {
        // v2 只做 RFC 转义,这些内容会被 Excel 当公式执行(CVE 类 CSV 注入)
        assertThat(CsvWriter.sanitizeFormula("=1+1")).isEqualTo("'=1+1");
        assertThat(CsvWriter.sanitizeFormula("+SUM(A1)")).isEqualTo("'+SUM(A1)");
        assertThat(CsvWriter.sanitizeFormula("-2+3")).isEqualTo("'-2+3");
        assertThat(CsvWriter.sanitizeFormula("@SUM(A1)")).isEqualTo("'@SUM(A1)");
    }

    @Test
    void sanitizesFormulaHiddenBehindLeadingBlanks() {
        // Excel/LibreOffice 先剥离前导 Tab/空格/换行再解析公式,
        // 只判首字符的实现可被 "\t=cmd|..." 绕过(OWASP CSV Injection)
        assertThat(CsvWriter.sanitizeFormula("\t=cmd|'/C calc'!A0"))
                .as("Tab 前导的公式必须被转义").isEqualTo("'\t=cmd|'/C calc'!A0");
        assertThat(CsvWriter.sanitizeFormula(" =1+1")).isEqualTo("' =1+1");
        assertThat(CsvWriter.sanitizeFormula("\n=SUM(A1)")).isEqualTo("'\n=SUM(A1)");
        assertThat(CsvWriter.sanitizeFormula("\r=1+1")).isEqualTo("'\r=1+1");
    }

    @Test
    void doesNotSanitizeNumbersWithLeadingSpaces() {
        // 带前导空格的纯数字仍是数值,不该被加引号变文本
        assertThat(CsvWriter.sanitizeFormula(" -12.5")).isEqualTo(" -12.5");
        assertThat(CsvWriter.sanitizeFormula("  42")).isEqualTo("  42");
    }

    @Test
    void doesNotSanitizeNumericValues() {
        // 负数/小数是合法统计值,加引号会变文本破坏表格计算
        assertThat(CsvWriter.sanitizeFormula("-12.5")).isEqualTo("-12.5");
        assertThat(CsvWriter.sanitizeFormula("0")).isEqualTo("0");
        assertThat(CsvWriter.sanitizeFormula("+3")).isEqualTo("+3");
    }

    @Test
    void leavesNormalTextUntouched() {
        assertThat(CsvWriter.sanitizeFormula("正常姓名")).isEqualTo("正常姓名");
        assertThat(CsvWriter.sanitizeFormula("")).isEqualTo("");
        // 公式字符不在首位则不处理
        assertThat(CsvWriter.sanitizeFormula("姓名=张三")).isEqualTo("姓名=张三");
    }

    @Test
    void nullCellBecomesEmpty() {
        assertThat(CsvWriter.escape(null)).isEmpty();
    }

    @Test
    void columnOrderIsExplicitNotMapOrder() {
        // v2 依赖 row.values() 顺序对应 SELECT 列序,换驱动就错列;
        // v3 传有序数组,列序由调用方写死
        byte[] bytes = CsvWriter.write(new String[]{"学号", "姓名", "竞赛"},
                List.<String[]>of(new String[]{"212206030", "张三", "挑战杯"}));
        String text = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
        assertThat(text).contains("学号,姓名,竞赛").contains("212206030,张三,挑战杯");
    }

    @Test
    void emptyRowsStillWritesHeader() {
        byte[] bytes = CsvWriter.write(new String[]{"学号", "姓名"}, List.of());
        String text = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
        // 空结果导出只有表头(不是空文件)
        assertThat(text).isEqualTo("﻿学号,姓名\r\n");
    }

}
