package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * 登录链路黑盒(语义翻译自 v1 pytest HTTP 层测试):
 * fixtures 测试账号 v2t_user/v2t_br4 做改密往返,零污染 1834 个存量账号;
 * 存量账号(admin/212306413)只做只读登录验证。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class LoginAuthTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private static final String FIXTURE_HASH = null; // 由 @BeforeEach 从 admin 行复制(scrypt 样本)

    @BeforeEach
    void seedFixtures() {
        seedAccounts();
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                SELECT 'v2t_user', '测试用户', 'student', password_hash, TRUE, FALSE FROM users WHERE login_code='admin'
                ON CONFLICT (login_code) DO NOTHING
                """);
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                SELECT 'v2t_br4', 'BR4测试', 'student', password_hash, TRUE, TRUE FROM users WHERE login_code='admin'
                ON CONFLICT (login_code) DO NOTHING
                """);
    }

    @AfterEach
    void cleanup() {
        jdbc.update("DELETE FROM users WHERE login_code IN ('v2t_user','v2t_br4')");
    }

    private ResponseEntity<String> post(String uri, Object body) {
        return postJson(uri, body, null); // 匿名 POST:自动带 CSRF
    }

    private ResponseEntity<String> getWithSession(String uri, String cookie) {
        HttpHeaders headers = new HttpHeaders();
        if (cookie != null) {
            headers.set("Cookie", cookie);
        }
        return rest.exchange(uri, HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    private ResponseEntity<String> login(String account, String password) {
        return post("/api/v2/auth/login", Map.of("account", account, "password", password));
    }

    @org.junit.jupiter.api.Test
    void adminLegacyScryptLoginOk() {
        // fixture 账号携带 admin 的 scrypt 哈希(与存量 1834 条同构);不用真实账号——
        // 登录状态测试必须对 DB 状态自洽,避免跨轮污染
        ResponseEntity<String> resp = login("v2t_user", "Mayy123");
        assertThat(resp.getStatusCode().value()).isEqualTo(200);
        assertThat(resp.getBody()).contains("\"code\":0").contains("\"role\":\"student\"");
    }

    @org.junit.jupiter.api.Test
    void studentLegacyLoginOk() {
        // 学生 212306413 只读登录一次(不做任何改密;哈希升级属机制预期)
        ResponseEntity<String> resp = login("212306413", "P@ss301");
        assertThat(resp.getStatusCode().value()).isEqualTo(200);
        assertThat(resp.getBody()).contains("\"role\":\"student\"");
    }

    @org.junit.jupiter.api.Test
    void wrongPasswordRejected() {
        assertThat(login("admin", "wrong-pass").getBody()).contains("\"code\":4010");
    }

    @org.junit.jupiter.api.Test
    void unknownAccountRejected() {
        assertThat(login("no_such_user", "whatever").getBody()).contains("\"code\":4010");
    }

    @org.junit.jupiter.api.Test
    void meRequiresSession() {
        assertThat(getWithSession("/api/v2/auth/me", null).getBody()).contains("未登录");
    }

    @org.junit.jupiter.api.Test
    void protectedEndpointRequiresAuth() {
        ResponseEntity<String> resp = rest.exchange("/api/v2/anything", HttpMethod.GET, null, String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(401);
    }

    @org.junit.jupiter.api.Test
    void meWorksAfterLogin() {
        ResponseEntity<String> loginResp = login("admin", "Mayy123");
        String cookie = loginResp.getHeaders().getFirst(HttpHeaders.SET_COOKIE).split(";")[0];
        ResponseEntity<String> me = getWithSession("/api/v2/auth/me", cookie);
        assertThat(me.getBody()).contains("\"role\":\"admin\"").contains("admin");
    }

    @org.junit.jupiter.api.Test
    @org.junit.jupiter.api.Order(1)
    void loginKeepsLegacyHashFormatForV1Compat() {
        // ADR-0002 推论:双库共存期 v2 不得改写口令哈希格式(v1 werkzeug 无法验证裸 bcrypt)
        String before = jdbc.queryForObject(
                "SELECT password_hash FROM users WHERE login_code='v2t_user'", String.class);
        assertThat(before).startsWith("scrypt:");
        assertThat(login("v2t_user", "Mayy123").getStatusCode().value()).isEqualTo(200);
        String after = jdbc.queryForObject(
                "SELECT password_hash FROM users WHERE login_code='v2t_user'", String.class);
        assertThat(after).isEqualTo(before); // 登录不改写哈希
    }

    @org.junit.jupiter.api.Test
    void weakPasswordRejectedByBr6() {
        ResponseEntity<String> loginResp = login("v2t_user", "Mayy123");
        String cookie = loginResp.getHeaders().getFirst(HttpHeaders.SET_COOKIE).split(";")[0];
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Cookie", cookie);
        ResponseEntity<String> resp = postJson("/api/v2/auth/password",
                Map.of("oldPassword", "Mayy123", "newPassword", "short1"), cookie);
        assertThat(resp.getBody()).contains("BR-6");
    }

    @org.junit.jupiter.api.Test
    @org.junit.jupiter.api.Order(2)
    void changePasswordFlowAndBr4() {
        // BR-4:needs_password_change=1 的账号登录响应必须标记
        ResponseEntity<String> br4Login = login("v2t_br4", "Mayy123");
        assertThat(br4Login.getBody()).contains("\"needsPasswordChange\":true");

        // v2t_user 登录拿会话
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        String cookie = login("v2t_user", "Mayy123").getHeaders().getFirst(HttpHeaders.SET_COOKIE).split(";")[0];
        headers.set("Cookie", cookie);

        // 改密:旧密码错误 → 4012(带会话+CSRF)
        ResponseEntity<String> badOld = postJson("/api/v2/auth/password",
                Map.of("oldPassword", "nope", "newPassword", "NewPass123"), cookie);
        assertThat(badOld.getBody()).contains("\"code\":4012");

        // 正确改密 → 新密码可登录、旧密码失效;新哈希仍为 werkzeug scrypt 格式(v1 兼容)
        ResponseEntity<String> change = postJson("/api/v2/auth/password",
                Map.of("oldPassword", "Mayy123", "newPassword", "NewPass123"), cookie);
        assertThat(change.getBody()).contains("\"code\":0");
        assertThat(jdbc.queryForObject("SELECT password_hash FROM users WHERE login_code='v2t_user'", String.class))
                .startsWith("scrypt:"); // v1 兼容:改密后 v1 仍可登录该账号
        assertThat(login("v2t_user", "NewPass123").getStatusCode().value()).isEqualTo(200);
        assertThat(login("v2t_user", "Mayy123").getBody()).contains("\"code\":4010");

        // v2t_br4 改密后 BR-4 标记清除(重新登录验证)
        String br4Cookie = login("v2t_br4", "Mayy123").getHeaders().getFirst(HttpHeaders.SET_COOKIE).split(";")[0];
        headers.set("Cookie", br4Cookie);
        ResponseEntity<String> br4Change = postJson("/api/v2/auth/password",
                Map.of("oldPassword", "Mayy123", "newPassword", "NewPass123"), br4Cookie);
        assertThat(br4Change.getBody()).contains("\"code\":0");
        assertThat(login("v2t_br4", "NewPass123").getBody()).contains("\"needsPasswordChange\":false");
    }
}
