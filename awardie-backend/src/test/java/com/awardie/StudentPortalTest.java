package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;

/** #35 学生门户聚合:summary/achievements 仅 student 角色;断言数据无关(结构层)。 */
class StudentPortalTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    private ResponseEntity<String> get(String uri, String cookie) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie);
        return rest.exchange(uri, HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    @Test
    void studentOnlyEndpoints() {
        String ck = loginAs("212306413", "P@ss301");
        ResponseEntity<String> summary = get("/api/v2/student/portal/summary", ck);
        assertThat(summary.getBody()).contains("\"code\":0").contains("awardCount").contains("publicProfile");
        ResponseEntity<String> achievements = get("/api/v2/student/portal/achievements", ck);
        assertThat(achievements.getBody())
                .contains("\"code\":0").contains("awards").contains("innovations")
                .contains("patents").contains("software");
    }

    @Test
    void teacherForbidden() {
        // 仅学生可访问(教师走 Goal D 教师门户)
        assertThat(get("/api/v2/student/portal/summary", loginAs("02110606", "P@ss301"))
                .getStatusCode().value()).isEqualTo(403);
        assertThat(get("/api/v2/student/portal/summary", loginAs("admin", "Mayy123"))
                .getStatusCode().value()).isEqualTo(403);
    }
}
