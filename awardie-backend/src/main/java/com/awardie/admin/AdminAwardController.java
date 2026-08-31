package com.awardie.admin;

import java.util.List;

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

    /** 列表:分页 + 可选 status 筛选(pending/archived/rejected)+ 可选类型。 */
    @GetMapping("/achievements")
    public ApiResponse<Page<PendingAchievementEntity>> list(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String achievementType,
            Authentication auth) {
        requireAdmin(auth);
        var spec = pendingRepo.findAll(PageRequest.of(page, Math.min(size, 100), Sort.by(Sort.Direction.DESC, "id")));
        if ((status == null || status.isBlank()) && (achievementType == null || achievementType.isBlank())) {
            return ApiResponse.ok(spec);
        }
        // 内存过滤(数据量小;P2 后期如超千行改 Specification)
        List<PendingAchievementEntity> filtered = spec.getContent().stream()
                .filter(e -> status == null || status.isBlank() || status.equals(e.getStatus()))
                .filter(e -> achievementType == null || achievementType.isBlank()
                        || achievementType.equals(e.getAchievementType()))
                .toList();
        return ApiResponse.ok(new org.springframework.data.domain.PageImpl<>(filtered, spec.getPageable(), filtered.size()));
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
