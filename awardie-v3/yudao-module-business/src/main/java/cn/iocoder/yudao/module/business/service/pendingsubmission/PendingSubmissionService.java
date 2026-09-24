package cn.iocoder.yudao.module.business.service.pendingsubmission;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission.PendingAchievementDO;
import cn.iocoder.yudao.module.business.dal.mysql.pendingsubmission.PendingAchievementMapper;
import cn.iocoder.yudao.module.business.service.file.AwardieFileStorage;
import cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo.PendingAchievementPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo.PendingAchievementRespVO;
import cn.iocoder.yudao.framework.common.util.object.BeanUtils;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.validation.annotation.Validated;

import java.io.IOException;
import java.time.LocalDateTime;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_DUPLICATE_FILE;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_FORBIDDEN;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_NOT_EXISTS;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_NOT_WITHDRAWABLE;

/**
 * 待审成果提交服务(批4):三校验 → 五类字段校验 → 去重前置 → 落盘 → 入库
 *
 * <p>顺序与 v2 SubmissionService.submit 一致(去重只看 status=pending,
 * 驳回后可重新提交,新行);批7 把去重提到落盘之前,理由见 submit() 内注释。
 *
 * @author AwardIE
 */
@Service
@Validated
@Slf4j
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
        // 3. 去重前置(批7):去重判据是 file_hash,哈希可由字节直接算出,不必落盘就知道。
        //    v2/批4 原顺序是"先落盘再去重",重复提交会留下一个其实已被引用的文件——
        //    虽然内容寻址下它通常无害,但会让"落盘成功=一定有记录指向"这个不变式失效。
        String fileHash = fileStorage.sha256Hex(fileBytes);
        if (pendingMapper.selectByFileHashAndStatus(fileHash, STATUS_PENDING) != null) {
            throw exception(PENDING_ACHIEVEMENT_DUPLICATE_FILE);
        }
        // 4. 落盘 + sha256
        AwardieFileStorage.StoredFile stored = fileStorage.store(filename, fileBytes);
        // 5. 立刻注册孤儿补偿(批7):必须在入库之前注册——若等到 insert 之后,
        //    insert 本身失败时回调还没挂上,那正是最需要补偿的场景。
        //    文件是内容寻址,同一内容可能已被其他记录引用(同内容另一个待审行、物化后的
        //    成果证书/其他文件、实验室附件、模板样本图),故回收走"删前查引用"。
        registerOrphanCompensation(stored.relativePath());
        // 6. 入库
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
     * 注册事务回滚补偿:回滚后回收刚落盘的文件
     *
     * <p>为何用 TransactionSynchronization 而非 try/catch:try/catch 只能看见方法体内的
     * 异常,看不见**事务提交阶段**的失败(commit 时死锁、连接中断),而那正是最需要补偿的场景。
     * afterCompletion 钩子在事务真正结束后才跑,能看到最终状态。
     *
     * <p>钩子里的引用查询不能依赖当前线程的事务资源(afterCompletion 时 DataSource
     * 资源尚未解绑,复用旧连接可能看到不确定状态),因此显式要求新连接。
     *
     * <p>已知边界:补偿本身失败(磁盘满/权限)会留残留文件,按可接受处理——
     * 残留只是占空间,不影响数据正确性;为它引入事务代理重写不值得。
     */
    private void registerOrphanCompensation(String relativePath) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            return;
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCompletion(int status) {
                // 只在**明确回滚**时回收。STATUS_UNKNOWN 表示事务结果未知(例如 commit 时
                // 连接中断),不等于没提交——此时库行可能已经落库,删文件会打断它。
                if (status != TransactionSynchronization.STATUS_ROLLED_BACK) {
                    if (status == TransactionSynchronization.STATUS_UNKNOWN) {
                        log.warn("[submit] 事务结果未知,保留文件待巡检清理: {}", relativePath);
                    }
                    return;
                }
                try {
                    // 事务已结束,此时的查询走新连接,能看到回滚后的真实行状态
                    fileStorage.deleteIfUnreferenced(relativePath);
                } catch (Exception e) {
                    // 补偿失败只留残留文件,不影响数据正确性,记 warn 不打断流程
                    log.warn("[submit] 孤儿文件补偿失败,残留文件: {}", relativePath, e);
                }
            }
        });
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
