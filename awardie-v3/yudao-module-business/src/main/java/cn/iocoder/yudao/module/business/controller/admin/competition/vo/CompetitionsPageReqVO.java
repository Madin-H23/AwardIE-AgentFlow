package cn.iocoder.yudao.module.business.controller.admin.competition.vo;

import lombok.*;
import java.util.*;
import io.swagger.v3.oas.annotations.media.Schema;
import cn.iocoder.yudao.framework.common.pojo.PageParam;
import org.springframework.format.annotation.DateTimeFormat;
import java.time.LocalDateTime;

import static cn.iocoder.yudao.framework.common.util.date.DateUtils.FORMAT_YEAR_MONTH_DAY_HOUR_MINUTE_SECOND;

/**
 * 管理后台 - AwardIE 竞赛分页 Request VO
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 竞赛分页 Request VO")
@Data
public class CompetitionsPageReqVO extends PageParam {

    @Schema(description = "竞赛名称(模糊匹配)", example = "挑战杯")
    private String competitionName;

    @Schema(description = "是否白名单")
    private Boolean whiteList;

    @Schema(description = "是否观察名单")
    private Boolean watchList;

    @Schema(description = "是否自动创建")
    private Boolean isAutoAdded;

    @Schema(description = "创建时间")
    @DateTimeFormat(pattern = FORMAT_YEAR_MONTH_DAY_HOUR_MINUTE_SECOND)
    private LocalDateTime[] createTime;

}