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
        return loginAs("02110606", "P@ss301");
    }

    private String studentCookie() {
        return loginAs("212306413", "P@ss301");
    }

    private String adminCookie() {
        return loginAs("admin", "Mayy123");
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
        // 学生 → 403;教师 → 200;admin(超集)→ 200
        assertThat(get("/api/v2/teacher/pending", studentCookie()).getStatusCode().value()).isEqualTo(403);
        assertThat(get("/api/v2/teacher/pending", teacherCookie()).getStatusCode().value()).isEqualTo(200);
        assertThat(get("/api/v2/teacher/pending", adminCookie()).getStatusCode().value()).isEqualTo(200);
    }
}
