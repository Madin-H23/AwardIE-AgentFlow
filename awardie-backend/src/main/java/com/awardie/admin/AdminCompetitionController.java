package com.awardie.admin;

import java.util.List;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;

/** 竞赛管理(#20,BR-1 口径源头):CRUD + 白名单/观察名单切换。 */
@RestController
@RequestMapping("/api/v2/admin/competitions")
public class AdminCompetitionController {

    public record CompetitionView(Integer id, String competitionName, boolean whiteList, boolean watchList,
            boolean isAutoAdded) {}

    public record CompetitionUpsert(Integer id, String competitionName, boolean whiteList, boolean watchList) {}

    private final org.springframework.jdbc.core.JdbcTemplate jdbc;

    public AdminCompetitionController(org.springframework.jdbc.core.JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping
    public ApiResponse<List<CompetitionView>> list(Authentication auth, @RequestParam(required = false) String q) {
        requireAdmin(auth);
        String sql = "SELECT id, competition_name, white_list, watch_list, is_auto_added FROM competitions"
                + (q == null || q.isBlank() ? " ORDER BY id DESC LIMIT 200" : " WHERE competition_name LIKE ? ORDER BY id DESC LIMIT 200");
        Object[] args = q == null || q.isBlank() ? new Object[0] : new Object[] {"%" + q + "%"};
        List<CompetitionView> rows = jdbc.query(sql, (rs, i) -> new CompetitionView(
                rs.getInt("id"), rs.getString("competition_name"),
                rs.getBoolean("white_list"), rs.getBoolean("watch_list"), rs.getBoolean("is_auto_added")), args);
        return ApiResponse.ok(rows);
    }

    @PostMapping
    public ApiResponse<CompetitionView> create(@RequestBody CompetitionUpsert req, Authentication auth) {
        requireAdmin(auth);
        if (req.competitionName() == null || req.competitionName().isBlank()) {
            return ApiResponse.error(4000, "竞赛名称不能为空");
        }
        Integer dup = jdbc.queryForObject(
                "SELECT COUNT(*) FROM competitions WHERE competition_name=?", Integer.class, req.competitionName());
        if (dup != null && dup > 0) {
            return ApiResponse.error(4009, "竞赛已存在");
        }
        jdbc.update("INSERT INTO competitions (competition_name, white_list, watch_list, is_auto_added) VALUES (?,?,?,FALSE)",
                req.competitionName(), req.whiteList(), req.watchList());
        Integer id = jdbc.queryForObject(
                "SELECT id FROM competitions WHERE competition_name=?", Integer.class, req.competitionName());
        return ApiResponse.ok(new CompetitionView(id, req.competitionName(), req.whiteList(), req.watchList(), false), "已创建");
    }

    @PutMapping("/{id}")
    public ApiResponse<CompetitionView> update(@PathVariable Integer id, @RequestBody CompetitionUpsert req,
            Authentication auth) {
        requireAdmin(auth);
        int n = jdbc.update("UPDATE competitions SET white_list=?, watch_list=? WHERE id=?",
                req.whiteList(), req.watchList(), id);
        if (n == 0) {
            return ApiResponse.error(4004, "竞赛不存在");
        }
        return ApiResponse.ok(new CompetitionView(id, req.competitionName(), req.whiteList(), req.watchList(), false),
                "已更新");
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
