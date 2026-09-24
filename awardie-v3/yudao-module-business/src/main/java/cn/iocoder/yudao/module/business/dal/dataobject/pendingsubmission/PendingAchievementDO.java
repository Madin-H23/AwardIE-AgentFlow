package cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission;

import lombok.*;
import java.util.*;
import java.time.LocalDateTime;
import java.time.LocalDateTime;
import java.time.LocalDateTime;
import java.time.LocalDateTime;
import com.baomidou.mybatisplus.annotation.*;
import cn.iocoder.yudao.framework.mybatis.core.dataobject.BaseDO;

/**
 * AwardIE 待审成果 DO
 *
 * @author AwardIE
 * <p>
 * KeySequence 用于 Oracle、PostgreSQL、Kingbase、DB2、H2 数据库的主键自增;MySQL 等数据库可不写。
 */
@TableName("awardie_pending_achievements")
@KeySequence("awardie_pending_achievements_seq")
@Data
@EqualsAndHashCode(callSuper = true)
@ToString(callSuper = true)
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PendingAchievementDO extends BaseDO {

    /**
     * 主键
     */
    @TableId
    private Long id;
    /**
     * 成果类型(award/patent/software/innovation/other)
     */
    private String achievementType;
    /**
     * 结构化成果字段(15 字段等)
     */
    private String achievementData;
    /**
     * 校验结果(is_valid/content_issues/completeness_issues)
     */
    private String validationResult;
    /**
     * 提交人类型(student/teacher/admin)
     */
    private String submitterType;
    /**
     * 提交人编号
     */
    private Long submitterId;
    /**
     * 提交时间
     */
    private LocalDateTime submitTime;
    /**
     * 状态(pending/archived/rejected)
     */
    private String status;
    /**
     * 审核人编号
     */
    private Long reviewerId;
    /**
     * 审核时间
     */
    private LocalDateTime reviewTime;
    /**
     * 审核意见
     */
    private String reviewComment;
    /**
     * 文件相对路径
     */
    private String filePath;
    /**
     * 指派审核人类型(teacher/admin)
     */
    private String assignedReviewerType;
    /**
     * 审核人类型(teacher/admin)
     */
    private String reviewerType;
    /**
     * 文件 SHA-256(去重依据)
     */
    private String fileHash;
    /**
     * OCR 文本
     */
    private String ocrText;
    /**
     * LLM 提示词
     */
    private String llmPrompt;
    /**
     * LLM 响应
     */
    private String llmResponse;
    /**
     * 扩展信息
     */
    private String extInfo;
    /**
     * AI 会话编号
     */
    private String sessionId;
    /**
     * 实验室编号
     */
    private Long laboratoryId;
    /**
     * 版本号
     */
    private Integer version;


}
