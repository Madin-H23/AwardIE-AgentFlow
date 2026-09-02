package com.awardie.admin;

import java.util.List;
import java.util.Map;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestBody;
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
    private final org.springframework.security.crypto.password.PasswordEncoder encoder;

    public AdminConsoleController(JdbcTemplate jdbc,
            org.springframework.security.crypto.password.PasswordEncoder encoder) {
        this.jdbc = jdbc;
        this.encoder = encoder;
    }

    /** 日志查看(对照 v1 日志管理 Tab1):source=audit 审核留痕 | system 系统事件;level/keyword/日期区间可选。 */
    @GetMapping("/logs")
    public ApiResponse<PageView<Map<String, Object>>> logs(Authentication auth,
            @RequestParam(defaultValue = "audit") String source,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String level,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String dateFrom,
            @RequestParam(required = false) String dateTo) {
        requireAdmin(auth);
        int p = Math.max(page, 1);
        int s = Math.min(Math.max(size, 1), 100);
        String kw = keyword == null || keyword.isBlank() ? null : "%" + keyword.trim() + "%";
        boolean audit = !"system".equals(source);

        // 日期区间(yyyy-MM-dd,上海墙上时间;对照 v1 start_date/end_date)
        java.time.ZoneId zone = java.time.ZoneId.of("Asia/Shanghai");
        java.time.Instant from = parseDay(dateFrom, zone, false);
        java.time.Instant to = parseDay(dateTo, zone, true);

        String timeCol = audit ? "created_at" : "created_at";
        StringBuilder where = new StringBuilder();
        List<Object> countArgs = new java.util.ArrayList<>();
        if (audit) {
            if (kw != null) {
                where.append(" AND (operator_name LIKE ? OR CAST(achievement_id AS TEXT) LIKE ? OR trace_id LIKE ?)");
                countArgs.add(kw);
                countArgs.add(kw);
                countArgs.add(kw);
            }
        } else {
            if (level != null && !level.isBlank()) {
                where.append(" AND event_level = ?");
                countArgs.add(level.trim());
            }
            if (kw != null) {
                where.append(" AND (event_message LIKE ? OR trace_id LIKE ?)");
                countArgs.add(kw);
                countArgs.add(kw);
            }
        }
        if (from != null) {
            where.append(" AND ").append(timeCol).append(" >= ?");
            countArgs.add(java.sql.Timestamp.from(from));
        }
        if (to != null) {
            where.append(" AND ").append(timeCol).append(" < ?");
            countArgs.add(java.sql.Timestamp.from(to));
        }

        Integer total = jdbc.queryForObject(
                "SELECT COUNT(*) FROM " + (audit ? "achievement_audit_log" : "system_event_log")
                        + " WHERE 1=1" + where,
                Integer.class, countArgs.toArray());
        String cols = audit
                ? "id, achievement_id, achievement_kind, action_type, operator_code, operator_name, operator_role, trace_id, remark, created_at"
                : "id, event_category, event_level, event_message, trace_id, operator_code, source_module, created_at";
        List<Object> listArgs = new java.util.ArrayList<>(countArgs);
        listArgs.add(s);
        listArgs.add((long) (p - 1) * s);
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT " + cols + " FROM " + (audit ? "achievement_audit_log" : "system_event_log")
                        + " WHERE 1=1" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
                listArgs.toArray());
        int totalPages = total == null || total == 0 ? 0 : (total + s - 1) / s;
        return ApiResponse.ok(new PageView<>(rows, total == null ? 0 : total, totalPages, p - 1, s));
    }

    private java.time.Instant parseDay(String raw, java.time.ZoneId zone, boolean endOfDay) {
        if (raw == null || raw.isBlank()) {
            return null;
        }
        try {
            var d = java.time.LocalDate.parse(raw.trim());
            return (endOfDay ? d.plusDays(1) : d).atStartOfDay(zone).toInstant();
        } catch (java.time.format.DateTimeParseException e) {
            throw new IllegalArgumentException("日期格式须为 yyyy-MM-dd");
        }
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

    // ---------- CRUD(#38,对照 v1 students/teachers/laboratories 编辑页) ----------

    public record UserUpsert(String loginCode, String name, String major, String grade, String department,
            String title, String phone, String skills) {}

    /** 创建学生/教师:默认口令 P@ss301(恒产 werkzeug scrypt 格式,ADR-0002),首登强制改密。 */
    @PostMapping("/users/{role}")
    public ApiResponse<Map<String, Object>> createUser(@PathVariable String role,
            @RequestBody UserUpsert req, Authentication auth) {
        requireAdmin(auth);
        if (!role.equals("student") && !role.equals("teacher")) {
            throw new IllegalArgumentException("role 仅允许 student/teacher");
        }
        if (req.loginCode() == null || req.loginCode().isBlank()
                || req.name() == null || req.name().isBlank()) {
            return ApiResponse.error(4000, "学号/工号与姓名必填");
        }
        Integer dup = jdbc.queryForObject(
                "SELECT COUNT(*) FROM users WHERE login_code=?", Integer.class, req.loginCode().trim());
        if (dup != null && dup > 0) {
            return ApiResponse.error(4009, "账号已存在");
        }
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change,
                                   major, grade, department, title, phone, skills)
                VALUES (?, ?, ?, ?, TRUE, TRUE, ?, ?, ?, ?, ?, ?)
                """, req.loginCode().trim(), req.name().trim(), role, encoder.encode("P@ss301"),
                req.major(), req.grade(), req.department(), req.title(), req.phone(), req.skills());
        Integer id = jdbc.queryForObject(
                "SELECT id FROM users WHERE login_code=?", Integer.class, req.loginCode().trim());
        return ApiResponse.ok(Map.of("id", id == null ? 0 : id), "已创建,默认口令 P@ss301(首登须修改)");
    }

    /** 编辑学生/教师(不可改 login_code 与角色)。 */
    @PutMapping("/users/{role}/{id}")
    public ApiResponse<Integer> updateUser(@PathVariable String role, @PathVariable Integer id,
            @RequestBody UserUpsert req, Authentication auth) {
        requireAdmin(auth);
        int n = jdbc.update("""
                UPDATE users SET name=?, major=?, grade=?, department=?, title=?, phone=?, skills=?,
                                 updated_at=NOW()
                WHERE id=? AND role=?
                """, req.name(), req.major(), req.grade(), req.department(), req.title(),
                req.phone(), req.skills(), id, role);
        if (n == 0) {
            return ApiResponse.error(4004, "记录不存在");
        }
        return ApiResponse.ok(n, "已更新");
    }

    /** 删除学生/教师:存在成果/指导等关联时拒绝(4009)。 */
    @org.springframework.web.bind.annotation.DeleteMapping("/users/{role}/{id}")
    public ApiResponse<Integer> deleteUser(@PathVariable String role, @PathVariable Integer id,
            Authentication auth) {
        requireAdmin(auth);
        try {
            int n = jdbc.update("DELETE FROM users WHERE id=? AND role=?", id, role);
            if (n == 0) {
                return ApiResponse.error(4004, "记录不存在");
            }
            return ApiResponse.ok(n, "已删除");
        } catch (org.springframework.dao.DataIntegrityViolationException e) {
            return ApiResponse.error(4009, "存在关联成果数据,无法删除;可改为禁用");
        }
    }

    public record LabUpsert(String name, String description) {}

    @PostMapping("/laboratories")
    public ApiResponse<Map<String, Object>> createLab(@RequestBody LabUpsert req, Authentication auth) {
        requireAdmin(auth);
        if (req.name() == null || req.name().isBlank()) {
            return ApiResponse.error(4000, "实验室名称必填");
        }
        jdbc.update("INSERT INTO laboratories (name, description) VALUES (?, ?)",
                req.name().trim(), req.description());
        Integer id = jdbc.queryForObject(
                "SELECT id FROM laboratories WHERE name=?", Integer.class, req.name().trim());
        return ApiResponse.ok(Map.of("id", id == null ? 0 : id), "已创建");
    }

    @PutMapping("/laboratories/{id}")
    public ApiResponse<Integer> updateLab(@PathVariable Integer id, @RequestBody LabUpsert req,
            Authentication auth) {
        requireAdmin(auth);
        if (req.name() == null || req.name().isBlank()) {
            return ApiResponse.error(4000, "实验室名称必填");
        }
        int n = jdbc.update("UPDATE laboratories SET name=?, description=?, updated_at=NOW() WHERE id=?",
                req.name(), req.description(), id);
        if (n == 0) {
            return ApiResponse.error(4004, "实验室不存在");
        }
        return ApiResponse.ok(n, "已更新");
    }

    /** 实验室详情聚合(Fix-G 对照 v1 laboratories/detail):信息+统计+教师+学生+下载文件。 */
    @GetMapping("/laboratories/{id}/detail")
    public ApiResponse<Map<String, Object>> labDetail(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        List<Map<String, Object>> lab = jdbc.queryForList(
            "SELECT id, name, description, cover_image AS coverImage, created_at AS createdAt FROM laboratories WHERE id = ?",
            id);
        if (lab.isEmpty()) {
            return ApiResponse.error(4004, "实验室不存在");
        }
        Map<String, Object> out = new java.util.HashMap<>(lab.get(0));
        out.put("instructors", jdbc.queryForList(
            "SELECT u.id, u.name, COALESCE(u.title, '-') AS title FROM laboratory_instructors li "
                + "INNER JOIN users u ON li.teacher_id = u.id WHERE li.laboratory_id = ? ORDER BY u.id", id));
        out.put("students", jdbc.queryForList(
            "SELECT u.id, u.name, COALESCE(u.grade, '-') AS grade FROM laboratory_students ls "
                + "INNER JOIN users u ON ls.student_id = u.id WHERE ls.laboratory_id = ? ORDER BY u.id", id));
        out.put("downloadCount", jdbc.queryForObject(
            "SELECT COUNT(*) FROM laboratory_downloads WHERE laboratory_id = ?", Integer.class, id));
        out.put("awardCount", jdbc.queryForObject(
            "SELECT COUNT(*) FROM awards WHERE laboratory_id = ?", Integer.class, id));
        return ApiResponse.ok(out);
    }

    public record LabUpdate(String name, String description) {}

    /** 下载专区(Fix-G,对照 v1 downloads.html):该实验室可下载文件列表。 */
    @GetMapping("/laboratories/{id}/downloads")
    public ApiResponse<List<Map<String, Object>>> labDownloads(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        return ApiResponse.ok(jdbc.queryForList(
            "SELECT id, file_title AS fileTitle, file_name AS fileName, file_size, "
                + "submitter_type AS submitterType, created_at AS createdAt "
                + "FROM laboratory_downloads WHERE laboratory_id = ? ORDER BY display_order, id DESC", id));
    }

    @org.springframework.web.bind.annotation.DeleteMapping("/laboratories/{id}")
    public ApiResponse<Integer> deleteLab(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        try {
            int n = jdbc.update("DELETE FROM laboratories WHERE id=?", id);
            if (n == 0) {
                return ApiResponse.error(4004, "实验室不存在");
            }
            return ApiResponse.ok(n, "已删除");
        } catch (org.springframework.dao.DataIntegrityViolationException e) {
            return ApiResponse.error(4009, "存在关联数据,无法删除");
        }
    }    @GetMapping("/laboratories")
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
