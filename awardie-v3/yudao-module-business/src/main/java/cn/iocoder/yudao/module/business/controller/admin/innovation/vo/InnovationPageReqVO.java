package cn.iocoder.yudao.module.business.controller.admin.innovation.vo;

import cn.iocoder.yudao.framework.common.pojo.PageParam;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 管理后台 - AwardIE 大创分页 Request VO(批8)
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 大创分页 Request VO")
@Data
public class InnovationPageReqVO extends PageParam {

    @Schema(description = "项目状态(进行中/已结题/终止)", example = "进行中")
    private String status;

    @Schema(description = "项目类型(国家级/省级/院级)", example = "省级")
    private String projectType;

    @Schema(description = "项目名称(模糊匹配)", example = "智能审稿")
    private String projectName;

}
