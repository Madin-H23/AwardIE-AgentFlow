package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;

/** #21 看板统计:口径与 RBAC。 */
class AdminStatsTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Test
    void statsHasCoreMetricsAndTrend() {
        HttpHeaders headers = new HttpHeaders();
        String ck = loginAs("admin", "Mayy123");
        headers.set("Cookie", ck);
        ResponseEntity<String> resp = rest.exchange("/api/v2/admin/stats",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(resp.getBody())
                .contains("awardsTotal").contains("pendingTotal")
                .contains("usersTotal").contains("trend");
    }

    @Test
    void statsForbiddenForNonAdmin() {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", loginAs("212306413", "P@ss301"));
        ResponseEntity<String> resp = rest.exchange("/api/v2/admin/stats",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(403);
    }
}
