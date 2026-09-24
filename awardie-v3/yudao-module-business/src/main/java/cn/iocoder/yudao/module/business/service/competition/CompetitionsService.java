package cn.iocoder.yudao.module.business.service.competition;

import java.util.*;
import jakarta.validation.*;
import cn.iocoder.yudao.module.business.controller.admin.competition.vo.*;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.common.pojo.PageParam;

/**
 * AwardIE 竞赛 Service 接口
 *
 * @author AwardIE
 */
public interface CompetitionsService {

    /**
     * 创建AwardIE 竞赛
     *
     * @param createReqVO 创建信息
     * @return 编号
     */
    Long createCompetitions(@Valid CompetitionsSaveReqVO createReqVO);

    /**
     * 更新AwardIE 竞赛
     *
     * @param updateReqVO 更新信息
     */
    void updateCompetitions(@Valid CompetitionsSaveReqVO updateReqVO);

    /**
     * 删除AwardIE 竞赛
     *
     * @param id 编号
     */
    void deleteCompetitions(Long id);

    /**
    * 批量删除AwardIE 竞赛
    *
    * @param ids 编号
    */
    void deleteCompetitionsListByIds(List<Long> ids);

    /**
     * 获得AwardIE 竞赛
     *
     * @param id 编号
     * @return AwardIE 竞赛
     */
    CompetitionsDO getCompetitions(Long id);

    /**
     * 获得AwardIE 竞赛分页
     *
     * @param pageReqVO 分页查询
     * @return AwardIE 竞赛分页
     */
    PageResult<CompetitionsDO> getCompetitionsPage(CompetitionsPageReqVO pageReqVO);

}
