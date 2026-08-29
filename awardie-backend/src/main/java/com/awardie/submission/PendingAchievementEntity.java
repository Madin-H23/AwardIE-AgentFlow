package com.awardie.submission;

import java.time.Instant;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** pending_achievements 映射(提交-审核-时间线纵切面的核心表;生成列 is_valid 不映射)。 */
@Entity
@Table(name = "pending_achievements")
public class PendingAchievementEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Integer id;

    @Column(name = "achievement_type", nullable = false)
    private String achievementType;

    /** 结构化字段(JSONB,15 个 award 字段等)。 */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "achievement_data", columnDefinition = "jsonb", nullable = false)
    private String achievementData;

    /** v1 校验结果:{"is_valid":bool,"content_issues":[],"completeness_issues":[]} */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "validation_result", columnDefinition = "jsonb")
    private String validationResult;

    @Column(name = "submitter_type", nullable = false)
    private String submitterType;

    @Column(name = "submitter_id")
    private Integer submitterId;

    @Column(name = "submit_time")
    private Instant submitTime;

    /** pending → (approved)archived / (rejected)rejected;BR-5 驳回后修改可重新提交(新行)。 */
    @Column(name = "status", nullable = false)
    private String status;

    @Column(name = "reviewer_id")
    private Integer reviewerId;

    @Column(name = "review_time")
    private Instant reviewTime;

    @Column(name = "review_comment")
    private String reviewComment;

    @Column(name = "created_at")
    private Instant createdAt;

    @Column(name = "file_path")
    private String filePath;

    @Column(name = "file_hash", nullable = false)
    private String fileHash;

    @Column(name = "version", nullable = false)
    private Integer version;

    public Integer getId() { return id; }
    public String getAchievementType() { return achievementType; }
    public void setAchievementType(String v) { this.achievementType = v; }
    public String getAchievementData() { return achievementData; }
    public void setAchievementData(String v) { this.achievementData = v; }
    public String getValidationResult() { return validationResult; }
    public void setValidationResult(String v) { this.validationResult = v; }
    public String getSubmitterType() { return submitterType; }
    public void setSubmitterType(String v) { this.submitterType = v; }
    public Integer getSubmitterId() { return submitterId; }
    public void setSubmitterId(Integer v) { this.submitterId = v; }
    public Instant getSubmitTime() { return submitTime; }
    public void setSubmitTime(Instant v) { this.submitTime = v; }
    public String getStatus() { return status; }
    public void setStatus(String v) { this.status = v; }
    public Integer getReviewerId() { return reviewerId; }
    public void setReviewerId(Integer v) { this.reviewerId = v; }
    public Instant getReviewTime() { return reviewTime; }
    public void setReviewTime(Instant v) { this.reviewTime = v; }
    public String getReviewComment() { return reviewComment; }
    public void setReviewComment(String v) { this.reviewComment = v; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant v) { this.createdAt = v; }
    public String getFilePath() { return filePath; }
    public void setFilePath(String v) { this.filePath = v; }
    public String getFileHash() { return fileHash; }
    public void setFileHash(String v) { this.fileHash = v; }
    public Integer getVersion() { return version; }
    public void setVersion(Integer v) { this.version = v; }
}
