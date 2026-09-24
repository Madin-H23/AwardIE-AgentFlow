package cn.iocoder.yudao.module.business.controller.admin.template.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * 管理后台 - AwardIE 证书模板创建 Request VO(批7)
 *
 * <p>由 controller 以 multipart 接收:样本图走 MultipartFile,其余字段走 @RequestPart JSON。
 * 规则字段为结构化对象/数组,由 service 序列化成 JSON 列存储。
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 证书模板创建 Request VO")
@Data
public class TemplateCreateReqVO {

    @Schema(description = "竞赛编号", requiredMode = Schema.RequiredMode.REQUIRED, example = "1")
    @NotNull(message = "竞赛编号不能为空")
    private Long competitionId;

    @Schema(description = "授予角色(学生/教师)", requiredMode = Schema.RequiredMode.REQUIRED, example = "学生")
    @NotBlank(message = "授予角色不能为空")
    private String grantedRole;

    @Schema(description = "抽取文本最小长度(0=不限)", example = "0")
    private Integer minLength;

    @Schema(description = "抽取文本最大长度(0=不限)", example = "0")
    private Integer maxLength;

    @Schema(description = "关键词(字符串数组)")
    @Size(max = 100, message = "关键词不能超过 100 条")
    private List<@Size(max = 100, message = "单个关键词不能超过 100 字符") String> keywords;

    @Schema(description = "样本文本")
    @Size(max = 20000, message = "样本文本不能超过 20000 字符")
    private String sampleText;

    @Schema(description = "样本抽取结果(对象)")
    private Map<String, Object> sampleExtracted;

    @Schema(description = "默认字段(对象)")
    private Map<String, Object> defaultFields;

    @Schema(description = "交给 LLM 的字段(对象)")
    private Map<String, Object> llmFields;

    @Schema(description = "输出语言", example = "zh")
    @Size(max = 10, message = "语言代码不能超过 10 个字符")
    private String language;

    @Schema(description = "是否需要翻译", example = "false")
    private Boolean needTranslate;

}
