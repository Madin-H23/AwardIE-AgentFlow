package com.awardie.admin;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
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

    public AdminAwardController(PendingAchievementRepository pendingRepo, ReviewService reviewService,
            UserRepository users) {
        this.pendingRepo = pendingRepo;
        this.reviewService = reviewService;
        this.users = users;
    }

    /**
     * 列表(#26 真分页):Specification 下推全部筛选——status/achievementType 等值,
     * keyword 对 jsonb 文本模糊(对照 v1 winner_name/supervisor_name 能力),
     * dateFrom/dateTo(yyyy-MM-dd,上海墙上时间)作用于 submit_time。
     */
    @GetMapping("/achievements")
    public ApiResponse<Page<PendingAchievementEntity>> list(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String achievementType,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String dateFrom,
            @RequestParam(required = false) String dateTo,
            Authentication auth) {
        requireAdmin(auth);
        // 日期解析前移(参数校验期抛 IllegalArgumentException→4000),Specification 内不懒解析
        var zone = java.time.ZoneId.of("Asia/Shanghai");
        java.time.Instant from = parseDate(dateFrom, zone, false);
        java.time.Instant to = parseDate(dateTo, zone, true);
        var spec = pendingAchievementSpec(status, achievementType, keyword, from, to);
        return ApiResponse.ok(pendingRepo.findAll(spec,
                PageRequest.of(page, Math.min(size, 100), Sort.by(Sort.Direction.DESC, "id"))));
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

    private org.springframework.data.jpa.domain.Specification<PendingAchievementEntity> pendingAchievementSpec(
            String status, String achievementType, String keyword, java.time.Instant from, java.time.Instant to) {
        return (root, query, cb) -> {
            var predicates = new java.util.ArrayList<jakarta.persistence.criteria.Predicate>();
            if (status != null && !status.isBlank()) {
                predicates.add(cb.equal(root.get("status"), status.trim()));
            }
            if (achievementType != null && !achievementType.isBlank()) {
                predicates.add(cb.equal(root.get("achievementType"), achievementType.trim()));
            }
            if (keyword != null && !keyword.isBlank()) {
                predicates.add(cb.like(root.get("achievementData").as(String.class),
                        "%" + keyword.trim() + "%"));
            }
            if (from != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("submitTime"), from));
            }
            if (to != null) {
                predicates.add(cb.lessThan(root.get("submitTime"), to));
            }
            return cb.and(predicates.toArray(new jakarta.persistence.criteria.Predicate[0]));
        };
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
