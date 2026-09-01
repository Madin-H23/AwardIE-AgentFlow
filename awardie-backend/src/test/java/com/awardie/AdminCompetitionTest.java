package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

/** #20 竞赛管理:CRUD + 白名单切换(BR-1 口径源头)。 */
class AdminCompetitionTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private String adminCk() {
        return loginAs("admin", "Mayy123");
    }

    private ResponseEntity<String> op(String method, String uri, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        String ck = adminCk();
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        return rest.exchange(uri, org.springframework.http.HttpMethod.valueOf(method),
                new HttpEntity<>(body, headers), String.class);
    }

    private HttpHeaders headers(String ck) {
        HttpHeaders h = new HttpHeaders();
        h.set("Cookie", ck);
        h.set("X-XSRF-TOKEN", xsrfFrom(ck));
        return h;
    }

    @Test
    @Order(1)
    void createAndToggleWhitelist() {
        String name = "E2E竞赛-" + System.nanoTime();
        // 创建(默认白名单开)
        ResponseEntity<String> created = op("POST", "/api/v2/admin/competitions",
                Map.of("competitionName", name, "whiteList", true, "watchList", false));
        assertThat(created.getBody()).contains("\"code\":0").contains("已创建");
        Integer id = jdbc.queryForObject(
                "SELECT id FROM competitions WHERE competition_name=?", Integer.class, name);
        assertThat(id).isNotNull();
        assertThat(jdbc.queryForObject(
                "SELECT white_list FROM competitions WHERE id=?", Boolean.class, id)).isTrue();

        // 切白名单关
        ResponseEntity<String> toggled = op("PUT", "/api/v2/admin/competitions/" + id,
                Map.of("competitionName", name, "whiteList", false, "watchList", true));
        assertThat(toggled.getBody()).contains("\"code\":0");
        assertThat(jdbc.queryForObject(
                "SELECT white_list FROM competitions WHERE id=?", Boolean.class, id)).isFalse();
        assertThat(jdbc.queryForObject(
                "SELECT watch_list FROM competitions WHERE id=?", Boolean.class, id)).isTrue();
    }

    @Test
    @Order(2)
    void duplicateNameRejected() {
        String name = "E2E重复竞赛-" + System.nanoTime();
        op("POST", "/api/v2/admin/competitions", Map.of("competitionName", name, "whiteList", true));
        String dup = op("POST", "/api/v2/admin/competitions", Map.of("competitionName", name, "whiteList", false))
                .getBody();
        assertThat(dup).contains("\"code\":4009").contains("已存在");
    }

    @Test
    @Order(3)
    void autoAddedFlagDistinct() {
        // 自给自足:CI 空库先种一行(幂等),再断言计数
        jdbc.update("""
                INSERT INTO competitions (competition_name, white_list, watch_list, is_auto_added)
                VALUES ('E2E自动建赛-' || EXTRACT(EPOCH FROM NOW())::BIGINT, TRUE, FALSE, TRUE)
                ON CONFLICT (competition_name) DO NOTHING
                """);
        Integer autoAdded = jdbc.queryForObject(
                "SELECT COUNT(*) FROM competitions WHERE is_auto_added=TRUE", Integer.class);
        assertThat(autoAdded).isGreaterThanOrEqualTo(1);
    }

    /** #26:列表真分页——q 模糊命中 + PageView 结构(content/totalElements/totalPages/page/size)。 */
    @Test
    @Order(4)
    void listPaginatedPageView() {
        String ck = adminCk();
        String name = "E2EComp-" + System.nanoTime(); // 纯 ASCII:URL 消编码变量
        String createdBody = op("POST", "/api/v2/admin/competitions",
                Map.of("competitionName", name, "whiteList", true, "watchList", false)).getBody();
        assertThat(createdBody).contains("\"code\":0");

        // {q} 占位:RestTemplate 自动编码,规避手拼 URL 的编码/Host 问题
        String hit = rest.exchange("/api/v2/admin/competitions?page=1&size=20&q={q}",
                HttpMethod.GET, new HttpEntity<>(headers(ck)), String.class, name).getBody();
        assertThat(hit).contains("\"code\":0")
                .contains("\"content\":[").contains(name)
                .contains("\"totalElements\":1").contains("\"totalPages\":1")
                .contains("\"page\":0").contains("\"size\":20");

    }
}
