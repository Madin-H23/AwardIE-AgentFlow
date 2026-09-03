package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

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

/** Fix-T 专利/软著/大创 编辑页端点测试(测试库 awardie_test,自给自足)。 */
class AdminAchievementEditTest extends BaseIntegrationTest {

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

    @Test
    void patentDetailAndUpdate() {
        jdbc.update("DELETE FROM patents WHERE application_number = 'FixT-APP'");
        jdbc.update("""
                INSERT INTO patents (patent_name, patent_type, application_number, inventor, patentee, submitter_type)
                VALUES ('FixT专利', '发明专利', 'FixT-APP', 'FixT发明人', 'FixT专利权人', 'admin')
                """);
        Integer id = jdbc.queryForObject("SELECT id FROM patents WHERE application_number = 'FixT-APP'", Integer.class);
        String body = get(adminCk(), "/api/v2/admin/patents/" + id + "/edit-detail").getBody();
        assertThat(body).contains("\"code\":0")
                .contains("\"patentName\"").contains("\"applicationNumber\"").contains("\"laboratories\"")
                .contains("FixT专利");
        Map<String, Object> up = new java.util.HashMap<>();
        up.put("patentName", "FixT专利改");
        up.put("patentType", "实用新型");
        up.put("applicationNumber", "FixT-APP");
        up.put("publicationNumber", "FixT-PUB");
        up.put("inventor", "FixT发明人2");
        up.put("applicationDate", "2024-05-01");
        up.put("patentee", "FixT专利权人2");
        up.put("laboratoryId", null);
        ResponseEntity<String> resp = put(adminCk(), "/api/v2/admin/patents/" + id, up);
        assertThat(resp.getBody()).contains("\"code\":0").contains("已更新");
        Map<String, Object> row = jdbc.queryForMap(
                "SELECT patent_name, patent_type, publication_number, inventor FROM patents WHERE id = ?", id);
        assertThat(row.get("patent_name")).isEqualTo("FixT专利改");
        assertThat(row.get("patent_type")).isEqualTo("实用新型");
        assertThat(row.get("publication_number")).isEqualTo("FixT-PUB");
        // 必填/404
        assertThat(put(adminCk(), "/api/v2/admin/patents/" + id,
                Map.of("patentName", "")).getBody()).contains("4000");
        assertThat(get(adminCk(), "/api/v2/admin/patents/999999/edit-detail").getBody()).contains("4004");
    }

    @Test
    void softwareDetailAndUpdate() {
        jdbc.update("DELETE FROM software_copyrights WHERE registration_number = 'FixT-REG'");
        jdbc.update("""
                INSERT INTO software_copyrights (software_name, software_version, registration_number, copyright_owner, submitter_type)
                VALUES ('FixT软著', 'V1.0', 'FixT-REG', 'FixT著作权人', 'admin')
                """);
        Integer id = jdbc.queryForObject(
                "SELECT id FROM software_copyrights WHERE registration_number = 'FixT-REG'", Integer.class);
        String body = get(adminCk(), "/api/v2/admin/software/" + id + "/edit-detail").getBody();
        assertThat(body).contains("\"code\":0")
                .contains("\"softwareName\"").contains("\"registrationNumber\"")
                .contains("\"certificateNo\"").contains("\"laboratories\"");
        Map<String, Object> up = new java.util.HashMap<>();
        up.put("softwareName", "FixT软著改");
        up.put("softwareVersion", "V2.0");
        up.put("registrationNumber", "FixT-REG");
        up.put("certificateNo", "FixT-CERT");
        up.put("registrationDate", "2024-06-01");
        up.put("copyrightOwner", "FixT著作权人2");
        up.put("laboratoryId", null);
        ResponseEntity<String> resp = put(adminCk(), "/api/v2/admin/software/" + id, up);
        assertThat(resp.getBody()).contains("\"code\":0").contains("已更新");
        assertThat(jdbc.queryForObject(
                "SELECT software_name FROM software_copyrights WHERE id = ?", String.class, id))
                .isEqualTo("FixT软著改");
        assertThat(put(adminCk(), "/api/v2/admin/software/" + id,
                Map.of("softwareName", "")).getBody()).contains("4000");
    }

    @Test
    void innovationDetailAndUpdateWithLeaderStatus() {
        jdbc.update("DELETE FROM innovation_projects WHERE project_no = 'FixT-NO'");
        jdbc.update("""
                INSERT INTO innovation_projects (project_no, project_name, project_type, status,
                                                 student_leader_name, student_leader_id, other_members, supervisors, submitter_type)
                VALUES ('FixT-NO', 'FixT大创', '省级', '进行中', '测试学生', '212306413',
                        '["老成员甲","老成员乙"]', 'FixT指导教师', 'admin')
                """);
        Integer id = jdbc.queryForObject(
                "SELECT id FROM innovation_projects WHERE project_no = 'FixT-NO'", Integer.class);
        String body = get(adminCk(), "/api/v2/admin/innovation/" + id + "/edit-detail").getBody();
        assertThat(body).contains("\"code\":0")
                .contains("\"projectNo\"").contains("\"fundingAmount\"").contains("\"otherMembers\"")
                .contains("\"leaderStatus\"").contains("\"laboratories\"")
                // 学号精确命中 → matched
                .contains("\"status\":\"matched\"")
                .contains("老成员甲");
        // 13 字段超 Map.of 上限(台账坑),用 HashMap
        Map<String, Object> up = new java.util.HashMap<>();
        up.put("projectNo", "FixT-NO");
        up.put("projectName", "FixT大创改");
        up.put("projectType", "国家级");
        up.put("status", "已结题");
        up.put("startDate", "2023-06-01");
        up.put("endDate", "2024-06-01");
        up.put("fundingAmount", 1.5);
        up.put("studentLeaderName", "测试学生");
        up.put("studentLeaderId", "212306413");
        up.put("otherMembers", List.of("新成员甲", "新成员乙"));
        up.put("supervisors", "FixT指导教师2");
        up.put("laboratoryId", null);
        ResponseEntity<String> resp = put(adminCk(), "/api/v2/admin/innovation/" + id, up);
        assertThat(resp.getBody()).contains("\"code\":0").contains("已更新");
        Map<String, Object> row = jdbc.queryForMap(
                "SELECT project_name, project_type, status, funding_amount, "
                        + "other_members::TEXT AS members FROM innovation_projects WHERE id = ?", id);
        assertThat(row.get("project_name")).isEqualTo("FixT大创改");
        assertThat(row.get("project_type")).isEqualTo("国家级");
        assertThat(row.get("status")).isEqualTo("已结题");
        assertThat(String.valueOf(row.get("members"))).contains("新成员甲");
        assertThat(put(adminCk(), "/api/v2/admin/innovation/" + id,
                Map.of("projectName", "")).getBody()).contains("4000");
    }

    @Test
    void studentForbiddenOnAll() {
        String ck = loginAs("212306413", "P@ss301");
        assertThat(get(ck, "/api/v2/admin/patents/1/edit-detail").getStatusCode().value()).isEqualTo(403);
        assertThat(get(ck, "/api/v2/admin/software/1/edit-detail").getStatusCode().value()).isEqualTo(403);
        assertThat(get(ck, "/api/v2/admin/innovation/1/edit-detail").getStatusCode().value()).isEqualTo(403);
    }
}
