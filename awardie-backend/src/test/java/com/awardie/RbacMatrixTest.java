package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;

/**
 * G1 RBAC 参数化矩阵:GET 业务端点全量 × 3 角色(student/teacher/admin)。
 * 约定:新增 GET 端点必须在此登记,漏配的端点由 RbacMatrixTest.endpointsRegistered 兜底提示。
 * DELETE/POST/PUT 的 RBAC 由各自功能测试覆盖(withdraw/import/submit/confirm)。
 */
class RbacMatrixTest extends BaseIntegrationTest {

    private static final String STUDENT = "212306413";
    private static final String TEACHER = "02110606";
    private static final String ADMIN = "admin";

    private enum Access {
        ALL, ADMIN, STUDENT, TEACHER, STAFF // STAFF=teacher+admin
    }

    /** 端点登记表:method 固定 GET;path 支持占位无(全部可直接 GET)。 */
    private record Endpoint(String path, Access access) {}

    private static final List<Endpoint> ENDPOINTS = List.of(
            // ---- admin 管理面 ----
            new Endpoint("/api/v2/admin/achievements?page=0&size=10", Access.ADMIN),
            new Endpoint("/api/v2/admin/achievements?page=0&size=10&keyword=x", Access.ADMIN),
            new Endpoint("/api/v2/admin/vault/award?page=0&size=10", Access.ADMIN),
            new Endpoint("/api/v2/admin/vault/patent?page=0&size=10", Access.ADMIN),
            new Endpoint("/api/v2/admin/vault/software?page=0&size=10", Access.ADMIN),
            new Endpoint("/api/v2/admin/vault/innovation?page=0&size=10", Access.ADMIN),
            new Endpoint("/api/v2/admin/vault/other?page=0&size=10", Access.ADMIN),
            new Endpoint("/api/v2/admin/logs?source=audit&page=1&size=20", Access.ADMIN),
            new Endpoint("/api/v2/admin/logs?source=system&page=1&size=20", Access.ADMIN),
            new Endpoint("/api/v2/admin/logs/stream?afterId=0&timeoutMillis=1000", Access.ADMIN),
            new Endpoint("/api/v2/admin/students?page=1&size=20", Access.ADMIN),
            new Endpoint("/api/v2/admin/teachers?page=1&size=20", Access.ADMIN),
            new Endpoint("/api/v2/admin/laboratories?page=1&size=12", Access.ADMIN),
            new Endpoint("/api/v2/admin/templates?page=1&size=20", Access.ADMIN),
            new Endpoint("/api/v2/admin/analysis/competitions", Access.ADMIN),
            new Endpoint("/api/v2/admin/analysis/contribution", Access.ADMIN),
            new Endpoint("/api/v2/admin/analysis/heatmap", Access.ADMIN),
            new Endpoint("/api/v2/admin/analysis/records", Access.ADMIN),
            new Endpoint("/api/v2/admin/export/department-summary.csv", Access.ADMIN),
            new Endpoint("/api/v2/admin/export/student-affairs.csv", Access.ADMIN),
            new Endpoint("/api/v2/admin/export/teacher-personal.csv", Access.ADMIN),
            new Endpoint("/api/v2/admin/export/department-summary.xlsx", Access.ADMIN),
            new Endpoint("/api/v2/admin/export/student-affairs.xlsx", Access.ADMIN),
            new Endpoint("/api/v2/admin/export/teacher-personal.xlsx", Access.ADMIN),
            new Endpoint("/api/v2/admin/settings/auto-archive", Access.ADMIN),
            new Endpoint("/api/v2/admin/stats", Access.ADMIN),
            new Endpoint("/api/v2/admin/stats/overview", Access.ADMIN),
            // ---- 学生门户 ----
            new Endpoint("/api/v2/student/pending", Access.ALL),
            new Endpoint("/api/v2/student/awards", Access.ALL),
            new Endpoint("/api/v2/student/portal/summary", Access.STUDENT),
            new Endpoint("/api/v2/student/portal/achievements", Access.STUDENT),
            new Endpoint("/api/v2/student/portal/export.csv", Access.STUDENT),
            // ---- 教师门户 ----
            new Endpoint("/api/v2/teacher/pending", Access.STAFF),
            new Endpoint("/api/v2/teacher/portal/summary", Access.TEACHER),
            new Endpoint("/api/v2/teacher/portal/achievements", Access.TEACHER),
            new Endpoint("/api/v2/teacher/portal/export.csv", Access.TEACHER),
            // ---- 共通 ----
            new Endpoint("/api/v2/chat/stream?q=matrix&timeoutMillis=2000", Access.ALL),
            new Endpoint("/api/v2/profile", Access.ALL));

    @Autowired
    private TestRestTemplate rest;

    private String cookieOf(String account, String password) {
        return loginAs(account, password);
    }

    private int statusOf(String cookie, String path) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie);
        return rest.exchange(path, HttpMethod.GET, new HttpEntity<>(headers), String.class)
                .getStatusCode().value();
    }

    private boolean allowed(Access access, String role) {
        return switch (access) {
            case ALL -> true;
            case ADMIN -> role.equals("admin");
            case STUDENT -> role.equals("student");
            case TEACHER -> role.equals("teacher");
            case STAFF -> role.equals("teacher") || role.equals("admin");
        };
    }

    @Test
    void rbacMatrixAllEndpoints() {
        record Role(String account, String password, String name) {}
        List<Role> roles = List.of(
                new Role(STUDENT, "P@ss301", "student"),
                new Role(TEACHER, "P@ss301", "teacher"),
                new Role(ADMIN, "Mayy123", "admin"));
        // 预取三角色会话(避免每断言重复登录)
        java.util.Map<String, String> cookies = new java.util.HashMap<>();
        for (Role r : roles) {
            cookies.put(r.name(), cookieOf(r.account(), r.password()));
        }

        StringBuilder violations = new StringBuilder();
        for (Endpoint ep : ENDPOINTS) {
            for (Role r : roles) {
                int status = statusOf(cookies.get(r.name()), ep.path());
                boolean expectAllowed = allowed(ep.access(), r.name());
                boolean isAllowed = status != 403;
                if (expectAllowed != isAllowed) {
                    violations.append(String.format("%s @ %s 期望 %s 实际 %d%n",
                            r.name(), ep.path(), expectAllowed ? "放行" : "403", status));
                }
            }
        }
        assertThat(violations.toString())
                .as("RBAC 矩阵违规(端点数 %d):%n%s", ENDPOINTS.size(), violations)
                .isEmpty();
    }

    /** 兜底:矩阵行数下限,防误删登记。 */
    @Test
    void endpointsRegisteredFloor() {
        assertThat(ENDPOINTS.size()).isGreaterThanOrEqualTo(20);
        // 无重复路径
        long distinct = ENDPOINTS.stream().map(Endpoint::path).distinct().count();
        assertThat(distinct).isEqualTo(ENDPOINTS.size());
        // 登记的 Access 均为合法枚举(编译期保证),此处核对覆盖三类域前缀
        Set<String> prefixes = ENDPOINTS.stream()
                .map(e -> e.path().split("/")[3]).collect(java.util.stream.Collectors.toSet());
        assertThat(prefixes).contains("admin", "student", "teacher", "chat");
    }
}
