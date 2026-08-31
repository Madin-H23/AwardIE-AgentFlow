package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;

/** #33 AI 问答 SSE(fake 模式):事件序列完整/BR-2 免责声明/未登录 401。 */
class ChatStreamTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Test
    void fakeStreamEmitsFullSequence() {
        String ck = loginAs("admin", "Mayy123");
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", ck);
        ResponseEntity<String> resp = rest.exchange(
                "/api/v2/chat/stream?q=" + "哪些是白名单赛事?",
                HttpMethod.GET, new HttpEntity<>(headers), String.class);
        String body = resp.getBody();
        assertThat(resp.getStatusCode().value()).isEqualTo(200);
        assertThat(body)
                .contains("\"kind\":\"node\"")
                .contains("delta")
                .contains("\"kind\":\"final\"")
                .contains("fake 模式")
                .contains("BR-2");
    }

    @Test
    void blankQuestionRejected() {
        String ck = loginAs("admin", "Mayy123");
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", ck);
        ResponseEntity<String> resp = rest.exchange(
                "/api/v2/chat/stream?q=", HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(resp.getStatusCode().value()).isIn(400, 500);
    }

    @Test
    void anonymousGets401() {
        ResponseEntity<String> resp = rest.exchange(
                "/api/v2/chat/stream?q=test", HttpMethod.GET, new HttpEntity<>(new HttpHeaders()), String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(401);
    }
}
