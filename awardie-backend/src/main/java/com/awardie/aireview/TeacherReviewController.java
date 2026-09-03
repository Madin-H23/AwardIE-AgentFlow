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
        if (!"pending".equals(pending.getStatus())) {
            // Fix-U/V OCR Low 销账:已审结记录不再触发 AI 调用(API 直调面收口)
            emitter.send(SseEmitter.event().name("final")
                    .data("{\"kind\":\"final\",\"code\":4009,\"message\":\"记录已审结,无需 AI 建议\"}"));
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

    private final com.fasterxml.jackson.databind.ObjectMapper objectMapper =
            new com.fasterxml.jackson.databind.ObjectMapper();

    /** SSE 行协议 JSON:Jackson 序列化(换行/引号/反斜杠安全,替代手拼+引号替换的有损转义)。 */
    private String toJson(AiProxyService.AiEvent evt) {
        java.util.Map<String, Object> out = new java.util.LinkedHashMap<>();
        out.put("kind", evt.kind());
        if (evt.node() != null) {
            out.put("node", evt.node());
        }
        if (evt.text() != null) {
            out.put("text", evt.text());
        }
        if (evt.code() != null) {
            out.put("code", evt.code());
        }
        if (evt.message() != null) {
            out.put("message", evt.message());
        }
        out.put("disclaimer", "AI 建议仅辅助参考(BR-2)");
        try {
            return objectMapper.writeValueAsString(out);
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            return "{\"kind\":\"final\",\"code\":5000,\"message\":\"AI 建议序列化失败\"}";
        }
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
