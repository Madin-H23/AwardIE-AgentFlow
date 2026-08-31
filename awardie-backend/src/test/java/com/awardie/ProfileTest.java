package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

/** #17 个人资料:查看/修改/字段字典;RBAC 与 v1 字段等价。 */
class ProfileTest extends BaseIntegrationTest {

    private ResponseEntity<String> get(String uri, String cookie) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie);
        return rest.exchange(uri, org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    @Test
    void profileViewAndFieldsForStudent() {
        String ck = loginAs("212306413", "P@ss301");
        assertThat(get("/api/v2/profile", ck).getBody())
                .contains("\"role\":\"student\"").contains("loginCode");
        assertThat(get("/api/v2/profile/fields", ck).getBody())
                .contains("major").contains("grade").doesNotContain("title");
    }

    @Test
    void profileFieldsForTeacher() {
        String ck = loginAs("02110606", "P@ss301");
        String body = get("/api/v2/profile/fields", ck).getBody();
        assertThat(body).contains("title").contains("department").doesNotContain("major");
    }

    @Test
    void profileUpdatePersistsAndReturns() {
        String ck = loginAs("212306413", "P@ss301");
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        ResponseEntity<String> resp = rest.exchange("/api/v2/profile", org.springframework.http.HttpMethod.PUT,
                new HttpEntity<>(Map.of("name", "陈品天", "phone", "13800000000", "qq", "12345",
                        "skills", "Java,Vue", "major", "计算机科学", "grade", "2023",
                        "title", "", "department", "", "profileIsPublic", true), headers), String.class);
        assertThat(resp.getBody()).contains("\"code\":0").contains("13800000000").contains("计算机科学");
        // 复核持久化
        assertThat(get("/api/v2/profile", ck).getBody()).contains("13800000000");
        // 还原(避免污染本地存量数据展示)
        rest.exchange("/api/v2/profile", org.springframework.http.HttpMethod.PUT,
                new HttpEntity<>(Map.of("name", "陈品天", "phone", "", "qq", "", "skills", "",
                        "major", "", "grade", "", "title", "", "department", "",
                        "profileIsPublic", false), headers), String.class);
    }

    @Test
    void profileRequiresAuth() {
        ResponseEntity<String> resp = rest.getForEntity("/api/v2/profile", String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(401);
    }
}
