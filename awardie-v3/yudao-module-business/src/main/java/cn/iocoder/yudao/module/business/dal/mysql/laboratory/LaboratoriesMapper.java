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

    /**
     * 按实验室名称查询(唯一性校验用;逻辑删除行自动过滤)
     *
     * @param name 实验室名称
     * @return 实验室,不存在返回 null
     */
    default LaboratoriesDO selectByName(String name) {
        return selectOne(LaboratoriesDO::getName, name);
    }

    /**
     * 分页查询实验室(名称 LIKE、创建时间区间,ID 倒序)
     *
     * @param reqVO 分页参数
     * @return 实验室分页结果
     */
    default PageResult<LaboratoriesDO> selectPage(LaboratoriesPageReqVO reqVO) {
        return selectPage(reqVO, new LambdaQueryWrapperX<LaboratoriesDO>()
                .likeIfPresent(LaboratoriesDO::getName, reqVO.getName())
                .betweenIfPresent(LaboratoriesDO::getCreateTime, reqVO.getCreateTime())
                .orderByDesc(LaboratoriesDO::getId));
    }

}