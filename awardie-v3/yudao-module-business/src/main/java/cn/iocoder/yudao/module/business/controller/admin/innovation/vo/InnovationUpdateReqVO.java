package cn.iocoder.yudao.module.business.controller.admin.innovation.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 管理后台 - AwardIE 大创更新 Request VO(批8,status 方向1)
 *
 * <p>status 与 projectType 留空表示"不改"——批量校准之外的零散修正走这个端点,
 * 管理员只想改个状态时不必把全字段重传一遍。
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 大创更新 Request VO")
@Data
public class InnovationUpdateReqVO {

    @Schema(description = "项目编号")
    @Size(max = 50, message = "项目编号不能超过 50 字符")
    private String projectNo;

    @Schema(description = "项目名称")
    @Size(max = 200, message = "项目名称不能超过 200 字符")
    private String projectName;

    @Schema(description = "项目类型(国家级/省级/院级)")
    @Size(max = 20, message = "项目类型不能超过 20 字符")
    private String projectType;

    @Schema(description = "状态(进行中/已结题/终止)")
    @Size(max = 20, message = "状态不能超过 20 字符")
    private String status;

    @Schema(description = "开始日期")
    @Size(max = 10, message = "开始日期不能超过 10 字符")
    private String startDate;

    @Schema(description = "结束日期")
    @Size(max = 10, message = "结束日期不能超过 10 字符")
    private String endDate;

    @Schema(description = "资助金额(单位:元)")
    @DecimalMin(value = "0", message = "资助金额不能为负")
    private BigDecimal fundingAmount;

    @Schema(description = "学生负责人姓名")
    @Size(max = 50, message = "负责人姓名不能超过 50 字符")
    private String studentLeaderName;

    @Schema(description = "学生负责人学号")
    @Size(max = 50, message = "负责人学号不能超过 50 字符")
    private String studentLeaderId;

    @Schema(description = "指导教师")
    private String supervisors;

    @Schema(description = "实验室编号")
    private Long laboratoryId;

}
