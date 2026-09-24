package cn.iocoder.yudao.module.business.dal.mysql.competition;

import java.util.*;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.mybatis.core.query.LambdaQueryWrapperX;
import cn.iocoder.yudao.framework.mybatis.core.mapper.BaseMapperX;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import org.apache.ibatis.annotations.Mapper;
import cn.iocoder.yudao.module.business.controller.admin.competition.vo.*;

/**
 * AwardIE 竞赛 Mapper
 *
 * @author AwardIE
 */
@Mapper
public interface CompetitionsMapper extends BaseMapperX<CompetitionsDO> {

    /**
     * 按竞赛名称查询(唯一性校验用;逻辑删除行自动过滤)
     *
     * @param competitionName 竞赛名称
     * @return 竞赛,不存在返回 null
     */
    default CompetitionsDO selectByCompetitionName(String competitionName) {
        return selectOne(CompetitionsDO::getCompetitionName, competitionName);
    }

    /**
     * 分页查询竞赛(名称 LIKE、名单等值、创建时间区间,ID 倒序)
     *
     * @param reqVO 分页参数
     * @return 竞赛分页结果
     */
    default PageResult<CompetitionsDO> selectPage(CompetitionsPageReqVO reqVO) {
        return selectPage(reqVO, new LambdaQueryWrapperX<CompetitionsDO>()
                .likeIfPresent(CompetitionsDO::getCompetitionName, reqVO.getCompetitionName())
                .eqIfPresent(CompetitionsDO::getWhiteList, reqVO.getWhiteList())
                .eqIfPresent(CompetitionsDO::getWatchList, reqVO.getWatchList())
                .eqIfPresent(CompetitionsDO::getIsAutoAdded, reqVO.getIsAutoAdded())
                .betweenIfPresent(CompetitionsDO::getCreateTime, reqVO.getCreateTime())
                .orderByDesc(CompetitionsDO::getId));
    }

}