package cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo;

import cn.iocoder.yudao.module.business.dal.dataobject.audit.AchievementAuditLogDO;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 管理后台 - AwardIE 审核时间线 Response VO
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 审核时间线 Response VO")
@Data
public class PendingTimelineRespVO {

    @Schema(description = "留痕编号", example = "1024")
    private Long id;

    @Schema(description = "待审成果编号", example = "7")
    private Long achievementId;

    @Schema(description = "动作码(1 提交/6 通过/7 驳回/8 物化)", example = "6")
    private Integer actionType;

    @Schema(description = "操作人账号", example = "teacher01")
    private String operatorCode;

    @Schema(description = "操作人姓名", example = "张老师")
    private String operatorName;

    @Schema(description = "变更详情 JSON")
    private String changeDetail;

    @Schema(description = "发生时间")
    private LocalDateTime createTime;

    /**
     * 从留痕 DO 转换
     *
     * @param log 留痕
     * @return 响应 VO
     */
    public static PendingTimelineRespVO from(AchievementAuditLogDO log) {
        PendingTimelineRespVO vo = new PendingTimelineRespVO();
        vo.setId(log.getId());
        vo.setAchievementId(log.getAchievementId());
        vo.setActionType(log.getActionType());
        vo.setOperatorCode(log.getOperatorCode());
        vo.setOperatorName(log.getOperatorName());
        vo.setChangeDetail(log.getChangeDetail());
        vo.setCreateTime(log.getCreateTime());
        return vo;
    }

}
