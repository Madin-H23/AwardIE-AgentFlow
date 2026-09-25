package cn.iocoder.yudao.module.business.service.audit;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.common.util.object.BeanUtils;
import cn.iocoder.yudao.module.business.controller.admin.log.vo.AuditLogPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.log.vo.AuditLogRespVO;
import cn.iocoder.yudao.module.business.dal.dataobject.audit.AchievementAuditLogDO;
import cn.iocoder.yudao.module.business.dal.mysql.audit.AchievementAuditLogMapper;
import cn.iocoder.yudao.module.business.enums.AuditActionType;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.validation.annotation.Validated;

import java.util.List;

/**
 * 业务审计日志查询 Service(批9)
 *
 * <p>v3 审核流(批5)已在写 action 1/6/7/8,数据链完整,本服务只补查询面——
 * 不新建日志表,也不重复写日志。
 *
 * @author AwardIE
 */
@Service
@Validated
public class AuditLogService {

    @Resource
    private AchievementAuditLogMapper auditLogMapper;

    /**
     * 分页查询业务审计日志
     *
     * <p>租户隔离说明:本查询走 MyBatis-Plus,租户拦截器会自动追加 tenant_id 条件
     * (与批8 的 JdbcTemplate 统计不同——那条路径必须显式带条件,见 AchievementVaultService)。
     *
     * @param pageReqVO 分页与筛选参数
     * @return 分页结果(含动作中文标签)
     */
    public PageResult<AuditLogRespVO> getAuditLogPage(AuditLogPageReqVO pageReqVO) {
        PageResult<AchievementAuditLogDO> page = auditLogMapper.selectAuditPage(pageReqVO);
        List<AuditLogRespVO> list = page.getList().stream()
                .map(this::toRespVO)
                .toList();
        return new PageResult<>(list, page.getTotal());
    }

    private AuditLogRespVO toRespVO(AchievementAuditLogDO entity) {
        AuditLogRespVO vo = BeanUtils.toBean(entity, AuditLogRespVO.class);
        vo.setActionLabel(AuditActionType.label(entity.getActionType()));
        return vo;
    }

}
