package com.awardie.admin;

import java.time.LocalDate;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

/** InnovationStatusService.parseLooseDate 纯函数单测(存量 TEXT 日期混杂格式,不可识别绝不猜)。 */
class InnovationStatusServiceTest {

    @Test
    void parsesYearMonth() {
        assertThat(InnovationStatusService.parseLooseDate("2025-06")).isEqualTo(LocalDate.of(2025, 6, 1));
    }

    @Test
    void parsesDottedDate() {
        assertThat(InnovationStatusService.parseLooseDate("2024.5.1")).isEqualTo(LocalDate.of(2024, 5, 1));
    }

    @Test
    void parsesFullIso() {
        assertThat(InnovationStatusService.parseLooseDate("2025-06-30")).isEqualTo(LocalDate.of(2025, 6, 30));
    }

    @Test
    void parsesSlashed() {
        assertThat(InnovationStatusService.parseLooseDate("2025/6/1")).isEqualTo(LocalDate.of(2025, 6, 1));
    }

    @Test
    void parsesChineseYearMonth() {
        assertThat(InnovationStatusService.parseLooseDate("2025年6月")).isEqualTo(LocalDate.of(2025, 6, 1));
    }

    @Test
    void parsesChineseFullDate() {
        assertThat(InnovationStatusService.parseLooseDate("2025年6月30日")).isEqualTo(LocalDate.of(2025, 6, 30));
    }

    @Test
    void trimsWhitespace() {
        assertThat(InnovationStatusService.parseLooseDate("  2025-06  ")).isEqualTo(LocalDate.of(2025, 6, 1));
    }

    @Test
    void rejectsNull() {
        assertThat(InnovationStatusService.parseLooseDate(null)).isNull();
    }

    @Test
    void rejectsBlank() {
        assertThat(InnovationStatusService.parseLooseDate("")).isNull();
        assertThat(InnovationStatusService.parseLooseDate("   ")).isNull();
    }

    @Test
    void rejectsGarbage() {
        assertThat(InnovationStatusService.parseLooseDate("待定")).isNull();
        assertThat(InnovationStatusService.parseLooseDate("2025")).isNull();
        assertThat(InnovationStatusService.parseLooseDate("2025-06-30-01")).isNull();
    }

    @Test
    void rejectsMonth13() {
        assertThat(InnovationStatusService.parseLooseDate("2025-13")).isNull();
        assertThat(InnovationStatusService.parseLooseDate("2025年13月")).isNull();
    }

    @Test
    void rejectsImpossibleDay() {
        assertThat(InnovationStatusService.parseLooseDate("2025-02-30")).isNull();
        assertThat(InnovationStatusService.parseLooseDate("2025.13.1")).isNull();
    }

    @Test
    void toleratesMixedSeparators() {
        assertThat(InnovationStatusService.parseLooseDate("2025-06.30")).isEqualTo(LocalDate.of(2025, 6, 30));
        assertThat(InnovationStatusService.parseLooseDate("2025/6.1")).isEqualTo(LocalDate.of(2025, 6, 1));
    }
}
