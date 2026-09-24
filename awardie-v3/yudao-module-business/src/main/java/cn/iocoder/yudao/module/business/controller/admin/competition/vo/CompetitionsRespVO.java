package cn.iocoder.yudao.module.business.controller.admin.competition.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.*;
import java.util.*;
import org.springframework.format.annotation.DateTimeFormat;
import java.time.LocalDateTime;
import cn.idev.excel.annotation.*;

/**
 * 管理后台 - AwardIE 竞赛 Response VO
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 竞赛 Response VO")
@Data
@ExcelIgnoreUnannotated
public class CompetitionsRespVO {

    @Schema(description = "主键", requiredMode = Schema.RequiredMode.REQUIRED, example = "5396")
    @ExcelProperty("主键")
    private Long id;

    @Schema(description = "竞赛名称", requiredMode = Schema.RequiredMode.REQUIRED, example = "李四")
    @ExcelProperty("竞赛名称")
    private String competitionName;

    @Schema(description = "官网地址")
    @ExcelProperty("官网地址")
    private String officialWebsite;

    @Schema(description = "主办方")
    @ExcelProperty("主办方")
    private String organizer;

    @Schema(description = "竞赛时间(如 4-10月)")
    @ExcelProperty("竞赛时间(如 4-10月)")
    private String competitionTime;

    @Schema(description = "参赛要求")
    @ExcelProperty("参赛要求")
    private String participantRequirements;

    @Schema(description = "组别类别")
    @ExcelProperty("组别类别")
    private String gradeCategory;

    @Schema(description = "简介", example = "你说的对")
    @ExcelProperty("简介")
    private String briefDescription;

    @Schema(description = "别名列表(换行分隔)")
    @ExcelProperty("别名列表(换行分隔)")
    private String aliasList;

    @Schema(description = "是否白名单", requiredMode = Schema.RequiredMode.REQUIRED)
    @ExcelProperty("是否白名单")
    private Boolean whiteList;

    @Schema(description = "是否观察名单", requiredMode = Schema.RequiredMode.REQUIRED)
    @ExcelProperty("是否观察名单")
    private Boolean watchList;

    @Schema(description = "是否自动创建", requiredMode = Schema.RequiredMode.REQUIRED)
    @ExcelProperty("是否自动创建")
    private Boolean isAutoAdded;

    @Schema(description = "创建时间")
    @ExcelProperty("创建时间")
    private LocalDateTime createTime;

}
