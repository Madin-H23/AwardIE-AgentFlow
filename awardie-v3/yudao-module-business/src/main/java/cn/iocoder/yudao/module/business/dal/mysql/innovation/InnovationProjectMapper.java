package cn.iocoder.yudao.module.business.dal.mysql.innovation;

import cn.iocoder.yudao.framework.mybatis.core.mapper.BaseMapperX;
import cn.iocoder.yudao.framework.mybatis.core.query.LambdaQueryWrapperX;
import cn.iocoder.yudao.module.business.dal.dataobject.innovation.InnovationProjectDO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;

/**
 * AwardIE 大创项目 Mapper(批8)
 *
 * <p>本表 DO 继承 BaseDO 而非 TenantBaseDO,故**租户条件必须由每个方法显式携带**
 * ——MyBatis-Plus 租户拦截器只对 TenantBaseDO 子类生效(批7 security-audit 误判过一次,
 * 实际 computeIgnoreTable 对无 @TenantIgnore 的表返回"不忽略",但那是拦截器层;
 * 本表已有 tenant_id 列却不被拦截器填充,故显式传 tenantId 是唯一可靠做法)。
 *
 * @author AwardIE
 */
@Mapper
public interface InnovationProjectMapper extends BaseMapperX<InnovationProjectDO> {

    /**
     * 按项目编号查(导入幂等判据)
     *
     * @param projectNo 项目编号
     * @param tenantId  租户编号
     * @return 项目,不存在返回 null
     */
    default InnovationProjectDO selectByProjectNo(String projectNo, Long tenantId) {
        return selectOne(new LambdaQueryWrapperX<InnovationProjectDO>()
                .eq(InnovationProjectDO::getProjectNo, projectNo)
                .eq(InnovationProjectDO::getTenantId, tenantId));
    }

    /**
     * status 校准候选集:仅"进行中"且结束日期非空
     *
     * <p>v2 口径:`status='进行中' AND end_date IS NOT NULL AND btrim(end_date)<>''`
     * (InnovationStatusService.java)。终止/已结题不进候选,保证重复调用幂等。
     *
     * @param tenantId 租户编号
     * @return 候选项目列表
     */
    @Select("SELECT * FROM awardie_innovation_projects "
            + "WHERE status = '进行中' AND end_date IS NOT NULL AND TRIM(end_date) <> '' "
            + "AND deleted = b'0' AND tenant_id = #{tenantId}")
    List<InnovationProjectDO> selectCalibrateCandidates(@Param("tenantId") Long tenantId);

    /**
     * status 校准更新:带状态条件实现 compare-and-set
     *
     * <p>用 `AND status='进行中'` 而非只按 id:并发两次校准时,
     * 后到的那条 UPDATE 影响 0 行而不是把别人已改的状态盖回去。
     *
     * @param id       项目编号
     * @param tenantId 租户编号
     * @return 影响行数(1=改成功,0=已被并发改掉)
     */
    @Update("UPDATE awardie_innovation_projects SET status = '已结题', update_time = NOW() "
            + "WHERE id = #{id} AND status = '进行中' AND deleted = b'0' AND tenant_id = #{tenantId}")
    int markFinished(@Param("id") Long id, @Param("tenantId") Long tenantId);

}
