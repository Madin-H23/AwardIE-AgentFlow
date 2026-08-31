package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;

/** #29 管理面补充域:日志/学生/教师/实验室/模板 只读列表 + RBAC。 */
class AdminConsoleTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    private ResponseEntity<String> get(String uri, String cookie) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie);
        return rest.exchange(uri, HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    @Test
    void logsDualSourcePaged() {
        String ck = loginAs("admin", "Mayy123");
        ResponseEntity<String> audit = get("/api/v2/admin/logs?source=audit&page=1&size=20", ck);
        assertThat(audit.getBody())
                .contains("\"code\":0").contains("\"content\":[").contains("action_type");
        ResponseEntity<String> system = get("/api/v2/admin/logs?source=system&page=1&size=20", ck);
        assertThat(system.getBody()).contains("\"code\":0").contains("event_message");
        // 非法级别不炸(空结果);keyword 过滤可执行
        assertThat(get("/api/v2/admin/logs?source=system&level=info&keyword=seed", ck).getBody())
                .contains("\"code\":0");
    }

    @Test
    void studentsAndTeachersRoleScoped() {
        String ck = loginAs("admin", "Mayy123");
        ResponseEntity<String> students = get("/api/v2/admin/students?page=1&size=20", ck);
        assertThat(students.getBody()).contains("\"code\":0").contains("login_code").contains("user_activated");
        // 种子学生 212306413 可被搜索命中
        assertThat(get("/api/v2/admin/students?search=212306413", ck).getBody())
                .contains("212306413");
        ResponseEntity<String> teachers = get("/api/v2/admin/teachers?page=1&size=20", ck);
        assertThat(teachers.getBody()).contains("\"code\":0").contains("department").contains("title");
        // 教师列表不含学生角色行(角色隔离)
        assertThat(get("/api/v2/admin/teachers?search=212306413", ck).getBody())
                .contains("\"totalElements\":0");
    }

    @Test
    void laboratoriesAndTemplatesPaged() {
        String ck = loginAs("admin", "Mayy123");
        assertThat(get("/api/v2/admin/laboratories?page=1&size=12", ck).getBody())
                .contains("\"code\":0").contains("\"content\":").contains("description");
        assertThat(get("/api/v2/admin/templates?page=1&size=20", ck).getBody())
                .contains("\"code\":0").contains("template_type").contains("competition_name");
    }

    @Test
    void nonAdminForbidden() {
        assertThat(get("/api/v2/admin/logs", loginAs("212306413", "P@ss301")).getStatusCode().value()).isEqualTo(403);
        assertThat(get("/api/v2/admin/students", loginAs("02110606", "P@ss301")).getStatusCode().value()).isEqualTo(403);
    }
}
