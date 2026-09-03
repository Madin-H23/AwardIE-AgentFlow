package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

/** Fix-R 奖状详情/编辑端点测试(测试库 awardie_test,自给自足)。 */
class AdminAwardEditTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private static final org.springframework.http.MediaType MediaType_JSON =
            org.springframework.http.MediaType.APPLICATION_JSON;

    private String adminCk() {
        return loginAs("admin", "Mayy123");
    }

    private ResponseEntity<String> get(String ck, String path) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", ck);
        return rest.exchange(path, HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    private ResponseEntity<String> put(String ck, String path, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType_JSON);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        return rest.exchange(path, HttpMethod.PUT, new HttpEntity<>(body, headers), String.class);
    }

    /** 造一枚奖状(含两名专属教师),返回 awardId;幂等:先清同标记旧数。 */
    private Integer seedAward() {
        jdbc.update("DELETE FROM award_student_winners WHERE award_id IN (SELECT id FROM awards WHERE certificate_id = 'FixRCert')");
        jdbc.update("DELETE FROM award_teacher_winners WHERE award_id IN (SELECT id FROM awards WHERE certificate_id = 'FixRCert')");
        jdbc.update("DELETE FROM award_supervisors WHERE award_id IN (SELECT id FROM awards WHERE certificate_id = 'FixRCert')");
        jdbc.update("DELETE FROM award_related_students WHERE award_id IN (SELECT id FROM awards WHERE certificate_id = 'FixRCert')");
        jdbc.update("DELETE FROM awards WHERE certificate_id = 'FixRCert'");
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('02990001', 'FixR教师甲', 'teacher', 'x', TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """);
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('02990002', 'FixR教师乙', 'teacher', 'x', TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """);
        jdbc.update("INSERT INTO competitions (competition_name) VALUES ('FixR竞赛') ON CONFLICT (competition_name) DO NOTHING");
        Integer compId = jdbc.queryForObject("SELECT id FROM competitions WHERE competition_name = 'FixR竞赛'", Integer.class);
        jdbc.update("""
                INSERT INTO awards (competition_id, certificate_id, competition_name_in_file, award_level,
                                    winner_name, supervisor_name, year, granted_role)
                VALUES (?, 'FixRCert', 'FixR竞赛', '一等奖', '测试学生, 不存在学生', 'FixR教师甲', 2025, '学生')
                """, compId);
        return jdbc.queryForObject(
                "SELECT id FROM awards WHERE certificate_id = 'FixRCert' ORDER BY id DESC LIMIT 1", Integer.class);
    }

    private Integer teacherId(String name) {
        return jdbc.queryForObject("SELECT id FROM users WHERE name = ? AND role = 'teacher'", Integer.class, name);
    }

    private Integer studentId() {
        return jdbc.queryForObject("SELECT id FROM users WHERE login_code = '212306413'", Integer.class);
    }

    /** PUT 请求体:17 字段超过 Map.of 上限,用 HashMap 构建(台账坑)。 */
    private Map<String, Object> updateBody(Integer compId, Integer labId, String grantedRole,
            List<Integer> supervisorIds) {
        Map<String, Object> m = new HashMap<>();
        m.put("competitionId", compId);
        m.put("competitionLevel", "省赛");
        m.put("awardLevel", "二等奖");
        m.put("year", 2024);
        m.put("track", "软件类");
        m.put("certificateId", "FixRCert");
        m.put("projectTitle", "FixR项目");
        m.put("date", "2024-08-01");
        m.put("province", "福建省");
        m.put("issuer", "FixR颁发机构");
        m.put("laboratoryId", labId);
        m.put("grantedRole", grantedRole);
        m.put("studentWinnerNames", "测试学生, 不存在学生");
        m.put("supervisorIds", supervisorIds);
        m.put("teacherWinnerIds", List.of(teacherId("FixR教师甲")));
        m.put("studentWinnerIds", List.of(studentId()));
        m.put("relatedStudentIds", List.of(studentId()));
        return m;
    }

    @Test
    void editDetailAggregatesWithKeyContract() {
        Integer id = seedAward();
        String body = get(adminCk(), "/api/v2/admin/awards/" + id + "/edit-detail").getBody();
        // 键名级断言:别名双引号保留 + 聚合组齐全(键名就是契约)
        assertThat(body).contains("\"code\":0")
                .contains("\"competitionId\"").contains("\"competitionName\"")
                .contains("\"studentWinners\"").contains("\"teacherWinners\"")
                .contains("\"supervisors\"").contains("\"relatedStudents\"")
                .contains("\"winnerStatus\"").contains("\"supervisorStatus\"")
                .contains("\"competitions\"").contains("\"teachers\"")
                .contains("\"students\"").contains("\"laboratories\"")
                .contains("\"defaultLaboratoryId\"")
                .contains("\"isAbnormal\"")
                // 匹配状态:测试学生 matched / 不存在学生 not_found
                .contains("\"status\":\"matched\"").contains("\"status\":\"not_found\"");
        // 404
        assertThat(get(adminCk(), "/api/v2/admin/awards/999999/edit-detail").getBody()).contains("4004");
    }

    @Test
    void updateRewritesFieldsAndAssociations() {
        Integer id = seedAward();
        Integer compId = jdbc.queryForObject("SELECT id FROM competitions WHERE competition_name = 'FixR竞赛'", Integer.class);
        Integer labId = jdbc.queryForObject(
                "SELECT id FROM laboratories ORDER BY id LIMIT 1", Integer.class);
        List<Integer> supervisorOrder = new ArrayList<>(List.of(teacherId("FixR教师乙"), teacherId("FixR教师甲")));
        ResponseEntity<String> resp = put(adminCk(), "/api/v2/admin/awards/" + id,
                updateBody(compId, labId, "teacher", supervisorOrder));
        assertThat(resp.getBody()).contains("\"code\":0").contains("已更新");
        // 主字段库内核对
        Map<String, Object> row = jdbc.queryForMap(
                "SELECT award_level, year, track, project_title, laboratory_id, granted_role, winner_name, "
                        + "supervisor_name FROM awards WHERE id = ?", id);
        assertThat(row.get("award_level")).isEqualTo("二等奖");
        assertThat(row.get("year")).isEqualTo(2024);
        assertThat(row.get("track")).isEqualTo("软件类");
        assertThat(row.get("project_title")).isEqualTo("FixR项目");
        assertThat(row.get("laboratory_id")).isEqualTo(labId);
        assertThat(row.get("granted_role")).isEqualTo("教师");
        // supervisor 顺序敏感:按提交顺序同步 supervisor_name
        assertThat(row.get("supervisor_name")).isEqualTo("FixR教师乙, FixR教师甲");
        assertThat(String.valueOf(row.get("winner_name"))).contains("不存在学生");
        // 四关联表重写
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM award_student_winners WHERE award_id = ?", Integer.class, id)).isEqualTo(1);
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM award_teacher_winners WHERE award_id = ?", Integer.class, id)).isEqualTo(1);
        List<Integer> sups = jdbc.queryForList(
                "SELECT teacher_id FROM award_supervisors WHERE award_id = ?", Integer.class, id);
        assertThat(sups).containsExactlyInAnyOrderElementsOf(supervisorOrder);
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM award_related_students WHERE award_id = ?", Integer.class, id)).isEqualTo(1);
    }

    @Test
    void studentCertificateClearsRelatedStudents() {
        Integer id = seedAward();
        Integer compId = jdbc.queryForObject("SELECT id FROM competitions WHERE competition_name = 'FixR竞赛'", Integer.class);
        put(adminCk(), "/api/v2/admin/awards/" + id, updateBody(compId, null, "student", List.of()));
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM award_related_students WHERE award_id = ?", Integer.class, id)).isZero();
        assertThat(jdbc.queryForObject(
                "SELECT granted_role FROM awards WHERE id = ?", String.class, id)).isEqualTo("学生");
    }

    @Test
    void competitionRequiredAndNotFound() {
        Integer id = seedAward();
        Integer compId = jdbc.queryForObject("SELECT id FROM competitions WHERE competition_name = 'FixR竞赛'", Integer.class);
        // 竞赛必填
        Map<String, Object> body = updateBody(compId, null, "student", List.of());
        body.put("competitionId", null);
        assertThat(put(adminCk(), "/api/v2/admin/awards/" + id, body).getBody()).contains("4000");
        // 不存在
        assertThat(put(adminCk(), "/api/v2/admin/awards/999999",
                updateBody(compId, null, "student", List.of())).getBody()).contains("4004");
    }

    @Test
    void studentForbiddenOnAll() {
        Integer id = seedAward();
        Integer compId = jdbc.queryForObject("SELECT id FROM competitions WHERE competition_name = 'FixR竞赛'", Integer.class);
        String ck = loginAs("212306413", "P@ss301");
        assertThat(get(ck, "/api/v2/admin/awards/" + id + "/edit-detail").getStatusCode().value()).isEqualTo(403);
        assertThat(put(ck, "/api/v2/admin/awards/" + id,
                updateBody(compId, null, "student", List.of())).getStatusCode().value()).isEqualTo(403);
    }
}
