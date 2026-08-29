package com.awardie.submission;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** achievement_audit_log 映射(时间线/留痕;动作枚举沿 v1 ACTION_LABELS)。 */
@Entity
@Table(name = "achievement_audit_log")
public class AuditLogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Integer id;

    @Column(name = "achievement_id", nullable = false)
    private Integer achievementId;

    @Column(name = "achievement_kind", nullable = false)
    private String achievementKind;

    @Column(name = "action_type", nullable = false)
    private Integer actionType;

    @Column(name = "action_result")
    private Integer actionResult;

    @Column(name = "operator_id")
    private Integer operatorId;

    @Column(name = "operator_code")
    private String operatorCode;

    @Column(name = "operator_name")
    private String operatorName;

    @org.hibernate.annotations.JdbcTypeCode(org.hibernate.type.SqlTypes.JSON)
    @Column(name = "change_detail", columnDefinition = "jsonb")
    private String changeDetail;

    @Column(name = "remark")
    private String remark;

    @Column(name = "created_at")
    private Instant createdAt;

    public Integer getId() { return id; }
    public Integer getAchievementId() { return achievementId; }
    public void setAchievementId(Integer v) { this.achievementId = v; }
    public String getAchievementKind() { return achievementKind; }
    public void setAchievementKind(String v) { this.achievementKind = v; }
    public Integer getActionType() { return actionType; }
    public void setActionType(Integer v) { this.actionType = v; }
    public Integer getActionResult() { return actionResult; }
    public void setActionResult(Integer v) { this.actionResult = v; }
    public Integer getOperatorId() { return operatorId; }
    public void setOperatorId(Integer v) { this.operatorId = v; }
    public String getOperatorCode() { return operatorCode; }
    public void setOperatorCode(String v) { this.operatorCode = v; }
    public String getOperatorName() { return operatorName; }
    public void setOperatorName(String v) { this.operatorName = v; }
    public String getChangeDetail() { return changeDetail; }
    public void setChangeDetail(String v) { this.changeDetail = v; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant v) { this.createdAt = v; }
}
