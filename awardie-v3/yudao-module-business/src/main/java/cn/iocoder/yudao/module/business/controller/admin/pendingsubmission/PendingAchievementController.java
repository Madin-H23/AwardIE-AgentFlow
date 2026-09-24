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

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.framework.common.pojo.CommonResult.success;
import static cn.iocoder.yudao.framework.security.core.util.SecurityFrameworkUtils.getLoginUser;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_FORBIDDEN;

/**
 * 管理后台 - AwardIE 待审成果提交(批4,提交流纵切面)
 *
 * <p>四个端点:v2 提交流的提交侧等价物(时间线与审核动作属批5)。
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
        PendingAchievementDO entity = submissionService.submit(userId, submitterType, achievementType,
                file.getOriginalFilename(), file.getBytes(), data);
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

    private String fileNameOf(String filePath) {
        int slash = Math.max(filePath.lastIndexOf('/'), filePath.lastIndexOf('\\'));
        return slash >= 0 ? filePath.substring(slash + 1) : filePath;
    }

}
