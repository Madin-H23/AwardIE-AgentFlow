package cn.iocoder.yudao.module.business.service.competition;

import cn.iocoder.yudao.module.business.controller.admin.competition.vo.CompetitionsPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.competition.vo.CompetitionsSaveReqVO;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import cn.iocoder.yudao.module.business.dal.mysql.competition.CompetitionsMapper;
import cn.iocoder.yudao.module.business.service.reference.AchievementReferenceChecker;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.common.util.object.BeanUtils;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;

import java.util.List;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.COMPETITIONS_DELETE_TOO_MANY;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.COMPETITIONS_IN_USE;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.COMPETITIONS_NAME_DUPLICATE;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.COMPETITIONS_NOT_EXISTS;

/**
 * AwardIE 竞赛 Service 实现类
 *
 * @author AwardIE
 */
@Service
@Validated
public class CompetitionsServiceImpl implements CompetitionsService {

    @Resource
    private CompetitionsMapper competitionsMapper;
    @Resource
    private AchievementReferenceChecker referenceChecker;
    /** 批量删除上限:引用检查走 IN 查询,避免超长 SQL 与 JDBC 占位符上限 */
    private static final int MAX_BATCH_DELETE_SIZE = 1000;

    @Override
    public Long createCompetitions(CompetitionsSaveReqVO createReqVO) {
        // 校验竞赛名称唯一(v2 前置查询语义;不加 DB 唯一索引——逻辑删除下已删同名会永久占位)
        validateCompetitionNameUnique(createReqVO.getCompetitionName(), null);
        // 插入(is_auto_added 建档恒 false:v2 INSERT 写死 FALSE,该标记由 OCR 抽取链路置位)
        CompetitionsDO competitions = BeanUtils.toBean(createReqVO, CompetitionsDO.class);
        competitions.setIsAutoAdded(false);
        competitionsMapper.insert(competitions);
        return competitions.getId();
    }

    @Override
    public void updateCompetitions(CompetitionsSaveReqVO updateReqVO) {
        // 校验存在
        validateCompetitionsExists(updateReqVO.getId());
        // 校验竞赛名称唯一(改名场景排除自身)
        validateCompetitionNameUnique(updateReqVO.getCompetitionName(), updateReqVO.getId());
        // 更新(is_auto_added 为系统标记,不由人工修改,不在 SaveReqVO 中暴露)
        CompetitionsDO updateObj = BeanUtils.toBean(updateReqVO, CompetitionsDO.class);
        competitionsMapper.updateById(updateObj);
    }

    @Override
    public void deleteCompetitions(Long id) {
        // 校验存在
        validateCompetitionsExists(id);
        // 校验未被成果/模板引用
        referenceChecker.validateNoReference(id, AchievementReferenceChecker.COMPETITION_REFERENCES,
                COMPETITIONS_IN_USE);
        // 删除
        competitionsMapper.deleteById(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteCompetitionsListByIds(List<Long> ids) {
        if (ids.size() > MAX_BATCH_DELETE_SIZE) {
            throw exception(COMPETITIONS_DELETE_TOO_MANY);
        }
        for (Long id : ids) {
            validateCompetitionsExists(id);
        }
        // 批量删除:引用检查一次性查完(任一被引用则整体拒绝并回滚)
        referenceChecker.validateNoReference(ids, AchievementReferenceChecker.COMPETITION_REFERENCES,
                COMPETITIONS_IN_USE);
        competitionsMapper.deleteByIds(ids);
    }

    private void validateCompetitionsExists(Long id) {
        if (competitionsMapper.selectById(id) == null) {
            throw exception(COMPETITIONS_NOT_EXISTS);
        }
    }

    private void validateCompetitionNameUnique(String name, Long excludeId) {
        if (name == null || name.isBlank()) {
            return;
        }
        CompetitionsDO sameName = competitionsMapper.selectByCompetitionName(name);
        if (sameName != null && !sameName.getId().equals(excludeId)) {
            throw exception(COMPETITIONS_NAME_DUPLICATE);
        }
    }

    @Override
    public CompetitionsDO getCompetitions(Long id) {
        return competitionsMapper.selectById(id);
    }

    @Override
    public PageResult<CompetitionsDO> getCompetitionsPage(CompetitionsPageReqVO pageReqVO) {
        return competitionsMapper.selectPage(pageReqVO);
    }

}
