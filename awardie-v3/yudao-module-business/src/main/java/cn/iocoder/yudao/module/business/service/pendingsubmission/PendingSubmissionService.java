package cn.iocoder.yudao.module.business.service.pendingsubmission;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission.PendingAchievementDO;
import cn.iocoder.yudao.module.business.dal.mysql.pendingsubmission.PendingAchievementMapper;
import cn.iocoder.yudao.module.business.service.file.AwardieFileStorage;
import cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo.PendingAchievementPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo.PendingAchievementRespVO;
import cn.iocoder.yudao.framework.common.util.object.BeanUtils;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;

import java.io.IOException;
import java.time.LocalDateTime;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_DUPLICATE_FILE;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_FORBIDDEN;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_NOT_EXISTS;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_NOT_WITHDRAWABLE;

/**
 * 待审成果提交服务(批4):三校验 → 五类字段校验 → 落盘去重 → 入库
 *
 * <p>顺序与 v2 SubmissionService.submit 一致;去重只针对 status=pending
 * (v2 语义:驳回后修改可重新提交,新行)。
 *
 * @author AwardIE
 */
@Service
@Validated
public class PendingSubmissionService {

    /** 待审状态(v2 同) */
    public static final String STATUS_PENDING = "pending";
    /** 已通过(物化入库) */
    public static final String STATUS_ARCHIVED = "archived";
    /** 已驳回(可修改后重新提交,新行) */
    public static final String STATUS_REJECTED = "rejected";
    /** 新建版本号(v2 同) */
    private static final int INITIAL_VERSION = 1;

    @Resource
    private PendingAchievementMapper pendingMapper;
    @Resource
    private AwardieFileStorage fileStorage;
    @Resource
    private SubmissionValidator validator;
    @Resource
    private ReviewService reviewService;

    /**
     * 提交成果
     *
     * @param submitterId      提交人编号
     * @param submitterType    提交人类型(student/teacher/admin)
     * @param achievementType  成果类型
     * @param filename         原始文件名
     * @param fileBytes        文件内容
     * @param dataJson         成果字段 JSON
     * @param submitterCode    提交人账号(留痕用)
     * @param submitterName    提交人姓名(留痕用)
     * @return 入库后的待审成果
     * @throws IOException 落盘失败
     */
    @Transactional(rollbackFor = Exception.class)
    public PendingAchievementDO submit(Long submitterId, String submitterType, String achievementType,
            String filename, byte[] fileBytes, String dataJson, String submitterCode, String submitterName)
            throws IOException {
        // 1. 文件三校验(扩展名 → 大小 → 魔术字节,顺序沿 v2)
        fileStorage.assertAllowed(filename, fileBytes);
        // 2. 五类成果字段校验(结果落库,不阻断提交——沿 v2:校验结果供审核参考)
        SubmissionValidator.ValidationResult validation = validator.validate(achievementType, dataJson);
        // 3. 落盘 + sha256
        AwardieFileStorage.StoredFile stored = fileStorage.store(filename, fileBytes);
        // 4. 去重:同内容且仍在待审队列则拒(驳回后可重新提交)
        if (pendingMapper.selectByFileHashAndStatus(stored.sha256(), STATUS_PENDING) != null) {
            throw exception(PENDING_ACHIEVEMENT_DUPLICATE_FILE);
        }
        // 5. 入库
        PendingAchievementDO entity = new PendingAchievementDO();
        entity.setAchievementType(achievementType);
        entity.setAchievementData(dataJson == null || dataJson.isBlank() ? "{}" : dataJson);
        entity.setValidationResult(validator.toValidationJson(validation));
        entity.setSubmitterType(submitterType);
        entity.setSubmitterId(submitterId);
        entity.setSubmitTime(LocalDateTime.now());
        entity.setStatus(STATUS_PENDING);
        entity.setFilePath(stored.relativePath());
        entity.setFileHash(stored.sha256());
        entity.setVersion(INITIAL_VERSION);
        pendingMapper.insert(entity);
        // 提交留痕(action_type=1,v2 同:提交即留痕)
        reviewService.auditSubmit(entity, submitterId, submitterCode, submitterName);
        return entity;
    }

    /**
     * 我的提交分页(按提交人过滤)
     *
     * @param pageReqVO 分页参数(提交人编号由 controller 填当前登录用户)
     * @return 分页结果
     */
    public PageResult<PendingAchievementRespVO> getMySubmissionPage(PendingAchievementPageReqVO pageReqVO) {
        PageResult<PendingAchievementDO> pageResult = pendingMapper.selectPage(pageReqVO);
        return BeanUtils.toBean(pageResult, PendingAchievementRespVO.class);
    }

    /**
     * 撤回提交:仅本人且 status=pending
     *
     * @param id         待审成果编号
     * @param submitterId 当前用户编号
     */
    @Transactional(rollbackFor = Exception.class)
    public void withdraw(Long id, Long submitterId) {
        PendingAchievementDO entity = pendingMapper.selectById(id);
        if (entity == null) {
            throw exception(PENDING_ACHIEVEMENT_NOT_EXISTS);
        }
        if (!submitterId.equals(entity.getSubmitterId())) {
            throw exception(PENDING_ACHIEVEMENT_FORBIDDEN);
        }
        if (!STATUS_PENDING.equals(entity.getStatus())) {
            throw exception(PENDING_ACHIEVEMENT_NOT_WITHDRAWABLE);
        }
        pendingMapper.deleteById(id);
    }

    /**
     * 取待审成果(供下载端点做归属与状态判定)
     *
     * @param id 编号
     * @return 待审成果
     */
    public PendingAchievementDO get(Long id) {
        PendingAchievementDO entity = pendingMapper.selectById(id);
        if (entity == null) {
            throw exception(PENDING_ACHIEVEMENT_NOT_EXISTS);
        }
        return entity;
    }

}
