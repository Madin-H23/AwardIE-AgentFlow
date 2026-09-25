package cn.iocoder.yudao.module.business.controller.admin.log;

import cn.iocoder.yudao.framework.common.pojo.CommonResult;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.module.business.controller.admin.log.vo.AuditLogPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.log.vo.AuditLogRespVO;
import cn.iocoder.yudao.module.business.service.audit.AuditLogService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.Resource;
import jakarta.validation.Valid;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import static cn.iocoder.yudao.framework.common.pojo.CommonResult.success;

/**
 * 管理后台 - 业务审计日志(批9)
 *
 * <p>只查 v3 业务审核留痕(awardie_achievement_audit_log)。芋道 infra/system 自带的
 * 访问日志、错误日志、操作日志**不在本端点聚合**——它们是框架层日志,与业务成果动作
 * 语义不同,硬凑成一张"总日志"会让两套语义混淆。需要统一视图时另排"日志中心"。
 *
 * @author AwardIE
 */
@Tag(name = "管理后台 - 业务审计日志")
@RestController
@RequestMapping("/business/logs")
@Validated
public class AuditLogController {

    @Resource
    private AuditLogService auditLogService;

    @GetMapping("/audit")
    @Operation(summary = "获得业务审计日志分页")
    @PreAuthorize("@ss.hasPermission('business:logs:query')")
    public CommonResult<PageResult<AuditLogRespVO>> getAuditLogPage(@Valid AuditLogPageReqVO pageReqVO) {
        return success(auditLogService.getAuditLogPage(pageReqVO));
    }

}
