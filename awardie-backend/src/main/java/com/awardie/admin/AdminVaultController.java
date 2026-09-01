package com.awardie.admin;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;
import com.awardie.common.PageView;

/**
 * 成果库管理(Fix-C,对照 v1 achievements 五 tabs):awards/patents/software/innovation/other
 * 五张已入库成果表的分页列表+行编辑/删除——区别于 pending 待审池(admin/awards)。
 */
@RestController
@RequestMapping("/api/v2/admin/vault")
public class AdminVaultController {

    private final JdbcTemplate jdbc;

    public AdminVaultController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 五类列表:type=award|patent|software|innovation|other;keyword 按名称模糊。 */
    @GetMapping("/{type}")
    public ApiResponse<PageView<Map<String, Object>>> list(@PathVariable String type,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String keyword,
            Authentication auth) {
        requireAdmin(auth);
        int p = Math.max(page, 0);
        int s = Math.min(Math.max(size, 1), 100);
        VaultSpec spec = VaultSpec.of(type);
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        List<Object> args = new java.util.ArrayList<>();
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND ").append(spec.nameColumn()).append(" LIKE ?");
            args.add("%" + keyword.trim() + "%");
        }
        Integer total = jdbc.queryForObject(
                "SELECT COUNT(*) FROM " + spec.from() + where, Integer.class, args.toArray());
        List<Object> listArgs = new java.util.ArrayList<>(args);
        listArgs.add(s);
        listArgs.add((long) p * s);
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT " + spec.columns() + " FROM " + spec.from() + where
                        + " ORDER BY id DESC LIMIT ? OFFSET ?", listArgs.toArray());
        int totalPages = total == null || total == 0 ? 0 : (total + s - 1) / s;
        return ApiResponse.ok(new PageView<>(rows, total == null ? 0 : total, totalPages, p, s));
    }

    /** awards 行编辑(核心字段)。 */
    public record AwardUpdate(String awardLevel, String winnerName, String supervisorName, Integer laboratoryId) {}

    @PutMapping("/awards/{id}")
    public ApiResponse<Integer> updateAward(@PathVariable Integer id, @RequestBody AwardUpdate req,
            Authentication auth) {
        requireAdmin(auth);
        int n = jdbc.update("""
                UPDATE awards SET award_level=?, winner_name=?, supervisor_name=?, laboratory_id=?,
                                   updated_at=NOW()
                WHERE id=?
                """, req.awardLevel(), req.winnerName(), req.supervisorName(), req.laboratoryId(), id);
        if (n == 0) {
            return ApiResponse.error(4004, "记录不存在");
        }
        return ApiResponse.ok(n, "已更新");
    }

    /** 行删除:type 分发到五表。 */
    @DeleteMapping("/{type}/{id}")
    public ResponseEntity<ApiResponse<Integer>> delete(@PathVariable String type, @PathVariable Integer id,
            Authentication auth) {
        requireAdmin(auth);
        VaultSpec spec;
        try {
            spec = VaultSpec.of(type);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.ok(ApiResponse.error(4000, e.getMessage()));
        }
        try {
            int n = jdbc.update("DELETE FROM " + spec.deleteTable() + " WHERE id = ?", id);
            if (n == 0) {
                return ResponseEntity.ok(ApiResponse.error(4004, "记录不存在"));
            }
            return ResponseEntity.ok(ApiResponse.ok(n, "已删除"));
        } catch (org.springframework.dao.DataIntegrityViolationException e) {
            return ResponseEntity.ok(ApiResponse.error(4009, "存在关联数据,无法删除"));
        }
    }

    /** 五表白名单(表名/名称列/SELECT 列),杜绝字符串拼接注入面。 */
    enum VaultSpec {
        AWARDS("awards a LEFT JOIN laboratories l ON a.laboratory_id = l.id",
                "a.competition_name_in_file",
                "a.id, a.competition_name_in_file AS name, a.competition_level AS level, a.award_level AS award_level, "
                        + "a.winner_name, a.supervisor_name, a.year::TEXT AS year, a.is_abnormal AS is_abnormal, "
                        + "COALESCE(l.name, '-') AS laboratory"),
        PATENTS("patents p", "p.patent_name",
                "p.id, p.patent_name AS name, p.patent_type AS patent_type, p.patentee, p.inventor"),
        SOFTWARE("software_copyrights s", "s.software_name",
                "s.id, s.software_name AS name, s.software_version AS software_version, "
                        + "s.registration_number AS registration_number, s.copyright_owner"),
        INNOVATION("innovation_projects i", "i.project_name",
                "i.id, i.project_no AS project_no, i.project_name AS name, i.project_type AS project_type, "
                        + "i.student_leader_name AS leader, i.supervisors, i.status"),
        OTHER("other_files o", "o.file_name",
                "o.id, o.file_name AS name, o.file_type AS file_type, o.file_size AS file_size, o.description");

        private final String from;
        private final String nameColumn;
        private final String columns;

        VaultSpec(String from, String nameColumn, String columns) {
            this.from = from;
            this.nameColumn = nameColumn;
            this.columns = columns;
        }

        String from() {
            return from;
        }

        /** DELETE 用单表名(不带 join)。 */
        String deleteTable() {
            return switch (this) {
                case AWARDS -> "awards";
                case PATENTS -> "patents";
                case SOFTWARE -> "software_copyrights";
                case INNOVATION -> "innovation_projects";
                case OTHER -> "other_files";
            };
        }

        String nameColumn() {
            return nameColumn;
        }

        String columns() {
            return columns;
        }

        static VaultSpec of(String type) {
            return switch (type) {
                case "award" -> AWARDS;
                case "patent" -> PATENTS;
                case "software" -> SOFTWARE;
                case "innovation" -> INNOVATION;
                case "other" -> OTHER;
                default -> throw new IllegalArgumentException("type 仅允许 award/patent/software/innovation/other");
            };
        }
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
