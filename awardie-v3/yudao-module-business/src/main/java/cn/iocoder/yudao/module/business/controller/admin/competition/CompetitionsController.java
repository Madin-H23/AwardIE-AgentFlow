package cn.iocoder.yudao.module.business.controller.admin.competition;

import org.springframework.web.bind.annotation.*;
import jakarta.annotation.Resource;
import org.springframework.validation.annotation.Validated;
import org.springframework.security.access.prepost.PreAuthorize;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.Operation;

import jakarta.validation.constraints.*;
import jakarta.validation.*;
import jakarta.servlet.http.*;
import java.util.*;
import java.io.IOException;

import cn.iocoder.yudao.framework.common.pojo.PageParam;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.common.pojo.CommonResult;
import cn.iocoder.yudao.framework.common.util.object.BeanUtils;
import static cn.iocoder.yudao.framework.common.pojo.CommonResult.success;

import cn.iocoder.yudao.framework.excel.core.util.ExcelUtils;

import cn.iocoder.yudao.framework.apilog.core.annotation.ApiAccessLog;
import static cn.iocoder.yudao.framework.apilog.core.enums.OperateTypeEnum.*;

import cn.iocoder.yudao.module.business.controller.admin.competition.vo.*;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import cn.iocoder.yudao.module.business.service.competition.CompetitionsService;

/**
 * 管理后台 - AwardIE 竞赛
 *
 * @author AwardIE
 */
@Tag(name = "管理后台 - AwardIE 竞赛")
@RestController
@RequestMapping("/business/competitions")
@Validated
public class CompetitionsController {

    @Resource
    private CompetitionsService competitionsService;

    @PostMapping("/create")
    @Operation(summary = "创建AwardIE 竞赛")
    @PreAuthorize("@ss.hasPermission('business:competitions:create')")
    public CommonResult<Long> createCompetitions(@Valid @RequestBody CompetitionsSaveReqVO createReqVO) {
        return success(competitionsService.createCompetitions(createReqVO));
    }

    @PutMapping("/update")
    @Operation(summary = "更新AwardIE 竞赛")
    @PreAuthorize("@ss.hasPermission('business:competitions:update')")
    public CommonResult<Boolean> updateCompetitions(@Valid @RequestBody CompetitionsSaveReqVO updateReqVO) {
        competitionsService.updateCompetitions(updateReqVO);
        return success(true);
    }

    @DeleteMapping("/delete")
    @Operation(summary = "删除AwardIE 竞赛")
    @Parameter(name = "id", description = "编号", required = true)
    @PreAuthorize("@ss.hasPermission('business:competitions:delete')")
    public CommonResult<Boolean> deleteCompetitions(@RequestParam("id") Long id) {
        competitionsService.deleteCompetitions(id);
        return success(true);
    }

    @DeleteMapping("/delete-list")
    @Parameter(name = "ids", description = "编号", required = true)
    @Operation(summary = "批量删除AwardIE 竞赛")
                @PreAuthorize("@ss.hasPermission('business:competitions:delete')")
    public CommonResult<Boolean> deleteCompetitionsList(@RequestParam("ids") List<Long> ids) {
        competitionsService.deleteCompetitionsListByIds(ids);
        return success(true);
    }

    @GetMapping("/get")
    @Operation(summary = "获得AwardIE 竞赛")
    @Parameter(name = "id", description = "编号", required = true, example = "1024")
    @PreAuthorize("@ss.hasPermission('business:competitions:query')")
    public CommonResult<CompetitionsRespVO> getCompetitions(@RequestParam("id") Long id) {
        CompetitionsDO competitions = competitionsService.getCompetitions(id);
        return success(BeanUtils.toBean(competitions, CompetitionsRespVO.class));
    }

    @GetMapping("/page")
    @Operation(summary = "获得AwardIE 竞赛分页")
    @PreAuthorize("@ss.hasPermission('business:competitions:query')")
    public CommonResult<PageResult<CompetitionsRespVO>> getCompetitionsPage(@Valid CompetitionsPageReqVO pageReqVO) {
        PageResult<CompetitionsDO> pageResult = competitionsService.getCompetitionsPage(pageReqVO);
        return success(BeanUtils.toBean(pageResult, CompetitionsRespVO.class));
    }

    @GetMapping("/export-excel")
    @Operation(summary = "导出AwardIE 竞赛 Excel")
    @PreAuthorize("@ss.hasPermission('business:competitions:export')")
    @ApiAccessLog(operateType = EXPORT)
    public void exportCompetitionsExcel(@Valid CompetitionsPageReqVO pageReqVO,
              HttpServletResponse response) throws IOException {
        pageReqVO.setPageSize(PageParam.PAGE_SIZE_NONE);
        List<CompetitionsDO> list = competitionsService.getCompetitionsPage(pageReqVO).getList();
        // 导出 Excel
        ExcelUtils.write(response, "AwardIE 竞赛.xls", "数据", CompetitionsRespVO.class,
                        BeanUtils.toBean(list, CompetitionsRespVO.class));
    }

}
