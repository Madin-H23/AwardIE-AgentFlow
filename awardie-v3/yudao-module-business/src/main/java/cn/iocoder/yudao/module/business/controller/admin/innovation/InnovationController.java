package cn.iocoder.yudao.module.business.controller.admin.innovation;

import cn.iocoder.yudao.framework.common.pojo.CommonResult;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.controller.admin.innovation.vo.InnovationPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.innovation.vo.InnovationRespVO;
import cn.iocoder.yudao.module.business.controller.admin.innovation.vo.InnovationUpdateReqVO;
import cn.iocoder.yudao.module.business.service.innovation.InnovationImportService;
import cn.iocoder.yudao.module.business.service.innovation.InnovationService;
import cn.iocoder.yudao.module.business.service.innovation.InnovationStatusService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.Resource;
import jakarta.validation.Valid;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import static cn.iocoder.yudao.framework.common.pojo.CommonResult.success;
import static cn.iocoder.yudao.framework.security.core.util.SecurityFrameworkUtils.getLoginUserId;

/**
 * 管理后台 - AwardIE 大创(批8)
 *
 * <p>五组端点:分页/详情/编辑(status 方向1)+ xlsx 导入 preview/confirm + 状态批量校准(status 方向2)。
 * 大创管理是 admin 专属(与 v2 一致),学生/教师不授权——学生的"我的大创"门户属批10。
 *
 * <p>**不做审核通过自动物化**:v2 的 ReviewService 对 innovation 返回 skipped,
 * v3 沿用该语义(见 00-需求 F1)。
 *
 * @author AwardIE
 */
@Tag(name = "管理后台 - AwardIE 大创")
@RestController
@RequestMapping("/business/innovations")
@Validated
public class InnovationController {

    @Resource
    private InnovationService innovationService;
    @Resource
    private InnovationImportService importService;
    @Resource
    private InnovationStatusService statusService;

    @GetMapping("/page")
    @Operation(summary = "获得 AwardIE 大创分页列表")
    @PreAuthorize("@ss.hasPermission('business:innovation:query')")
    public CommonResult<PageResult<InnovationRespVO>> getInnovationPage(@Valid InnovationPageReqVO pageReqVO) {
        return success(innovationService.getInnovationPage(pageReqVO,
                TenantContextHolder.getRequiredTenantId()));
    }

    @GetMapping("/get")
    @Operation(summary = "获得 AwardIE 大创详情")
    @Parameter(name = "id", description = "项目编号", required = true, example = "1")
    @PreAuthorize("@ss.hasPermission('business:innovation:query')")
    public CommonResult<InnovationRespVO> getInnovation(@RequestParam("id") Long id) {
        return success(innovationService.getInnovation(id, TenantContextHolder.getRequiredTenantId()));
    }

    @PutMapping("/update")
    @Operation(summary = "更新 AwardIE 大创(status 方向1:单项编辑)")
    @Parameter(name = "id", description = "项目编号", required = true, example = "1")
    @PreAuthorize("@ss.hasPermission('business:innovation:update')")
    public CommonResult<Boolean> updateInnovation(@RequestParam("id") Long id,
            @Valid @RequestBody InnovationUpdateReqVO updateReqVO) {
        innovationService.updateInnovation(id, updateReqVO, TenantContextHolder.getRequiredTenantId());
        return success(true);
    }

    @PostMapping("/import/preview")
    @Operation(summary = "大创 xlsx 导入预览(返回一次性令牌,确认时凭令牌取回行数据)")
    @PreAuthorize("@ss.hasPermission('business:innovation:import')")
    public CommonResult<InnovationImportService.ImportPreview> importPreview(
            @RequestPart("file") MultipartFile file) {
        return success(importService.preview(file,
                TenantContextHolder.getRequiredTenantId(), getLoginUserId()));
    }

    @PostMapping("/import/confirm")
    @Operation(summary = "确认导入(凭预览令牌入库,令牌一次性)")
    @PreAuthorize("@ss.hasPermission('business:innovation:import')")
    public CommonResult<InnovationImportService.ImportResult> importConfirm(
            @RequestParam("token") String token) {
        return success(importService.confirm(token, TenantContextHolder.getRequiredTenantId(),
                getLoginUserId()));
    }

    @PostMapping("/calibrate-status")
    @Operation(summary = "大创状态批量校准(status 方向2:结束日期已过的进行中 → 已结题)")
    @PreAuthorize("@ss.hasPermission('business:innovation:calibrate')")
    public CommonResult<InnovationStatusService.CalibrationResult> calibrateStatus() {
        return success(statusService.calibrateEndedProjects(TenantContextHolder.getRequiredTenantId()));
    }

}
