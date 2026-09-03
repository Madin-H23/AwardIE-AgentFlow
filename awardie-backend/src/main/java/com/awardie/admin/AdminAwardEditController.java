package com.awardie.admin;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.ArrayList;

import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;

/** Fix-R:奖状详情/编辑页端点(对照 v1 admin/awards/edit.html + admin_awards.award_edit)。 */
@RestController
@RequestMapping("/api/v2/admin/awards")
public class AdminAwardEditController {

    private final JdbcTemplate jdbc;
    private final com.awardie.submission.FileStorageService fileStorage;

    public AdminAwardEditController(JdbcTemplate jdbc, com.awardie.submission.FileStorageService fileStorage) {
        this.jdbc = jdbc;
        this.fileStorage = fileStorage;
    }

    /** 详情聚合:主字段+四组关联+姓名匹配状态+下拉四数据+默认实验室推断。 */
    @GetMapping("/{id}/edit-detail")
    public ApiResponse<Map<String, Object>> editDetail(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT a.id, a.competition_id AS "competitionId", c.competition_name AS "competitionName",
                       a.competition_level AS "competitionLevel", a.award_level AS "awardLevel",
                       a.year, a.track, a.certificate_id AS "certificateId",
                       a.project_title AS "projectTitle", a.date, a.province, a.issuer,
                       a.laboratory_id AS "laboratoryId", a.granted_role AS "grantedRole",
                       a.winner_name AS "winnerName", a.supervisor_name AS "supervisorName",
                       a.image_hash AS "imageHash", a.certificate_path AS "certificatePath", a.is_abnormal AS "isAbnormal",
                       a.ocr_result AS "ocrResult",
                       a.validation_result::TEXT AS "validationResult"
                FROM awards a LEFT JOIN competitions c ON a.competition_id = c.id
                WHERE a.id = ?
                """, id);
        if (rows.isEmpty()) {
            return ApiResponse.error(4004, "奖状不存在");
        }
        Map<String, Object> out = new LinkedHashMap<>(rows.get(0));
        out.put("studentWinners", jdbc.queryForList("""
                SELECT u.id, u.name, COALESCE(u.grade, '-') AS grade
                FROM award_student_winners w INNER JOIN users u ON w.student_id = u.id
                WHERE w.award_id = ? ORDER BY u.id
                """, id));
        out.put("teacherWinners", jdbc.queryForList("""
                SELECT u.id, u.name, COALESCE(u.title, '-') AS title, u.login_code AS "loginCode"
                FROM award_teacher_winners w INNER JOIN users u ON w.teacher_id = u.id
                WHERE w.award_id = ? ORDER BY u.id
                """, id));
        out.put("supervisors", jdbc.queryForList("""
                SELECT u.id, u.name, COALESCE(u.title, '-') AS title
                FROM award_supervisors s INNER JOIN users u ON s.teacher_id = u.id
                WHERE s.award_id = ? ORDER BY u.id
                """, id));
        out.put("relatedStudents", jdbc.queryForList("""
                SELECT u.id, u.name, COALESCE(u.grade, '-') AS grade
                FROM award_related_students r INNER JOIN users u ON r.student_id = u.id
                WHERE r.award_id = ? ORDER BY u.id
                """, id));
        boolean teacherRole = out.get("grantedRole") != null && String.valueOf(out.get("grantedRole")).contains("教师");
        out.put("winnerStatus", resolveNameStatus((String) out.get("winnerName"), teacherRole ? "teacher" : "student"));
        out.put("supervisorStatus", resolveNameStatus((String) out.get("supervisorName"), "teacher"));
        out.put("competitions", jdbc.queryForList(
                "SELECT id, competition_name AS \"name\" FROM competitions ORDER BY id"));
        out.put("teachers", jdbc.queryForList(
                "SELECT id, name, COALESCE(title, '-') AS title, login_code AS \"loginCode\" "
                    + "FROM users WHERE role = 'teacher' ORDER BY id"));
        out.put("students", jdbc.queryForList(
                "SELECT id, name, COALESCE(grade, '-') AS grade, COALESCE(major, '-') AS major "
                    + "FROM users WHERE role = 'student' ORDER BY id"));
        out.put("laboratories", jdbc.queryForList("SELECT id, name FROM laboratories ORDER BY id"));
        out.put("defaultLaboratoryId", defaultLaboratoryId(out));
        return ApiResponse.ok(out);
    }

    /** 全量编辑保存:主字段 + 四关联表重写(v1 award_edit POST 同构)。 */
    public record AwardEditUpdate(Integer competitionId, String competitionLevel, String awardLevel, Integer year,
            String track, String certificateId, String projectTitle, String date, String province, String issuer,
            Integer laboratoryId, String grantedRole, String studentWinnerNames,
            List<Integer> supervisorIds, List<Integer> teacherWinnerIds, List<Integer> studentWinnerIds,
            List<Integer> relatedStudentIds) {}

    /** 证书图回显:inline 显示语义(批 2 证书链;编辑页 <img> 直用)。 */
    @GetMapping("/{id}/certificate")
    public ResponseEntity<byte[]> certificate(@PathVariable Integer id, Authentication auth) throws Exception {
        requireAdmin(auth);
        List<String> rows = jdbc.queryForList(
                "SELECT certificate_path FROM awards WHERE id = ?", String.class, id);
        if (rows.isEmpty() || rows.get(0) == null) {
            return ResponseEntity.notFound().build();
        }
        byte[] bytes;
        try {
            bytes = fileStorage.readAll(rows.get(0));
        } catch (java.nio.file.NoSuchFileException | IllegalArgumentException e) {
            // 存量死引用(文件失存/越界路径):回 404 走"可上传补齐"分支,不落 5000
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok()
                .header("Content-Type", fileStorage.contentTypeOf(rows.get(0)))
                .body(bytes);
    }

    /** 证书图上传/替换:三校验+目录存储(批 2 证书链,清偿 Fix-R hash 占位)。 */
    @PostMapping("/{id}/certificate")
    public ApiResponse<Map<String, Object>> uploadCertificate(@PathVariable Integer id,
            @RequestParam(value = "file", required = false) MultipartFile file,
            Authentication auth) throws Exception {
        requireAdmin(auth);
        if (file == null || file.isEmpty()) {
            return ApiResponse.error(4000, "请上传证书图片");
        }
        byte[] bytes = file.getBytes();
        fileStorage.assertAllowed(file.getOriginalFilename(), bytes);
        var stored = fileStorage.store(file.getOriginalFilename(), bytes);
        int n = jdbc.update("UPDATE awards SET certificate_path = ? WHERE id = ?",
                stored.relativePath(), id);
        if (n == 0) {
            return ApiResponse.error(4004, "award 不存在");
        }
        return ApiResponse.ok(Map.of("path", stored.relativePath(), "sha256", stored.sha256()));
    }

    @PutMapping("/{id}")
    @Transactional
    public ApiResponse<Integer> update(@PathVariable Integer id, @RequestBody AwardEditUpdate req,
            Authentication auth) {
        requireAdmin(auth);
        if (req.competitionId() == null) {
            return ApiResponse.error(4000, "竞赛必填");
        }
        Integer exist = jdbc.queryForObject("SELECT COUNT(*) FROM awards WHERE id = ?", Integer.class, id);
        if (exist == null || exist == 0) {
            return ApiResponse.error(4004, "奖状不存在");
        }
        String grantedRole = "teacher".equalsIgnoreCase(req.grantedRole()) ? "教师" : "学生";
        // 指导教师顺序敏感:supervisor_name 按提交顺序同步(v1 同语义)
        String supervisorName = joinNames(req.supervisorIds());
        jdbc.update("""
                UPDATE awards SET competition_id = ?, competition_level = ?, award_level = ?, year = ?,
                       track = ?, certificate_id = ?, project_title = ?, date = ?, province = ?, issuer = ?,
                       laboratory_id = ?, granted_role = ?, winner_name = ?, supervisor_name = ?, updated_at = NOW()
                WHERE id = ?
                """, req.competitionId(), req.competitionLevel(), req.awardLevel(), req.year(),
                req.track(), req.certificateId(), req.projectTitle(), req.date(), req.province(),
                req.issuer(), req.laboratoryId(), grantedRole,
                blankToNull(req.studentWinnerNames()), supervisorName, id);
        rewriteWinners(id, "award_student_winners", "student_id", req.studentWinnerIds());
        rewriteWinners(id, "award_teacher_winners", "teacher_id", req.teacherWinnerIds());
        rewriteWinners(id, "award_supervisors", "teacher_id", req.supervisorIds());
        rewriteWinners(id, "award_related_students", "student_id",
                "学生".equals(grantedRole) ? List.of() : req.relatedStudentIds());
        return ApiResponse.ok(1, "已更新");
    }

    /** 关联表重写:先删后插,去重保序(award_supervisors 有联合主键)。 */
    private void rewriteWinners(Integer awardId, String table, String column, List<Integer> ids) {
        jdbc.update("DELETE FROM " + table + " WHERE award_id = ?", awardId);
        if (ids == null || ids.isEmpty()) {
            return;
        }
        for (Integer rid : new LinkedHashSet<>(ids)) {
            if (rid != null) {
                jdbc.update("INSERT INTO " + table + " (award_id, " + column + ") VALUES (?, ?)", awardId, rid);
            }
        }
    }

    private String joinNames(List<Integer> ids) {
        if (ids == null || ids.isEmpty()) {
            return null;
        }
        List<String> names = new ArrayList<>();
        for (Integer rid : new LinkedHashSet<>(ids)) {
            if (rid == null) {
                continue;
            }
            List<String> one = jdbc.queryForList("SELECT name FROM users WHERE id = ?", String.class, rid);
            if (!one.isEmpty() && one.get(0) != null) {
                names.add(one.get(0));
            }
        }
        return names.isEmpty() ? null : String.join(", ", names);
    }

    /** winner_name/supervisor_name 姓名解析:去括号去重,逐名标注 matched/ambiguous/not_found。 */
    private List<Map<String, Object>> resolveNameStatus(String joined, String role) {
        List<Map<String, Object>> out = new ArrayList<>();
        if (joined == null || joined.isBlank()) {
            return out;
        }
        LinkedHashSet<String> seen = new LinkedHashSet<>();
        for (String seg : joined.split("[,，、;；]")) {
            String base = seg.trim();
            if (base.contains("(")) {
                base = base.substring(0, base.indexOf('(')).trim();
            }
            if (!base.isEmpty()) {
                seen.add(base);
            }
        }
        for (String name : seen) {
            List<Integer> ids = jdbc.queryForList(
                    "SELECT id FROM users WHERE role = ? AND name = ? ORDER BY id", Integer.class, role, name);
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("name", name);
            item.put("status", ids.isEmpty() ? "not_found" : ids.size() == 1 ? "matched" : "ambiguous");
            if (!ids.isEmpty()) {
                item.put("id", ids.get(0));
            }
            out.add(item);
        }
        return out;
    }

    /** 默认实验室推断(v1 同语义):已关联 > 第一指导教师所在实验室 > 无。 */
    private Integer defaultLaboratoryId(Map<String, Object> award) {
        Object labId = award.get("laboratoryId");
        if (labId instanceof Integer i) {
            return i;
        }
        Object supervisorName = award.get("supervisorName");
        if (supervisorName instanceof String s && !s.isBlank()) {
            String first = s.split("[,，、;；]")[0].trim();
            if (first.contains("(")) {
                first = first.substring(0, first.indexOf('(')).trim();
            }
            List<Integer> labs = jdbc.queryForList("""
                    SELECT li.laboratory_id FROM laboratory_instructors li
                    INNER JOIN users u ON li.teacher_id = u.id WHERE u.name = ? ORDER BY li.laboratory_id LIMIT 1
                    """, Integer.class, first);
            if (!labs.isEmpty()) {
                return labs.get(0);
            }
        }
        return null;
    }

    private String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s;
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
