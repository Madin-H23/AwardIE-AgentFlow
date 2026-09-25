package cn.iocoder.yudao.module.business.service.pendingsubmission;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.util.regex.Pattern;
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
    /** 申请号最小长度(v2:<5 视为格式错) */
    private static final int APPLICATION_NUMBER_MIN_LENGTH = 5;
    /** 申请号前缀(v2:CN 开头) */
    private static final String APPLICATION_NUMBER_PREFIX = "CN";
    /**
     * 软著登记号格式(2026-09-25 用户拍板放宽;v2 的"20 开头 + 11 位"是错的)
     *
     * <p>真实规范:年份(4 位数字)+ {@code SR} + 流水号(7 位数字),如 {@code 2024SR2002865}。
     * 证据:V1 与 V2 库里的软著登记号**都是** {@code 2024SR2002865}(13 位、含 SR)——
     * v2 的规则会把它判非法,且 v2 自己的报错文案示例也写的是这个 12-13 位含字母的格式,
     * 规则与示例互相矛盾(批4 发现,批4-批8 一直挂账)。
     *
     * <p>保留 20 开头的年份下限校验(2000-2100 与日期校验同口径,挡明显笔误)。
     */
    private static final Pattern REGISTRATION_NUMBER_PATTERN = Pattern.compile("^20\\d{2}SR\\d{7}$");

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
        // 2026-09-25 用户拍板:按真实软著登记号规范(年份+SR+流水号)校验。
        // v2 的"20 开头且长度 11"会把真实数据 2024SR2002865(13 位含字母)判为非法。
        if (!REGISTRATION_NUMBER_PATTERN.matcher(registration).matches()) {
            content.add("登记号格式不正确,应为 4 位年份 + SR + 7 位流水号,如 2024SR2002865");
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
