package cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 管理后台 - AwardIE 待审成果审核 Request VO
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 待审成果审核 Request VO")
@Data
public class PendingReviewReqVO {

    /** 审核动作:approve 通过(并物化)/ reject 驳回 */
    public static final String ACTION_APPROVE = "approve";
    public static final String ACTION_REJECT = "reject";

    @Schema(description = "审核动作(approve/reject)", requiredMode = Schema.RequiredMode.REQUIRED, example = "approve")
    @NotBlank(message = "审核动作不能为空")
    private String action;

    @Schema(description = "审核意见;驳回时必填(BR-5)", example = "证书清晰,通过")
    private String comment;

}
