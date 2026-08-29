package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Iterator;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;

import java.util.Map;
import org.springframework.http.MediaType;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;

import com.awardie.aireview.AiProxyService;
import com.awardie.submission.PendingAchievementEntity;

/** #9:AI 建议(fake 模式确定性行为)+ 教师端点 RBAC + SSE 冒烟。 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class TeacherAiReviewTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private AiProxyService ai;

    private String teacherCookie() {
        return cookieOf(post("/api/v2/auth/login", Map.of("account", "02110606", "password", "P@ss301")));
    }

    private String studentCookie() {
        return cookieOf(post("/api/v2/auth/login", Map.of("account", "212306413", "password", "P@ss301")));
    }

    private String adminCookie() {
        return cookieOf(post("/api/v2/auth/login", Map.of("account", "admin", "password", "Mayy123")));
    }

    private ResponseEntity<String> post(String uri, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return rest.postForEntity(uri, new HttpEntity<>(body, headers), String.class);
    }

    private String cookieOf(ResponseEntity<String> resp) {
        return resp.getHeaders().getFirst(HttpHeaders.SET_COOKIE).split(";")[0];
    }

    private ResponseEntity<String> get(String uri, String cookie) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie);
        return rest.exchange(uri, HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    @org.junit.jupiter.api.BeforeEach
    void seedBase() {
        seedAccounts();
    }

    @Test
    void fakeModeProducesDeterministicEventSequence() {
        PendingAchievementEntity p = new PendingAchievementEntity();
        p.setId(1);
        p.setFilePath("files/v2/whatever.png");
        Iterator<AiProxyService.AiEvent> it = ai.suggest(p);
        List<String> kinds = new java.util.ArrayList<>();
        AtomicReference<String> finalDecision = new AtomicReference<>();
        while (it.hasNext()) {
            AiProxyService.AiEvent e = it.next();
            kinds.add(e.kind());
            if ("final".equals(e.kind())) {
                finalDecision.set(e.message());
            }
        }
        assertThat(kinds).containsExactly("node", "delta", "node", "delta", "final");
        assertThat(finalDecision.get()).startsWith("pass|");
    }

    @Test
    void aiProxyIsFakeInP0Tests() {
        assertThat(ai.isFake()).isTrue();
    }

    @Test
    void teacherPendingListRequiresTeacherRole() {
        // 学生 → 403;教师 → 200
        assertThat(get("/api/v2/teacher/pending", studentCookie()).getStatusCode().value()).isEqualTo(403);
        ResponseEntity<String> teacherLogin = post("/api/v2/auth/login",
                Map.of("account", "02110606", "password", "P@ss301"));
        System.out.println("[diag] teacher login = " + teacherLogin.getBody()
                + " hasCookie=" + (teacherLogin.getHeaders().getFirst(HttpHeaders.SET_COOKIE) != null));
        ResponseEntity<String> teacherList = get("/api/v2/teacher/pending", cookieOf(teacherLogin));
        System.out.println("[diag] teacher pending = " + teacherList.getBody());
        assertThat(teacherList.getStatusCode().value()).isEqualTo(200);
        ResponseEntity<String> adminLogin = post("/api/v2/auth/login",
                Map.of("account", "admin", "password", "Mayy123"));
        System.out.println("[diag] admin login = " + adminLogin.getBody());
        ResponseEntity<String> adminList = get("/api/v2/teacher/pending", cookieOf(adminLogin));
        System.out.println("[diag] admin list status=" + adminList.getStatusCode().value() + " body=" + adminList.getBody());
        assertThat(adminList.getStatusCode().value()).isEqualTo(200);
    }
}
