package cn.iocoder.yudao.module.business.controller.admin.template;

import cn.iocoder.yudao.framework.common.pojo.CommonResult;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateCreateReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateUpdateReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplatesPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplatesRespVO;
import cn.iocoder.yudao.module.business.dal.dataobject.template.TemplatesDO;
import cn.iocoder.yudao.module.business.service.template.TemplateAiService;
import cn.iocoder.yudao.module.business.service.template.TemplateService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpHeaders;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.OutputStream;
import java.util.Map;

import static cn.iocoder.yudao.framework.common.pojo.CommonResult.success;

/**
 * 管理后台 - AwardIE 证书模板(批7)
 *
 * <p>对照 v2 AdminTemplateDetailController + AdminConsoleController 的 8 个端点:
 * 路由改为芋道风格,补删除端点,AI 三端点分离为独立路径。
 * 样本图回显与 AI 端点归 query 权限(AI 是模板编辑的辅助动作)。
 *
 * @author AwardIE
 */
@Tag(name = "管理后台 - AwardIE 证书模板")
@RestController
@RequestMapping("/business/templates")
@Validated
public class TemplateController {

    @Resource
    private TemplateService templateService;
    @Resource
    private TemplateAiService templateAiService;

    @GetMapping("/page")
    @Operation(summary = "获得 AwardIE 证书模板分页列表")
    @PreAuthorize("@ss.hasPermission('business:templates:query')")
    public CommonResult<PageResult<TemplatesRespVO>> getTemplatePage(@Valid TemplatesPageReqVO pageReqVO) {
        return success(templateService.getTemplatePage(pageReqVO));
    }

    @GetMapping("/get")
    @Operation(summary = "获得 AwardIE 证书模板详情")
    @Parameter(name = "id", description = "模板编号", required = true, example = "1")
    @PreAuthorize("@ss.hasPermission('business:templates:query')")
    public CommonResult<TemplatesRespVO> getTemplate(@RequestParam("id") Long id) {
        return success(templateService.getTemplate(id));
    }

    @PostMapping("/create")
    @Operation(summary = "创建 AwardIE 证书模板")
    @PreAuthorize("@ss.hasPermission('business:templates:create')")
    public CommonResult<Long> createTemplate(@RequestPart("file") MultipartFile file,
            @Valid @RequestPart("data") TemplateCreateReqVO createReqVO) throws IOException {
        return success(templateService.createTemplate(createReqVO, file.getOriginalFilename(), file.getBytes()));
    }

    @PutMapping("/update")
    @Operation(summary = "更新 AwardIE 证书模板(仅规则字段)")
    @Parameter(name = "id", description = "模板编号", required = true, example = "1")
    @PreAuthorize("@ss.hasPermission('business:templates:update')")
    public CommonResult<Boolean> updateTemplate(@RequestParam("id") Long id,
            @Valid @RequestBody TemplateUpdateReqVO updateReqVO) {
        templateService.updateTemplate(id, updateReqVO);
        return success(true);
    }

    @DeleteMapping("/delete")
    @Operation(summary = "删除 AwardIE 证书模板")
    @Parameter(name = "id", description = "模板编号", required = true, example = "1")
    @PreAuthorize("@ss.hasPermission('business:templates:delete')")
    public CommonResult<Boolean> deleteTemplate(@RequestParam("id") Long id) {
        templateService.deleteTemplate(id);
        return success(true);
    }

    @GetMapping("/image")
    @Operation(summary = "回显 AwardIE 证书模板样本图")
    @Parameter(name = "id", description = "模板编号", required = true, example = "1")
    @PreAuthorize("@ss.hasPermission('business:templates:query')")
    public void getTemplateImage(@RequestParam("id") Long id, HttpServletResponse response) throws IOException {
        byte[] bytes = templateService.getSampleImage(id);
        response.setContentType(templateService.getSampleImageContentType(id));
        response.setHeader(HttpHeaders.CACHE_CONTROL, "no-store");
        try (OutputStream out = response.getOutputStream()) {
            out.write(bytes);
        }
    }

    @PostMapping("/test")
    @Operation(summary = "证书模板试测(按已保存样本图跑 AI 抽取)")
    @Parameter(name = "id", description = "模板编号", required = true, example = "1")
    @PreAuthorize("@ss.hasPermission('business:templates:query')")
    public CommonResult<Map<String, Object>> testTemplate(@RequestParam("id") Long id) throws IOException {
        TemplatesDO template = templateService.getTemplateDO(id);
        byte[] imageBytes = templateService.getSampleImage(id);
        // Worker 按 filename 推断临时文件后缀以选 OCR 引擎,故保留存储路径里的真实扩展名
        String storedName = template.getSampleImagePath();
        String extension = storedName.contains(".") ? storedName.substring(storedName.lastIndexOf('.')) : ".png";
        return success(templateAiService.testTemplate(template, imageBytes, "sample" + extension));
    }

    @PostMapping("/extract-for-create")
    @Operation(summary = "创建前 AI 抽取(不落库)")
    @PreAuthorize("@ss.hasPermission('business:templates:query')")
    public CommonResult<Map<String, Object>> extractForCreate(@RequestPart("file") MultipartFile file,
            @RequestParam(value = "ruleJson", required = false) @Size(max = 20000, message = "规则 JSON 过长")
            String ruleJson) throws IOException {
        return success(templateAiService.extractForCreate(file.getBytes(), file.getOriginalFilename(), ruleJson));
    }

    @PostMapping("/generate-prompt")
    @Operation(summary = "生成抽取 prompt")
    @PreAuthorize("@ss.hasPermission('business:templates:query')")
    public CommonResult<Map<String, Object>> generatePrompt(
            @RequestParam(value = "ruleJson", required = false) @Size(max = 20000, message = "规则 JSON 过长")
            String ruleJson,
            @RequestParam(value = "sampleText", required = false) @Size(max = 20000, message = "样本文本过长")
            String sampleText) {
        return success(templateAiService.generatePrompt(ruleJson, sampleText));
    }

}
