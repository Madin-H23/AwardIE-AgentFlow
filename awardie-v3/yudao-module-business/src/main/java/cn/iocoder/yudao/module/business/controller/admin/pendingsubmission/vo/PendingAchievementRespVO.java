package cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.*;
import java.util.*;
import org.springframework.format.annotation.DateTimeFormat;
import java.time.LocalDateTime;

/**
 * 管理后台 - AwardIE 待审成果 Response VO
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 待审成果 Response VO")
@Data
public class PendingAchievementRespVO {

    @Schema(description = "主键", requiredMode = Schema.RequiredMode.REQUIRED, example = "16350")
    private Long id;

    @Schema(description = "成果类型(award/patent/software/innovation/other)", requiredMode = Schema.RequiredMode.REQUIRED, example = "2")
    private String achievementType;

    @Schema(description = "结构化成果字段(15 字段等)", requiredMode = Schema.RequiredMode.REQUIRED)
    private String achievementData;

    @Schema(description = "校验结果(is_valid/content_issues/completeness_issues)")
    private String validationResult;

    @Schema(description = "提交人类型(student/teacher/admin)", requiredMode = Schema.RequiredMode.REQUIRED, example = "2")
    private String submitterType;

    @Schema(description = "提交人编号", example = "21599")
    private Long submitterId;

    @Schema(description = "提交时间")
    private LocalDateTime submitTime;

    @Schema(description = "状态(pending/archived/rejected)", requiredMode = Schema.RequiredMode.REQUIRED, example = "1")
    private String status;

    @Schema(description = "审核人编号", example = "29419")
    private Long reviewerId;

    @Schema(description = "审核时间")
    private LocalDateTime reviewTime;

    @Schema(description = "审核意见")
    private String reviewComment;

    @Schema(description = "文件相对路径")
    private String filePath;

    @Schema(description = "指派审核人类型(teacher/admin)", example = "1")
    private String assignedReviewerType;

    @Schema(description = "审核人类型(teacher/admin)", example = "1")
    private String reviewerType;

    @Schema(description = "文件 SHA-256(去重依据)", requiredMode = Schema.RequiredMode.REQUIRED)
    private String fileHash;

    @Schema(description = "OCR 文本")
    private String ocrText;

    @Schema(description = "LLM 提示词")
    private String llmPrompt;

    @Schema(description = "LLM 响应")
    private String llmResponse;

    @Schema(description = "扩展信息")
    private String extInfo;

    @Schema(description = "AI 会话编号", example = "5030")
    private String sessionId;

    @Schema(description = "实验室编号", example = "10839")
    private Long laboratoryId;

    @Schema(description = "版本号", requiredMode = Schema.RequiredMode.REQUIRED)
    private Integer version;

    @Schema(description = "创建时间")
    private LocalDateTime createTime;

}
