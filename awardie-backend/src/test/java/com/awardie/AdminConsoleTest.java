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
        // 数据无关断言(CI 空库 content 为空数组,不含行内列名):只断结构
        ResponseEntity<String> audit = get("/api/v2/admin/logs?source=audit&page=1&size=20", ck);
        assertThat(audit.getBody())
                .contains("\"code\":0").contains("\"content\":")
                .contains("\"totalElements\"").contains("\"totalPages\"");
        ResponseEntity<String> system = get("/api/v2/admin/logs?source=system&page=1&size=20", ck);
        assertThat(system.getBody()).contains("\"code\":0").contains("\"content\":");
        // 过滤参数可执行(空结果也是 0)
        assertThat(get("/api/v2/admin/logs?source=system&level=info&keyword=seed", ck).getBody())
                .contains("\"code\":0").contains("\"totalElements\":");
    }

    @Test
    void studentsAndTeachersRoleScoped() {
        String ck = loginAs("admin", "Mayy123");
        ResponseEntity<String> students = get("/api/v2/admin/students?page=1&size=20", ck);
        assertThat(students.getBody()).contains("\"code\":0").contains("\"content\":");
        // 种子学生 212306413 三角色自举保证存在(数据相关断言仅限种子账号)
        assertThat(get("/api/v2/admin/students?search=212306413", ck).getBody())
                .contains("212306413");
        ResponseEntity<String> teachers = get("/api/v2/admin/teachers?page=1&size=20", ck);
        assertThat(teachers.getBody()).contains("\"code\":0").contains("\"content\":");
        // 教师列表不含学生角色行(角色隔离;种子学生非教师)
        assertThat(get("/api/v2/admin/teachers?search=212306413", ck).getBody())
                .contains("\"totalElements\":0");
    }

    @Test
    void laboratoriesAndTemplatesPaged() {
        String ck = loginAs("admin", "Mayy123");
        assertThat(get("/api/v2/admin/laboratories?page=1&size=12", ck).getBody())
                .contains("\"code\":0").contains("\"content\":").contains("\"page\":0");
        assertThat(get("/api/v2/admin/templates?page=1&size=20", ck).getBody())
                .contains("\"code\":0").contains("\"content\":").contains("\"size\":20");
    }

    @Test
    void nonAdminForbidden() {
        assertThat(get("/api/v2/admin/logs", loginAs("212306413", "P@ss301")).getStatusCode().value()).isEqualTo(403);
        assertThat(get("/api/v2/admin/students", loginAs("02110606", "P@ss301")).getStatusCode().value()).isEqualTo(403);
    }
}
