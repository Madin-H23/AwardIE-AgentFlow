package com.awardie.submission;

import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;

import com.awardie.auth.UserEntity;
import com.awardie.auth.UserRepository;

import jakarta.transaction.Transactional;

/** 提交领域服务:字段校验(语义对齐 v1 _validate_award_data)+ 三校验文件 + 入库。 */
@Service
public class SubmissionService {

    /** v1 award 字段集(15 字段中 P0 表单收集 8 个核心字段;date 多格式校验对齐 v1)。 */
    private static final List<String> AWARD_REQUIRED = List.of("competition_name", "award_level", "winner_name", "date");
    private static final DateTimeFormatter[] DATE_FORMATS = {
            DateTimeFormatter.ofPattern("yyyy-MM-dd"),
            DateTimeFormatter.ofPattern("yyyy-MM"),
            DateTimeFormatter.ofPattern("yyyy-M"),
            DateTimeFormatter.ofPattern("yyyy/MM/dd"),
    };

    private final PendingAchievementRepository pendingRepo;
    private final FileStorageService storage;
    private final UserRepository users;
    private final AuditLogRepository auditRepo;

    public SubmissionService(PendingAchievementRepository pendingRepo, FileStorageService storage,
            UserRepository users, AuditLogRepository auditRepo) {
        this.pendingRepo = pendingRepo;
        this.storage = storage;
        this.users = users;
        this.auditRepo = auditRepo;
    }

    public record SubmissionResult(PendingAchievementEntity entity, List<String> contentIssues,
            List<String> completenessIssues) {}

    @Transactional
    public SubmissionResult submitAward(Integer studentId, String filename, byte[] fileBytes, String dataJson)
            throws java.io.IOException {
        // 1. 文件三校验
        storage.assertAllowed(filename, fileBytes);

        // 2. 字段校验(v1 语义:必填 + date 多格式 + 年份区间)
        List<String> completeness = new ArrayList<>();
        List<String> content = new ArrayList<>();
        var data = parseData(dataJson);
        for (String field : AWARD_REQUIRED) {
            if (isBlank(data, field)) {
                completeness.add("缺少必填字段: " + field);
            }
        }
        String date = str(data, "date");
        if (!date.isBlank() && !validDate(date)) {
            content.add("日期格式不正确,支持格式:YYYY-MM-DD、YYYY-MM、YYYY-M");
        }
        boolean isValid = content.isEmpty() && completeness.isEmpty();

        // 3. file_hash 去重(BR:同一文件不重复入库)
        FileStorageService.StoredFile stored = storage.store(filename, fileBytes);
        pendingRepo.findByFileHashAndStatus(stored.sha256(), "pending").ifPresent(e -> {
            throw new IllegalStateException("该文件已在待审列表中(sha256 去重)");
        });

        // 4. 入库
        PendingAchievementEntity e = new PendingAchievementEntity();
        e.setAchievementType("award");
        e.setAchievementData(dataJson == null || dataJson.isBlank() ? "{}" : dataJson);
        e.setValidationResult("{\"is_valid\":" + isValid
                + ",\"content_issues\":" + toJsonArray(content)
                + ",\"completeness_issues\":" + toJsonArray(completeness) + "}");
        e.setSubmitterType("student");
        e.setSubmitterId(studentId);
        e.setSubmitTime(Instant.now());
        e.setCreatedAt(Instant.now());
        e.setStatus("pending");
        e.setFilePath(stored.relativePath());
        e.setFileHash(stored.sha256());
        e.setVersion(1);
        pendingRepo.save(e);
        // 留痕 action_type=1(提交),v1 ACTION_LABELS 单一真源
        UserEntity operator = users.findById(Long.valueOf(studentId)).orElse(null);
        if (operator != null) {
            AuditLogEntity a = new AuditLogEntity();
            a.setAchievementId(e.getId());
            a.setAchievementKind("award");
            a.setActionType(1);
            a.setActionResult(1);
            a.setOperatorId(operator.getId());
            a.setOperatorCode(operator.getLoginCode());
            a.setOperatorName(operator.getName());
            a.setChangeDetail("{\"message\":\"提交成果\"}");
            a.setCreatedAt(Instant.now());
            auditRepo.save(a);
        }
        return new SubmissionResult(e, content, completeness);
    }

    public List<PendingAchievementEntity> mySubmissions(Integer studentId) {
        return pendingRepo.findBySubmitterIdOrderByCreatedAtDesc(studentId);
    }

    public UserEntity requireUser(String loginCode) {
        return users.findByLoginCode(loginCode).orElseThrow(() -> new IllegalStateException("用户不存在"));
    }

    private static boolean validDate(String s) {
        for (DateTimeFormatter f : DATE_FORMATS) {
            try {
                var d = LocalDate.parse(s, f);
                return d.getYear() >= 2000 && d.getYear() <= 2100;
            } catch (Exception ignore) {
                // 尝试下一格式
            }
        }
        try {
            var ym = YearMonth.parse(s, DateTimeFormatter.ofPattern("yyyy-M"));
            return ym.getYear() >= 2000 && ym.getYear() <= 2100;
        } catch (Exception ignore) {
            return false;
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> parseData(String dataJson) {
        try {
            return new com.fasterxml.jackson.databind.ObjectMapper().readValue(
                    dataJson == null || dataJson.isBlank() ? "{}" : dataJson, Map.class);
        } catch (Exception e) {
            throw new IllegalArgumentException("achievement_data 不是合法 JSON");
        }
    }

    private static String str(Map<String, Object> data, String key) {
        Object v = data.get(key);
        return v == null ? "" : String.valueOf(v).trim();
    }

    private static boolean isBlank(Map<String, Object> data, String key) {
        return str(data, key).isEmpty();
    }

    private static String toJsonArray(List<String> items) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < items.size(); i++) {
            if (i > 0) {
                sb.append(",");
            }
            sb.append('"').append(items.get(i).replace("\"", "'")).append('"');
        }
        return sb.append("]").toString();
    }
}
