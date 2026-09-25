package cn.iocoder.yudao.module.business.service.innovation;

import cn.hutool.core.util.StrUtil;
import cn.iocoder.yudao.module.business.service.innovation.InnovationStudentMatcher.MemberRef;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * 大创"其他成员"列的解析与序列化(批8,以 V1 数据为准)
 *
 * <p>为什么按 V1 的三种格式来:V1 库实测 `other_members` 存的是
 * {@code [{"姓名":"江圣","学号":"212206016"}, ...]} 结构化对象数组;
 * V1 代码(`InnovationProject._parse_other_members`)另兼容旧格式
 * {@code ["张三(2022001)"]} 字符串数组与逗号分隔纯姓名。三种都认才能把
 * V1/V2 的存量数据原样迁进 v3。
 *
 * <p>序列化不再手拼 JSON 字符串(v2 那样做,成员名含引号/反斜杠就会拼出坏 JSON),
 * 改用 Jackson;输出统一为 V1 的对象数组格式(姓名 + 学号),这样 ETL 从 V1 迁来的数据
 * 与 v3 新导入的数据格式一致。
 *
 * @author AwardIE
 */
final class StudentMembers {

    /** 成员分隔符(沿 v2:顿号、中英文逗号、中英文分号) */
    private static final String SEPARATORS = "[、,，;；]";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** 成员 JSON 的姓名字段 */
    private static final String KEY_NAME = "姓名";
    /** 成员 JSON 的学号字段 */
    private static final String KEY_STUDENT_ID = "学号";

    /**
     * 解析成员文本为引用列表(三种格式都认)
     *
     * @param text 成员原文,可空
     * @return 成员引用列表;纯姓名项的 studentId 为 null
     */
    static List<MemberRef> parseMembers(String text) {
        if (StrUtil.isBlank(text)) {
            return List.of();
        }
        String trimmed = text.trim();
        // 格式1:V1 新格式 JSON 数组 [{"姓名":"江圣","学号":"212206016"}]
        if (trimmed.startsWith("[")) {
            List<MemberRef> parsed = parseJsonArray(trimmed);
            if (!parsed.isEmpty()) {
                return parsed;
            }
        }
        // 格式2/3:分隔文本,项内可能是 "张三(2022001)" 或纯姓名
        return parseDelimited(trimmed);
    }

    /** 解析 JSON 数组格式(对象数组或 "姓名(学号)" 字符串数组) */
    private static List<MemberRef> parseJsonArray(String json) {
        try {
            JsonNode root = MAPPER.readTree(json);
            if (!root.isArray()) {
                return List.of();
            }
            List<MemberRef> refs = new ArrayList<>(root.size());
            for (JsonNode node : root) {
                if (node.isObject()) {
                    refs.add(new MemberRef(
                            StrUtil.trim(StrUtil.nullToEmpty(node.path(KEY_NAME).asText(null))),
                            StrUtil.trim(StrUtil.nullToEmpty(node.path(KEY_STUDENT_ID).asText(null)))));
                } else if (node.isTextual()) {
                    refs.addAll(parseNameWithId(node.asText()));
                }
            }
            return refs;
        } catch (Exception e) {
            // 非法 JSON:退回分隔文本解析,不因格式怪异让整行导入失败
            return List.of();
        }
    }

    /** 解析分隔文本(顿号/逗号/分号),项内识别 "姓名(学号)" */
    private static List<MemberRef> parseDelimited(String text) {
        List<MemberRef> refs = new ArrayList<>();
        for (String item : Arrays.stream(text.split(SEPARATORS))
                .map(String::trim).filter(s -> !s.isEmpty()).toList()) {
            refs.addAll(parseNameWithId(item));
        }
        return refs;
    }

    /**
     * 解析单项:"张三(212206016)" → 姓名=张三,学号=212206016;否则整体作为纯姓名
     */
    private static List<MemberRef> parseNameWithId(String item) {
        String value = item;
        // Excel 里常见 "张三" 这种带引号的写法,先剥外层引号
        if (value.length() >= 2 && value.startsWith("\"") && value.endsWith("\"")) {
            value = value.substring(1, value.length() - 1).trim();
        }
        int open = value.indexOf('(');
        int close = value.lastIndexOf(')');
        if (open > 0 && close > open) {
            String name = value.substring(0, open).trim();
            String studentId = value.substring(open + 1, close).trim();
            return List.of(new MemberRef(name, studentId));
        }
        return List.of(new MemberRef(value, null));
    }

    /**
     * 成员列表转 JSON 字符串(输出 V1 的对象数组格式)
     *
     * @param refs 成员引用列表
     * @return JSON 数组字符串;入参空时返回 "[]"
     */
    static String toJson(List<MemberRef> refs) {
        if (refs == null || refs.isEmpty()) {
            return "[]";
        }
        List<Map<String, String>> payload = refs.stream()
                .map(r -> {
                    Map<String, String> m = new java.util.LinkedHashMap<>();
                    if (StrUtil.isNotBlank(r.name())) {
                        m.put(KEY_NAME, r.name());
                    }
                    if (StrUtil.isNotBlank(r.studentId())) {
                        m.put(KEY_STUDENT_ID, r.studentId());
                    }
                    return m;
                })
                .filter(m -> !m.isEmpty())
                .toList();
        try {
            return MAPPER.writeValueAsString(payload);
        } catch (Exception e) {
            // 普通字符串序列化失败只可能是内存/编码异常,退化为空数组不阻断导入
            return "[]";
        }
    }

    /**
     * 成员原文转 JSON(导入路径用:解析后再序列化,统一成 V1 对象数组格式)
     *
     * @param text 成员原文
     * @return JSON 数组字符串
     */
    static String toJson(String text) {
        return toJson(parseMembers(text));
    }

    private StudentMembers() {
    }

}
