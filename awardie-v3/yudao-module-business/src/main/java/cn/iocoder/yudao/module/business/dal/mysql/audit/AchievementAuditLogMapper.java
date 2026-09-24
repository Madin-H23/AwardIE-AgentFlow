package cn.iocoder.yudao.module.business.dal.mysql.audit;

import cn.iocoder.yudao.framework.mybatis.core.mapper.BaseMapperX;
import cn.iocoder.yudao.framework.mybatis.core.query.LambdaQueryWrapperX;
import cn.iocoder.yudao.module.business.dal.dataobject.audit.AchievementAuditLogDO;
import org.apache.ibatis.annotations.Mapper;

import java.util.List;

/**
 * AwardIE 成果审核留痕 Mapper
 *
 * @author AwardIE
 */
@Mapper
public interface AchievementAuditLogMapper extends BaseMapperX<AchievementAuditLogDO> {

    /**
     * 按待审成果编号取留痕(时间线,创建时间升序)
     *
     * @param achievementId 待审成果编号
     * @return 留痕列表
     */
    default List<AchievementAuditLogDO> selectListByAchievementId(Long achievementId) {
        return selectList(new LambdaQueryWrapperX<AchievementAuditLogDO>()
                .eq(AchievementAuditLogDO::getAchievementId, achievementId)
                .orderByAsc(AchievementAuditLogDO::getCreateTime)
                .orderByAsc(AchievementAuditLogDO::getId));
    }

    /**
     * 判断某动作码是否已留痕(提交留痕补写时防重)
     *
     * @param achievementId 待审成果编号
     * @param actionType    动作码
     * @return 已留痕条数
     */
    default Long selectCountByAchievementAndAction(Long achievementId, Integer actionType) {
        return selectCount(new LambdaQueryWrapperX<AchievementAuditLogDO>()
                .eq(AchievementAuditLogDO::getAchievementId, achievementId)
                .eq(AchievementAuditLogDO::getActionType, actionType));
    }

}
