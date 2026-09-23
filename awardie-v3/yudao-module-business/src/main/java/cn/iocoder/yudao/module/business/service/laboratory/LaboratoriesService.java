package cn.iocoder.yudao.module.business.service.laboratory;

import java.util.*;
import jakarta.validation.*;
import cn.iocoder.yudao.module.business.controller.admin.laboratory.vo.*;
import cn.iocoder.yudao.module.business.dal.dataobject.laboratory.LaboratoriesDO;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.common.pojo.PageParam;

/**
 * AwardIE 实验室 Service 接口
 *
 * @author AwardIE
 */
public interface LaboratoriesService {

    /**
     * 创建AwardIE 实验室
     *
     * @param createReqVO 创建信息
     * @return 编号
     */
    Long createLaboratories(@Valid LaboratoriesSaveReqVO createReqVO);

    /**
     * 更新AwardIE 实验室
     *
     * @param updateReqVO 更新信息
     */
    void updateLaboratories(@Valid LaboratoriesSaveReqVO updateReqVO);

    /**
     * 删除AwardIE 实验室
     *
     * @param id 编号
     */
    void deleteLaboratories(Long id);

    /**
    * 批量删除AwardIE 实验室
    *
    * @param ids 编号
    */
    void deleteLaboratoriesListByIds(List<Long> ids);

    /**
     * 获得AwardIE 实验室
     *
     * @param id 编号
     * @return AwardIE 实验室
     */
    LaboratoriesDO getLaboratories(Long id);

    /**
     * 获得AwardIE 实验室分页
     *
     * @param pageReqVO 分页查询
     * @return AwardIE 实验室分页
     */
    PageResult<LaboratoriesDO> getLaboratoriesPage(LaboratoriesPageReqVO pageReqVO);

}