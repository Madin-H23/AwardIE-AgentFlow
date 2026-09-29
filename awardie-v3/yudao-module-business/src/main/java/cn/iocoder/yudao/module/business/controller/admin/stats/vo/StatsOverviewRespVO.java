package cn.iocoder.yudao.module.business.controller.admin.stats.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.Map;

/**
 * 管理后台 - 统计分析总览 Response VO(批9)
 *
 * <p>维度现状(批20 订正):实验室维度见 by-laboratory(批16);教师维度见
 * by-teacher(批20,文本匹配 FIND_IN_SET);年份趋势仍未做——物化链不写 year
 * (欠账 D-16 剩余项),待补齐后再上。
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - 统计分析总览 Response VO")
@Data
public class StatsOverviewRespVO {

    @Schema(description = "汇总指标")
    private Summary summary;

    @Schema(description = "五类成果分类计数(award/patent/software/innovation/other)")
    private Map<String, Long> category;

    @Schema(description = "汇总指标")
    @Data
    public static class Summary {

        @Schema(description = "成果总数(五类合计)", requiredMode = Schema.RequiredMode.REQUIRED, example = "42")
        private Long awardsTotal;

        @Schema(description = "待审核数(status=pending)", requiredMode = Schema.RequiredMode.REQUIRED, example = "5")
        private Long pendingSubmit;

        @Schema(description = "用户数", requiredMode = Schema.RequiredMode.REQUIRED, example = "1834")
        private Long usersTotal;

        @Schema(description = "竞赛数", requiredMode = Schema.RequiredMode.REQUIRED, example = "218")
        private Long competitionsTotal;

        @Schema(description = "白名单竞赛数", requiredMode = Schema.RequiredMode.REQUIRED, example = "30")
        private Long whitelist;
    }

}
