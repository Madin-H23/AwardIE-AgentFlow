package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.io.IOException;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import com.awardie.auth.UserEntity;
import com.awardie.auth.UserRepository;
import com.awardie.submission.AuditLogEntity;
import com.awardie.submission.AuditLogRepository;
import com.awardie.submission.FileStorageService;
import com.awardie.submission.PendingAchievementEntity;
import com.awardie.submission.PendingAchievementRepository;
import com.awardie.submission.ReviewService;
import com.awardie.submission.SubmissionService;

/**
 * G5 服务层纯 Mockito 单测(不起 Spring 上下文,秒级):
 * SubmissionService 校验分发五分支/去重/上限 + ReviewService 状态机非法流转。
 * LENIENT 模式:共享 helper 桩允许部分用例未触发。
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class ServiceLayerUnitTest {

    @Mock
    private PendingAchievementRepository pendingRepo;

    @Mock
    private FileStorageService storage;

    @Mock
    private UserRepository users;

    @Mock
    private AuditLogRepository auditRepo;

    @Mock
    private org.springframework.jdbc.core.JdbcTemplate jdbc;

    private UserEntity operator() {
        // UserEntity 字段无 setter(实体风格),用反射置测试值
        UserEntity u = new UserEntity();
        setField(u, "id", 9);
        setField(u, "loginCode", "unit-op");
        setField(u, "role", "admin");
        return u;
    }

    private static void setField(Object target, String name, Object value) {
        try {
            var f = target.getClass().getDeclaredField(name);
            f.setAccessible(true);
            f.set(target, value);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException(e);
        }
    }

    private PendingAchievementEntity pending(String status) {
        PendingAchievementEntity e = new PendingAchievementEntity();
        e.setId(1);
        e.setAchievementType("award");
        e.setAchievementData("{\"competition_name\":\"单测赛\",\"award_level\":\"一等奖\"}");
        e.setSubmitterType("student");
        e.setSubmitterId(2);
        e.setStatus(status);
        e.setVersion(1);
        return e;
    }

    private static final byte[] PNG = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A};

    // ---------- ReviewService 状态机 ----------

    private ReviewService reviewService() {
        return new ReviewService(pendingRepo, auditRepo, users, jdbc);
    }

    @Test
    void approvePendingToArchived() {
        PendingAchievementEntity e = pending("pending");
        when(pendingRepo.findById(1)).thenReturn(Optional.of(e));
        when(pendingRepo.save(any())).thenAnswer(inv -> inv.getArgument(0));
        // 物化链 jdbc 桩:竞赛匹配命中/新 award id/关联 COUNT
        when(jdbc.queryForList(anyString(), org.mockito.ArgumentMatchers.eq(Integer.class),
                any(Object[].class))).thenReturn(List.of(5));
        when(jdbc.queryForObject(anyString(), org.mockito.ArgumentMatchers.eq(Integer.class),
                any(Object[].class))).thenReturn(7, 0);
        ReviewService svc = reviewService();
        PendingAchievementEntity out = svc.approve(1, operator(), "ok");
        assertThat(out.getStatus()).isEqualTo("archived");
        verify(auditRepo).save(any(AuditLogEntity.class));
    }

    @Test
    void rejectPendingToRejected() {
        PendingAchievementEntity e = pending("pending");
        when(pendingRepo.findById(1)).thenReturn(Optional.of(e));
        ReviewService svc = reviewService();
        PendingAchievementEntity out = svc.reject(1, operator(), "材料不全");
        assertThat(out.getStatus()).isEqualTo("rejected");
        assertThat(out.getReviewComment()).isEqualTo("材料不全");
        verify(auditRepo).save(any(AuditLogEntity.class));
    }

    @Test
    void archivedCannotBeReviewedAgain() {
        when(pendingRepo.findById(1)).thenReturn(Optional.of(pending("archived")));
        assertThatThrownBy(() -> reviewService().approve(1, operator(), "x"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("非法流转");
    }

    @Test
    void rejectedCannotBeReviewedAgain() {
        when(pendingRepo.findById(1)).thenReturn(Optional.of(pending("rejected")));
        assertThatThrownBy(() -> reviewService().reject(1, operator(), "x"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("非法流转");
    }

    @Test
    void missingRecordIsIllegalArgument() {
        when(pendingRepo.findById(99)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> reviewService().approve(99, operator(), "x"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("记录不存在");
    }

    // ---------- SubmissionService 校验分发 ----------

    private SubmissionService submissionService() throws IOException {
        SubmissionService svc = new SubmissionService(pendingRepo, storage, users, auditRepo);
        when(storage.store(anyString(), any())).thenReturn(
                new FileStorageService.StoredFile("files/v2/unit.png", "sha-unit", 10));
        when(users.findById(any())).thenReturn(Optional.of(operator()));
        when(pendingRepo.findByFileHashAndStatus(anyString(), anyString()))
                .thenReturn(Optional.empty());
        when(pendingRepo.save(any())).thenAnswer(inv -> {
            PendingAchievementEntity e = inv.getArgument(0);
            e.setId(7);
            return e;
        });
        return svc;
    }

    @Test
    void awardValidPasses() throws IOException {
        var r = submissionService().submit(2, "award", "u.png", PNG,
                "{\"competition_name\":\"单测\",\"award_level\":\"一等奖\",\"winner_name\":\"张三\",\"date\":\"2026-09\"}");
        assertThat(r.entity().getStatus()).isEqualTo("pending");
        assertThat(r.contentIssues()).isEmpty();
        assertThat(r.completenessIssues()).isEmpty();
    }

    @Test
    void patentBadNumberIsContentIssue() throws IOException {
        var r = submissionService().submit(2, "patent", "u.png", PNG,
                "{\"patent_name\":\"P\",\"application_number\":\"XX123\"}");
        assertThat(r.contentIssues()).isNotEmpty();
    }

    @Test
    void softwareBadRegistrationIsContentIssue() throws IOException {
        var r = submissionService().submit(2, "software", "u.png", PNG,
                "{\"software_name\":\"S\",\"registration_number\":\"短号\"}");
        assertThat(r.contentIssues()).isNotEmpty();
    }

    @Test
    void innovationRequiresProjectName() throws IOException {
        var r = submissionService().submit(2, "innovation", "u.png", PNG, "{}");
        assertThat(r.completenessIssues()).isNotEmpty();
    }

    @Test
    void otherRequiresTitle() throws IOException {
        var r = submissionService().submit(2, "other", "u.png", PNG, "{}");
        assertThat(r.completenessIssues()).isNotEmpty();
    }

    @Test
    void unknownTypeRejected() {
        assertThatThrownBy(() -> submissionService().submit(2, "nope", "u.png", PNG, "{}"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("未知成果类型");
    }

    @Test
    void duplicateShaRejected() throws IOException {
        SubmissionService svc = submissionService();
        // helper 已置空桩;此处重桩为"已存在"——顺序在创建之后,后桩生效
        when(pendingRepo.findByFileHashAndStatus(anyString(), anyString()))
                .thenReturn(Optional.of(pending("pending")));
        assertThatThrownBy(() -> svc.submit(2, "award", "u.png", PNG,
                "{\"competition_name\":\"重复\"}"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("去重");
    }

    @Test
    void oversizeRejectedBeforeStore() throws IOException {
        byte[] big = new byte[10 * 1024 * 1024 + 1];
        big[0] = PNG[0];
        big[1] = PNG[1];
        org.mockito.Mockito.doThrow(new IllegalArgumentException("文件超过 10MB 上限"))
                .when(storage).assertAllowed(anyString(), any());
        SubmissionService svc = new SubmissionService(pendingRepo, storage, users, auditRepo);
        assertThatThrownBy(() -> svc.submit(2, "award", "big.png", big, "{}"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("10MB");
        verify(storage, never()).store(anyString(), any());
    }
}
