package com.awardie.submission;

import java.time.Instant;
import java.util.List;

import org.springframework.stereotype.Service;

import com.awardie.auth.UserEntity;
import com.awardie.auth.UserRepository;

import jakarta.transaction.Transactional;

/**
 * 审核闭环(#11):状态机 pending→archived/rejected + BR-5 + 留痕。
 * 动作枚举沿 v1 ACTION_LABELS:1=提交,6=审核通过,7=驳回打回。
 * P0 口径:批准=状态 archived + 留痕;awards 正式物化入库列高频扩展阶段。
 */
@Service
public class ReviewService {

    public static final int ACTION_SUBMIT = 1;
    public static final int ACTION_APPROVE = 6;
    public static final int ACTION_REJECT = 7;

    private final PendingAchievementRepository pendingRepo;
    private final AuditLogRepository auditRepo;
    private final UserRepository users;

    public ReviewService(PendingAchievementRepository pendingRepo, AuditLogRepository auditRepo,
            UserRepository users) {
        this.pendingRepo = pendingRepo;
        this.auditRepo = auditRepo;
        this.users = users;
    }

    @Transactional
    public PendingAchievementEntity approve(Integer pendingId, UserEntity operator, String comment) {
        PendingAchievementEntity e = requirePending(pendingId);
        e.setStatus("archived");
        e.setReviewerId(operator.getId());
        e.setReviewTime(Instant.now());
        e.setReviewComment(comment == null ? "" : comment);
        pendingRepo.save(e);
        audit(e, operator, ACTION_APPROVE, "{\"message\":\"审核通过\"}" + (comment == null || comment.isBlank() ? "" : "").replace("{", "{"));
        return e;
    }

    @Transactional
    public PendingAchievementEntity reject(Integer pendingId, UserEntity operator, String comment) {
        if (comment == null || comment.isBlank()) {
            throw new IllegalArgumentException("驳回必须填写原因(BR-5)");
        }
        PendingAchievementEntity e = requirePending(pendingId);
        e.setStatus("rejected");
        e.setReviewerId(operator.getId());
        e.setReviewTime(Instant.now());
        e.setReviewComment(comment);
        pendingRepo.save(e);
        audit(e, operator, ACTION_REJECT, jsonDetail("驳回打回", comment));
        return e;
    }

    /** BR-5:rejected/pending 均不阻断同 hash 重提?——去重仅对 pending 生效;rejected 行可修改后重提(新行)。 */
    @Transactional
    public void auditSubmit(Integer pendingId, UserEntity operator) {
        PendingAchievementEntity e = pendingRepo.findById(pendingId).orElse(null);
        if (e != null) {
            audit(e, operator, ACTION_SUBMIT, jsonDetail("提交成果", null));
        }
    }

    public List<AuditLog> timeline(Integer pendingId) {
        return auditRepo.findByAchievementIdOrderByCreatedAtAsc(pendingId).stream()
                .map(a -> new AuditLog(a.getId(), a.getAchievementId(), a.getActionType(),
                        a.getOperatorCode(), a.getOperatorName(), a.getChangeDetail(),
                        a.getCreatedAt() == null ? null : a.getCreatedAt().toString()))
                .toList();
    }

    private PendingAchievementEntity requirePending(Integer id) {
        PendingAchievementEntity e = pendingRepo.findById(id).orElse(null);
        if (e == null) {
            throw new IllegalArgumentException("记录不存在");
        }
        if (!"pending".equals(e.getStatus())) {
            throw new IllegalStateException("状态机非法流转:" + e.getStatus() + " 不可再审");
        }
        return e;
    }

    /** change_detail 为 jsonb 列:统一写 {"message":...,"comment":...} 对象。 */
    private String jsonDetail(String message, String comment) {
        String c = comment == null ? "" : comment.replace("\"", "'");
        return "{\"message\":\"" + message + "\",\"comment\":\"" + c + "\"}";
    }

    private void audit(PendingAchievementEntity e, UserEntity operator, int actionType, String detail) {
        AuditLogEntity a = new AuditLogEntity();
        a.setAchievementId(e.getId());
        a.setAchievementKind(e.getAchievementType());
        a.setActionType(actionType);
        a.setActionResult(1);
        a.setOperatorId(operator.getId());
        a.setOperatorCode(operator.getLoginCode());
        a.setOperatorName(operator.getName());
        a.setChangeDetail(detail);
        a.setCreatedAt(Instant.now());
        auditRepo.save(a);
    }

    public record AuditLog(Integer id, Integer achievementId, Integer actionType, String operatorCode,
            String operatorName, String changeDetail, String createdAt) {}
}
