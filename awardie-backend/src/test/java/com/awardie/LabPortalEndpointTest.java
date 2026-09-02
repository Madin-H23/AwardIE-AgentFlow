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
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

/** Fix-G 实验室详情/编辑/下载端点测试(测试库 awardie_test,自给自足)。 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class LabPortalEndpointTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private String adminCk() {
        return loginAs("admin", "Mayy123");
    }

    private ResponseEntity<String> get(String ck, String path) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", ck);
        // 相对 path:TestRestTemplate 自带根 URI(与其他测试类一致)
        return rest.exchange(path, HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    private ResponseEntity<String> put(String ck, String path, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType_JSON);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        return rest.exchange(path, HttpMethod.PUT, new HttpEntity<>(body, headers), String.class);
    }

    private Integer seedLab() {
        jdbc.update("""
                INSERT INTO laboratories (name, description)
                VALUES ('FixG实验室', 'Fix-G 测试简介')
                ON CONFLICT (id) DO NOTHING
                """.replace("ON CONFLICT (id) DO NOTHING", ""));
        return jdbc.queryForObject(
                "SELECT id FROM laboratories WHERE name='FixG实验室' ORDER BY id DESC LIMIT 1", Integer.class);
    }

    @Test
    @Order(1)
    void detailAggregates() {
        Integer id = seedLab();
        String body = get(adminCk(), "/api/v2/admin/laboratories/" + id + "/detail").getBody();
        assertThat(body).contains("\"code\":0")
                .contains("FixG实验室")
                .contains("instructors")
                .contains("students")
                .contains("downloadCount")
                .contains("awardCount");
        // 404
        assertThat(get(adminCk(), "/api/v2/admin/laboratories/999999/detail").getBody())
                .contains("4004");
    }

    @Test
    @Order(2)
    void updateLabFields() {
        Integer id = seedLab();
        String ck = adminCk();
        ResponseEntity<String> resp = put(ck, "/api/v2/admin/laboratories/" + id,
                Map.of("name", "FixG改名", "description", "改简介"));
        assertThat(resp.getBody()).contains("\"code\":0").contains("已更新");
        assertThat(jdbc.queryForObject(
                "SELECT name FROM laboratories WHERE id=?", String.class, id)).isEqualTo("FixG改名");
        // 名称必填
        assertThat(put(ck, "/api/v2/admin/laboratories/" + id, Map.of("name", "")).getBody())
                .contains("4000");
    }

    @Test
    @Order(3)
    void downloadsListForLab() {
        Integer id = seedLab();
        jdbc.update("""
                INSERT INTO laboratory_downloads (laboratory_id, file_path, file_title, file_name, file_size)
                VALUES (?, 'diag/dl.png', 'FixG下载文件', 'dl.png', 2048)
                """, id);
        String body = get(adminCk(), "/api/v2/admin/laboratories/" + id + "/downloads").getBody();
        assertThat(body).contains("\"code\":0").contains("FixG下载文件").contains("2048");
    }

    @Test
    @Order(4)
    void nonAdminForbiddenOnAll() {
        // 与其他测试类同口径:rest.exchange 相对 path(根 URI 自动补全)
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", loginAs("212306413", "P@ss301"));
        assertThat(rest.exchange("/api/v2/admin/laboratories/1/detail", HttpMethod.GET,
                new HttpEntity<>(headers), String.class).getStatusCode().value()).isEqualTo(403);
        assertThat(rest.exchange("/api/v2/admin/laboratories/1/downloads", HttpMethod.GET,
                new HttpEntity<>(headers), String.class).getStatusCode().value()).isEqualTo(403);
    }

    private static final org.springframework.http.MediaType MediaType_JSON =
            org.springframework.http.MediaType.APPLICATION_JSON;
}
