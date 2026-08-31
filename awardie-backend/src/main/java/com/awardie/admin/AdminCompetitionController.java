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
import com.awardie.common.PageView;

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

    /** 列表(#26 真分页):page 1 基 + size + q 模糊;替换原 LIMIT 200 硬截。 */
    @GetMapping
    public ApiResponse<PageView<CompetitionView>> list(Authentication auth,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String q) {
        requireAdmin(auth);
        int p = Math.max(page, 1);
        int s = Math.min(Math.max(size, 1), 100);
        boolean hasQ = q != null && !q.isBlank();
        String where = hasQ ? " WHERE competition_name LIKE ?" : "";
        String countSql = "SELECT COUNT(*) FROM competitions" + where;
        String listSql = "SELECT id, competition_name, white_list, watch_list, is_auto_added FROM competitions"
                + where + " ORDER BY id DESC LIMIT ? OFFSET ?";
        Object[] countArgs = hasQ ? new Object[] {"%" + q + "%"} : new Object[0];
        Object[] listArgs = hasQ
                ? new Object[] {"%" + q + "%", s, (long) (p - 1) * s}
                : new Object[] {s, (long) (p - 1) * s};
        Integer total = jdbc.queryForObject(countSql, Integer.class, countArgs);
        long totalElements = total == null ? 0 : total;
        var rows = jdbc.query(listSql, (rs, i) -> new CompetitionView(
                rs.getInt("id"), rs.getString("competition_name"),
                rs.getBoolean("white_list"), rs.getBoolean("watch_list"), rs.getBoolean("is_auto_added")), listArgs);
        int totalPages = totalElements == 0 ? 0 : (int) ((totalElements + s - 1) / s);
        return ApiResponse.ok(new PageView<>(rows, totalElements, totalPages, p - 1, s));
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
