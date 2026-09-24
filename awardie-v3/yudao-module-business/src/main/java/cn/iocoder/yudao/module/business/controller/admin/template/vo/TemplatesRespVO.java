package cn.iocoder.yudao.module.business.controller.admin.template.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 管理后台 - AwardIE 证书模板 Response VO(批7)
 *
 * <p>JSON 规则字段在这里是**结构化对象/数组**而非 JSON 字符串——v2 出入参都是字符串,
 * 前端还得二次 decode,且 keywords 存的时候就存成了 JSON 字符串,读出来再解一层,
 * 前后端契约错位(前端发字符串、后端要数组)。本批统一为结构化。
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 证书模板 Response VO")
@Data
public class TemplatesRespVO {

    @Schema(description = "主键", requiredMode = Schema.RequiredMode.REQUIRED, example = "1")
    private Long id;

    @Schema(description = "模板类型", requiredMode = Schema.RequiredMode.REQUIRED, example = "AWARD")
    private String templateType;

    @Schema(description = "竞赛编号", requiredMode = Schema.RequiredMode.REQUIRED, example = "1")
    private Long competitionId;

    @Schema(description = "竞赛名称", requiredMode = Schema.RequiredMode.REQUIRED, example = "挑战杯")
    private String competitionName;

    @Schema(description = "授予角色", requiredMode = Schema.RequiredMode.REQUIRED, example = "学生")
    private String grantedRole;

    @Schema(description = "抽取文本最小长度(0=不限)", requiredMode = Schema.RequiredMode.REQUIRED, example = "0")
    private Integer minLength;

    @Schema(description = "抽取文本最大长度(0=不限)", requiredMode = Schema.RequiredMode.REQUIRED, example = "0")
    private Integer maxLength;

    @Schema(description = "关键词(字符串数组)")
    private List<String> keywords;

    @Schema(description = "样本文本")
    private String sampleText;

    @Schema(description = "样本抽取结果(对象)")
    private Map<String, Object> sampleExtracted;

    @Schema(description = "默认字段(对象)")
    private Map<String, Object> defaultFields;

    @Schema(description = "交给 LLM 的字段(对象)")
    private Map<String, Object> llmFields;

    @Schema(description = "输出语言", requiredMode = Schema.RequiredMode.REQUIRED, example = "zh")
    private String language;

    @Schema(description = "是否需要翻译", requiredMode = Schema.RequiredMode.REQUIRED, example = "false")
    private Boolean needTranslate;

    @Schema(description = "是否有样本图", requiredMode = Schema.RequiredMode.REQUIRED, example = "true")
    private Boolean hasImage;

    @Schema(description = "创建时间")
    private LocalDateTime createTime;

}
