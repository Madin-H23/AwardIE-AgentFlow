package cn.iocoder.yudao.module.business.controller.admin.template.vo;

import cn.iocoder.yudao.framework.common.pojo.PageParam;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 管理后台 - AwardIE 证书模板分页 Request VO(批7)
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 证书模板分页 Request VO")
@Data
public class TemplatesPageReqVO extends PageParam {

    @Schema(description = "竞赛编号(精确匹配)", example = "1")
    private Long competitionId;

    @Schema(description = "授予角色(精确匹配:学生/教师)", example = "学生")
    private String grantedRole;

}
