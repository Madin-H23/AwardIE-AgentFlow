package com.awardie.admin;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;
import com.fasterxml.jackson.databind.ObjectMapper;

/** Fix-T:专利/软著/大创 编辑页端点(对照 v1 patents|software|innovation 的 edit+view,v1 view 字段为 edit 子集故并入)。 */
@RestController
@RequestMapping("/api/v2/admin")
public class AdminAchievementEditController {

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public AdminAchievementEditController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // ---------- patents ----------

    @GetMapping("/patents/{id}/edit-detail")
    public ApiResponse<Map<String, Object>> patentDetail(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT id, patent_name AS "patentName", patent_type AS "patentType",
                       application_number AS "applicationNumber", publication_number AS "publicationNumber",
                       inventor, application_date AS "applicationDate", patentee,
                       laboratory_id AS "laboratoryId", certificate_file AS "certificateFile",
                       submitter_type AS "submitterType", submitter_id AS "submitterId",
                       created_at AS "createdAt", updated_at AS "updatedAt"
                FROM patents WHERE id = ?
                """, id);
        return detailOut(rows, "专利不存在");
    }

    public record PatentUpdate(String patentName, String patentType, String applicationNumber,
            String publicationNumber, String inventor, String applicationDate, String patentee,
            Integer laboratoryId) {}

    @PutMapping("/patents/{id}")
    @Transactional
    public ApiResponse<Integer> patentUpdate(@PathVariable Integer id, @RequestBody PatentUpdate req,
            Authentication auth) {
        requireAdmin(auth);
        if (req.patentName() == null || req.patentName().isBlank()) {
            return ApiResponse.error(4000, "专利名称必填");
        }
        int n;
        try {
            n = jdbc.update("""
                UPDATE patents SET patent_name = ?, patent_type = ?, application_number = ?,
                       publication_number = ?, inventor = ?, application_date = ?, patentee = ?,
                       laboratory_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """, req.patentName(), req.patentType(), req.applicationNumber(), req.publicationNumber(),
                req.inventor(), req.applicationDate(), req.patentee(), req.laboratoryId(), id);
        } catch (org.springframework.dao.DataIntegrityViolationException e) {
            return ApiResponse.error(4009, "申请号已存在(唯一字段冲突)");
        }
        return updated(n);
    }

    // ---------- software ----------

    @GetMapping("/software/{id}/edit-detail")
    public ApiResponse<Map<String, Object>> softwareDetail(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT id, software_name AS "softwareName", software_version AS "softwareVersion",
                       registration_number AS "registrationNumber", certificate_no AS "certificateNo",
                       registration_date AS "registrationDate", copyright_owner AS "copyrightOwner",
                       laboratory_id AS "laboratoryId", certificate_file AS "certificateFile",
                       submitter_type AS "submitterType", submitter_id AS "submitterId",
                       submit_time AS "submitTime"
                FROM software_copyrights WHERE id = ?
                """, id);
        return detailOut(rows, "软著不存在");
    }

    public record SoftwareUpdate(String softwareName, String softwareVersion, String registrationNumber,
            String certificateNo, String registrationDate, String copyrightOwner, Integer laboratoryId) {}

    @PutMapping("/software/{id}")
    @Transactional
    public ApiResponse<Integer> softwareUpdate(@PathVariable Integer id, @RequestBody SoftwareUpdate req,
            Authentication auth) {
        requireAdmin(auth);
        if (req.softwareName() == null || req.softwareName().isBlank()) {
            return ApiResponse.error(4000, "软件名称必填");
        }
        int n;
        try {
            n = jdbc.update("""
                UPDATE software_copyrights SET software_name = ?, software_version = ?,
                       registration_number = ?, certificate_no = ?, registration_date = ?,
                       copyright_owner = ?, laboratory_id = ? WHERE id = ?
                """, req.softwareName(), req.softwareVersion(), req.registrationNumber(),
                req.certificateNo(), req.registrationDate(), req.copyrightOwner(), req.laboratoryId(), id);
        } catch (org.springframework.dao.DataIntegrityViolationException e) {
            return ApiResponse.error(4009, "登记号已存在(唯一字段冲突)");
        }
        return updated(n);
    }

    // ---------- innovation ----------

    @GetMapping("/innovation/{id}/edit-detail")
    public ApiResponse<Map<String, Object>> innovationDetail(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT id, project_no AS "projectNo", project_name AS "projectName",
                       project_type AS "projectType", status, start_date AS "startDate",
                       end_date AS "endDate", funding_amount AS "fundingAmount",
                       student_leader_name AS "studentLeaderName", student_leader_id AS "studentLeaderId",
                       other_members::TEXT AS "otherMembers", supervisors,
                       laboratory_id AS "laboratoryId", submitter_type AS "submitterType",
                       submitter_id AS "submitterId", submit_time AS "submitTime"
                FROM innovation_projects WHERE id = ?
                """, id);
        ApiResponse<Map<String, Object>> resp = detailOut(rows, "大创项目不存在");
        if (resp.data() != null) {
            Map<String, Object> d = resp.data();
            d.put("leaderStatus", leaderStatus((String) d.get("studentLeaderId"),
                    (String) d.get("studentLeaderName")));
        }
        return resp;
    }

    public record InnovationUpdate(String projectNo, String projectName, String projectType, String status,
            String startDate, String endDate, Double fundingAmount, String studentLeaderName,
            String studentLeaderId, List<Object> otherMembers, String supervisors, Integer laboratoryId) {}

    @PutMapping("/innovation/{id}")
    @Transactional
    public ApiResponse<Integer> innovationUpdate(@PathVariable Integer id, @RequestBody InnovationUpdate req,
            Authentication auth) {
        requireAdmin(auth);
        if (req.projectName() == null || req.projectName().isBlank()) {
            return ApiResponse.error(4000, "项目名称必填");
        }
        String membersJson = toJsonArray(req.otherMembers());
        int n;
        try {
            n = jdbc.update("""
                UPDATE innovation_projects SET project_no = ?, project_name = ?, project_type = ?, status = ?,
                       start_date = ?, end_date = ?, funding_amount = ?, student_leader_name = ?,
                       student_leader_id = ?, other_members = CAST(? AS jsonb), supervisors = ?,
                       laboratory_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """, req.projectNo(), req.projectName(), req.projectType(), req.status(), req.startDate(),
                req.endDate(), req.fundingAmount(), req.studentLeaderName(), req.studentLeaderId(),
                membersJson, req.supervisors(), req.laboratoryId(), id);
        } catch (org.springframework.dao.DataIntegrityViolationException e) {
            return ApiResponse.error(4009, "项目编号已存在(唯一字段冲突)");
        }
        return updated(n);
    }

    /** 学生负责人匹配状态(v1 同构):学号精确 → 姓名精确(唯一 matched/多名 ambiguous/无 not_found)。 */
    private Map<String, Object> leaderStatus(String leaderId, String leaderName) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("name", leaderName);
        out.put("studentId", leaderId);
        out.put("status", "not_found");
        Integer byId = jdbc.queryForObject(
                "SELECT COUNT(*) FROM users WHERE role = 'student' AND login_code = ?",
                Integer.class, leaderId == null ? "" : leaderId);
        if (leaderId != null && !leaderId.isBlank() && byId != null && byId > 0) {
            out.put("status", "matched");
            return out;
        }
        if (leaderName != null && !leaderName.isBlank()) {
            List<Integer> hits = jdbc.queryForList(
                    "SELECT id FROM users WHERE role = 'student' AND name = ? ORDER BY id",
                    Integer.class, leaderName);
            if (hits.size() == 1) {
                out.put("status", "matched");
                out.put("id", hits.get(0));
            } else if (hits.size() > 1) {
                out.put("status", "ambiguous");
            }
        }
        return out;
    }

    /** 成员数组原样序列化(元素可为字符串或 {姓名,学号} 对象,未改动时透传原结构避免数据退化)。 */
    private String toJsonArray(List<Object> items) {
        if (items == null || items.isEmpty()) {
            return null;
        }
        List<Object> cleaned = new ArrayList<>();
        for (Object s : items) {
            if (s != null && !String.valueOf(s).isBlank()) {
                cleaned.add(s instanceof String str ? str.trim() : s);
            }
        }
        if (cleaned.isEmpty()) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(cleaned);
        } catch (Exception e) {
            return null;
        }
    }

    private ApiResponse<Map<String, Object>> detailOut(List<Map<String, Object>> rows, String notFoundMsg) {
        if (rows.isEmpty()) {
            return ApiResponse.error(4004, notFoundMsg);
        }
        Map<String, Object> out = new LinkedHashMap<>(rows.get(0));
        out.put("laboratories", jdbc.queryForList("SELECT id, name FROM laboratories ORDER BY id"));
        return ApiResponse.ok(out);
    }

    private ApiResponse<Integer> updated(int n) {
        if (n == 0) {
            return ApiResponse.error(4004, "记录不存在");
        }
        return ApiResponse.ok(n, "已更新");
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
