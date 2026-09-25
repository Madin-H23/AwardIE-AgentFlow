package cn.iocoder.yudao.module.business.service.innovation;

import cn.hutool.core.util.StrUtil;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.mybatis.core.query.LambdaQueryWrapperX;
import cn.iocoder.yudao.module.business.controller.admin.innovation.vo.InnovationPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.innovation.vo.InnovationRespVO;
import cn.iocoder.yudao.module.business.controller.admin.innovation.vo.InnovationUpdateReqVO;
import cn.iocoder.yudao.module.business.dal.dataobject.innovation.InnovationProjectDO;
import cn.iocoder.yudao.module.business.dal.mysql.innovation.InnovationProjectMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.INNOVATION_NOT_EXISTS;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.INNOVATION_STATUS_INVALID;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.INNOVATION_TYPE_INVALID;

/**
 * 大创项目 Service(批8):分页查询、详情、编辑(status 方向1)
 *
 * <p>与批6 通用成果库的关系:批6 的 `AchievementVaultService` 用 JdbcTemplate 按类型分派,
 * 已支持 innovation 的列表/编辑/删除且有测试覆盖——**那部分保留不动**(减少回归面)。
 * 本 Service 承担大创**专属**能力:完整字段编辑(带枚举校验)、分页(带竞赛名关联)、
 * 供导入与校准复用的查询。
 *
 * @author AwardIE
 */
@Service
@Validated
public class InnovationService {

    /** 状态白名单(应用层校验,v2 靠 DB CHECK,v3 沿项目口径不用 CHECK) */
    public static final Set<String> STATUSES =
            Set.of(InnovationProjectDO.STATUS_ONGOING,
                    InnovationProjectDO.STATUS_FINISHED,
                    InnovationProjectDO.STATUS_TERMINATED);
    /** 项目类型白名单 */
    public static final Set<String> PROJECT_TYPES = Set.of("国家级", "省级", "院级");

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Resource
    private InnovationProjectMapper projectMapper;

    /**
     * 分页查询大创项目
     *
     * @param pageReqVO 分页参数
     * @param tenantId  租户编号
     * @return 分页结果(含竞赛名)
     */
    public PageResult<InnovationRespVO> getInnovationPage(InnovationPageReqVO pageReqVO, Long tenantId) {
        LambdaQueryWrapperX<InnovationProjectDO> wrapper = new LambdaQueryWrapperX<InnovationProjectDO>()
                .eqIfPresent(InnovationProjectDO::getStatus, pageReqVO.getStatus())
                .eqIfPresent(InnovationProjectDO::getProjectType, pageReqVO.getProjectType())
                .likeIfPresent(InnovationProjectDO::getProjectName, pageReqVO.getProjectName())
                .eq(InnovationProjectDO::getTenantId, tenantId)
                .orderByDesc(InnovationProjectDO::getId);
        PageResult<InnovationProjectDO> page = projectMapper.selectPage(pageReqVO, wrapper);
        List<InnovationRespVO> list = page.getList().stream().map(this::toRespVO).toList();
        return new PageResult<>(list, page.getTotal());
    }

    /**
     * 查详情
     *
     * @param id      项目编号
     * @param tenantId 租户编号
     * @return 详情(含竞赛名)
     */
    public InnovationRespVO getInnovation(Long id, Long tenantId) {
        return toRespVO(getDO(id, tenantId));
    }

    /**
     * 编辑大创项目(status 方向1)
     *
     * <p>状态与类型走应用层枚举校验——v2 的编辑端点无校验、靠 DB CHECK 兜底,
     * 且把所有 DataIntegrityViolation 统一误报成"项目编号已存在",排障时方向全错。
     *
     * @param id         项目编号
     * @param updateReqVO 更新参数
     * @param tenantId   租户编号
     */
    @Transactional(rollbackFor = Exception.class)
    public void updateInnovation(Long id, InnovationUpdateReqVO updateReqVO, Long tenantId) {
        InnovationProjectDO existing = getDO(id, tenantId);
        if (StrUtil.isNotBlank(updateReqVO.getStatus())
                && !STATUSES.contains(updateReqVO.getStatus())) {
            throw exception(INNOVATION_STATUS_INVALID);
        }
        if (StrUtil.isNotBlank(updateReqVO.getProjectType())
                && !PROJECT_TYPES.contains(updateReqVO.getProjectType())) {
            throw exception(INNOVATION_TYPE_INVALID);
        }
        InnovationProjectDO update = new InnovationProjectDO();
        update.setId(existing.getId());
        update.setTenantId(tenantId);
        update.setProjectNo(StrUtil.blankToDefault(updateReqVO.getProjectNo(), existing.getProjectNo()));
        update.setProjectName(StrUtil.blankToDefault(updateReqVO.getProjectName(), existing.getProjectName()));
        update.setProjectType(StrUtil.blankToDefault(updateReqVO.getProjectType(), existing.getProjectType()));
        update.setStatus(StrUtil.blankToDefault(updateReqVO.getStatus(), existing.getStatus()));
        update.setStartDate(updateReqVO.getStartDate());
        update.setEndDate(updateReqVO.getEndDate());
        update.setFundingAmount(updateReqVO.getFundingAmount());
        update.setStudentLeaderName(updateReqVO.getStudentLeaderName());
        update.setStudentLeaderId(updateReqVO.getStudentLeaderId());
        update.setSupervisors(updateReqVO.getSupervisors());
        update.setLaboratoryId(updateReqVO.getLaboratoryId());
        projectMapper.updateById(update);
    }

    /**
     * 取项目(带租户与逻辑删除条件)
     *
     * @param id      项目编号
     * @param tenantId 租户编号
     * @return 项目
     */
    public InnovationProjectDO getDO(Long id, Long tenantId) {
        InnovationProjectDO entity = projectMapper.selectOne(new LambdaQueryWrapperX<InnovationProjectDO>()
                .eq(InnovationProjectDO::getId, id)
                .eq(InnovationProjectDO::getTenantId, tenantId));
        if (entity == null) {
            throw exception(INNOVATION_NOT_EXISTS);
        }
        return entity;
    }

    private InnovationRespVO toRespVO(InnovationProjectDO entity) {
        InnovationRespVO vo = new InnovationRespVO();
        vo.setId(entity.getId());
        vo.setProjectNo(entity.getProjectNo());
        vo.setProjectName(entity.getProjectName());
        vo.setProjectType(entity.getProjectType());
        vo.setStatus(entity.getStatus());
        vo.setStartDate(entity.getStartDate());
        vo.setEndDate(entity.getEndDate());
        vo.setFundingAmount(entity.getFundingAmount());
        vo.setStudentLeaderName(entity.getStudentLeaderName());
        vo.setStudentLeaderId(entity.getStudentLeaderId());
        vo.setOtherMembers(readMembers(entity.getOtherMembers()));
        vo.setSupervisors(entity.getSupervisors());
        vo.setLaboratoryId(entity.getLaboratoryId());
        vo.setSubmitTime(entity.getSubmitTime());
        vo.setCreateTime(entity.getCreateTime());
        return vo;
    }

    private List<Map<String, String>> readMembers(String json) {
        if (StrUtil.isBlank(json)) {
            return List.of();
        }
        try {
            return MAPPER.readValue(json, new com.fasterxml.jackson.core.type.TypeReference<>() {
            });
        } catch (Exception e) {
            return List.of();
        }
    }

}
