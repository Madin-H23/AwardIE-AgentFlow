package com.awardie.aireview;

import java.io.IOException;
import com.awardie.auth.UserEntity;
import java.util.List;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import com.awardie.common.ApiResponse;
import com.awardie.submission.PendingAchievementEntity;
import com.awardie.submission.PendingAchievementRepository;

/** 教师审核侧(#9):待审列表 + AI 建议 SSE 流式(fake/grpc 双模式,BR-2 免责声明)。 */
@RestController
@RequestMapping("/api/v2/teacher")
public class TeacherReviewController {

    private final PendingAchievementRepository pendingRepo;
    private final AiProxyService ai;
    private final com.awardie.submission.ReviewService reviewService;
    private final com.awardie.auth.UserRepository users;

    public TeacherReviewController(PendingAchievementRepository pendingRepo, AiProxyService ai,
            com.awardie.submission.ReviewService reviewService, com.awardie.auth.UserRepository users) {
        this.pendingRepo = pendingRepo;
        this.ai = ai;
        this.reviewService = reviewService;
        this.users = users;
    }

    /** 审核闭环(#11):批准→archived / 驳回→rejected(BR-5:驳回必须填写原因)。 */
    @org.springframework.web.bind.annotation.PostMapping("/review/{id}")
    public ApiResponse<PendingAchievementEntity> review(@PathVariable Integer id,
            @org.springframework.web.bind.annotation.RequestBody ReviewRequest req, Authentication auth) {
        requireRole(auth, "teacher");
        UserEntity operator = users.findByLoginCode(auth.getName()).orElseThrow();
        PendingAchievementEntity e = switch (req.action()) {
            case "approve" -> reviewService.approve(id, operator, req.comment());
            case "reject" -> reviewService.reject(id, operator, req.comment());
            default -> throw new IllegalArgumentException("action 仅允许 approve/reject");
        };
        return ApiResponse.ok(e, "审核完成");
    }

    public record ReviewRequest(@jakarta.validation.constraints.NotBlank String action, String comment) {}

    @GetMapping("/pending")
    public ApiResponse<List<PendingAchievementEntity>> pendingList(Authentication auth) {
        requireRole(auth, "teacher");
        return ApiResponse.ok(pendingRepo.findAll());
    }

    /** AI 建议 SSE:事件流(node/delta/final),前端打字机渲染;降级为 4003 人工审提示。 */
    @GetMapping(value = "/review/{id}/ai-suggest", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter aiSuggest(@PathVariable Integer id) throws IOException {
        SseEmitter emitter = new SseEmitter(320_000L); // 与探针 P1 硬条目对齐
        PendingAchievementEntity pending = pendingRepo.findById(id).orElse(null);
        if (pending == null) {
            emitter.send(SseEmitter.event().name("final")
                    .data("{\"kind\":\"final\",\"code\":404,\"message\":\"记录不存在\"}"));
            emitter.complete();
            return emitter;
        }
        Thread worker = new Thread(() -> {
            try {
                for (AiProxyService.AiEvent evt : (Iterable<AiProxyService.AiEvent>) () -> ai.suggest(pending)) {
                    emitter.send(SseEmitter.event().name(evt.kind()).data(toJson(evt)));
                    if ("final".equals(evt.kind())) {
                        break;
                    }
                }
                emitter.complete();
            } catch (Exception e) {
                emitter.completeWithError(e);
            }
        }, "ai-suggest-" + id);
        worker.setDaemon(true);
        worker.start();
        return emitter;
    }

    private String toJson(AiProxyService.AiEvent evt) {
        StringBuilder sb = new StringBuilder("{\"kind\":\"").append(evt.kind()).append('"');
        if (evt.node() != null) {
            sb.append(",\"node\":\"").append(evt.node()).append('"');
        }
        if (evt.text() != null) {
            sb.append(",\"text\":\"").append(evt.text().replace("\"", "'")).append('"');
        }
        if (evt.code() != null) {
            sb.append(",\"code\":").append(evt.code());
        }
        if (evt.message() != null) {
            sb.append(",\"message\":\"").append(evt.message().replace("\"", "'")).append('"');
        }
        sb.append(",\"disclaimer\":\"AI 建议仅辅助参考(BR-2)\"}");
        return sb.toString();
    }

    private void requireRole(Authentication auth, String role) {
        // admin 为教师权限的超集(管理权可看待审)
        if (!hasRole(auth, role) && !hasRole(auth, "admin")) {
            throw new org.springframework.security.access.AccessDeniedException("需要 " + role + " 角色");
        }
    }

    private boolean hasRole(Authentication auth, String role) {
        for (GrantedAuthority a : auth.getAuthorities()) {
            if (a.getAuthority().equals("ROLE_" + role.toUpperCase())) {
                return true;
            }
        }
        return false;
    }

}
