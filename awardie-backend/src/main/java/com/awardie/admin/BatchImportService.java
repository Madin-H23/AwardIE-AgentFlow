package com.awardie.admin;

import java.util.ArrayList;
import java.util.List;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.awardie.auth.UserEntity;
import com.awardie.submission.PendingAchievementEntity;
import com.awardie.submission.PendingAchievementRepository;
import com.awardie.submission.SubmissionService;

/** 图片批量导入(#40,对照 v1 file_import 自动导入通道):多图→校验/存储/去重→admin pending 归档。 */
@Service
public class BatchImportService {

    public record BatchItem(String filename, boolean ok, Integer pendingId, String message) {}

    private final SubmissionService submissions;
    private final PendingAchievementRepository pendingRepo;
    private final JdbcTemplate jdbc;

    public BatchImportService(SubmissionService submissions, PendingAchievementRepository pendingRepo,
            JdbcTemplate jdbc) {
        this.submissions = submissions;
        this.pendingRepo = pendingRepo;
        this.jdbc = jdbc;
    }

    /**
     * 逐张导入:复用 submit 三校验/存储/去重/留痕(submitterType=admin,满足创新项目 CHECK 的同款通道语义)。
     * 字段占位待人工补录——OCR 自动抽取待 AI Worker 扩 extract RPC 后接入(对照记录声明)。
     */
    public List<BatchItem> importBatch(List<byte[]> fileBytesList, List<String> filenames, UserEntity operator) {
        List<BatchItem> results = new ArrayList<>();
        for (int i = 0; i < filenames.size(); i++) {
            String filename = filenames.get(i);
            byte[] bytes = fileBytesList.get(i);
            try {
                // 文件名进 JSON 前清洗(引号/反斜杠/控制符),防 dataJson 转义破坏
                String safeName = filename.replaceAll("[\"\\\\\\r\\n]", "");
                String dataJson = "{\"competition_name\":\"批量导入-" + safeName
                        + "\",\"award_level\":\"\",\"date\":\"\"}";
                SubmissionService.SubmissionResult r = submissions.submit(
                        operator.getId(), "award", filename, bytes, dataJson, "admin");
                markImported(r.entity().getId());
                results.add(new BatchItem(filename, true, r.entity().getId(),
                        r.contentIssues().isEmpty() && r.completenessIssues().isEmpty()
                                ? "已入库,待人工补录字段"
                                : "已入库(" + String.join(";", r.completenessIssues()) + ")"));
            } catch (IllegalStateException e) { // sha 去重
                results.add(new BatchItem(filename, false, null, "跳过:" + e.getMessage()));
            } catch (IllegalArgumentException e) { // 校验失败(类型/大小)
                results.add(new BatchItem(filename, false, null, "拒绝:" + e.getMessage()));
            } catch (Exception e) {
                results.add(new BatchItem(filename, false, null, "失败:" + e.getMessage()));
            }
        }
        return results;
    }

    private void markImported(Integer pendingId) {
        jdbc.update("UPDATE pending_achievements SET validation_result = ?::jsonb WHERE id = ?",
                "{\"batch_import\":true,\"ocr_extracted\":false}", pendingId);
    }
}
