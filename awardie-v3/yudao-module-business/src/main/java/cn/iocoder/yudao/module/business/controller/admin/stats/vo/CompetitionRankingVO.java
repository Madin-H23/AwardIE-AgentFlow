package cn.iocoder.yudao.module.business.controller.admin.stats.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 管理后台 - 竞赛战果排行 Response VO(批9)
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - 竞赛战果排行 Response VO")
@Data
public class CompetitionRankingVO {

    @Schema(description = "竞赛名称(无关联竞赛的成果归入\"未关联\")", requiredMode = Schema.RequiredMode.REQUIRED,
            example = "挑战杯")
    private String name;

    @Schema(description = "成果数", requiredMode = Schema.RequiredMode.REQUIRED, example = "15")
    private Long total;

}
