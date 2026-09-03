package com.awardie.admin;

import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;

/** 数据分析聚合(#30,对照 v1 data_analysis):竞赛信息/贡献度/热力图/明细 records——全部只读。 */
@RestController
@RequestMapping("/api/v2/admin/analysis")
public class AdminAnalysisController {

    private final JdbcTemplate jdbc;

    public AdminAnalysisController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** Tab1 竞赛信息:有奖状的竞赛+获奖数(时间范围以 competition_time 原串呈现,偏差见对照记录)。 */
    @GetMapping("/competitions")
    public ApiResponse<List<Map<String, Object>>> competitions(Authentication auth) {
        requireAdmin(auth);
        return ApiResponse.ok(jdbc.queryForList("""
                SELECT c.id, c.competition_name AS name, c.competition_time AS "timeRaw",
                       COALESCE(c.official_website, '-') AS website, c.white_list AS "whiteList",
                       COUNT(a.id) AS "awardCount"
                FROM competitions c
                INNER JOIN awards a ON c.id = a.competition_id
                GROUP BY c.id ORDER BY c.competition_name
                """));
    }

    /** Tab2 竞赛贡献度:years 多选(IN)/whiteListOnly/includeTeacher(默认排除 granted_role='教师')。 */
    @GetMapping("/contribution")
    public ApiResponse<List<Map<String, Object>>> contribution(Authentication auth,
            @RequestParam(required = false) List<Integer> years,
            @RequestParam(defaultValue = "false") boolean whiteListOnly,
            @RequestParam(defaultValue = "false") boolean includeTeacher) {
        requireAdmin(auth);
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        List<Object> args = new java.util.ArrayList<>();
        if (years != null && !years.isEmpty()) {
            where.append(" AND a.year IN (");
            for (int i = 0; i < years.size(); i++) {
                where.append(i == 0 ? "?" : ",?");
                args.add(years.get(i));
            }
            where.append(")");
        }
        if (whiteListOnly) {
            where.append(" AND c.white_list = TRUE");
        }
        if (!includeTeacher) {
            where.append(" AND (a.granted_role IS NULL OR a.granted_role <> '教师')");
        }
        return ApiResponse.ok(jdbc.queryForList(
                "SELECT c.id AS \"competitionId\", c.competition_name AS name, COUNT(a.id) AS \"awardCount\""
                        + " FROM competitions c INNER JOIN awards a ON c.id = a.competition_id" + where
                        + " GROUP BY c.id, c.competition_name ORDER BY COUNT(a.id) DESC",
                args.toArray()));
    }

    /** Fix-P 实验室维度贡献度(对照 v1 /laboratory/{id}/data-analysis/competitions):按实验室过滤。 */
    @GetMapping("/laboratory/{labId}/contribution")
    public ApiResponse<List<Map<String, Object>>> labContribution(@PathVariable Integer labId,
            Authentication auth, @RequestParam(required = false) List<Integer> years,
            @RequestParam(defaultValue = "false") boolean includeTeacher) {
        requireAdmin(auth);
        Integer exist = jdbc.queryForObject("SELECT COUNT(*) FROM laboratories WHERE id = ?", Integer.class, labId);
        if (exist == null || exist == 0) {
            return ApiResponse.error(4004, "实验室不存在");
        }
        StringBuilder where = new StringBuilder(" WHERE a.laboratory_id = ?");
        List<Object> args = new java.util.ArrayList<>();
        args.add(labId);
        if (years != null && !years.isEmpty()) {
            where.append(" AND a.year IN (");
            for (int i = 0; i < years.size(); i++) {
                where.append(i == 0 ? "?" : ",?");
                args.add(years.get(i));
            }
            where.append(")");
        }
        if (!includeTeacher) {
            where.append(" AND (a.granted_role IS NULL OR a.granted_role <> '教师')");
        }
        return ApiResponse.ok(jdbc.queryForList(
                "SELECT c.id AS \"competitionId\", c.competition_name AS name, COUNT(a.id) AS \"awardCount\""
                        + " FROM competitions c INNER JOIN awards a ON c.id = a.competition_id" + where
                        + " GROUP BY c.id, c.competition_name ORDER BY COUNT(a.id) DESC",
                args.toArray()));
    }

    /** Tab2 热力图:竞赛×实验室 获奖数矩阵。 */
    @GetMapping("/heatmap")
    public ApiResponse<Map<String, Object>> heatmap(Authentication auth,
            @RequestParam(required = false) List<Integer> years,
            @RequestParam(defaultValue = "false") boolean includeTeacher) {
        requireAdmin(auth);
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        List<Object> args = new java.util.ArrayList<>();
        if (years != null && !years.isEmpty()) {
            where.append(" AND a.year IN (");
            for (int i = 0; i < years.size(); i++) {
                where.append(i == 0 ? "?" : ",?");
                args.add(years.get(i));
            }
            where.append(")");
        }
        if (!includeTeacher) {
            where.append(" AND (a.granted_role IS NULL OR a.granted_role <> '教师')");
        }
        List<Map<String, Object>> cells = jdbc.queryForList(
                "SELECT c.competition_name AS competition, COALESCE(l.name, '未分配') AS lab, COUNT(*) AS count"
                        + " FROM awards a"
                        + " INNER JOIN competitions c ON a.competition_id = c.id"
                        + " LEFT JOIN laboratories l ON a.laboratory_id = l.id" + where
                        + " GROUP BY 1, 2 ORDER BY 1, 2",
                args.toArray());
        return ApiResponse.ok(Map.of("cells", cells));
    }

    /** Tab3 动态图明细(前端聚合):year/lab/competition/level/granted_role。 */
    @GetMapping("/records")
    public ApiResponse<List<Map<String, Object>>> records(Authentication auth) {
        requireAdmin(auth);
        return ApiResponse.ok(jdbc.queryForList("""
                SELECT a.year, COALESCE(l.name, '未分配') AS lab,
                       c.competition_name AS competition, a.competition_level AS level,
                       a.granted_role
                FROM awards a
                LEFT JOIN laboratories l ON a.laboratory_id = l.id
                LEFT JOIN competitions c ON a.competition_id = c.id
                WHERE a.year IS NOT NULL
                """));
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
