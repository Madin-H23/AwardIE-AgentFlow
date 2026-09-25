package cn.iocoder.yudao.module.business.controller.admin.pendingsubmission;

import cn.iocoder.yudao.framework.common.pojo.CommonResult;
import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.security.core.LoginUser;
import cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo.PendingAchievementPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo.PendingAchievementRespVO;
import cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission.PendingAchievementDO;
import cn.iocoder.yudao.module.business.service.file.AwardieFileStorage;
import cn.iocoder.yudao.module.business.service.pendingsubmission.PendingSubmissionService;
import cn.iocoder.yudao.module.business.service.pendingsubmission.SubmissionValidator;
import cn.iocoder.yudao.module.business.service.pendingsubmission.ReviewOperatorResolver;
import cn.iocoder.yudao.module.business.service.pendingsubmission.SubmitterTypeResolver;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpHeaders;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import cn.iocoder.yudao.framework.common.util.object.BeanUtils;
import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo.PendingReviewReqVO;
import cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo.PendingTimelineRespVO;
import cn.iocoder.yudao.module.business.service.pendingsubmission.AiReviewService;
import cn.iocoder.yudao.module.business.service.pendingsubmission.ReviewService;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import java.util.List;
import java.util.Map;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.REVIEW_ACTION_INVALID;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.REVIEW_TIMELINE_FORBIDDEN;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.framework.common.pojo.CommonResult.success;
import static cn.iocoder.yudao.framework.security.core.util.SecurityFrameworkUtils.getLoginUser;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_FORBIDDEN;

/**
 * 管理后台 - AwardIE 待审成果提交(批4,提交流纵切面)
 *
 * <p>端点:批4 提交侧四件套 + 批5 审核侧(审核/时间线/待审列表/AI 建议)。
 * submitter_type 由服务端按登录用户角色推导,不信任前端入参。
 *
 * @author AwardIE
 */
@Tag(name = "管理后台 - AwardIE 待审成果")
@RestController
@RequestMapping("/business/pending-achievements")
@Validated
public class PendingAchievementController {

    @Resource
    private PendingSubmissionService submissionService;
    @Resource
    private SubmitterTypeResolver submitterTypeResolver;
    @Resource
    private AwardieFileStorage fileStorage;
    @Resource
    private ReviewOperatorResolver operatorResolver;
    @Resource
    private ReviewService reviewService;
    @Resource
    private AiReviewService aiReviewService;
    @Resource
    private org.springframework.jdbc.core.JdbcTemplate jdbcTemplate;

    /**
     * 提交成果(multipart)。字段问题不阻断提交(校验结果落库供审核参考,沿 v2 语义)。
     *
     * @param file             成果文件
     * @param achievementType  成果类型
     * @param data             成果字段 JSON
     * @return 入库后的待审成果
     */
    @PostMapping("/submit")
    @Operation(summary = "提交 AwardIE 待审成果")
    @PreAuthorize("@ss.hasPermission('business:pending-achievement:create')")
    public CommonResult<PendingAchievementRespVO> submit(
            @RequestPart("file") MultipartFile file,
            @RequestParam(value = "achievementType", defaultValue = SubmissionValidator.TYPE_AWARD) String achievementType,
            @RequestParam("data") String data) throws IOException {
        Long userId = getLoginUser().getId();
        String submitterType = submitterTypeResolver.resolve(userId);
        ReviewOperatorResolver.Operator operator = operatorResolver.current();
        PendingAchievementDO entity = submissionService.submit(userId, submitterType, achievementType,
                file.getOriginalFilename(), file.getBytes(), data, operator.code(), operator.name());
        return success(cn.iocoder.yudao.framework.common.util.object.BeanUtils.toBean(entity,
                PendingAchievementRespVO.class));
    }

