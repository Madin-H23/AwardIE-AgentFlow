package cn.iocoder.yudao.module.business.service.pendingsubmission;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_TYPE_UNKNOWN;

/**
 * 五类成果字段校验器(批4):语义逐条对齐 v2 SubmissionService 与 v1 _validate_*_data
 *
 * <p>纯函数组件(不依赖 Spring 上下文,可直测);校验结果分两类——
 * completeness=必填缺失、content=格式/取值问题,与 v2 的 validation_result 结构一致。
 *
 * @author AwardIE
 */
@Component
public class SubmissionValidator {

    /** award 必填字段(v2 AWARD_REQUIRED) */
    private static final List<String> AWARD_REQUIRED =
            List.of("competition_name", "award_level", "winner_name", "date");
    /** 专利类型白名单 */
    private static final Set<String> PATENT_TYPES = Set.of("发明专利", "实用新型", "外观设计");
    /** 日期年份下限/上限(v2 同) */
    private static final int MIN_YEAR = 2000;
    private static final int MAX_YEAR = 2100;
    /** 登记号长度(v2:11 位) */
    private static final int REGISTRATION_NUMBER_LENGTH = 11;
    /** 申请号最小长度(v2:<5 视为格式错) */
    private static final int APPLICATION_NUMBER_MIN_LENGTH = 5;
    /** 申请号前缀(v2:CN 开头) */
    private static final String APPLICATION_NUMBER_PREFIX = "CN";
    /** 登记号前缀(v2:20 开头) */
    private static final String REGISTRATION_NUMBER_PREFIX = "20";

    /** 五类成果类型码(v2 语义;controller 层 defaultValue="award" 与之对应) */
    public static final String TYPE_AWARD = "award";
    public static final String TYPE_PATENT = "patent";
    public static final String TYPE_SOFTWARE = "software";
    public static final String TYPE_INNOVATION = "innovation";
    public static final String TYPE_OTHER = "other";

    private static final DateTimeFormatter[] DATE_FORMATS = {
            DateTimeFormatter.ofPattern("yyyy-MM-dd"),
            DateTimeFormatter.ofPattern("yyyy-MM"),
            DateTimeFormatter.ofPattern("yyyy-M"),
            DateTimeFormatter.ofPattern("yyyy/MM/dd"),
    };
    private static final DateTimeFormatter YEAR_MONTH_FORMAT = DateTimeFormatter.ofPattern("yyyy-M");

    /**
     * 校验结果
     *
     * @param contentIssues       格式/取值问题
     * @param completenessIssues 必填缺失问题
     */
    public record ValidationResult(List<String> contentIssues, List<String> completenessIssues) {

        public boolean isValid() {
            return contentIssues.isEmpty() && completenessIssues.isEmpty();
        }
    }

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /**
     * 按成果类型分发校验
     *
     * @param achievementType 成果类型
     * @param dataJson        成果字段 JSON
     * @return 校验结果
     */
    public ValidationResult validate(String achievementType, String dataJson) {
        List<String> completeness = new ArrayList<>();
        List<String> content = new ArrayList<>();
        Map<String, Object> data = parseData(dataJson);
        // if-else 分发而非 switch:p3c SwitchStatementRule 要求 default 标签,而箭头语法的
        // default 块与表达式 case 类型不兼容(java 编译期报错),5 个分支无穿透用 if-else 更直白
        if (TYPE_AWARD.equals(achievementType)) {
            validateAward(data, completeness, content);
        } else if (TYPE_PATENT.equals(achievementType)) {
            validatePatent(data, completeness, content);
        } else if (TYPE_SOFTWARE.equals(achievementType)) {
            validateSoftware(data, completeness, content);
        } else if (TYPE_INNOVATION.equals(achievementType)) {
            requireField(data, "project_name", "项目名称不能为空", completeness);
        } else if (TYPE_OTHER.equals(achievementType)) {
            requireField(data, "title", "成果名称不能为空", completeness);
        } else {
            // 含 achievementType == null 的兜底
            throw exception(PENDING_ACHIEVEMENT_TYPE_UNKNOWN);
        }
        return new ValidationResult(List.copyOf(content), List.copyOf(completeness));
    }

