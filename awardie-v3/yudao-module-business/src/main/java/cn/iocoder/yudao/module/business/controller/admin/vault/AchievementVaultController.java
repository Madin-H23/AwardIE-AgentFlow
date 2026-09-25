package cn.iocoder.yudao.module.business.controller.admin.vault;

import cn.iocoder.yudao.framework.common.pojo.CommonResult;
import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.service.vault.AchievementVaultService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.Resource;
import jakarta.validation.Valid;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

import static cn.iocoder.yudao.framework.common.pojo.CommonResult.success;

/**
 * 管理后台 - AwardIE 成果库(批6):五类已入库成果的列表/行编辑/行删除
 *
 * <p>对照 v2 AdminVaultController(Fix-C);区别于 pending 待审池(批4/批5)。
 *
 * @author AwardIE
 */
@Tag(name = "管理后台 - AwardIE 成果库")
@RestController
@RequestMapping("/business/vault")
@Validated
public class AchievementVaultController {

    @Resource
    private AchievementVaultService vaultService;

    /**
     * 五类成果分页列表
     *
     * @param type     成果类型(award/patent/software/innovation/other)
     * @param pageNo   页码
     * @param pageSize 每页条数
     * @param keyword  名称关键词
     * @return list + total
     */
    @GetMapping("/{type}")
    @Operation(summary = "获得 AwardIE 成果库分页列表")
    @Parameter(name = "type", description = "成果类型", required = true, example = "award")
    @PreAuthorize("@ss.hasPermission('business:vault:query')")
    public CommonResult<Map<String, Object>> list(@PathVariable("type") String type,
            @RequestParam(value = "pageNo", defaultValue = "1") Integer pageNo,
            @RequestParam(value = "pageSize", defaultValue = "20") Integer pageSize,
            @RequestParam(value = "keyword", required = false) String keyword) {
        return success(vaultService.list(type, pageNo, pageSize, keyword,
                TenantContextHolder.getRequiredTenantId()));
    }

    /**
     * 行编辑(各表可编辑列白名单)
     *
     * @param type   成果类型
     * @param id     记录编号
     * @param fields 可更新字段
     * @return 是否成功
     */
    @PostMapping("/{type}/{id}/update")
    @Operation(summary = "编辑 AwardIE 成果库行")
    @Parameter(name = "type", description = "成果类型", required = true)
    @Parameter(name = "id", description = "编号", required = true)
    @PreAuthorize("@ss.hasPermission('business:vault:update')")
    public CommonResult<Boolean> update(@PathVariable("type") String type, @PathVariable("id") Long id,
            @Valid @RequestBody Map<String, Object> fields) {
        return success(vaultService.update(type, id, fields,
                TenantContextHolder.getRequiredTenantId()) > 0);
    }

    /**
     * 行删除(有引用时拒绝)
     *
     * @param type 成果类型
     * @param id   记录编号
     * @return 是否成功
     */
    @DeleteMapping("/{type}/{id}")
    @Operation(summary = "删除 AwardIE 成果库行")
    @Parameter(name = "type", description = "成果类型", required = true)
    @Parameter(name = "id", description = "编号", required = true)
    @PreAuthorize("@ss.hasPermission('business:vault:delete')")
    public CommonResult<Boolean> delete(@PathVariable("type") String type, @PathVariable("id") Long id) {
        return success(vaultService.delete(type, id, TenantContextHolder.getRequiredTenantId()) > 0);
    }

}
