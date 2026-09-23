package cn.iocoder.yudao.module.business.controller.admin.laboratory.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.*;
import java.util.*;
import org.springframework.format.annotation.DateTimeFormat;
import java.time.LocalDateTime;
import cn.idev.excel.annotation.*;

@Schema(description = "管理后台 - AwardIE 实验室 Response VO")
@Data
@ExcelIgnoreUnannotated
public class LaboratoriesRespVO {

    @Schema(description = "主键", requiredMode = Schema.RequiredMode.REQUIRED, example = "7245")
    @ExcelProperty("主键")
    private Long id;

    @Schema(description = "实验室名称", requiredMode = Schema.RequiredMode.REQUIRED, example = "芋艿")
    @ExcelProperty("实验室名称")
    private String name;

    @Schema(description = "实验室描述", example = "随便")
    @ExcelProperty("实验室描述")
    private String description;

    @Schema(description = "创建时间")
    @ExcelProperty("创建时间")
    private LocalDateTime createTime;

}