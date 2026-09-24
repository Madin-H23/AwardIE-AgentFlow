package cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo;

import lombok.*;
import java.util.*;
import io.swagger.v3.oas.annotations.media.Schema;
import cn.iocoder.yudao.framework.common.pojo.PageParam;
import org.springframework.format.annotation.DateTimeFormat;
import java.time.LocalDateTime;

import static cn.iocoder.yudao.framework.common.util.date.DateUtils.FORMAT_YEAR_MONTH_DAY_HOUR_MINUTE_SECOND;

/**
 * 管理后台 - AwardIE 待审成果分页 Request VO
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 待审成果分页 Request VO")
@Data
public class PendingAchievementPageReqVO extends PageParam {

    @Schema(description = "成果类型(award/patent/software/innovation/other)", example = "award")
    private String achievementType;

    @Schema(description = "提交人类型(student/teacher/admin)", example = "student")
    private String submitterType;

    @Schema(description = "状态(pending/archived/rejected)", example = "pending")
    private String status;

    @Schema(description = "提交人编号(我的提交按当前登录用户填充)")
    private Long submitterId;

    @Schema(description = "创建时间")
    @DateTimeFormat(pattern = FORMAT_YEAR_MONTH_DAY_HOUR_MINUTE_SECOND)
    private LocalDateTime[] createTime;

}