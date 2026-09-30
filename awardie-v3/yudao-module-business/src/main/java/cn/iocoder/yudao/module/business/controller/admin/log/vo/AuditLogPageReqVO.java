package cn.iocoder.yudao.module.business.controller.admin.log.vo;

import cn.iocoder.yudao.framework.common.pojo.PageParam;
import cn.iocoder.yudao.framework.common.validation.InEnum;
import cn.iocoder.yudao.module.business.enums.AuditActionType;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.springframework.format.annotation.DateTimeFormat;

import java.time.LocalDateTime;

import static cn.iocoder.yudao.framework.common.util.date.DateUtils.FORMAT_YEAR_MONTH_DAY_HOUR_MINUTE_SECOND;

/**
 * 管理后台 - 业务审计日志分页 Request VO(批9;批27 D-21 补过滤参数校验)
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - 业务审计日志分页 Request VO")
@Data
@EqualsAndHashCode(callSuper = true)
public class AuditLogPageReqVO extends PageParam {

    /**
     * 允许为空串:前端 el-select clearable 清空筛选时发的是空串,拦掉会把合法请求打死
     */
    @Schema(description = "成果类型(award/patent/software/innovation/other)", example = "award")
    @Pattern(regexp = "^(award|patent|software|innovation|other)?$",
            message = "成果类型只能是 award/patent/software/innovation/other")
    private String achievementKind;

    @Schema(description = "动作码(1 提交/6 审核通过/7 驳回/8 物化入库)", example = "6")
    @InEnum(value = AuditActionType.class, message = "动作码只能是 1 提交/6 审核通过/7 驳回/8 物化入库")
    private Integer actionType;

    @Schema(description = "操作人关键词(姓名或账号模糊匹配)", example = "张")
    @Size(max = 50, message = "操作人关键词不能超过 50 个字符")
    private String operatorKeyword;

    @Schema(description = "创建时间区间")
    @DateTimeFormat(pattern = FORMAT_YEAR_MONTH_DAY_HOUR_MINUTE_SECOND)
    private LocalDateTime[] createTime;

}
