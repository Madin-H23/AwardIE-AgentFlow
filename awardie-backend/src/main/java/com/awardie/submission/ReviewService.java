package com.awardie.submission;

import java.time.Instant;
import java.util.List;
import java.util.Map;

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
    public static final int ACTION_MATERIALIZE = 8;

    private final PendingAchievementRepository pendingRepo;
    private final AuditLogRepository auditRepo;
    private final UserRepository users;
    private final org.springframework.jdbc.core.JdbcTemplate jdbc;

    public ReviewService(PendingAchievementRepository pendingRepo, AuditLogRepository auditRepo,
            UserRepository users, org.springframework.jdbc.core.JdbcTemplate jdbc) {
        this.pendingRepo = pendingRepo;
        this.auditRepo = auditRepo;
        this.users = users;
        this.jdbc = jdbc;
    }

    @Transactional
    public PendingAchievementEntity approve(Integer pendingId, UserEntity operator, String comment) {
        PendingAchievementEntity e = requirePending(pendingId);
        e.setStatus("archived");
        e.setReviewerId(operator.getId());
        e.setReviewTime(Instant.now());
        e.setReviewComment(comment == null ? "" : comment);
        pendingRepo.save(e);
        audit(e, operator, ACTION_APPROVE, jsonDetail("审核通过", comment));
        materialize(e, operator); // #14:批准即入库(awards 物化)
        return e;
    }

    /**
     * #14 物化:pending → awards(成果资产)+ award_student_winners(学生关联)。
     * 幂等:audit 已有 action_type=8(入库)则跳过;竞赛按名匹配,缺失自动建(is_auto_added,v1 语义)。
     */
    @SuppressWarnings("unchecked")
    private void materialize(PendingAchievementEntity e, UserEntity operator) {
        Integer done = jdbc.queryForObject(
                "SELECT COUNT(*) FROM achievement_audit_log WHERE achievement_id=? AND action_type=8",
                Integer.class, e.getId());
        if (done != null && done > 0) {
            return; // 幂等
        }
        Map<String, Object> data;
        try {
            data = new com.fasterxml.jackson.databind.ObjectMapper().readValue(
                    e.getAchievementData() == null ? "{}" : e.getAchievementData(), Map.class);
        } catch (Exception ex) {
            throw new IllegalStateException("achievement_data 不是合法 JSON", ex);
        }
        // #19:按类型分发物化到各自资产表(v1 五表结构);空串转 NULL 避免撞 UNIQUE 约束
        String ref = switch (e.getAchievementType()) {
            case "award" -> materializeAward(e, data);
            case "patent" -> materializePatent(e, data);
            case "software" -> materializeSoftware(e, data);
            case "innovation" -> "skipped"; // v1 语义:innovation_projects 限 admin(Excel 导入通道),学生归档不物化
            case "other" -> materializeOther(e, data);
            default -> throw new IllegalStateException("未知类型不可物化: " + e.getAchievementType());
        };
        audit(e, operator, ACTION_MATERIALIZE, jsonDetail("入库", ref));
    }

    /** 竞赛按名匹配,缺失自动建;返回 competition_id。 */
    private Integer resolveCompetition(String compName) {
        java.util.List<Integer> found = jdbc.queryForList(
                "SELECT id FROM competitions WHERE competition_name=?", Integer.class, compName);
        if (!found.isEmpty()) {
            return found.get(0);
        }
        jdbc.update("INSERT INTO competitions (competition_name, is_auto_added) VALUES (?, TRUE)", compName);
        return jdbc.queryForList("SELECT id FROM competitions WHERE competition_name=?",
                Integer.class, compName).get(0);
    }

    private String materializeAward(PendingAchievementEntity e, Map<String, Object> data) {
        String compName = str(data.get("competition_name"));
        Integer competitionId = resolveCompetition(compName);
        jdbc.update("""
                INSERT INTO awards (image_hash, certificate_id, certificate_path, competition_name_in_file, track, issuer,
                    province, group_name, winner_name, supervisor_name, award_level, competition_level,
                    date, project_title, competition_id, submitter_type, submitter_id, submit_time,
                    created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW())
                """,
                e.getFileHash(), str(data.get("certificate_id")), e.getFilePath(), compName, str(data.get("track")),
                str(data.get("issuer")), str(data.get("province")), str(data.get("group_name")),
                str(data.get("winner_name")), str(data.get("supervisor_name")), str(data.get("award_level")),
                str(data.get("competition_level")), str(data.get("date")), str(data.get("project_title")),
                competitionId, e.getSubmitterType(), e.getSubmitterId(),
                ts(e.getSubmitTime()), ts(Instant.now()));
        Integer awardId = jdbc.queryForObject(
                "SELECT id FROM awards WHERE image_hash=? ORDER BY id DESC LIMIT 1", Integer.class, e.getFileHash());
        // 学生获奖关联(submitter 为学生时)
        if ("student".equals(e.getSubmitterType()) && e.getSubmitterId() != null) {
            Integer exists = jdbc.queryForObject(
                    "SELECT COUNT(*) FROM award_student_winners WHERE award_id=? AND student_id=?",
                    Integer.class, awardId, e.getSubmitterId());
            if (exists != null && exists == 0) {
                jdbc.update("INSERT INTO award_student_winners (award_id, student_id, created_at) VALUES (?,?,NOW())",
                        awardId, e.getSubmitterId());
            }
        }
        return "awards#" + awardId;
    }

    private String materializePatent(PendingAchievementEntity e, Map<String, Object> data) {
        jdbc.update("""
                INSERT INTO patents (patent_name, patent_type, application_number, inventor, patentee,
                    certificate_file, submitter_type, submitter_id, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,NOW(),NOW())
                """,
                str(data.get("patent_name")), str(data.get("patent_type")),
                nullable(str(data.get("application_number"))), str(data.get("inventor")),
                str(data.get("patentee")), e.getFilePath(),
                e.getSubmitterType(), e.getSubmitterId());
        return "patents#" + jdbc.queryForObject("SELECT MAX(id) FROM patents", Integer.class);
    }

    private String materializeSoftware(PendingAchievementEntity e, Map<String, Object> data) {
        jdbc.update("""
                INSERT INTO software_copyrights (software_name, software_version, registration_number,
                    copyright_owner, certificate_file, submitter_type, submitter_id, submit_time,
                    created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,NOW(),NOW())
                """,
                str(data.get("software_name")), str(data.get("software_version")),
                nullable(str(data.get("registration_number"))), str(data.get("copyright_owner")),
                e.getFilePath(), e.getSubmitterType(), e.getSubmitterId(), ts(Instant.now()));
        return "software_copyrights#" + jdbc.queryForObject(
                "SELECT MAX(id) FROM software_copyrights", Integer.class);
    }

    private String materializeOther(PendingAchievementEntity e, Map<String, Object> data) {
        jdbc.update("""
                INSERT INTO other_files (file_name, file_path, file_hash, description,
                    submitter_type, submitter_id, submit_time, created_at)
                VALUES (?,?,?,?,?,?,?,NOW())
                """,
                str(data.get("title")), e.getFilePath(), e.getFileHash(),
                str(data.get("title")), e.getSubmitterType(), e.getSubmitterId(), ts(Instant.now())); // description 回填 title(v1 语义:成果名即描述)
        return "other_files#" + jdbc.queryForObject("SELECT MAX(id) FROM other_files", Integer.class);
    }

    private static String nullable(String v) {
        return v == null || v.isBlank() ? null : v; // 空串撞 UNIQUE 约束,统一转 NULL
    }

    private static java.sql.Timestamp ts(Instant t) {
        return java.sql.Timestamp.from(t);
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

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
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
