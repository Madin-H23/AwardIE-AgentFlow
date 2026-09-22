package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 大创状态校准端点测试(挂账清偿,方向2)。
 * 夹具 8 行覆盖全部判定分支:过期三格式/未来/当天边界/无日期(NULL+空串)/不可识别日期/终止/已结题。
 * 日期相对今天动态计算,跨天可重复;行标记 CAL-%,DELETE+INSERT 自给自足,不依赖库存量。
 */
class InnovationCalibrateTest extends BaseIntegrationTest {

    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");
    private static final String URI = "/api/v2/admin/vault/innovation/calibrate-status";

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private final ObjectMapper om = new ObjectMapper();

    private String adminCk() {
        return loginAs("admin", "Mayy123");
    }

    private ResponseEntity<String> calibrate(String ck) {
        return postJson(URI, null, ck);
    }

    private String statusOf(String projectNo) {
        return jdbc.queryForObject(
                "SELECT status FROM innovation_projects WHERE project_no = ?", String.class, projectNo);
    }

    @BeforeEach
    void seedCalibrationFixtures() {
        LocalDate today = LocalDate.now(ZONE);
        String pastYm = today.minusMonths(1).format(DateTimeFormatter.ofPattern("yyyy-MM"));
        LocalDate dotted = today.minusMonths(2);
        String pastDot = dotted.getYear() + "." + dotted.getMonthValue() + "." + dotted.getDayOfMonth();
        String futureYm = today.plusMonths(1).format(DateTimeFormatter.ofPattern("yyyy-MM"));
        String todayFull = today.format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));

        jdbc.update("DELETE FROM innovation_projects WHERE project_no LIKE 'CAL-%'");
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status, end_date, submitter_type)
                VALUES ('CAL-PAST-YYYYMM', '校准过去月格式', '省级', '进行中', ?, 'admin')
                """, pastYm);
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status, end_date, submitter_type)
                VALUES ('CAL-PAST-DOT', '校准点分格式', '省级', '进行中', ?, 'admin')
                """, pastDot);
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status, end_date, submitter_type)
                VALUES ('CAL-FUTURE', '未来不变', '省级', '进行中', ?, 'admin')
                """, futureYm);
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status, end_date, submitter_type)
                VALUES ('CAL-TODAY', '当天边界不变', '省级', '进行中', ?, 'admin')
                """, todayFull);
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status, end_date, submitter_type)
                VALUES ('CAL-NODATE-NULL', '无日期NULL不变', '省级', '进行中', NULL, 'admin')
                """);
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status, end_date, submitter_type)
                VALUES ('CAL-NODATE-EMPTY', '无日期空串不变', '省级', '进行中', '', 'admin')
                """);
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status, end_date, submitter_type)
                VALUES ('CAL-GARBAGE', '不可识别日期不变', '省级', '进行中', '待定', 'admin')
                """);
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status, end_date, submitter_type)
                VALUES ('CAL-TERM', '终止不被覆盖', '省级', '终止', '2020-01', 'admin')
                """);
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status, end_date, submitter_type)
                VALUES ('CAL-DONE', '已结题不回退', '省级', '已结题', '2020-01', 'admin')
                """);
    }

    @Test
    void calibratesPastDueRowsInAllFormats() throws Exception {
        ResponseEntity<String> resp = calibrate(adminCk());
        assertThat(resp.getBody()).contains("\"code\":0").contains("已校准");
        JsonNode data = om.readTree(resp.getBody()).path("data");
        assertThat(data.path("calibrated").asInt()).isGreaterThanOrEqualTo(2);
        assertThat(data.path("skippedUnparsed").asInt()).isGreaterThanOrEqualTo(1);
        assertThat(statusOf("CAL-PAST-YYYYMM")).isEqualTo("已结题");
        assertThat(statusOf("CAL-PAST-DOT")).isEqualTo("已结题");
    }

    @Test
    void leavesNonQualifyingRowsUntouched() {
        assertThat(calibrate(adminCk()).getBody()).contains("\"code\":0");
        assertThat(statusOf("CAL-FUTURE")).isEqualTo("进行中");
        assertThat(statusOf("CAL-TODAY")).isEqualTo("进行中");
        assertThat(statusOf("CAL-NODATE-NULL")).isEqualTo("进行中");
        assertThat(statusOf("CAL-NODATE-EMPTY")).isEqualTo("进行中");
        assertThat(statusOf("CAL-GARBAGE")).isEqualTo("进行中");
        assertThat(statusOf("CAL-TERM")).isEqualTo("终止");
        assertThat(statusOf("CAL-DONE")).isEqualTo("已结题");
    }

    @Test
    void idempotentOnSecondRun() {
        String ck = adminCk();
        assertThat(calibrate(ck).getBody()).contains("\"code\":0");
        assertThat(calibrate(ck).getBody()).contains("\"code\":0");
        assertThat(statusOf("CAL-PAST-YYYYMM")).isEqualTo("已结题");
        assertThat(statusOf("CAL-PAST-DOT")).isEqualTo("已结题");
        Integer stillRunning = jdbc.queryForObject(
                "SELECT COUNT(*) FROM innovation_projects WHERE project_no LIKE 'CAL-%' AND status = '进行中'",
                Integer.class);
        assertThat(stillRunning).isEqualTo(5);
    }

    @Test
    void teacherForbidden() {
        String ck = loginAs("02110606", "P@ss301");
        assertThat(calibrate(ck).getStatusCode().value()).isEqualTo(403);
    }

    @Test
    void studentForbidden() {
        String ck = loginAs("212306413", "P@ss301");
        assertThat(calibrate(ck).getStatusCode().value()).isEqualTo(403);
    }

    @Test
    void writesAuditLog() {
        assertThat(calibrate(adminCk()).getBody()).contains("\"code\":0");
        Integer n = jdbc.queryForObject("""
                SELECT COUNT(*) FROM system_event_log
                WHERE event_category = 'system' AND event_message LIKE '大创状态校准%' AND operator_code = 'admin'
                """, Integer.class);
        assertThat(n).isGreaterThanOrEqualTo(1);
    }

    @Test
    void consideredEqualsActiveRowsWithNonBlankEndDate() throws Exception {
        Integer expected = jdbc.queryForObject("""
                SELECT COUNT(*) FROM innovation_projects
                WHERE status = '进行中' AND end_date IS NOT NULL AND btrim(end_date) <> ''
                """, Integer.class);
        JsonNode data = om.readTree(calibrate(adminCk()).getBody()).path("data");
        assertThat(data.path("considered").asInt()).isEqualTo(expected);
    }

    @Test
    void responseCarriesCalibratedIds() throws Exception {
        JsonNode data = om.readTree(calibrate(adminCk()).getBody()).path("data");
        Integer pastYmId = jdbc.queryForObject(
                "SELECT id FROM innovation_projects WHERE project_no = 'CAL-PAST-YYYYMM'", Integer.class);
        Integer pastDotId = jdbc.queryForObject(
                "SELECT id FROM innovation_projects WHERE project_no = 'CAL-PAST-DOT'", Integer.class);
        JsonNode ids = data.path("calibratedIds");
        assertThat(ids.toString()).contains(String.valueOf(pastYmId));
        assertThat(ids.toString()).contains(String.valueOf(pastDotId));
    }
}
