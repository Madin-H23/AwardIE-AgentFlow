package cn.iocoder.yudao.module.business.service.pendingsubmission;

import cn.iocoder.yudao.framework.common.exception.ServiceException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 批4 五类成果字段校验器单测(纯函数,不依赖 Spring/DB)。
 *
 * <p>断言前自问"是否因默认值巧合通过":每类都同时测合法值与具体非法值,
 * 并断言 issues 的具体文案而非仅断言 isValid。
 *
 * @author AwardIE
 */
class SubmissionValidatorTest {

    private final SubmissionValidator validator = new SubmissionValidator();

    @Test
    void awardValid() {
        SubmissionValidator.ValidationResult result = validator.validate("award",
                "{\"competition_name\":\"挑战杯\",\"award_level\":\"一等奖\",\"winner_name\":\"张三\",\"date\":\"2024-05-01\"}");
        assertThat(result.isValid()).isTrue();
        assertThat(result.completenessIssues()).isEmpty();
        assertThat(result.contentIssues()).isEmpty();
    }

    @Test
    void awardMissingRequiredFields() {
        SubmissionValidator.ValidationResult result = validator.validate("award",
                "{\"competition_name\":\"挑战杯\"}");
        assertThat(result.isValid()).isFalse();
        assertThat(result.completenessIssues()).hasSize(3);
        assertThat(result.completenessIssues()).anyMatch(s -> s.contains("award_level"));
        assertThat(result.completenessIssues()).anyMatch(s -> s.contains("winner_name"));
        assertThat(result.completenessIssues()).anyMatch(s -> s.contains("date"));
    }

    @Test
    void awardDateAcceptsFourFormats() {
        for (String date : new String[]{"2024-05-01", "2024-05", "2024-5", "2024/05/01"}) {
            SubmissionValidator.ValidationResult result = validator.validate("award",
                    "{\"competition_name\":\"X\",\"award_level\":\"一等奖\",\"winner_name\":\"张三\",\"date\":\"" + date + "\"}");
            assertThat(result.isValid()).as("date=%s 应通过", date).isTrue();
        }
    }

    @Test
    void awardDateRejectsOutOfRangeAndGarbage() {
        for (String date : new String[]{"1999-05-01", "2101-05-01", "not-a-date", "2024-13-45"}) {
            SubmissionValidator.ValidationResult result = validator.validate("award",
                    "{\"competition_name\":\"X\",\"award_level\":\"一等奖\",\"winner_name\":\"张三\",\"date\":\"" + date + "\"}");
            assertThat(result.isValid()).as("date=%s 应拒绝", date).isFalse();
            assertThat(result.contentIssues()).anyMatch(s -> s.contains("日期格式不正确"));
        }
    }

    @Test
    void patentValid() {
        SubmissionValidator.ValidationResult result = validator.validate("patent",
                "{\"patent_name\":\"一种发明\",\"application_number\":\"CN12345678\",\"patent_type\":\"发明专利\"}");
        assertThat(result.isValid()).isTrue();
    }

    @Test
    void patentRejectsBadApplicationNumberAndType() {
        // US1 长度 3 <5:同时触发"非 CN 开头"与"长度不足"两条;patent_type 取白名单外值
        SubmissionValidator.ValidationResult result = validator.validate("patent",
                "{\"patent_name\":\"X\",\"application_number\":\"US1\",\"patent_type\":\"外观设计费\"}");
        assertThat(result.isValid()).isFalse();
        assertThat(result.contentIssues()).anyMatch(s -> s.contains("CN开头"));
        assertThat(result.contentIssues()).anyMatch(s -> s.contains("申请号格式不正确"));
        assertThat(result.contentIssues()).anyMatch(s -> s.contains("专利类型应为"));
    }

    @Test
    void patentApplicationNumberTooShort() {
        SubmissionValidator.ValidationResult result = validator.validate("patent",
                "{\"patent_name\":\"X\",\"application_number\":\"CN1\"}");
        assertThat(result.contentIssues()).anyMatch(s -> s.contains("申请号格式不正确"));
    }

    @Test
    void softwareValid() {
        // 真实软著登记号规范(2026-09-25 用户拍板放宽):4 位年份 + SR + 7 位流水号
        // 回归锚点是 V1/V2 库里的真实数据 2024SR2002865——v2 的"20开头+11位"会把它判非法
        SubmissionValidator.ValidationResult real = validator.validate("software",
                "{\"software_name\":\"某系统\",\"registration_number\":\"2024SR2002865\"}");
        assertThat(real.isValid()).as("V1/V2 真实登记号应通过校验").isTrue();
    }

    @Test
    void softwareRejectsBadRegistrationNumber() {
        // 年份不对(1999 不是 20xx)
        assertThat(validator.validate("software",
                "{\"software_name\":\"X\",\"registration_number\":\"1999SR2002865\"}")
                .contentIssues()).anyMatch(s -> s.contains("登记号格式不正确"));
        // 流水号位数不对(6 位,规范是 7 位)
        assertThat(validator.validate("software",
                "{\"software_name\":\"X\",\"registration_number\":\"2024SR200285\"}")
                .contentIssues()).anyMatch(s -> s.contains("登记号格式不正确"));
        // 缺 SR 段(v2 允许的纯 11 位数字,现已被规范排除)
        SubmissionValidator.ValidationResult digitsOnly = validator.validate("software",
                "{\"software_name\":\"X\",\"registration_number\":\"20231234567\"}");
        assertThat(digitsOnly.isValid()).as("纯 11 位数字不再算合法登记号").isFalse();
        assertThat(digitsOnly.contentIssues()).anyMatch(s -> s.contains("登记号格式不正确"));
        // SR 小写
        assertThat(validator.validate("software",
                "{\"software_name\":\"X\",\"registration_number\":\"2024sr2002865\"}")
                .contentIssues()).anyMatch(s -> s.contains("登记号格式不正确"));
        // 流水号含字母
        assertThat(validator.validate("software",
                "{\"software_name\":\"X\",\"registration_number\":\"2024SR20028A5\"}")
                .contentIssues()).anyMatch(s -> s.contains("登记号格式不正确"));
    }

    @Test
    void innovationAndOtherRequiredFields() {
        assertThat(validator.validate("innovation", "{}").completenessIssues())
                .anyMatch(s -> s.contains("项目名称不能为空"));
        assertThat(validator.validate("other", "{}").completenessIssues())
                .anyMatch(s -> s.contains("成果名称不能为空"));
        assertThat(validator.validate("innovation", "{\"project_name\":\"大创\"}").isValid()).isTrue();
        assertThat(validator.validate("other", "{\"title\":\"某成果\"}").isValid()).isTrue();
    }

    @Test
    void unknownTypeRejected() {
        assertThatThrownBy(() -> validator.validate("unknown", "{}"))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("未知成果类型");
    }

    @Test
    void malformedJsonRejected() {
        assertThatThrownBy(() -> validator.validate("award", "not-json"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("不是合法 JSON");
    }

    @Test
    void blankDataTreatedAsEmptyObject() {
        assertThat(validator.validate("award", null).completenessIssues()).hasSize(4);
        assertThat(validator.validate("award", "  ").completenessIssues()).hasSize(4);
    }

    @Test
    void validationJsonShapeMatchesV2() {
        SubmissionValidator.ValidationResult result = validator.validate("award", "{}");
        String json = validator.toValidationJson(result);
        assertThat(json).contains("\"is_valid\":false")
                .contains("\"content_issues\"")
                .contains("\"completeness_issues\"");
    }
}
