package cn.iocoder.yudao.module.business.controller.admin.laboratory.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.*;
import java.util.*;
import jakarta.validation.constraints.*;

/**
 * 管理后台 - AwardIE 实验室新增/修改 Request VO
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 实验室新增/修改 Request VO")
@Data
public class LaboratoriesSaveReqVO {

    @Schema(description = "主键", requiredMode = Schema.RequiredMode.REQUIRED, example = "7245")
    private Long id;

    @Schema(description = "实验室名称", requiredMode = Schema.RequiredMode.REQUIRED, example = "芋艿")
    @NotEmpty(message = "实验室名称不能为空")
    private String name;

    @Schema(description = "实验室描述", example = "随便")
    private String description;

}