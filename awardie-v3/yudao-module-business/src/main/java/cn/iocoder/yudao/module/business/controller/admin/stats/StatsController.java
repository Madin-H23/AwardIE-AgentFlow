package cn.iocoder.yudao.module.business.controller.admin.stats;

import cn.iocoder.yudao.framework.common.pojo.CommonResult;
import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.controller.admin.stats.vo.CompetitionRankingVO;
import cn.iocoder.yudao.module.business.controller.admin.stats.vo.StatsOverviewRespVO;
import cn.iocoder.yudao.module.business.service.stats.StatsService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.Resource;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

import static cn.iocoder.yudao.framework.common.pojo.CommonResult.success;

/**
 * 管理后台 - 统计分析(批9)
 *
 * <p>只含数据链完整的维度:汇总计数、五类分类、竞赛 Top。
 * 年份/实验室/教师维度待 v3 补齐物化字段后再加(见 docs 批9 00-需求 F1/F2/F3)。
 *
 * @author AwardIE
 */
@Tag(name = "管理后台 - AwardIE 统计分析")
@RestController
@RequestMapping("/business/stats")
@Validated
public class StatsController {

    @Resource
    private StatsService statsService;

    @GetMapping("/overview")
    @Operation(summary = "获得统计分析总览(汇总 + 五类分类)")
    @PreAuthorize("@ss.hasPermission('business:stats:query')")
    public CommonResult<StatsOverviewRespVO> getOverview() {
        return success(statsService.getOverview(TenantContextHolder.getRequiredTenantId()));
    }

    @GetMapping("/by-competition")
    @Operation(summary = "获得竞赛战果 Top12")
    @PreAuthorize("@ss.hasPermission('business:stats:query')")
    public CommonResult<List<CompetitionRankingVO>> getByCompetition() {
        return success(statsService.getCompetitionRanking(TenantContextHolder.getRequiredTenantId()));
    }

}