    /**
     * 我的提交(按当前登录用户过滤)
     *
     * @param pageReqVO 分页参数
     * @return 分页结果
     */
    @GetMapping("/my-page")
    @Operation(summary = "获得我的待审成果分页")
    @PreAuthorize("@ss.hasPermission('business:pending-achievement:query')")
    public CommonResult<PageResult<PendingAchievementRespVO>> getMySubmissionPage(
            @Valid PendingAchievementPageReqVO pageReqVO) {
        pageReqVO.setSubmitterId(getLoginUser().getId());
        return success(submissionService.getMySubmissionPage(pageReqVO));
    }

    /**
     * 撤回提交(仅本人且待审状态)
     *
     * @param id 编号
     * @return 是否成功
     */
    @DeleteMapping("/withdraw")
    @Operation(summary = "撤回 AwardIE 待审成果")
    @Parameter(name = "id", description = "编号", required = true)
    @PreAuthorize("@ss.hasPermission('business:pending-achievement:delete')")
    public CommonResult<Boolean> withdraw(@RequestParam("id") Long id) {
        submissionService.withdraw(id, getLoginUser().getId());
        return success(true);
    }

    /**
     * 下载成果文件(本人或 teacher/admin;一律 attachment,BR-7)
     *
     * @param id       编号
     * @param response 响应
     * @throws IOException 读盘失败
     */
    @GetMapping("/download")
    @Operation(summary = "下载待审成果文件")
    @Parameter(name = "id", description = "编号", required = true)
    @PreAuthorize("@ss.hasPermission('business:pending-achievement:query')")
    public void download(@RequestParam("id") Long id, HttpServletResponse response) throws IOException {
        PendingAchievementDO entity = submissionService.get(id);
        LoginUser loginUser = getLoginUser();
        // 用登录用户 id 侧发起比较:submitter_id 列可空(批量通道可能不填),反向比较会 NPE
        boolean owner = loginUser.getId().equals(entity.getSubmitterId());
        if (!owner && !hasStaffRole(loginUser)) {
            throw exception(PENDING_ACHIEVEMENT_FORBIDDEN);
        }
        byte[] bytes = fileStorage.readAll(entity.getFilePath());
        response.setContentType(fileStorage.contentTypeOf(entity.getFilePath()));
        response.setHeader(HttpHeaders.CONTENT_DISPOSITION,
                "attachment; filename=\"" + fileNameOf(entity.getFilePath()) + "\"");
        try (OutputStream out = response.getOutputStream()) {
            out.write(bytes);
        }
    }

    private boolean hasStaffRole(LoginUser loginUser) {
        String submitterType = submitterTypeResolver.resolve(loginUser.getId());
        return SubmitterTypeResolver.TYPE_TEACHER.equals(submitterType)
                || SubmitterTypeResolver.TYPE_ADMIN.equals(submitterType);
    }

    // ========== 批5 审核侧 ==========

    /**
     * 审核动作(approve 通过并物化 / reject 驳回)
     *
     * @param id   待审成果编号
     * @param body 审核请求
     * @return 审核后的待审成果
     */
    @PostMapping("/{id}/review")
    @Operation(summary = "审核 AwardIE 待审成果(approve/reject)")
    @Parameter(name = "id", description = "编号", required = true)
    @PreAuthorize("@ss.hasPermission('business:pending-achievement:review')")
    public CommonResult<PendingAchievementRespVO> review(@PathVariable("id") Long id,
            @Valid @RequestBody PendingReviewReqVO body) {
        // 权限点只是"能不能进这个门",不等于"该不该由这个人审"。审核是教师/管理员的
        // 专属动作(approve 还会物化写入成果库),与 download/timeline/ai-suggest 三个
        // 兄弟端点一致地补一道 staff 校验:权限授权一旦配错(如把 review 误授给学生
        // 角色),这里仍是最后一道闸。
        if (!hasStaffRole(getLoginUser())) {
            throw exception(PENDING_ACHIEVEMENT_FORBIDDEN);
        }
        ReviewOperatorResolver.Operator operator = operatorResolver.current();
        Long userId = getLoginUser().getId();
        PendingAchievementDO entity;
        if (PendingReviewReqVO.ACTION_APPROVE.equals(body.getAction())) {
            entity = reviewService.approve(id, userId, operator.code(), operator.name(), body.getComment());
        } else if (PendingReviewReqVO.ACTION_REJECT.equals(body.getAction())) {
            entity = reviewService.reject(id, userId, operator.code(), operator.name(), body.getComment());
        } else {
            throw exception(REVIEW_ACTION_INVALID);
        }
        return success(BeanUtils.toBean(entity, PendingAchievementRespVO.class));
    }

