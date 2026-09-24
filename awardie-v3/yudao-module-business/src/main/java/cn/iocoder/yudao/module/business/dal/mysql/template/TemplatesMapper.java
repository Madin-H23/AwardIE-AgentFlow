package cn.iocoder.yudao.module.business.dal.mysql.template;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.mybatis.core.mapper.BaseMapperX;
import cn.iocoder.yudao.framework.mybatis.core.query.LambdaQueryWrapperX;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplatesPageReqVO;
import cn.iocoder.yudao.module.business.dal.dataobject.template.TemplatesDO;
import org.apache.ibatis.annotations.Mapper;

/**
 * AwardIE 证书模板 Mapper(批7)
 *
 * @author AwardIE
 */
@Mapper
public interface TemplatesMapper extends BaseMapperX<TemplatesDO> {

    /**
     * 同竞赛 + 同授予角色是否已有模板(唯一性校验用;逻辑删除行自动过滤)
     *
     * @param competitionId 竞赛编号
     * @param grantedRole   授予角色
     * @param excludeId     编辑场景排除自身,可为 null
     * @return 已存在的模板数
     */
    default Long selectCountByCompetitionAndRole(Long competitionId, String grantedRole, Long excludeId) {
        LambdaQueryWrapperX<TemplatesDO> wrapper = new LambdaQueryWrapperX<TemplatesDO>()
                .eq(TemplatesDO::getCompetitionId, competitionId)
                .eq(TemplatesDO::getGrantedRole, grantedRole);
        if (excludeId != null) {
            wrapper.ne(TemplatesDO::getId, excludeId);
        }
        return selectCount(wrapper);
    }

    /**
     * 分页查询模板(竞赛与角色等值过滤,ID 倒序)
     *
     * @param reqVO 分页参数
     * @return 模板分页结果
     */
    default PageResult<TemplatesDO> selectPage(TemplatesPageReqVO reqVO) {
        return selectPage(reqVO, new LambdaQueryWrapperX<TemplatesDO>()
                .eqIfPresent(TemplatesDO::getCompetitionId, reqVO.getCompetitionId())
                .eqIfPresent(TemplatesDO::getGrantedRole, reqVO.getGrantedRole())
                .orderByDesc(TemplatesDO::getId));
    }

}
