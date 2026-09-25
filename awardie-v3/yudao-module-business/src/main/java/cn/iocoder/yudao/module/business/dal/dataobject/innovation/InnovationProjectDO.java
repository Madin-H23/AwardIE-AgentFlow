package cn.iocoder.yudao.module.business.dal.dataobject.innovation;

import cn.iocoder.yudao.framework.mybatis.core.dataobject.BaseDO;
import com.baomidou.mybatisplus.annotation.KeySequence;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;
import lombok.ToString;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * AwardIE 大创项目 DO(批8)
 *
 * <p>为何独立于通用成果库:批6 的 AchievementVaultService 用 JdbcTemplate 按类型分派,
 * 列表/编辑/删除够用,但大创还需要导入事务、status 校准、学生关联建立——
 * 这些都需要按租户与逻辑删除精确控制,通用分派承载不了。
 *
 * <p>JSON 列(other_members)按 String 承载,出入参转换在 service 层。
 *
 * @author AwardIE
 * <p>
 * KeySequence 用于 Oracle、PostgreSQL、Kingbase、DB2、H2 数据库的主键自增;MySQL 等数据库可不写。
 */
@TableName("awardie_innovation_projects")
@KeySequence("awardie_innovation_projects_seq")
@Data
@EqualsAndHashCode(callSuper = true)
@ToString(callSuper = true)
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class InnovationProjectDO extends BaseDO {

    /** 状态:进行中 */
    public static final String STATUS_ONGOING = "进行中";
    /** 状态:已结题 */
    public static final String STATUS_FINISHED = "已结题";
    /** 状态:终止 */
    public static final String STATUS_TERMINATED = "终止";

    /**
     * 主键
     */
    @TableId
    private Long id;
    /**
     * 项目编号(导入幂等判据,全表唯一)
     */
    private String projectNo;
    /**
     * 项目名称
     */
    private String projectName;
    /**
     * 项目类型(国家级/省级/院级)
     */
    private String projectType;
    /**
     * 开始日期(VARCHAR,沿 v2:历史数据格式混杂,不强制 ISO)
     */
    private String startDate;
    /**
     * 结束日期(VARCHAR,同上;status 校准按此字段判定)
     */
    private String endDate;
    /**
     * 学生负责人姓名
     */
    private String studentLeaderName;
    /**
     * 学生负责人学号
     */
    private String studentLeaderId;
    /**
     * 其他成员(JSON 数组字符串)
     */
    private String otherMembers;
    /**
     * 指导教师
     */
    private String supervisors;
    /**
     * 资助金额(单位:元;导入时按万元 ×10000 换算)
     */
    private BigDecimal fundingAmount;
    /**
     * 状态(进行中/已结题/终止)
     */
    private String status;
    /**
     * 提交人类型(admin)
     */
    private String submitterType;
    /**
     * 提交人编号
     */
    private Long submitterId;
    /**
     * 提交时间
     */
    private LocalDateTime submitTime;
    /**
     * 实验室编号
     */
    private Long laboratoryId;
    /**
     * 租户编号(MyBatis-Plus 租户拦截器只对 TenantBaseDO 生效,本 DO 用 BaseDO,
     * 故租户条件由 service 显式携带,见 InnovationService)
     */
    private Long tenantId;

}
