package cn.iocoder.yudao.module.business.controller.admin.competition.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.*;
import java.util.*;
import jakarta.validation.constraints.*;

/**
 * 管理后台 - AwardIE 竞赛新增/修改 Request VO
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 竞赛新增/修改 Request VO")
@Data
public class CompetitionsSaveReqVO {

    @Schema(description = "主键", requiredMode = Schema.RequiredMode.REQUIRED, example = "5396")
    private Long id;

    @Schema(description = "竞赛名称", requiredMode = Schema.RequiredMode.REQUIRED, example = "李四")
    @NotEmpty(message = "竞赛名称不能为空")
    private String competitionName;

    @Schema(description = "官网地址")
    private String officialWebsite;

    @Schema(description = "主办方")
    private String organizer;

    @Schema(description = "竞赛时间(如 4-10月)")
    private String competitionTime;

    @Schema(description = "参赛要求")
    private String participantRequirements;

    @Schema(description = "组别类别")
    private String gradeCategory;

    @Schema(description = "简介", example = "你说的对")
    private String briefDescription;

    @Schema(description = "别名列表(换行分隔)")
    private String aliasList;

    @Schema(description = "是否白名单", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull(message = "是否白名单不能为空")
    private Boolean whiteList;

    @Schema(description = "是否观察名单", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull(message = "是否观察名单不能为空")
    private Boolean watchList;

    // is_auto_added 为系统标记(建档恒 false,由 OCR 抽取链路置位),不由人工维护,故不入 SaveReqVO

}