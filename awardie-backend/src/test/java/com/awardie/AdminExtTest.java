package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

/** #30/#31/#32 管理面第二批:数据分析聚合/CSV 导出/自动归档设置读写。断言数据无关(CI 空库兼容)。 */
class AdminExtTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private ResponseEntity<String> get(String uri, String cookie) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie);
        return rest.exchange(uri, HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    @Test
    void analysisEndpointsStructured() {
        String ck = loginAs("admin", "Mayy123");
        // 纪律:列表端点断言只到 code/结构层——CI 空库 data 为空数组,任何行内键名断言都会挂
        assertThat(get("/api/v2/admin/analysis/competitions", ck).getBody()).contains("\"code\":0");
        assertThat(get("/api/v2/admin/analysis/contribution?years=2026&whiteListOnly=false", ck).getBody())
                .contains("\"code\":0").contains("\"data\"");
        assertThat(get("/api/v2/admin/analysis/heatmap?includeTeacher=true", ck).getBody())
                .contains("\"code\":0");
        assertThat(get("/api/v2/admin/analysis/records", ck).getBody())
                .contains("\"code\":0");
    }

    @Test
    void exportCsvEndpoints() {
        String ck = loginAs("admin", "Mayy123");
        ResponseEntity<String> summary = get("/api/v2/admin/export/department-summary.csv?year=2026", ck);
        assertThat(summary.getHeaders().getFirst("Content-Disposition")).contains(".csv");
        // 种子提交的竞赛(种子竞赛-白名单,admin pending 提交含 award 数据但未物化——CSV 走 awards 表,空表也应有表头)
        assertThat(summary.getBody()).contains("竞赛");
        assertThat(get("/api/v2/admin/export/student-affairs.csv", ck).getBody()).contains("学号");
        assertThat(get("/api/v2/admin/export/teacher-personal.csv", ck).getBody()).contains("工号");
    }

    @Test
    void autoArchiveReadWrite() {
        String ck = loginAs("admin", "Mayy123");
        ResponseEntity<String> before = get("/api/v2/admin/settings/auto-archive", ck);
        assertThat(before.getBody()).contains("\"code\":0");

        // CI fixture 库无种子配置行:测试自保证目标行存在
        jdbc.update("""
                INSERT INTO auto_archive_config (achievement_type, validation_status, auto_archive_enabled)
                VALUES ('award', 'valid', FALSE)
                ON CONFLICT (achievement_type, validation_status) DO NOTHING
                """);

        // 翻转 award/valid 行(validation_status 非 null,避开 Map.of null)并回读
        Boolean first = jdbc.queryForObject(
                "SELECT auto_archive_enabled FROM auto_archive_config WHERE achievement_type='award' AND validation_status='valid'",
                Boolean.class);
        Map<String, Object> row = Map.of(
                "achievementType", "award",
                "validationStatus", "valid",
                "autoArchiveEnabled", !first);
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        ResponseEntity<String> put = rest.exchange("/api/v2/admin/settings/auto-archive",
                HttpMethod.PUT, new HttpEntity<>(Map.of("rows", java.util.List.of(row)), headers), String.class);
        assertThat(put.getBody()).contains("\"code\":0").contains("已保存");
        Boolean after = jdbc.queryForObject(
                "SELECT auto_archive_enabled FROM auto_archive_config WHERE achievement_type='award' AND validation_status='valid'",
                Boolean.class);
        assertThat(after).isEqualTo(!first);

        // 还原
        jdbc.update("UPDATE auto_archive_config SET auto_archive_enabled=? WHERE achievement_type='award' AND validation_status='valid'",
                first);
    }

    @Test
    void nonAdminForbidden() {
        String stu = loginAs("212306413", "P@ss301");
        assertThat(get("/api/v2/admin/analysis/competitions", stu).getStatusCode().value()).isEqualTo(403);
        assertThat(get("/api/v2/admin/export/student-affairs.csv", stu).getStatusCode().value()).isEqualTo(403);
        assertThat(get("/api/v2/admin/settings/auto-archive", stu).getStatusCode().value()).isEqualTo(403);
    }
}
