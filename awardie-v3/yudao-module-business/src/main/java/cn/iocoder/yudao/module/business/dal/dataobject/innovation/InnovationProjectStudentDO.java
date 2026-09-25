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

/**
 * AwardIE 大创项目学生关联 DO(批8)
 *
 * <p>学生门户"我的大创"只查这张表(v2 StudentPortalController 口径):
 * 不按 student_leader_id 临时匹配,故这张表是学生看到自己项目的唯一途径。
 *
 * @author AwardIE
 * <p>
 * KeySequence 用于 Oracle、PostgreSQL、Kingbase、DB2、H2 数据库的主键自增;MySQL 等数据库可不写。
 */
@TableName("awardie_innovation_project_students")
@KeySequence("awardie_innovation_project_students_seq")
@Data
@EqualsAndHashCode(callSuper = true)
@ToString(callSuper = true)
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class InnovationProjectStudentDO extends BaseDO {

    /** 角色:负责人 */
    public static final String ROLE_LEADER = "leader";
    /** 角色:成员 */
    public static final String ROLE_MEMBER = "member";
    /** 匹配方式:学号精确匹配 */
    public static final String MATCH_STUDENT_ID_EXACT = "student_id_exact";

    /**
     * 主键
     */
    @TableId
    private Long id;
    /**
     * 大创项目编号
     */
    private Long projectId;
    /**
     * 学生编号(系统用户)
     */
    private Long studentId;
    /**
     * 角色(leader/member)
     */
    private String role;
    /**
     * 学生姓名
     */
    private String studentName;
    /**
     * 学号
     */
    private String studentIdStr;
    /**
     * 匹配方式(student_id_exact)
     */
    private String matchType;
    /**
     * 租户编号(同 InnovationProjectDO:service 显式携带)
     */
    private Long tenantId;

}
