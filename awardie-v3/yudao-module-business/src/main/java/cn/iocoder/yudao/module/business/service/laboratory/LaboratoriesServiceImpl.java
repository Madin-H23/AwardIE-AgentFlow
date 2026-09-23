package cn.iocoder.yudao.module.business.service.laboratory;

import cn.hutool.core.collection.CollUtil;
import org.springframework.stereotype.Service;
import jakarta.annotation.Resource;
import org.springframework.validation.annotation.Validated;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import cn.iocoder.yudao.module.business.controller.admin.laboratory.vo.*;
import cn.iocoder.yudao.module.business.dal.dataobject.laboratory.LaboratoriesDO;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.common.pojo.PageParam;
import cn.iocoder.yudao.framework.common.util.object.BeanUtils;

import cn.iocoder.yudao.module.business.dal.mysql.laboratory.LaboratoriesMapper;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.framework.common.util.collection.CollectionUtils.convertList;
import static cn.iocoder.yudao.framework.common.util.collection.CollectionUtils.diffList;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.*;

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

    @Override
    public Long createLaboratories(LaboratoriesSaveReqVO createReqVO) {
        // 插入
        LaboratoriesDO laboratories = BeanUtils.toBean(createReqVO, LaboratoriesDO.class);
        laboratoriesMapper.insert(laboratories);

        // 返回
        return laboratories.getId();
    }

    @Override
    public void updateLaboratories(LaboratoriesSaveReqVO updateReqVO) {
        // 校验存在
        validateLaboratoriesExists(updateReqVO.getId());
        // 更新
        LaboratoriesDO updateObj = BeanUtils.toBean(updateReqVO, LaboratoriesDO.class);
        laboratoriesMapper.updateById(updateObj);
    }

    @Override
    public void deleteLaboratories(Long id) {
        // 校验存在
        validateLaboratoriesExists(id);
        // 删除
        laboratoriesMapper.deleteById(id);
    }

    @Override
        public void deleteLaboratoriesListByIds(List<Long> ids) {
        // 删除
        laboratoriesMapper.deleteByIds(ids);
        }


    private void validateLaboratoriesExists(Long id) {
        if (laboratoriesMapper.selectById(id) == null) {
            throw exception(LABORATORIES_NOT_EXISTS);
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