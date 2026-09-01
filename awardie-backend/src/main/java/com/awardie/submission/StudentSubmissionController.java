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
    private final org.springframework.jdbc.core.JdbcTemplate jdbc;

    public StudentSubmissionController(SubmissionService submissions, PendingAchievementRepository pendingRepo,
            FileStorageService storage, ReviewService reviewService,
            org.springframework.jdbc.core.JdbcTemplate jdbc) {
        this.submissions = submissions;
        this.pendingRepo = pendingRepo;
        this.storage = storage;
        this.reviewService = reviewService;
        this.jdbc = jdbc;
    }

    /** 我的成果(#14):批准物化后走 awards 维度(join 获奖关联)。 */
    @GetMapping("/student/awards")
    public ApiResponse<java.util.List<java.util.Map<String, Object>>> myAwards(Authentication auth)
            throws IOException {
        UserEntity user = submissions.requireUser(auth.getName());
        var rows = jdbc.queryForList("""
                SELECT a.id, a.competition_name_in_file AS competition_name, a.award_level,
                       a.winner_name, a.date, a.created_at
                FROM awards a
                JOIN award_student_winners w ON w.award_id = a.id
                WHERE w.student_id = ?
                ORDER BY a.id DESC
                """, user.getId());
        return ApiResponse.ok(rows);
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

    public record SubmitResponse(Integer id, String status, boolean isValid, String fileHash,
            String achievementType, String issues) {}

    @PostMapping(value = "/student/submit", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<SubmitResponse> submit(@RequestParam("file") MultipartFile file,
            @RequestParam(value = "achievement_type", defaultValue = "award") String achievementType,
            @RequestParam("data") String data,
            Authentication auth) throws IOException {
        UserEntity user = submissions.requireUser(auth.getName());
        // D2:教师也可提交成果(v1 语义);submitter_type 按实际角色落库
        requireRole(auth, "student", "teacher");
        if (!achievementType.matches("award|patent|software|innovation|other")) {
            return ApiResponse.error(4000, "未知成果类型");
        }
        byte[] bytes = file.getBytes();
        try {
            SubmissionService.SubmissionResult result = submissions.submit(
                    user.getId(), achievementType, file.getOriginalFilename(), bytes, data,
                    user.getRole().toLowerCase());
            var issues = new java.util.ArrayList<String>();
            issues.addAll(result.completenessIssues());
            issues.addAll(result.contentIssues());
            return ApiResponse.ok(new SubmitResponse(result.entity().getId(), result.entity().getStatus(),
                    result.contentIssues().isEmpty() && result.completenessIssues().isEmpty(),
                    result.entity().getFileHash(), result.entity().getAchievementType(),
                    String.join(";", issues)),
                    "提交成功");
        } catch (IllegalArgumentException e) {
            return ApiResponse.error(4000, e.getMessage());
        } catch (IllegalStateException e) {
            return ApiResponse.error(4001, e.getMessage());
        }
    }

    /** 我的提交(#26):默认全量(tracer/时间线兼容);带 page/size 时分页(单用户量小)。 */
    @GetMapping("/student/pending")
    public ApiResponse<Object> myPending(Authentication auth,
            @RequestParam(required = false) Integer page,
            @RequestParam(required = false) Integer size) {
        UserEntity user = submissions.requireUser(auth.getName());
        var all = submissions.mySubmissions(user.getId());
        if (page == null && size == null) {
            return ApiResponse.ok(all);
        }
        int p = Math.max(page == null ? 0 : page, 0);
        int s = Math.min(Math.max(size == null ? 20 : size, 1), 100);
        int from = Math.min(p * s, all.size());
        int to = Math.min(from + s, all.size());
        int totalPages = all.isEmpty() ? 0 : (all.size() + s - 1) / s;
        return ApiResponse.ok(new com.awardie.common.PageView<>(all.subList(from, to), all.size(), totalPages, p, s));
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

    private void requireRole(Authentication auth, String... roles) {
        for (String role : roles) {
            if (hasRole(auth, role)) {
                return;
            }
        }
        throw new org.springframework.security.access.AccessDeniedException("需要 " + String.join("/", roles) + " 角色");
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