    /**
     * 审核时间线(本人/教师/管理员可见)
     *
     * @param id 待审成果编号
     * @return 留痕列表(创建时间升序)
     */
    @GetMapping("/{id}/timeline")
    @Operation(summary = "获得待审成果审核时间线")
    @Parameter(name = "id", description = "编号", required = true)
    @PreAuthorize("@ss.hasPermission('business:pending-achievement:query')")
    public CommonResult<List<PendingTimelineRespVO>> timeline(@PathVariable("id") Long id) {
        PendingAchievementDO entity = submissionService.get(id);
        LoginUser loginUser = getLoginUser();
        boolean owner = loginUser.getId().equals(entity.getSubmitterId());
        if (!owner && !hasStaffRole(loginUser)) {
            throw exception(REVIEW_TIMELINE_FORBIDDEN);
        }
        return success(reviewService.timeline(id).stream()
                .map(PendingTimelineRespVO::from)
                .toList());
    }

    /**
     * 教师待审列表(含提交者姓名;键名驼峰即契约)
     *
     * @param status 可选状态过滤
     * @return 待审列表
     */
    @GetMapping("/teacher-pending-list")
    @Operation(summary = "获得教师待审列表")
    @PreAuthorize("@ss.hasPermission('business:pending-achievement:query')")
    public CommonResult<List<Map<String, Object>>> teacherPendingList(
            @RequestParam(value = "status", required = false) String status) {
        long tenantId = TenantContextHolder.getRequiredTenantId();
        String sql = "SELECT p.id, p.achievement_type AS achievementType, p.status, "
                + "p.submitter_type AS submitterType, p.submitter_id AS submitterId, "
                + "u.nickname AS submitterName, p.submit_time AS submitTime "
                + "FROM awardie_pending_achievements p "
                + "LEFT JOIN system_users u ON u.id = p.submitter_id "
                + "WHERE p.tenant_id = ? AND p.deleted = b'0' "
                + (status == null || status.isBlank() ? "" : " AND p.status = ? ")
                + "ORDER BY p.id DESC";
        if (status == null || status.isBlank()) {
            return success(jdbcTemplate.queryForList(sql, tenantId));
        }
        return success(jdbcTemplate.queryForList(sql, tenantId, status));
    }

    /**
     * AI 审核建议(fake/grpc 双模式;Worker 不可用时降级为人工审,不阻塞审核)
     *
     * <p>归属校验与 download/timeline 同口径:AI 建议会回带 OCR 文本与字段问题清单,
     * 属提交材料内容,不能只凭 query 权限让任意登录用户枚举 id 读他人成果。
     *
     * @param id 待审成果编号
     * @return 建议
     */
    @GetMapping("/{id}/ai-suggest")
    @Operation(summary = "获得待审成果的 AI 审核建议")
    @Parameter(name = "id", description = "编号", required = true)
    @PreAuthorize("@ss.hasPermission('business:pending-achievement:query')")
    public CommonResult<AiReviewService.Suggestion> aiSuggest(@PathVariable("id") Long id) {
        LoginUser loginUser = getLoginUser();
        PendingAchievementDO entity = submissionService.get(id);
        boolean owner = loginUser.getId().equals(entity.getSubmitterId());
        if (!owner && !hasStaffRole(loginUser)) {
            throw exception(PENDING_ACHIEVEMENT_FORBIDDEN);
        }
        return success(aiReviewService.suggest(entity));
    }

    private String fileNameOf(String filePath) {
        int slash = Math.max(filePath.lastIndexOf('/'), filePath.lastIndexOf('\\'));
        return slash >= 0 ? filePath.substring(slash + 1) : filePath;
    }

}
