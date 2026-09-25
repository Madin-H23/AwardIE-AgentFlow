package cn.iocoder.yudao.module.business.dal.mysql.audit;

import cn.hutool.core.util.StrUtil;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.mybatis.core.mapper.BaseMapperX;
import cn.iocoder.yudao.framework.mybatis.core.query.LambdaQueryWrapperX;
import cn.iocoder.yudao.module.business.controller.admin.log.vo.AuditLogPageReqVO;
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

    /**
     * 业务审计日志分页(批9)
     *
     * <p>排序固定 id DESC(留痕只增不改,id 即时间序,比 create_time 稳定——后者同秒可能并列)。
     *
     * @param pageReqVO 分页与筛选参数
     * @return 分页结果
     */
    default PageResult<AchievementAuditLogDO> selectAuditPage(AuditLogPageReqVO pageReqVO) {
        return selectPage(pageReqVO, new LambdaQueryWrapperX<AchievementAuditLogDO>()
                .eqIfPresent(AchievementAuditLogDO::getAchievementKind, pageReqVO.getAchievementKind())
                .eqIfPresent(AchievementAuditLogDO::getActionType, pageReqVO.getActionType())
                .and(StrUtil.isNotBlank(pageReqVO.getOperatorKeyword()), w -> w
                        .like(AchievementAuditLogDO::getOperatorName, pageReqVO.getOperatorKeyword())
                        .or()
                        .like(AchievementAuditLogDO::getOperatorCode, pageReqVO.getOperatorKeyword()))
                .betweenIfPresent(AchievementAuditLogDO::getCreateTime, pageReqVO.getCreateTime())
                .orderByDesc(AchievementAuditLogDO::getId));
    }

}
