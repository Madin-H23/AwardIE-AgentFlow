package cn.iocoder.yudao.module.business.dal.mysql.innovation;

import cn.iocoder.yudao.framework.mybatis.core.mapper.BaseMapperX;
import cn.iocoder.yudao.module.business.dal.dataobject.innovation.InnovationProjectStudentDO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * AwardIE 大创项目学生关联 Mapper(批8)
 *
 * @author AwardIE
 */
@Mapper
public interface InnovationProjectStudentMapper extends BaseMapperX<InnovationProjectStudentDO> {

    /**
     * 查某项目的全部有效关联
     *
     * @param projectId 项目编号
     * @param tenantId  租户编号
     * @return 关联行列表
     */
    @Select("SELECT * FROM awardie_innovation_project_students "
            + "WHERE project_id = #{projectId} AND deleted = b'0' AND tenant_id = #{tenantId}")
    java.util.List<InnovationProjectStudentDO> selectByProjectId(@Param("projectId") Long projectId,
            @Param("tenantId") Long tenantId);

    /**
     * 统计某项目的关联数(删除项目前的引用检查)
     *
     * @param projectId 项目编号
     * @param tenantId  租户编号
     * @return 关联行数
     */
    @Select("SELECT COUNT(*) FROM awardie_innovation_project_students "
            + "WHERE project_id = #{projectId} AND deleted = b'0' AND tenant_id = #{tenantId}")
    long countByProjectId(@Param("projectId") Long projectId, @Param("tenantId") Long tenantId);

}