    /**
     * 校验结果 → validation_result 列的 JSON(结构与 v2 一致)
     *
     * @param result 校验结果
     * @return JSON 字符串
     */
    public String toValidationJson(ValidationResult result) {
        try {
            Map<String, Object> payload = Map.of(
                    "is_valid", result.isValid(),
                    "content_issues", result.contentIssues(),
                    "completeness_issues", result.completenessIssues());
            return MAPPER.writeValueAsString(payload);
        } catch (Exception e) {
            throw new IllegalStateException("校验结果序列化失败", e);
        }
    }

    private static void validateAward(Map<String, Object> data, List<String> completeness, List<String> content) {
        for (String field : AWARD_REQUIRED) {
            if (isBlank(data, field)) {
                completeness.add("缺少必填字段: " + field);
            }
        }
        String date = str(data, "date");
        if (!date.isBlank() && !validDate(date)) {
            content.add("日期格式不正确,支持格式:YYYY-MM-DD、YYYY-MM、YYYY-M");
        }
    }

    private static void validatePatent(Map<String, Object> data, List<String> completeness, List<String> content) {
        requireField(data, "patent_name", "专利名称不能为空", completeness);
        String appNo = str(data, "application_number");
        if (!appNo.isBlank()) {
            if (!appNo.startsWith(APPLICATION_NUMBER_PREFIX)) {
                content.add("申请号应以CN开头");
            }
            if (appNo.length() < APPLICATION_NUMBER_MIN_LENGTH) {
                content.add("申请号格式不正确");
            }
        }
        String patentType = str(data, "patent_type");
        if (!patentType.isBlank() && !PATENT_TYPES.contains(patentType)) {
            content.add("专利类型应为:发明专利、实用新型或外观设计");
        }
    }

    private static void validateSoftware(Map<String, Object> data, List<String> completeness, List<String> content) {
        requireField(data, "software_name", "软件名称不能为空", completeness);
        String registration = str(data, "registration_number");
        if (registration.isBlank()) {
            return;
        }
        boolean badPrefix = !registration.startsWith(REGISTRATION_NUMBER_PREFIX);
        boolean badLength = registration.length() != REGISTRATION_NUMBER_LENGTH;
        if (badPrefix || badLength) {
            // 注:v2 原文案示例 "2023SR123456" 实为 12 位且含字母,与"11 位数字"自相矛盾;
            // 本批保持 v2 校验规则(20 开头且长度=11)等价,仅修正文案,规则是否放宽见 02-实施 挂账
            content.add("登记号格式不正确,应以 20 开头且长度为 11 位");
        }
    }

    private static void requireField(Map<String, Object> data, String field, String message,
            List<String> completeness) {
        if (isBlank(data, field)) {
            completeness.add(message);
        }
    }

    private static boolean validDate(String value) {
        for (DateTimeFormatter format : DATE_FORMATS) {
            try {
                int year = LocalDate.parse(value, format).getYear();
                return year >= MIN_YEAR && year <= MAX_YEAR;
            } catch (Exception ignored) {
                // 尝试下一格式
            }
        }
        try {
            int year = YearMonth.parse(value, YEAR_MONTH_FORMAT).getYear();
            return year >= MIN_YEAR && year <= MAX_YEAR;
        } catch (Exception ignored) {
            return false;
        }
    }

    private static Map<String, Object> parseData(String dataJson) {
        String body = dataJson == null || dataJson.isBlank() ? "{}" : dataJson;
        try {
            return MAPPER.readValue(body, new TypeReference<Map<String, Object>>() {
            });
        } catch (Exception e) {
            throw new IllegalArgumentException("achievement_data 不是合法 JSON");
        }
    }

    private static String str(Map<String, Object> data, String key) {
        Object value = data.get(key);
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static boolean isBlank(Map<String, Object> data, String key) {
        return str(data, key).isEmpty();
    }

}
