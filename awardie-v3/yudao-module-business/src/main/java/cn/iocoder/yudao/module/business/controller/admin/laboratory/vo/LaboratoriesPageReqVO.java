package cn.iocoder.yudao.module.business.controller.admin.laboratory.vo;

import lombok.*;
import java.util.*;
import io.swagger.v3.oas.annotations.media.Schema;
import cn.iocoder.yudao.framework.common.pojo.PageParam;
import org.springframework.format.annotation.DateTimeFormat;
import java.time.LocalDateTime;

import static cn.iocoder.yudao.framework.common.util.date.DateUtils.FORMAT_YEAR_MONTH_DAY_HOUR_MINUTE_SECOND;

/**
 * 管理后台 - AwardIE 实验室分页 Request VO
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 实验室分页 Request VO")
@Data
public class LaboratoriesPageReqVO extends PageParam {

    @Schema(description = "实验室名称(模糊匹配)", example = "网安")
    private String name;

    @Schema(description = "创建时间")
    @DateTimeFormat(pattern = FORMAT_YEAR_MONTH_DAY_HOUR_MINUTE_SECOND)
    private LocalDateTime[] createTime;

}