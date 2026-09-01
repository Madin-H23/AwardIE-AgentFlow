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

    /** #28 总览聚合:五区块取数——summary/category/trend/compare/byCompetition + 权限。 */
    @Test
    void overviewAggregatesFiveBlocks() {
        HttpHeaders headers = new HttpHeaders();
        String ck = loginAs("admin", "Mayy123");
        headers.set("Cookie", ck);
        ResponseEntity<String> resp = rest.exchange("/api/v2/admin/stats/overview?months=6&gran=month",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        String body = resp.getBody();
        assertThat(body).contains("\"code\":0")
                .contains("\"summary\":").contains("totalAwards").contains("pendingSubmit")
                .contains("whitelist").contains("awardTeacher")
                .contains("\"category\":").contains("\"patent\"").contains("\"innovation\"")
                .contains("\"trend\":").contains("\"compare\":").contains("deltaPct")
                .contains("\"byCompetition\":");
        // 按年粒度:period 形如 YYYY(4 位,无连字符)
        ResponseEntity<String> yearly = rest.exchange("/api/v2/admin/stats/overview?gran=year",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        // 空库时 trend 为空数组,period 键可能缺——只断结构
        assertThat(yearly.getBody()).contains("\"code\":0").contains("\"trend\"");
        // gran 非法 → 4000
        ResponseEntity<String> bad = rest.exchange("/api/v2/admin/stats/overview?gran=week",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(bad.getBody()).contains("\"code\":4000");
        // 非管理员 → 403
        HttpHeaders stu = new HttpHeaders();
        stu.set("Cookie", loginAs("212306413", "P@ss301"));
        ResponseEntity<String> forbidden = rest.exchange("/api/v2/admin/stats/overview",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(stu), String.class);
        assertThat(forbidden.getStatusCode().value()).isEqualTo(403);
    }
}
