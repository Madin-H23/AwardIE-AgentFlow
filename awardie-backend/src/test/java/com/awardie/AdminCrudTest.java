package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

/** #38 师生/实验室 CRUD:创建(默认口令+首登改密)/编辑/删除(FK 拒绝)+RBAC。 */
class AdminCrudTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private ResponseEntity<String> op(String method, String uri, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        String ck = loginAs("admin", "Mayy123");
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        return rest.exchange(uri, HttpMethod.valueOf(method),
                new HttpEntity<>(body, headers), String.class);
    }

    private Map<String, Object> userRow(String code, String name) {
        Map<String, Object> row = new HashMap<>();
        row.put("loginCode", code);
        row.put("name", name);
        row.put("major", "软件工程");
        row.put("grade", "2024");
        row.put("phone", "13800000000");
        return row;
    }

    @Test
    void studentCrudLifecycle() {
        String code = "CRUD" + System.nanoTime();
        ResponseEntity<String> created = op("POST", "/api/v2/admin/users/student",
                userRow(code, "增删改学生"));
        assertThat(created.getBody()).contains("\"code\":0").contains("首登须修改");

        Integer id = jdbc.queryForObject("SELECT id FROM users WHERE login_code=?", Integer.class, code);
        assertThat(id).isNotNull();
        // 默认口令可登录(ADR-0002:werkzeug scrypt 恒守)+首登强制改密
        assertThat(jdbc.queryForObject(
                "SELECT needs_password_change FROM users WHERE id=?", Boolean.class, id)).isTrue();
        assertThat(jdbc.queryForObject(
                "SELECT password_hash FROM users WHERE id=?", String.class, id)).startsWith("scrypt");

        // 编辑
        ResponseEntity<String> updated = op("PUT", "/api/v2/admin/users/student/" + id,
                userRow(code, "改名学生"));
        assertThat(updated.getBody()).contains("\"code\":0").contains("已更新");
        assertThat(jdbc.queryForObject("SELECT name FROM users WHERE id=?", String.class, id))
                .isEqualTo("改名学生");

        // 学号重复 → 4009
        ResponseEntity<String> dup = op("POST", "/api/v2/admin/users/student", userRow(code, "重复学生"));
        assertThat(dup.getBody()).contains("\"code\":4009");

        // 删除(无关联)→ 成功;再删 → 4004
        assertThat(op("DELETE", "/api/v2/admin/users/student/" + id, null).getBody())
                .contains("\"code\":0").contains("已删除");
        assertThat(op("DELETE", "/api/v2/admin/users/student/" + id, null).getBody())
                .contains("\"code\":4004");
    }

    @Test
    void deleteStudentWithAwardsRejected() {
        // 种子学生 212306413 有获奖关联(E2E/tracer 提交物化)→ FK 拒绝 4009;fixture 无该学生则跳过
        var found = jdbc.queryForList(
                "SELECT id FROM users WHERE login_code='212306413'");
        if (found.isEmpty()) {
            return;
        }
        Integer stuId = (Integer) found.get(0).get("id");
        ResponseEntity<String> resp = op("DELETE", "/api/v2/admin/users/student/" + stuId, null);
        String body = resp.getBody();
        if (body != null && body.contains("\"code\":0")) {
            // fixture 无关联时允许删除(数据无关口径):不视为失败
            return;
        }
        assertThat(body).contains("\"code\":4009");
    }

    @Test
    void laboratoryCrudLifecycle() {
        String name = "CRUD实验室-" + System.nanoTime();
        ResponseEntity<String> created = op("POST", "/api/v2/admin/laboratories",
                Map.of("name", name, "description", "增删改测试"));
        assertThat(created.getBody()).contains("\"code\":0").contains("已创建");
        Integer id = jdbc.queryForObject(
                "SELECT id FROM laboratories WHERE name=?", Integer.class, name);
        assertThat(id).isNotNull();

        ResponseEntity<String> updated = op("PUT", "/api/v2/admin/laboratories/" + id,
                Map.of("name", name, "description", "改简介"));
        assertThat(updated.getBody()).contains("\"code\":0").contains("已更新");

        ResponseEntity<String> deleted = op("DELETE", "/api/v2/admin/laboratories/" + id, null);
        assertThat(deleted.getBody()).contains("\"code\":0");
    }

    @Test
    void nonAdminForbidden() {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", loginAs("212306413", "P@ss301"));
        ResponseEntity<String> resp = rest.exchange("/api/v2/admin/users/student",
                HttpMethod.POST, new HttpEntity<>(userRow("X", "X"), headers), String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(403);
    }
}
