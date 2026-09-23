package cn.iocoder.yudao.module.business.dal.mysql.laboratory;

import java.util.*;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.mybatis.core.query.LambdaQueryWrapperX;
import cn.iocoder.yudao.framework.mybatis.core.mapper.BaseMapperX;
import cn.iocoder.yudao.module.business.dal.dataobject.laboratory.LaboratoriesDO;
import org.apache.ibatis.annotations.Mapper;
import cn.iocoder.yudao.module.business.controller.admin.laboratory.vo.*;

/**
 * AwardIE 实验室 Mapper
 *
 * @author AwardIE
 */
@Mapper
public interface LaboratoriesMapper extends BaseMapperX<LaboratoriesDO> {

    default PageResult<LaboratoriesDO> selectPage(LaboratoriesPageReqVO reqVO) {
        return selectPage(reqVO, new LambdaQueryWrapperX<LaboratoriesDO>()
                .likeIfPresent(LaboratoriesDO::getName, reqVO.getName())
                .eqIfPresent(LaboratoriesDO::getDescription, reqVO.getDescription())
                .betweenIfPresent(LaboratoriesDO::getCreateTime, reqVO.getCreateTime())
                .orderByDesc(LaboratoriesDO::getId));
    }

}