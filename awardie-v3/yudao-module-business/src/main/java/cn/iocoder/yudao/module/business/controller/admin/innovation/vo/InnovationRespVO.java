package cn.iocoder.yudao.module.business.controller.admin.innovation.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 管理后台 - AwardIE 大创 Response VO(批8)
 *
 * <p>other_members 是 V1 口径的对象数组([{姓名,学号}]),不是纯字符串数组——
 * 批8 实测 V1 库存的就是这个格式,统一后 ETL 迁移与新导入的数据格式一致。
 *
 * @author AwardIE
 */
@Schema(description = "管理后台 - AwardIE 大创 Response VO")
@Data
public class InnovationRespVO {

    @Schema(description = "主键", requiredMode = Schema.RequiredMode.REQUIRED, example = "1")
    private Long id;

    @Schema(description = "项目编号", example = "DC-2025-001")
    private String projectNo;

    @Schema(description = "项目名称", requiredMode = Schema.RequiredMode.REQUIRED, example = "智能审稿助手")
    private String projectName;

    @Schema(description = "项目类型(国家级/省级/院级)", example = "省级")
    private String projectType;

    @Schema(description = "状态(进行中/已结题/终止)", requiredMode = Schema.RequiredMode.REQUIRED, example = "进行中")
    private String status;

    @Schema(description = "开始日期", example = "2025-03-01")
    private String startDate;

    @Schema(description = "结束日期", example = "2026-05-31")
    private String endDate;

    @Schema(description = "资助金额(单位:元)", example = "25000.00")
    private BigDecimal fundingAmount;

    @Schema(description = "学生负责人姓名", example = "莫未文")
    private String studentLeaderName;

    @Schema(description = "学生负责人学号", example = "212206030")
    private String studentLeaderId;

    @Schema(description = "其他成员(对象数组:[{姓名,学号}])")
    private List<Map<String, String>> otherMembers;

    @Schema(description = "指导教师", example = "王五,赵六")
    private String supervisors;

    @Schema(description = "实验室编号", example = "1")
    private Long laboratoryId;

    @Schema(description = "提交时间")
    private LocalDateTime submitTime;

    @Schema(description = "创建时间")
    private LocalDateTime createTime;

}
