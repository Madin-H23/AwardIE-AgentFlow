package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

/** #18 admin 奖状管理:列表/筛选/详情/审核复用 + RBAC。 */
class AdminAwardTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @BeforeEach
    void seed() {
        seedAccounts();
    }

    private String cookie(String account) {
        return loginAs(account, account.equals("admin") ? "Mayy123" : "P@ss301");
    }

    private int submitAsStudent() {
        String[] c0 = fetchCsrf(null);
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        String ck = loginAs("212306413", "P@ss301");
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        byte[] tail = String.valueOf(System.nanoTime()).getBytes(StandardCharsets.UTF_8);
        byte[] head = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A};
        byte[] bytes = new byte[head.length + tail.length];
        System.arraycopy(head, 0, bytes, 0, head.length);
        System.arraycopy(tail, 0, bytes, head.length, tail.length);
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(bytes) {
            @Override
            public String getFilename() {
                return "admin-mgmt.png";
            }
        });
        form.add("achievement_type", "award");
        form.add("data", "{\"competition_name\":\"admin管理赛\",\"award_level\":\"一等奖\","
                + "\"winner_name\":\"测试学生\",\"date\":\"2026-01\"}");
        return Integer.parseInt(rest.postForEntity("/api/v2/student/submit",
                new HttpEntity<>(form, headers), String.class).getBody()
                .replaceAll(".*\"id\":(\\d+).*", "$1"));
    }

    private ResponseEntity<String> get(String uri, String ck) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", ck);
        return rest.exchange(uri, org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    @Test
    @Order(1)
    void adminListWithStatusFilter() {
        int id = submitAsStudent();
        String body = get("/api/v2/admin/achievements?status=pending&size=50", cookie("admin")).getBody();
        assertThat(body).contains("\"code\":0").contains("admin管理赛");
        assertThat(get("/api/v2/admin/achievements/" + id, cookie("admin")).getBody())
                .contains("\"id\":" + id).contains("achievementData");
    }

    @Test
    @Order(2)
    void adminReviewReusesReviewService() {
        int id = submitAsStudent();
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        String ck = cookie("admin");
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        ResponseEntity<String> resp = rest.exchange("/api/v2/admin/achievements/" + id + "/review",
                org.springframework.http.HttpMethod.POST,
                new HttpEntity<>(Map.of("action", "approve", "comment", "admin 通过"), headers), String.class);
        assertThat(resp.getBody()).contains("\"code\":0").contains("\"status\":\"archived\"");
        // 物化语义同步生效(复用 ReviewService)
        Integer m = jdbc.queryForObject(
                "SELECT COUNT(*) FROM achievement_audit_log WHERE achievement_id=? AND action_type=8",
                Integer.class, id);
        assertThat(m).isEqualTo(1);
    }

    private int submitType(String type, String data) {
        String[] c0 = fetchCsrf(null);
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        String ck = loginAs("212306413", "P@ss301");
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        byte[] tail = String.valueOf(System.nanoTime()).getBytes(StandardCharsets.UTF_8);
        byte[] head = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A};
        byte[] bytes = new byte[head.length + tail.length];
        System.arraycopy(head, 0, bytes, 0, head.length);
        System.arraycopy(tail, 0, bytes, head.length, tail.length);
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(bytes) {
            @Override
            public String getFilename() {
                return type + ".png";
            }
        });
        form.add("achievement_type", type);
        form.add("data", data);
        return Integer.parseInt(rest.postForEntity("/api/v2/student/submit",
                new HttpEntity<>(form, headers), String.class).getBody()
                .replaceAll(".*\"id\":(\\d+).*", "$1"));
    }

    private void adminApprove(int id) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        String ck = cookie("admin");
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        rest.exchange("/api/v2/admin/achievements/" + id + "/review",
                org.springframework.http.HttpMethod.POST,
                new HttpEntity<>(Map.of("action", "approve", "comment", ""), headers), String.class);
    }

    @Test
    @Order(4)
    void fourTypesMaterializeToOwnTables() {
        int patentId = submitType("patent", "{\"patent_name\":\"分发测试专利\"}");
        adminApprove(patentId);
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM patents WHERE patent_name='分发测试专利'", Integer.class)).isGreaterThanOrEqualTo(1);

        int softId = submitType("software", "{\"software_name\":\"分发测试软件\"}");
        adminApprove(softId);
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM software_copyrights WHERE software_name='分发测试软件'", Integer.class)).isGreaterThanOrEqualTo(1);

        // v1 语义:innovation_projects CHECK 强制 admin(Excel 导入通道)——学生归档不物化该表
        int innoId = submitType("innovation", "{\"project_name\":\"分发测试大创\"}");
        adminApprove(innoId);
        String innoStatus = jdbc.queryForObject(
                "SELECT status FROM pending_achievements WHERE id=?", String.class, innoId);
        assertThat(innoStatus).isEqualTo("archived"); // 归档生效
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM innovation_projects WHERE project_name='分发测试大创'", Integer.class)).isEqualTo(0);

        int otherId = submitType("other", "{\"title\":\"分发测试其他\"}");
        adminApprove(otherId);
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM other_files WHERE description LIKE '%分发测试其他%'", Integer.class)).isGreaterThanOrEqualTo(1);

        // 各自留痕 action_type=8
        Integer audits = jdbc.queryForObject(
                "SELECT COUNT(*) FROM achievement_audit_log WHERE achievement_id IN (?,?,?,?,?) AND action_type=8",
                Integer.class, patentId, softId, innoId, otherId, -1);
        assertThat(audits).isGreaterThanOrEqualTo(4);
    }

    @Test
    @Order(3)
    void teacherAndStudentForbiddenOnAdminEndpoints() {
        assertThat(get("/api/v2/admin/achievements", loginAs("02110606", "P@ss301")).getStatusCode().value())
                .isEqualTo(403);
        assertThat(get("/api/v2/admin/achievements", loginAs("212306413", "P@ss301")).getStatusCode().value())
                .isEqualTo(403);
    }

    /** #26:Specification 真分页——keyword 命中 jsonb 文本、时间窗外过滤、type 组合。 */
    @Test
    @Order(5)
    void adminListSpecFilters() {
        String marker = "规格测试" + System.nanoTime();
        int id = submitType("award", "{\"competition_name\":\"" + marker + "\",\"award_level\":\"二等奖\","
                + "\"winner_name\":\"规格学生\",\"date\":\"2026-03\"}");

        // keyword 命中(藏在 jsonb achievementData 里)
        String hit = get("/api/v2/admin/achievements?keyword=" + marker + "&size=50", cookie("admin")).getBody();
        assertThat(hit).contains("\"code\":0").contains("\"id\":" + id).contains(marker);

        // keyword 无命中
        assertThat(get("/api/v2/admin/achievements?keyword=规格测试绝不存在的词" + System.nanoTime(),
                cookie("admin")).getBody()).doesNotContain(marker);

        // 时间窗外(dateFrom=明天)不出现
        String tomorrow = java.time.LocalDate.now().plusDays(1).toString();
        assertThat(get("/api/v2/admin/achievements?keyword=" + marker + "&dateFrom=" + tomorrow,
                cookie("admin")).getBody()).doesNotContain("\"id\":" + id);

        // 时间窗内(dateFrom=今天)命中
        String today = java.time.LocalDate.now().toString();
        assertThat(get("/api/v2/admin/achievements?keyword=" + marker + "&dateFrom=" + today,
                cookie("admin")).getBody()).contains("\"id\":" + id);

        // 非法日期 → 4000
        assertThat(get("/api/v2/admin/achievements?dateFrom=2026/01/01", cookie("admin")).getBody())
                .contains("\"code\":4000");

        // 分页语义:size=1 时 content 只有一条且 totalElements>=1
        String paged = get("/api/v2/admin/achievements?keyword=" + marker + "&size=1", cookie("admin")).getBody();
        assertThat(paged).contains("\"size\":1").contains("\"totalPages\":1");
    }
}
