package cn.iocoder.yudao.module.business.service.innovation;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 批8 status 校准日期解析单测
 *
 * <p>口径逐条对齐 v2 InnovationStatusService.parseLooseDate:
 * 数值日期(2025-06 / 2024.5.1 / 2025-06-30 / 2025/6/1)、中文日期(2025年6月 / 2025年6月30日)、
 * 混合分隔符;只写年月按月首日;不可识别(待定/只有年份/13 月/2 月 30 日)返回 null。
 *
 * <p>用非默认输入:不只测"能解析"的那几种,重点测**边界与非法值**——
 * 校准逻辑对不可识别日期是"跳过并计数",若解析器把非法值猜成合法,就会误改状态。
 *
 * @author AwardIE
 */
class InnovationStatusServiceTest {

    @Test
    void parsesNumericFormats() {
        assertThat(InnovationStatusService.parseLooseDate("2025-06-30"))
                .isEqualTo(LocalDate.of(2025, 6, 30));
        assertThat(InnovationStatusService.parseLooseDate("2024.5.1"))
                .isEqualTo(LocalDate.of(2024, 5, 1));
        assertThat(InnovationStatusService.parseLooseDate("2025/6/1"))
                .isEqualTo(LocalDate.of(2025, 6, 1));
        // 混合分隔符(v2 明确支持)
        assertThat(InnovationStatusService.parseLooseDate("2025-06.30"))
                .isEqualTo(LocalDate.of(2025, 6, 30));
    }

    @Test
    void yearMonthOnlyBecomesFirstDayOfMonth() {
        // v2 语义:只写年月按月首日,不是月末
        assertThat(InnovationStatusService.parseLooseDate("2025-06"))
                .isEqualTo(LocalDate.of(2025, 6, 1));
    }

    @Test
    void parsesChineseFormats() {
        assertThat(InnovationStatusService.parseLooseDate("2025年6月30日"))
                .isEqualTo(LocalDate.of(2025, 6, 30));
        assertThat(InnovationStatusService.parseLooseDate("2025年6月"))
                .isEqualTo(LocalDate.of(2025, 6, 1));
    }

    @Test
    void trimsWhitespace() {
        assertThat(InnovationStatusService.parseLooseDate("  2025-06-30  "))
                .isEqualTo(LocalDate.of(2025, 6, 30));
    }

    @Test
    void returnsNullForUnparseable() {
        // 这批是"绝不猜"的边界:解析器若把非法值猜成合法,校准会误改状态
        assertThat(InnovationStatusService.parseLooseDate(null)).isNull();
        assertThat(InnovationStatusService.parseLooseDate("")).isNull();
        assertThat(InnovationStatusService.parseLooseDate("   ")).isNull();
        assertThat(InnovationStatusService.parseLooseDate("待定")).isNull();
        assertThat(InnovationStatusService.parseLooseDate("2025")).isNull();          // 只有年份
        assertThat(InnovationStatusService.parseLooseDate("2025-13-01")).isNull();    // 13 月
        assertThat(InnovationStatusService.parseLooseDate("2025-02-30")).isNull();    // 2 月 30 日
        assertThat(InnovationStatusService.parseLooseDate("2025-06-30-01")).isNull(); // 多余日期段
        assertThat(InnovationStatusService.parseLooseDate("06/30")).isNull();         // 缺年份
    }

    @Test
    void handlesLeapDay() {
        assertThat(InnovationStatusService.parseLooseDate("2024-02-29"))
                .isEqualTo(LocalDate.of(2024, 2, 29));
        assertThat(InnovationStatusService.parseLooseDate("2025-02-29")).isNull(); // 平年无 2 月 29
    }

}
