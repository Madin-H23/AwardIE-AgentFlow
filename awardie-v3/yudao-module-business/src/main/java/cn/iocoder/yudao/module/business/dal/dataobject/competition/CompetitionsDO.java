package cn.iocoder.yudao.module.business.dal.dataobject.competition;

import lombok.*;
import java.util.*;
import java.time.LocalDateTime;
import java.time.LocalDateTime;
import com.baomidou.mybatisplus.annotation.*;
import cn.iocoder.yudao.framework.mybatis.core.dataobject.BaseDO;

/**
 * AwardIE 竞赛 DO
 *
 * @author AwardIE
 * <p>
 * KeySequence 用于 Oracle、PostgreSQL、Kingbase、DB2、H2 数据库的主键自增;MySQL 等数据库可不写。
 */
@TableName("awardie_competitions")
@KeySequence("awardie_competitions_seq")
@Data
@EqualsAndHashCode(callSuper = true)
@ToString(callSuper = true)
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CompetitionsDO extends BaseDO {

    /**
     * 主键
     */
    @TableId
    private Long id;
    /**
     * 竞赛名称
     */
    private String competitionName;
    /**
     * 官网地址
     */
    private String officialWebsite;
    /**
     * 主办方
     */
    private String organizer;
    /**
     * 竞赛时间(如 4-10月)
     */
    private String competitionTime;
    /**
     * 参赛要求
     */
    private String participantRequirements;
    /**
     * 组别类别
     */
    private String gradeCategory;
    /**
     * 简介
     */
    private String briefDescription;
    /**
     * 别名列表(换行分隔)
     */
    private String aliasList;
    /**
     * 是否白名单
     */
    private Boolean whiteList;
    /**
     * 是否观察名单
     */
    private Boolean watchList;
    /**
     * 是否自动创建
     */
    private Boolean isAutoAdded;


}
