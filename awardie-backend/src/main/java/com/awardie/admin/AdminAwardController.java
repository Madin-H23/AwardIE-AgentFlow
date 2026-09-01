package com.awardie.admin;

import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.auth.UserEntity;
import com.awardie.auth.UserRepository;
import com.awardie.common.ApiResponse;
import com.awardie.common.PageView;
import com.awardie.submission.PendingAchievementEntity;
import com.awardie.submission.PendingAchievementRepository;
import com.awardie.submission.ReviewService;

/** admin 管理面(#18):award 类成果列表/详情/审核——审核语义零重复复用 ReviewService。 */
@RestController
@RequestMapping("/api/v2/admin")
public class AdminAwardController {

    private final PendingAchievementRepository pendingRepo;
    private final ReviewService reviewService;
    private final UserRepository users;
    private final JdbcTemplate jdbc;

    public AdminAwardController(PendingAchievementRepository pendingRepo, ReviewService reviewService,
            UserRepository users, JdbcTemplate jdbc) {
        this.pendingRepo = pendingRepo;
        this.reviewService = reviewService;
        this.users = users;
        this.jdbc = jdbc;
    }

    /**
     * 列表(#37 十维筛选对照 v1 achievements):列级 status/type/keyword/dateFrom-dateTo +
     * jsonb 下推 competitionName(LIKE)/year(date 前 4 位)/competitionLevel/awardLevel(等值)/
     * winnerName/supervisorName(LIKE)。track/laboratory_id/is_abnormal/certificate_type
     * 不在 pending 语义内(对照记录声明)。JdbcTemplate 手写分页(同 #26 competitions 口径)。
     */
    @GetMapping("/achievements")
    public ApiResponse<PageView<Map<String, Object>>> list(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String achievementType,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String dateFrom,
            @RequestParam(required = false) String dateTo,
            @RequestParam(required = false) String competitionName,
            @RequestParam(required = false) String year,
            @RequestParam(required = false) String competitionLevel,
            @RequestParam(required = false) String awardLevel,
            @RequestParam(required = false) String winnerName,
            @RequestParam(required = false) String supervisorName,
            Authentication auth) {
        requireAdmin(auth);
        var zone = java.time.ZoneId.of("Asia/Shanghai");
        java.time.Instant from = parseDate(dateFrom, zone, false);
        java.time.Instant to = parseDate(dateTo, zone, true);
        int p = Math.max(page, 0);
        int s = Math.min(Math.max(size, 1), 100);

        StringBuilder where = new StringBuilder(" WHERE 1=1");
        List<Object> args = new java.util.ArrayList<>();
        if (status != null && !status.isBlank()) {
            where.append(" AND status = ?");
            args.add(status.trim());
        }
        if (achievementType != null && !achievementType.isBlank()) {
            where.append(" AND achievement_type = ?");
            args.add(achievementType.trim());
        }
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND achievement_data::text LIKE ?");
            args.add("%" + keyword.trim() + "%");
        }
        if (from != null) {
            where.append(" AND submit_time >= ?");
            args.add(java.sql.Timestamp.from(from));
        }
        if (to != null) {
            where.append(" AND submit_time < ?");
            args.add(java.sql.Timestamp.from(to));
        }
        like(where, args, "competition_name", competitionName);
        if (year != null && !year.isBlank()) {
            where.append(" AND achievement_data->>'date' LIKE ?");
            args.add(year.trim() + "%");
        }
        eq(where, args, "competition_level", competitionLevel);
        eq(where, args, "award_level", awardLevel);
        like(where, args, "winner_name", winnerName);
        like(where, args, "supervisor_name", supervisorName);

        Integer total = jdbc.queryForObject(
                "SELECT COUNT(*) FROM pending_achievements" + where, Integer.class, args.toArray());
        List<Object> listArgs = new java.util.ArrayList<>(args);
        listArgs.add(s);
        listArgs.add((long) p * s);
        List<Map<String, Object>> content = jdbc.queryForList("""
                SELECT id, achievement_type AS "achievementType", submitter_type AS "submitterType",
                       submitter_id AS "submitterId", status, submit_time AS "submitTime",
                       achievement_data->>'competition_name' AS "competitionName",
                       achievement_data->>'competition_level' AS "competitionLevel",
                       achievement_data->>'award_level' AS "awardLevel",
                       achievement_data->>'winner_name' AS "winnerName",
                       achievement_data->>'supervisor_name' AS "supervisorName",
                       achievement_data->>'date' AS "awardDate"
                FROM pending_achievements
                """ + where + " ORDER BY id DESC LIMIT ? OFFSET ?", listArgs.toArray());
        int totalPages = total == null || total == 0 ? 0 : (total + s - 1) / s;
        return ApiResponse.ok(new PageView<>(
                content, total == null ? 0 : total, totalPages, p, s));
    }

    private void like(StringBuilder where, List<Object> args, String jsonbKey, String value) {
        if (value != null && !value.isBlank()) {
            where.append(" AND achievement_data->>'").append(jsonbKey).append("' LIKE ?");
            args.add("%" + value.trim() + "%");
        }
    }

    private void eq(StringBuilder where, List<Object> args, String jsonbKey, String value) {
        if (value != null && !value.isBlank()) {
            where.append(" AND achievement_data->>'").append(jsonbKey).append("' = ?");
            args.add(value.trim());
        }
    }

    private java.time.Instant parseDate(String raw, java.time.ZoneId zone, boolean endOfDay) {
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

    @GetMapping("/achievements/{id}")
    public ApiResponse<PendingAchievementEntity> detail(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        return pendingRepo.findById(id)
                .map(ApiResponse::ok)
                .orElse(ApiResponse.error(4004, "记录不存在"));
    }

    /** 审核操作:直接复用 ReviewService(状态机+物化+留痕,#11/#14 语义)。 */
    public record ReviewRequest(String action, String comment) {}

    @PostMapping("/achievements/{id}/review")
    public ApiResponse<PendingAchievementEntity> review(@PathVariable Integer id,
            @RequestBody ReviewRequest req, Authentication auth) {
        requireAdmin(auth);
        UserEntity operator = users.findByLoginCode(auth.getName()).orElseThrow();
        PendingAchievementEntity e = switch (req.action()) {
            case "approve" -> reviewService.approve(id, operator, req.comment());
            case "reject" -> reviewService.reject(id, operator, req.comment());
            default -> throw new IllegalArgumentException("action 仅允许 approve/reject");
        };
        return ApiResponse.ok(e, "审核完成");
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
