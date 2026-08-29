package com.awardie.submission;

import java.io.IOException;
import java.nio.file.Files;
import java.time.Instant;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.awardie.auth.UserEntity;
import com.awardie.common.ApiResponse;

/** 学生提交端点(纵切面 #7):提交 / 我的提交列表 / 文件下载(BR-7 attachment)。 */
@RestController
@RequestMapping("/api/v2")
public class StudentSubmissionController {

    private final SubmissionService submissions;
    private final PendingAchievementRepository pendingRepo;
    private final FileStorageService storage;
    private final ReviewService reviewService;

    public StudentSubmissionController(SubmissionService submissions, PendingAchievementRepository pendingRepo,
            FileStorageService storage, ReviewService reviewService) {
        this.submissions = submissions;
        this.pendingRepo = pendingRepo;
        this.storage = storage;
        this.reviewService = reviewService;
    }

    /** 时间线(#11):留痕事件按时间正序;本人/教师/管理员可见。 */
    @GetMapping("/student/timeline/{id}")
    public ApiResponse<java.util.List<ReviewService.AuditLog>> timeline(@PathVariable Integer id,
            Authentication auth) throws IOException {
        UserEntity user = submissions.requireUser(auth.getName());
        PendingAchievementEntity e = pendingRepo.findById(id).orElse(null);
        if (e == null) {
            return ApiResponse.error(4004, "记录不存在");
        }
        boolean owner = user.getId().equals(e.getSubmitterId());
        boolean staff = user.getRole() != null
                && (user.getRole().equalsIgnoreCase("teacher") || user.getRole().equalsIgnoreCase("admin"));
        if (!owner && !staff) {
            return ApiResponse.error(4030, "无权查看他人时间线");
        }
        return ApiResponse.ok(reviewService.timeline(id));
    }

    public record SubmitResponse(Integer id, String status, boolean isValid, String fileHash) {}

    @PostMapping(value = "/student/submit", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<SubmitResponse> submit(@RequestParam("file") MultipartFile file,
            @RequestParam(value = "achievement_type", defaultValue = "award") String achievementType,
            @RequestParam("data") String data,
            Authentication auth) throws IOException {
        UserEntity user = submissions.requireUser(auth.getName());
        requireRole(auth, "student");
        if (!"award".equals(achievementType)) {
            return ApiResponse.error(4000, "P0 纵切面仅开放 award 类型,其余四类在高频扩展阶段");
        }
        byte[] bytes = file.getBytes();
        try {
            SubmissionService.SubmissionResult result = submissions.submitAward(
                    user.getId(), file.getOriginalFilename(), bytes, data);
            return ApiResponse.ok(new SubmitResponse(result.entity().getId(), result.entity().getStatus(),
                    result.contentIssues().isEmpty() && result.completenessIssues().isEmpty(),
                    result.entity().getFileHash()),
                    "提交成功");
        } catch (IllegalArgumentException e) {
            return ApiResponse.error(4000, e.getMessage());
        } catch (IllegalStateException e) {
            return ApiResponse.error(4001, e.getMessage());
        }
    }

    @GetMapping("/student/pending")
    public ApiResponse<java.util.List<PendingAchievementEntity>> myPending(Authentication auth) {
        UserEntity user = submissions.requireUser(auth.getName());
        return ApiResponse.ok(submissions.mySubmissions(user.getId()));
    }

    /** BR-7:下载一律 attachment;本人或教师/管理员可下载。 */
    @GetMapping("/files/{id}/download")
    public ResponseEntity<byte[]> download(@PathVariable Integer id, Authentication auth) throws IOException {
        PendingAchievementEntity e = pendingRepo.findById(id).orElse(null);
        if (e == null) {
            return ResponseEntity.notFound().build();
        }
        UserEntity user = submissions.requireUser(auth.getName());
        boolean owner = user.getId().equals(e.getSubmitterId());
        boolean staff = hasRole(auth, "teacher") || hasRole(auth, "admin");
        if (!owner && !staff) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }
        var path = storage.resolve(e.getFilePath());
        byte[] bytes = Files.readAllBytes(path);
        String filename = path.getFileName().toString();
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .body(bytes);
    }

    private void requireRole(Authentication auth, String role) {
        if (!hasRole(auth, role)) {
            throw new org.springframework.security.access.AccessDeniedException("需要 " + role + " 角色");
        }
    }

    private boolean hasRole(Authentication auth, String role) {
        for (GrantedAuthority a : auth.getAuthorities()) {
            if (a.getAuthority().equals("ROLE_" + role.toUpperCase())) {
                return true;
            }
        }
        return false;
    }
}
