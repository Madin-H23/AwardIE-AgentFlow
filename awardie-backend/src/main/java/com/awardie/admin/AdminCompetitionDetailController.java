package com.awardie.admin;

import java.util.List;
import java.util.Map;

import org.springframework.dao.DataIntegrityViolationException;
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
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;

/** 竞赛详情/全字段编辑/删除(Fix-F 对照 v1 competitions/detail+edit)。 */
@RestController
@RequestMapping("/api/v2/admin/competitions")
public class AdminCompetitionDetailController {

    private final JdbcTemplate jdbc;

    public AdminCompetitionDetailController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 详情:全字段(含官网/主办/时间/简介/参赛要求)。 */
    @GetMapping("/{id}")
    public ApiResponse<Map<String, Object>> detail(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT id, competition_name AS "competitionName", official_website AS "officialWebsite",
                       organizer, competition_time AS "competitionTime", participant_requirements AS "participantRequirements",
                       grade_category AS "gradeCategory", brief_description AS "briefDescription",
                       white_list AS "whiteList", watch_list AS "watchList", is_auto_added AS "isAutoAdded",
                       alias_list AS "aliasList"
                FROM competitions WHERE id = ?
                """, id);
        if (rows.isEmpty()) {
            return ApiResponse.error(4004, "竞赛不存在");
        }
        return ApiResponse.ok(rows.get(0));
    }

    public record CompetitionDetailUpsert(String competitionName, String gradeCategory, String competitionTime,
            String organizer, String officialWebsite, String briefDescription,
            String participantRequirements, Boolean whiteList, Boolean watchList) {}

    /** 全字段编辑(v1 competition_edit 同字段集)。 */
    @PutMapping("/{id}/detail")
    public ApiResponse<Integer> updateDetail(@PathVariable Integer id, @RequestBody CompetitionDetailUpsert req,
            Authentication auth) {
        requireAdmin(auth);
        if (req.competitionName() == null || req.competitionName().isBlank()) {
            return ApiResponse.error(4000, "竞赛名称必填");
        }
        int n = jdbc.update("""
                UPDATE competitions SET competition_name=?, grade_category=?, competition_time=?,
                    organizer=?, official_website=?, brief_description=?, participant_requirements=?,
                    white_list=?, watch_list=?
                WHERE id=?
                """, req.competitionName(), req.gradeCategory(), req.competitionTime(),
                req.organizer(), req.officialWebsite(), req.briefDescription(), req.participantRequirements(),
                req.whiteList(), req.watchList(), id);
        if (n == 0) {
            return ApiResponse.error(4004, "竞赛不存在");
        }
        return ApiResponse.ok(n, "已更新");
    }

    /** 删除:存在成果关联时拒绝(FK)。 */
    @DeleteMapping("/{id}")
    public ResponseEntity<ApiResponse<Integer>> delete(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        try {
            int n = jdbc.update("DELETE FROM competitions WHERE id = ?", id);
            if (n == 0) {
                return ResponseEntity.ok(ApiResponse.error(4004, "竞赛不存在"));
            }
            return ResponseEntity.ok(ApiResponse.ok(n, "已删除"));
        } catch (DataIntegrityViolationException e) {
            return ResponseEntity.ok(ApiResponse.error(4009, "存在关联成果,无法删除"));
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
