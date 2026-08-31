package com.awardie.admin;

import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;
import com.awardie.common.PageView;

/**
 * 管理面补充域(#29 侧边栏补全):日志/学生/教师/实验室/奖状模板——
 * 全部只读列表(编辑/删除挂后续票),JdbcTemplate 手写分页与 #26 同口径。
 */
@RestController
@RequestMapping("/api/v2/admin")
public class AdminConsoleController {

    private final JdbcTemplate jdbc;

    public AdminConsoleController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 日志查看(对照 v1 日志管理 Tab1):source=audit 审核留痕 | system 系统事件;level/keyword/日期可选。 */
    @GetMapping("/logs")
    public ApiResponse<PageView<Map<String, Object>>> logs(Authentication auth,
            @RequestParam(defaultValue = "audit") String source,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String level,
            @RequestParam(required = false) String keyword) {
        requireAdmin(auth);
        int p = Math.max(page, 1);
        int s = Math.min(Math.max(size, 1), 100);
        String kw = keyword == null || keyword.isBlank() ? null : "%" + keyword.trim() + "%";
        boolean audit = !"system".equals(source);

        String from = audit
                ? " FROM achievement_audit_log"
                : " FROM system_event_log";
        String where = audit
                ? (kw != null ? " WHERE (operator_name LIKE ? OR CAST(achievement_id AS TEXT) LIKE ? OR trace_id LIKE ?)" : "")
                : ((level != null && !level.isBlank()) && kw != null
                        ? " WHERE event_level = ? AND (event_message LIKE ? OR trace_id LIKE ?)"
                        : (level != null && !level.isBlank()
                                ? " WHERE event_level = ?"
                                : (kw != null ? " WHERE event_message LIKE ? OR trace_id LIKE ?" : "")));
        java.util.List<Object> args = new java.util.ArrayList<>();
        if (audit) {
            if (kw != null) {
                args.add(kw);
                args.add(kw);
                args.add(kw);
            }
        } else {
            if (level != null && !level.isBlank()) {
                args.add(level.trim());
            }
            if (kw != null) {
                args.add(kw);
                args.add(kw);
            }
        }

        Integer total = jdbc.queryForObject("SELECT COUNT(*)" + from + where, Integer.class, args.toArray());
        String sql = (audit
                ? "SELECT id, achievement_id, achievement_kind, action_type, operator_code, operator_name, "
                        + "operator_role, trace_id, remark, created_at"
                : "SELECT id, event_category, event_level, event_message, trace_id, operator_code, "
                        + "source_module, created_at")
                + from + where + " ORDER BY id DESC LIMIT ? OFFSET ?";
        args.add(s);
        args.add((long) (p - 1) * s);
        var rows = jdbc.queryForList(sql, args.toArray());
        int totalPages = total == null || total == 0 ? 0 : (total + s - 1) / s;
        return ApiResponse.ok(new PageView<>(rows, total == null ? 0 : total, totalPages, p - 1, s));
    }

    /** 学生管理(对照 v1 students/list):学号/姓名/专业/年级/电话/激活,search 命中姓名或学号。 */
    @GetMapping("/students")
    public ApiResponse<PageView<Map<String, Object>>> students(Authentication auth,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String search) {
        return listUsers(auth, "student", page, size, search);
    }

    /** 教师管理(对照 v1 teachers/list):工号/姓名/部门/职称/电话。 */
    @GetMapping("/teachers")
    public ApiResponse<PageView<Map<String, Object>>> teachers(Authentication auth,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String search) {
        return listUsers(auth, "teacher", page, size, search);
    }

    private ApiResponse<PageView<Map<String, Object>>> listUsers(Authentication auth, String role,
            int page, int size, String search) {
        requireAdmin(auth);
        int p = Math.max(page, 1);
        int s = Math.min(Math.max(size, 1), 100);
        boolean hasSearch = search != null && !search.isBlank();
        String where = " WHERE role='" + role + "'"
                + (hasSearch ? " AND (name LIKE ? OR login_code LIKE ?)" : "");
        String countSql = "SELECT COUNT(*) FROM users" + where;
        String listSql = "SELECT id, login_code, name, major, grade, department, title, phone, "
                + "user_activated, created_at FROM users" + where + " ORDER BY id LIMIT ? OFFSET ?";
        Object[] countArgs = hasSearch ? new Object[] {"%" + search + "%", "%" + search + "%"} : new Object[0];
        java.util.List<Object> listArgs = new java.util.ArrayList<>();
        if (hasSearch) {
            listArgs.add("%" + search + "%");
            listArgs.add("%" + search + "%");
        }
        listArgs.add(s);
        listArgs.add((long) (p - 1) * s);
        Integer total = jdbc.queryForObject(countSql, Integer.class, countArgs);
        var rows = jdbc.queryForList(listSql, listArgs.toArray());
        int totalPages = total == null || total == 0 ? 0 : (total + s - 1) / s;
        return ApiResponse.ok(new PageView<>(rows, total == null ? 0 : total, totalPages, p - 1, s));
    }

    /** 实验室管理(对照 v1 laboratories/list 卡片网格):名称/简介/创建时间。 */
    @GetMapping("/laboratories")
    public ApiResponse<PageView<Map<String, Object>>> laboratories(Authentication auth,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "12") int size) {
        requireAdmin(auth);
        int p = Math.max(page, 1);
        int s = Math.min(Math.max(size, 1), 60);
        Integer total = jdbc.queryForObject("SELECT COUNT(*) FROM laboratories", Integer.class);
        var rows = jdbc.queryForList(
                "SELECT id, name, description, created_at FROM laboratories ORDER BY id LIMIT ? OFFSET ?",
                s, (long) (p - 1) * s);
        int totalPages = total == null || total == 0 ? 0 : (total + s - 1) / s;
        return ApiResponse.ok(new PageView<>(rows, total == null ? 0 : total, totalPages, p - 1, s));
    }

    /** 奖状模板管理(对照 v1 templates/main 列表页):类型/语言/长度区间/关联竞赛。 */
    @GetMapping("/templates")
    public ApiResponse<PageView<Map<String, Object>>> templates(Authentication auth,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) Integer competitionId) {
        requireAdmin(auth);
        int p = Math.max(page, 1);
        int s = Math.min(Math.max(size, 1), 100);
        String where = competitionId != null ? " WHERE t.competition_id = ?" : "";
        Object[] countArgs = competitionId != null ? new Object[] {competitionId} : new Object[0];
        Integer total = jdbc.queryForObject(
                "SELECT COUNT(*) FROM templates t" + where, Integer.class, countArgs);
        String sql = "SELECT t.id, t.template_type, t.language, t.min_length, t.max_length, "
                + "t.competition_id, COALESCE(c.competition_name, '-') AS competition_name "
                + "FROM templates t LEFT JOIN competitions c ON t.competition_id = c.id"
                + where + " ORDER BY t.id LIMIT ? OFFSET ?";
        java.util.List<Object> listArgs = new java.util.ArrayList<>();
        if (competitionId != null) {
            listArgs.add(competitionId);
        }
        listArgs.add(s);
        listArgs.add((long) (p - 1) * s);
        var rows = jdbc.queryForList(sql, listArgs.toArray());
        int totalPages = total == null || total == 0 ? 0 : (total + s - 1) / s;
        return ApiResponse.ok(new PageView<>(rows, total == null ? 0 : total, totalPages, p - 1, s));
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
