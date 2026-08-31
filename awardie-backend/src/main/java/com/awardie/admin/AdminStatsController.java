package com.awardie.admin;

import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;

/** admin 仪表盘(#21):总数/待审/月度趋势(PG date_trunc 替代 v1 strftime)。 */
@RestController
@RequestMapping("/api/v2/admin/stats")
public class AdminStatsController {

    private final JdbcTemplate jdbc;

    public AdminStatsController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping
    public ApiResponse<Map<String, Object>> stats(Authentication auth) {
        requireAdmin(auth);
        Integer awardsTotal = jdbc.queryForObject("SELECT COUNT(*) FROM awards", Integer.class);
        Integer pendingTotal = jdbc.queryForObject(
                "SELECT COUNT(*) FROM pending_achievements WHERE status='pending'", Integer.class);
        Integer usersTotal = jdbc.queryForObject("SELECT COUNT(*) FROM users", Integer.class);
        Integer competitionsTotal = jdbc.queryForObject("SELECT COUNT(*) FROM competitions", Integer.class);
        // 月度趋势(v1 语义:strftime('%Y-%m') → PG date_trunc),近 6 个月入库量
        List<Map<String, Object>> trend = jdbc.queryForList("""
                SELECT to_char(date_trunc('month', created_at), 'YYYY-MM') AS month, COUNT(*) AS count
                FROM awards
                WHERE created_at >= date_trunc('month', NOW()) - interval '5 months'
                GROUP BY 1 ORDER BY 1
                """);
        return ApiResponse.ok(Map.of(
                "awardsTotal", awardsTotal,
                "pendingTotal", pendingTotal,
                "usersTotal", usersTotal,
                "competitionsTotal", competitionsTotal,
                "trend", trend));
    }

    private void requireAdmin(Authentication auth) {
        for (GrantedAuthority a : auth.getAuthorities()) {
            if (a.getAuthority().equals("ROLE_ADMIN")) {
                return;
            }
        }
        throw new org.springframework.security.access.AccessDeniedException("需要 admin 角色");
    }
}
