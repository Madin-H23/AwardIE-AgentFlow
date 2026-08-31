package com.awardie.admin;

import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
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

    /**
     * 总览聚合(#28,对照 v1 /admin/api/dashboard/overview):资产条/汇总卡/Top表/趋势卡一次取数。
     * 口径:待审=status='pending'(v1 'submit' 的 v2 同位);months=趋势窗口月数(空=全部);
     * gran=month|year 趋势粒度(v1 死选项补全为活功能)。
     */
    @GetMapping("/overview")
    public ApiResponse<Map<String, Object>> overview(Authentication auth,
            @RequestParam(required = false) Integer months,
            @RequestParam(defaultValue = "month") String gran) {
        requireAdmin(auth);
        if (!gran.equals("month") && !gran.equals("year")) {
            throw new IllegalArgumentException("gran 仅允许 month/year");
        }
        Integer totalAwards = jdbc.queryForObject("SELECT COUNT(*) FROM awards", Integer.class);
        Integer awardMgmt = jdbc.queryForObject(
                "SELECT COUNT(*) FROM awards WHERE (granted_role IS NULL OR granted_role <> '教师')", Integer.class);
        Integer awardTeacher = jdbc.queryForObject(
                "SELECT COUNT(*) FROM awards WHERE granted_role = '教师'", Integer.class);
        Integer pendingSubmit = jdbc.queryForObject(
                "SELECT COUNT(*) FROM pending_achievements WHERE status='pending'", Integer.class);
        Integer whitelist = jdbc.queryForObject(
                "SELECT COUNT(*) FROM competitions WHERE white_list=TRUE", Integer.class);
        Integer competitions = jdbc.queryForObject("SELECT COUNT(*) FROM competitions", Integer.class);
        Map<String, Object> summary = new java.util.HashMap<>();
        summary.put("totalAwards", totalAwards);
        summary.put("awardMgmt", awardMgmt);
        summary.put("awardTeacher", awardTeacher);
        summary.put("pendingSubmit", pendingSubmit);
        summary.put("whitelist", whitelist);
        summary.put("competitions", competitions);

        Map<String, Object> category = Map.of(
                "award", totalAwards,
                "patent", jdbc.queryForObject("SELECT COUNT(*) FROM patents", Integer.class),
                "software", jdbc.queryForObject("SELECT COUNT(*) FROM software_copyrights", Integer.class),
                "innovation", jdbc.queryForObject("SELECT COUNT(*) FROM innovation_projects", Integer.class),
                "other", jdbc.queryForObject("SELECT COUNT(*) FROM other_files", Integer.class));

        // 趋势:gran=month → YYYY-MM;gran=year → YYYY;months 窗口含当期
        String trunc = gran.equals("month") ? "month" : "year";
        String periodExpr = gran.equals("month")
                ? "to_char(date_trunc('month', created_at), 'YYYY-MM')"
                : "to_char(date_trunc('year', created_at), 'YYYY')";
        String window = (months != null && months > 0)
                ? " AND date_trunc('" + trunc + "', created_at) >= date_trunc('" + trunc + "', NOW()) - ("
                        + (months - 1) + ") * interval '1 " + trunc + "'"
                : "";
        String trendSql = "SELECT " + periodExpr + " AS period, COUNT(*) AS count FROM awards"
                + " WHERE created_at IS NOT NULL" + window + " GROUP BY 1 ORDER BY 1";
        List<Map<String, Object>> trend = jdbc.queryForList(trendSql);

        // 环比:本月 vs 上月奖状新增
        Integer thisN = jdbc.queryForObject(
                "SELECT COUNT(*) FROM awards WHERE date_trunc('month', created_at)=date_trunc('month', NOW())",
                Integer.class);
        Integer lastN = jdbc.queryForObject(
                "SELECT COUNT(*) FROM awards WHERE date_trunc('month', created_at)=date_trunc('month', NOW()) - interval '1 month'",
                Integer.class);
        Map<String, Object> compare = new java.util.HashMap<>();
        compare.put("this", thisN);
        compare.put("last", lastN);
        compare.put("deltaPct", lastN != null && lastN > 0
                ? Math.round((thisN - lastN) * 1000.0 / lastN) / 10.0 : null);

        // 竞赛战果 Top 12(未关联兜底)
        List<Map<String, Object>> byComp = jdbc.queryForList("""
                SELECT COALESCE(c.competition_name, '未关联') AS name, COUNT(*) AS total
                FROM awards a LEFT JOIN competitions c ON a.competition_id = c.id
                GROUP BY COALESCE(c.competition_name, '未关联') ORDER BY total DESC LIMIT 12
                """);

        return ApiResponse.ok(Map.of(
                "summary", summary,
                "category", category,
                "trend", trend,
                "compare", compare,
                "byCompetition", byComp));
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
