package cn.iocoder.yudao.module.business.dal.dataobject.audit;

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

import java.time.LocalDateTime;

/**
 * AwardIE 成果审核留痕 DO(动作码:1 提交/6 通过/7 驳回/8 物化)
 *
 * @author AwardIE
 * <p>
 * KeySequence 用于 Oracle、PostgreSQL、Kingbase、DB2、H2 数据库的主键自增;MySQL 等数据库可不写。
 */
@TableName("awardie_achievement_audit_log")
@KeySequence("awardie_achievement_audit_log_seq")
@Data
@EqualsAndHashCode(callSuper = true)
@ToString(callSuper = true)
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AchievementAuditLogDO extends BaseDO {

    /**
     * 主键
     */
    @TableId
    private Long id;
    /**
     * 待审成果编号
     */
    private Long achievementId;
    /**
     * 成果类型
     */
    private String achievementKind;
    /**
     * 动作码
     */
    private Integer actionType;
    /**
     * 动作结果
     */
    private Integer actionResult;
    /**
     * 操作人编号
     */
    private Long operatorId;
    /**
     * 操作人账号
     */
    private String operatorCode;
    /**
     * 操作人姓名
     */
    private String operatorName;
    /**
     * 变更详情 JSON
     */
    private String changeDetail;
    /**
     * 备注
     */
    private String remark;

}
