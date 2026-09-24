package cn.iocoder.yudao.module.business.controller.admin.template.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * 管理后台 - AwardIE 证书模板更新 Request VO(批7)
 *
 * <p>编辑白名单:只接受规则字段。**grantedRole 与 competitionId 不在这里**——
 * v2 能通过改 defaultFields 把 granted_role 改掉从而绕过唯一性,那是缺陷不是语义,本批修掉。
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 证书模板更新 Request VO")
@Data
public class TemplateUpdateReqVO {

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
