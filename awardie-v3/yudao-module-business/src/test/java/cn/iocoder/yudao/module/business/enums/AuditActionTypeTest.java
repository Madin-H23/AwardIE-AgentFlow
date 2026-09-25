package cn.iocoder.yudao.module.business.enums;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 批9 动作码字典单测
 *
 * <p>锁三件事:已知码的中文标签、未知码的兜底文案、null 不编造标签。
 * 集成测试只断言"标签非空",锁不住这三条边界。
 *
 * @author AwardIE
 */
class AuditActionTypeTest {

    @Test
    void mapsKnownActionCodes() {
        assertThat(AuditActionType.label(1)).isEqualTo("提交成果");
        assertThat(AuditActionType.label(6)).isEqualTo("审核通过");
        assertThat(AuditActionType.label(7)).isEqualTo("驳回");
        assertThat(AuditActionType.label(8)).isEqualTo("物化入库");
    }

    @Test
    void fallsBackForUnknownCode() {
        // 未知码要有可读兜底(不能返回空串——管理员会看到空白动作列)
        assertThat(AuditActionType.label(99)).isEqualTo("动作 99");
        assertThat(AuditActionType.label(2)).isEqualTo("动作 2");
    }

    @Test
    void returnsEmptyForNull() {
        // null 不编造标签
        assertThat(AuditActionType.label(null)).isEmpty();
    }

}
