package cn.iocoder.yudao.module.business.controller.admin.laboratory;

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

import cn.iocoder.yudao.module.business.controller.admin.laboratory.vo.*;
import cn.iocoder.yudao.module.business.dal.dataobject.laboratory.LaboratoriesDO;
import cn.iocoder.yudao.module.business.service.laboratory.LaboratoriesService;

@Tag(name = "管理后台 - AwardIE 实验室")
@RestController
@RequestMapping("/business/laboratories")
@Validated
public class LaboratoriesController {

    @Resource
    private LaboratoriesService laboratoriesService;

    @PostMapping("/create")
    @Operation(summary = "创建AwardIE 实验室")
    @PreAuthorize("@ss.hasPermission('business:laboratories:create')")
    public CommonResult<Long> createLaboratories(@Valid @RequestBody LaboratoriesSaveReqVO createReqVO) {
        return success(laboratoriesService.createLaboratories(createReqVO));
    }

    @PutMapping("/update")
    @Operation(summary = "更新AwardIE 实验室")
    @PreAuthorize("@ss.hasPermission('business:laboratories:update')")
    public CommonResult<Boolean> updateLaboratories(@Valid @RequestBody LaboratoriesSaveReqVO updateReqVO) {
        laboratoriesService.updateLaboratories(updateReqVO);
        return success(true);
    }

    @DeleteMapping("/delete")
    @Operation(summary = "删除AwardIE 实验室")
    @Parameter(name = "id", description = "编号", required = true)
    @PreAuthorize("@ss.hasPermission('business:laboratories:delete')")
    public CommonResult<Boolean> deleteLaboratories(@RequestParam("id") Long id) {
        laboratoriesService.deleteLaboratories(id);
        return success(true);
    }

    @DeleteMapping("/delete-list")
    @Parameter(name = "ids", description = "编号", required = true)
    @Operation(summary = "批量删除AwardIE 实验室")
                @PreAuthorize("@ss.hasPermission('business:laboratories:delete')")
    public CommonResult<Boolean> deleteLaboratoriesList(@RequestParam("ids") List<Long> ids) {
        laboratoriesService.deleteLaboratoriesListByIds(ids);
        return success(true);
    }

    @GetMapping("/get")
    @Operation(summary = "获得AwardIE 实验室")
    @Parameter(name = "id", description = "编号", required = true, example = "1024")
    @PreAuthorize("@ss.hasPermission('business:laboratories:query')")
    public CommonResult<LaboratoriesRespVO> getLaboratories(@RequestParam("id") Long id) {
        LaboratoriesDO laboratories = laboratoriesService.getLaboratories(id);
        return success(BeanUtils.toBean(laboratories, LaboratoriesRespVO.class));
    }

    @GetMapping("/page")
    @Operation(summary = "获得AwardIE 实验室分页")
    @PreAuthorize("@ss.hasPermission('business:laboratories:query')")
    public CommonResult<PageResult<LaboratoriesRespVO>> getLaboratoriesPage(@Valid LaboratoriesPageReqVO pageReqVO) {
        PageResult<LaboratoriesDO> pageResult = laboratoriesService.getLaboratoriesPage(pageReqVO);
        return success(BeanUtils.toBean(pageResult, LaboratoriesRespVO.class));
    }

    @GetMapping("/export-excel")
    @Operation(summary = "导出AwardIE 实验室 Excel")
    @PreAuthorize("@ss.hasPermission('business:laboratories:export')")
    @ApiAccessLog(operateType = EXPORT)
    public void exportLaboratoriesExcel(@Valid LaboratoriesPageReqVO pageReqVO,
              HttpServletResponse response) throws IOException {
        pageReqVO.setPageSize(PageParam.PAGE_SIZE_NONE);
        List<LaboratoriesDO> list = laboratoriesService.getLaboratoriesPage(pageReqVO).getList();
        // 导出 Excel
        ExcelUtils.write(response, "AwardIE 实验室.xls", "数据", LaboratoriesRespVO.class,
                        BeanUtils.toBean(list, LaboratoriesRespVO.class));
    }

}