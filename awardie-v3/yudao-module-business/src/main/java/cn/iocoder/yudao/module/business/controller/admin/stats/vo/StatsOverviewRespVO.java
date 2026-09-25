package cn.iocoder.yudao.module.business.controller.admin.stats.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.Map;

/**
 * 管理后台 - 统计分析总览 Response VO(批9)
 *
 * <p>本批**不含**年份趋势、实验室维度、教师证书拆分——三者依赖 v3 尚未写入的字段
 * (`awardie_awards.year` / `laboratory_id` / `granted_role`),做了只会得到空数据。
 * 已记为前置债,见 docs 批9 00-需求 F1/F2/F3。
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
