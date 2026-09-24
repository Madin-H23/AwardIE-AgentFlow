package cn.iocoder.yudao.module.business.service.laboratory;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.common.util.object.BeanUtils;
import cn.iocoder.yudao.module.business.controller.admin.laboratory.vo.LaboratoriesPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.laboratory.vo.LaboratoriesSaveReqVO;
import cn.iocoder.yudao.module.business.dal.dataobject.laboratory.LaboratoriesDO;
import cn.iocoder.yudao.module.business.dal.mysql.laboratory.LaboratoriesMapper;
import cn.iocoder.yudao.module.business.service.reference.AchievementReferenceChecker;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;

import java.util.List;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.LABORATORIES_DELETE_TOO_MANY;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.LABORATORIES_IN_USE;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.LABORATORIES_NAME_DUPLICATE;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.LABORATORIES_NOT_EXISTS;

/**
 * AwardIE 实验室 Service 实现类
 *
 * @author AwardIE
 */
@Service
@Validated
public class LaboratoriesServiceImpl implements LaboratoriesService {

    @Resource
    private LaboratoriesMapper laboratoriesMapper;
    @Resource
    private AchievementReferenceChecker referenceChecker;
    /** 批量删除上限:引用检查走 IN 查询,避免超长 SQL 与 JDBC 占位符上限 */
    private static final int MAX_BATCH_DELETE_SIZE = 1000;

    @Override
    public Long createLaboratories(LaboratoriesSaveReqVO createReqVO) {
        // 校验实验室名称唯一(v2 无 DB 约束但按名称识别,重名会污染按名取值)
        validateLaboratoryNameUnique(createReqVO.getName(), null);
        // 插入
        LaboratoriesDO laboratories = BeanUtils.toBean(createReqVO, LaboratoriesDO.class);
        laboratoriesMapper.insert(laboratories);
        return laboratories.getId();
    }

    @Override
    public void updateLaboratories(LaboratoriesSaveReqVO updateReqVO) {
        // 校验存在
        validateLaboratoriesExists(updateReqVO.getId());
        // 校验实验室名称唯一(改名场景排除自身)
        validateLaboratoryNameUnique(updateReqVO.getName(), updateReqVO.getId());
        // 更新
        LaboratoriesDO updateObj = BeanUtils.toBean(updateReqVO, LaboratoriesDO.class);
        laboratoriesMapper.updateById(updateObj);
    }

    @Override
    public void deleteLaboratories(Long id) {
        // 校验存在
        validateLaboratoriesExists(id);
        // 校验未被成果引用
        referenceChecker.validateNoReference(id, AchievementReferenceChecker.LABORATORY_REFERENCES,
                LABORATORIES_IN_USE);
        // 删除
        laboratoriesMapper.deleteById(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteLaboratoriesListByIds(List<Long> ids) {
        if (ids.size() > MAX_BATCH_DELETE_SIZE) {
            throw exception(LABORATORIES_DELETE_TOO_MANY);
        }
        for (Long id : ids) {
            validateLaboratoriesExists(id);
        }
        // 批量删除:引用检查一次性查完(任一被引用则整体拒绝并回滚)
        referenceChecker.validateNoReference(ids, AchievementReferenceChecker.LABORATORY_REFERENCES,
                LABORATORIES_IN_USE);
        laboratoriesMapper.deleteByIds(ids);
    }

    private void validateLaboratoriesExists(Long id) {
        if (laboratoriesMapper.selectById(id) == null) {
            throw exception(LABORATORIES_NOT_EXISTS);
        }
    }

    private void validateLaboratoryNameUnique(String name, Long excludeId) {
        if (name == null || name.isBlank()) {
            return;
        }
        LaboratoriesDO sameName = laboratoriesMapper.selectByName(name);
        if (sameName != null && !sameName.getId().equals(excludeId)) {
            throw exception(LABORATORIES_NAME_DUPLICATE);
        }
    }

    @Override
    public LaboratoriesDO getLaboratories(Long id) {
        return laboratoriesMapper.selectById(id);
    }

    @Override
    public PageResult<LaboratoriesDO> getLaboratoriesPage(LaboratoriesPageReqVO pageReqVO) {
        return laboratoriesMapper.selectPage(pageReqVO);
    }

}
