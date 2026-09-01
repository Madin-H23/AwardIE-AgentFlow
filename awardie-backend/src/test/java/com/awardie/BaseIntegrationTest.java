package com.awardie;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;

import org.junit.jupiter.api.BeforeEach;

import java.util.Map;

/**
 * 集成测试基座:集成测试共享的自举约定。
 *
 * seedAccounts 让测试对数据库状态自洽(空库/任意库均可跑)——
 * 这是 CI(GitHub Actions postgres service + Flyway V1 空库建表)的前提,
 * 也是"测试不依赖本地库存量数据"的边界。密码哈希用 v2 的 werkzeug scrypt
 * 兼容编码器生成,与存量 1834 条同构。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        // Fix-A 测试库隔离:集成测试写 awardie_test(独立库,Flyway 空库自建表),
        // 不再触开发库 awardie_dev——根除"测试数据写入真实库"的污染源
        "spring.datasource.url=jdbc:postgresql://127.0.0.1:5433/awardie_test"
})
public abstract class BaseIntegrationTest {

    @Autowired
    protected JdbcTemplate jdbc;

    @Autowired
    protected PasswordEncoder passwordEncoder;

    @Autowired
    protected TestRestTemplate rest;

    /** 会话 cookie 串(JSESSIONID;由各测试从登录响应提取)。 */
    protected String sessionCookie(ResponseEntity<String> loginResp) {
        return loginResp.getHeaders().getFirst(HttpHeaders.SET_COOKIE).split(";")[0];
    }

    /** 从 cookie 串提取 XSRF-TOKEN 值;无则 null。 */
    protected String xsrfFrom(String cookie) {
        if (cookie == null) {
            return null;
        }
        for (String part : cookie.split("; ")) {
            if (part.startsWith("XSRF-TOKEN=")) {
                return part.substring("XSRF-TOKEN=".length());
            }
        }
        return null;
    }

    /** 取 CSRF cookie+token(GET /api/v2/auth/csrf,CookieCsrfTokenRepository 自动签发)。 */
    protected String[] fetchCsrf(String sessionCookie) {
        // 会话里已带 XSRF-TOKEN(cookie 与 header 同值即过 CookieCsrfTokenRepository 校验)——
        // 关键:不得再匿名新签,否则 Cookie 链出现两个 XSRF-TOKEN,取首失配 → 403
        if (sessionCookie != null) {
            for (String part : sessionCookie.split("; ")) {
                if (part.startsWith("XSRF-TOKEN=")) {
                    return new String[]{part, part.substring("XSRF-TOKEN=".length())};
                }
            }
        }
        HttpHeaders h = new HttpHeaders();
        if (sessionCookie != null) {
            h.set("Cookie", sessionCookie);
        }
        ResponseEntity<String> r = rest.exchange("/api/v2/auth/csrf", org.springframework.http.HttpMethod.GET,
                new HttpEntity<>(h), String.class);
        var setCookies = r.getHeaders().get(HttpHeaders.SET_COOKIE);
        if (setCookies == null) {
            throw new IllegalStateException("CSRF 端点未返回 Set-Cookie(检查 permitAll 与 deferred 配置)");
        }
        String xsrfCookie = setCookies.stream()
                .filter(c -> c.startsWith("XSRF-TOKEN=")).findFirst().orElse("");
        String cookiePair = xsrfCookie.split(";")[0];
        String token = cookiePair.substring("XSRF-TOKEN=".length());
        return new String[]{cookiePair, token};
    }

    /** CSRF-aware JSON POST:自动取 token 并携带会话。 */
    protected ResponseEntity<String> postJson(String uri, Object body, String sessionCookie) {
        String[] c = fetchCsrf(sessionCookie);
        HttpHeaders h = new HttpHeaders();
        h.setContentType(MediaType.APPLICATION_JSON);
        if (sessionCookie != null) {
            h.set("Cookie", sessionCookie);
        }
        h.set("X-XSRF-TOKEN", c[1]);
        h.set("Cookie", (sessionCookie == null ? "" : sessionCookie + "; ") + c[0]);
        return rest.postForEntity(uri, new HttpEntity<>(body, h), String.class);
    }

    /** 登录并返回合并 cookie 串(JSESSIONID + XSRF)。 */
    protected String loginAs(String account, String password) {
        ResponseEntity<String> resp = postJson("/api/v2/auth/login", Map.of("account", account, "password", password), null);
        String js = sessionCookie(resp); // 仅 JSESSIONID(login 响应无 XSRF cookie)
        String[] c = fetchCsrf(null);    // 匿名 GET /csrf 显式签发(XSRF cookie 与登录无关,token 全局有效)
        return js + "; " + c[0];
    }

    /** Fix-A:每个测试方法前统一自举三角色(幂等)——新类不再依赖隐式执行顺序。 */
    @BeforeEach
    void seedAccountsAuto() {
        seedAccounts();
    }

    /** 三角色测试账号:不存在则建(口令与本地约定一致)。 */
    protected void seedAccounts() {
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('admin', '系统管理员', 'admin', ?, TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """, passwordEncoder.encode("Mayy123"));
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('212306413', '测试学生', 'student', ?, TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """, passwordEncoder.encode("P@ss301"));
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('02110606', '测试教师', 'teacher', ?, TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """, passwordEncoder.encode("P@ss301"));
    }
}
