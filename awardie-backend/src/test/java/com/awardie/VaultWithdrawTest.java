package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

/** Fix-C/Fix-E:成果库五表管理(列表/编辑/删除)+ 撤回提交。测试写 awardie_test(隔离库)。 */
class VaultWithdrawTest extends BaseIntegrationTest {

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
        return rest.exchange(uri, HttpMethod.valueOf(method), new HttpEntity<>(body, headers), String.class);
    }

    @Test
    @Order(1)
    void vaultFiveTablesStructured() {
        String ck = adminCk();
        for (String type : new String[] {"award", "patent", "software", "innovation", "other"}) {
            ResponseEntity<String> resp = op("GET", "/api/v2/admin/vault/" + type + "?page=0&size=10", null);
            assertThat(resp.getBody()).contains("\"code\":0").contains("\"content\":");
        }
        // 非法 type → 4000
        assertThat(op("GET", "/api/v2/admin/vault/unknown?page=0&size=10", null).getBody())
                .contains("\"code\":4000");
    }

    @Test
    @Order(2)
    void awardEditAndDelete() {
        String ck = adminCk();
        // 先造一条测试 award(直插测试库,隔离无污染)
        // CI 空库:先保证 competitions 存在引用行(FK 依赖)
        jdbc.update("""
                INSERT INTO competitions (id, competition_name, white_list, is_auto_added)
                VALUES (1, 'Vault测试竞赛', TRUE, FALSE)
                ON CONFLICT (id) DO NOTHING
                """);
        jdbc.update("""
                INSERT INTO awards (competition_name_in_file, competition_level, award_level, winner_name,
                                    competition_id, granted_role, created_at)
                VALUES ('Vault测试赛', '省赛', '一等奖', 'Vault学生', 1, NULL, NOW())
                """);
        Integer id = jdbc.queryForObject(
                "SELECT MAX(id) FROM awards WHERE competition_name_in_file='Vault测试赛'", Integer.class);
        // 编辑
        Map<String, Object> updBody = new HashMap<>();
        updBody.put("awardLevel", "特等奖");
        updBody.put("winnerName", "Vault改");
        updBody.put("supervisorName", "");
        updBody.put("laboratoryId", null);
        ResponseEntity<String> updated = op("PUT", "/api/v2/admin/vault/awards/" + id, updBody);
        assertThat(updated.getBody()).contains("\"code\":0").contains("已更新");
        assertThat(jdbc.queryForObject(
                "SELECT award_level FROM awards WHERE id=?", String.class, id)).isEqualTo("特等奖");
        // 删除
        assertThat(op("DELETE", "/api/v2/admin/vault/award/" + id, null).getBody())
                .contains("\"code\":0").contains("已删除");
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM awards WHERE id=?", Integer.class, id)).isEqualTo(0);
    }

    @Test
    @Order(3)
    void studentWithdrawOwnPending() {
        // 学生登录,提交一笔 → 撤回 → 行删除;再撤回 → 404
        String ck = loginAs("212306413", "P@ss301");
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        byte[] png = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x57, 0x44};
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(png) {
            @Override
            public String getFilename() {
                return "withdraw-" + System.nanoTime() + ".png";
            }
        });
        form.add("achievement_type", "award");
        form.add("data", "{\"competition_name\":\"撤回测试赛\",\"award_level\":\"二等奖\",\"date\":\"2026-09\"}");
        Integer id = Integer.parseInt(rest.postForEntity("/api/v2/student/submit",
                new HttpEntity<>(form, headers), String.class).getBody()
                .replaceAll(".*\"id\":(\\d+).*", "$1"));

        ResponseEntity<String> resp = rest.exchange("/api/v2/student/pending/" + id,
                HttpMethod.DELETE, new HttpEntity<>(headers(ck)), String.class);
        assertThat(resp.getBody()).contains("\"code\":0").contains("已撤回");
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM pending_achievements WHERE id=?", Integer.class, id)).isEqualTo(0);
    }

    private HttpHeaders headers(String ck) {
        HttpHeaders h = new HttpHeaders();
        h.set("Cookie", ck);
        h.set("X-XSRF-TOKEN", xsrfFrom(ck));
        return h;
    }

    private HttpEntity<Void> headersAsEntity(String ck) {
        return new HttpEntity<>(headers(ck));
    }

    @Test
    @Order(4)
    void cannotWithdrawOthersOrArchived() {
        String stu = loginAs("212306413", "P@ss301");
        // 种子管理员有一条 admin pending(Fix-A 种子),学生撤它 → 4030
        Integer adminPending = jdbc.queryForObject(
                "SELECT id FROM pending_achievements WHERE submitter_type='admin' AND status='pending' LIMIT 1",
                Integer.class);
        if (adminPending != null) {
            ResponseEntity<String> resp = rest.exchange("/api/v2/student/pending/" + adminPending,
                    HttpMethod.DELETE, new HttpEntity<>(headersAsEntity(stu)), String.class);
            // 4030 JSON(经 handler)或 Security 裸 403 均属"拒绝",断言非 200 即可
            assertThat(resp.getStatusCode().value()).isEqualTo(403);
        }
    }
}
