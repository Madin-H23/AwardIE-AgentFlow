package cn.iocoder.yudao.module.business.controller.admin.log.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 管理后台 - 业务审计日志 Response VO(批9)
 *
 * <p>{@code actionLabel} 是给管理员看的中文标签——v2 前端也只对 1/6/7/8 做标签映射,
 * 历史码 2-5/9-12 在 v2 Java 里从未产出(取证确认),故本批同样只映射四个,未知码兜底为
 * "动作 {code}" 而不是空白。
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - 业务审计日志 Response VO")
@Data
public class AuditLogRespVO {

    @Schema(description = "主键", requiredMode = Schema.RequiredMode.REQUIRED, example = "1")
    private Long id;

    @Schema(description = "待审成果编号", requiredMode = Schema.RequiredMode.REQUIRED, example = "1")
    private Long achievementId;

    @Schema(description = "成果类型", example = "award")
    private String achievementKind;

    @Schema(description = "动作码", requiredMode = Schema.RequiredMode.REQUIRED, example = "6")
    private Integer actionType;

    @Schema(description = "动作中文标签", requiredMode = Schema.RequiredMode.REQUIRED, example = "审核通过")
    private String actionLabel;

    @Schema(description = "动作结果(0 失败/1 成功)", requiredMode = Schema.RequiredMode.REQUIRED, example = "1")
    private Integer actionResult;

    @Schema(description = "操作人编号", example = "1")
    private Long operatorId;

    @Schema(description = "操作人账号", example = "admin")
    private String operatorCode;

    @Schema(description = "操作人姓名", example = "系统管理员")
    private String operatorName;

    @Schema(description = "备注/变更说明", example = "通过")
    private String remark;

    @Schema(description = "变更详情 JSON 文本(提交/审核/驳回意见;驳回原因只在这里)")
    private String changeDetail;

    @Schema(description = "创建时间", requiredMode = Schema.RequiredMode.REQUIRED)
    private LocalDateTime createTime;

}
