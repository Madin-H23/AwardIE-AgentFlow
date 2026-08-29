package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.ResponseEntity;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class HealthSmokeTest {

    @Autowired
    private TestRestTemplate rest;

    @Test
    void healthIsUp() {
        ResponseEntity<String> resp = rest.getForEntity("/actuator/health", String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(200);
        assertThat(resp.getBody()).contains("UP");
    }

    @Test
    void unknownPathReturnsUnifiedErrorWithTraceId() {
        ResponseEntity<String> resp = rest.getForEntity("/api/definitely/not/exist", String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(404);
        assertThat(resp.getBody()).contains("\"code\":4004");
        assertThat(resp.getBody()).contains("traceId");
        assertThat(resp.getHeaders().getFirst("X-Trace-Id")).isNotBlank();
    }
}
