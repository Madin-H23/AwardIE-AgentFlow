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

    @Test
    @Order(3)
    void teacherAndStudentForbiddenOnAdminEndpoints() {
        assertThat(get("/api/v2/admin/achievements", loginAs("02110606", "P@ss301")).getStatusCode().value())
                .isEqualTo(403);
        assertThat(get("/api/v2/admin/achievements", loginAs("212306413", "P@ss301")).getStatusCode().value())
                .isEqualTo(403);
    }
}
