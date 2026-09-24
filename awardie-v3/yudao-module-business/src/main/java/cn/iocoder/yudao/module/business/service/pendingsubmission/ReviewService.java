package cn.iocoder.yudao.module.business.service.pendingsubmission;

import cn.iocoder.yudao.module.business.dal.dataobject.audit.AchievementAuditLogDO;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission.PendingAchievementDO;
import cn.iocoder.yudao.module.business.dal.mysql.audit.AchievementAuditLogMapper;
import cn.iocoder.yudao.module.business.dal.mysql.competition.CompetitionsMapper;
import cn.iocoder.yudao.module.business.dal.mysql.pendingsubmission.PendingAchievementMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.PENDING_ACHIEVEMENT_NOT_EXISTS;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.REVIEW_COMMENT_REQUIRED;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.REVIEW_ILLEGAL_STATE_TRANSITION;

/**
 * 审核服务(批5):状态机 + 审计留痕 + 物化入库,语义逐条对照 v2 ReviewService
 *
 * <p>与 v2 的两处刻意差异:
 * <ul>
 *   <li><b>幂等判据</b>:v2 靠"审计有 action_type=8"判幂等,但 v2 存量有 164 条 archived 无该留痕
 *       (不可靠);v3 改查业务事实(file_hash / 唯一键),见 materialize*</li>
 *   <li><b>innovation 不物化</b>:沿 v1/v2 语义——大创限 admin Excel 导入通道(批8),学生归档不物化</li>
 * </ul>
 *
 * @author AwardIE
 */
@Service
@Validated
public class ReviewService {

    /** 动作码(沿 v1 ACTION_LABELS) */
    public static final int ACTION_SUBMIT = 1;
    public static final int ACTION_APPROVE = 6;
    public static final int ACTION_REJECT = 7;
    public static final int ACTION_MATERIALIZE = 8;
    /** 动作结果(1=成功) */
    private static final int ACTION_RESULT_OK = 1;
    /** 大创物化占位(v1 语义:大创限 admin Excel 通道) */
    public static final String MATERIALIZE_SKIPPED = "skipped";
    /** BR-2:AI 建议仅辅助参考 */
    public static final String AI_DISCLAIMER = "AI 建议仅辅助参考,最终以人工审核为准";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Resource
    private PendingAchievementMapper pendingMapper;
    @Resource
    private CompetitionsMapper competitionsMapper;
    @Resource
    private AchievementAuditLogMapper auditMapper;
    @Resource
    private JdbcTemplate jdbcTemplate;

    /**
     * 审核通过:pending → archived,并物化入库(与 approve 同事务:物化失败整体回滚)
     *
     * @param id           待审成果编号
     * @param operatorId   审核人编号
     * @param operatorCode 审核人账号
     * @param operatorName 审核人姓名
     * @param comment      审核意见
     * @return 审核后的待审成果
     */
    @Transactional(rollbackFor = Exception.class)
    public PendingAchievementDO approve(Long id, Long operatorId, String operatorCode, String operatorName,
            String comment) {
        PendingAchievementDO entity = requirePending(id);
        entity.setStatus(PendingSubmissionService.STATUS_ARCHIVED);
        entity.setReviewerId(operatorId);
        entity.setReviewTime(LocalDateTime.now());
        entity.setReviewComment(comment == null ? "" : comment);
        pendingMapper.updateById(entity);
        audit(entity, ACTION_APPROVE, operatorId, operatorCode, operatorName, "审核通过", comment);
        String ref = materialize(entity);
        audit(entity, ACTION_MATERIALIZE, operatorId, operatorCode, operatorName, "入库", ref);
        return entity;
    }

    /**
     * 驳回:pending → rejected,原因必填(BR-5)
     *
     * @param id           待审成果编号
     * @param operatorId   审核人编号
     * @param operatorCode 审核人账号
     * @param operatorName 审核人姓名
     * @param comment      驳回原因
     * @return 审核后的待审成果
     */
    @Transactional(rollbackFor = Exception.class)
    public PendingAchievementDO reject(Long id, Long operatorId, String operatorCode, String operatorName,
            String comment) {
        if (comment == null || comment.isBlank()) {
            throw exception(REVIEW_COMMENT_REQUIRED);
        }
        PendingAchievementDO entity = requirePending(id);
        entity.setStatus(PendingSubmissionService.STATUS_REJECTED);
        entity.setReviewerId(operatorId);
        entity.setReviewTime(LocalDateTime.now());
        entity.setReviewComment(comment);
        pendingMapper.updateById(entity);
        audit(entity, ACTION_REJECT, operatorId, operatorCode, operatorName, "驳回打回", comment);
        return entity;
    }

    /**
     * 补写提交留痕(action_type=1;批4 提交时未写,此处按需补,防重)
     *
     * @param entity       待审成果
     * @param operatorId   操作人编号
     * @param operatorCode 操作人账号
     * @param operatorName 操作人姓名
     */
    @Transactional(rollbackFor = Exception.class)
    public void auditSubmit(PendingAchievementDO entity, Long operatorId, String operatorCode, String operatorName) {
        Long exists = auditMapper.selectCountByAchievementAndAction(entity.getId(), ACTION_SUBMIT);
        if (exists != null && exists > 0) {
            return;
        }
        audit(entity, ACTION_SUBMIT, operatorId, operatorCode, operatorName, "提交成果", null);
    }

    /**
     * 时间线:按待审成果编号升序返回留痕
     *
     * @param achievementId 待审成果编号
     * @return 留痕列表
     */
    public List<AchievementAuditLogDO> timeline(Long achievementId) {
        return auditMapper.selectListByAchievementId(achievementId);
    }

    /**
     * 物化入库:按类型分发到成果表;幂等查业务事实
     *
     * @return 物化引用(表名#id;innovation 返回 skipped)
     */
    private String materialize(PendingAchievementDO entity) {
        Map<String, Object> data = parseData(entity.getAchievementData());
        String type = entity.getAchievementType();
        if (SubmissionValidator.TYPE_AWARD.equals(type)) {
            return materializeAward(entity, data);
        }
        if (SubmissionValidator.TYPE_PATENT.equals(type)) {
            return materializePatent(entity, data);
        }
        if (SubmissionValidator.TYPE_SOFTWARE.equals(type)) {
            return materializeSoftware(entity, data);
        }
        if (SubmissionValidator.TYPE_OTHER.equals(type)) {
            return materializeOther(entity, data);
        }
        if (SubmissionValidator.TYPE_INNOVATION.equals(type)) {
            // v1/v2 语义:大创限 admin Excel 通道(批8),学生归档不物化
            return MATERIALIZE_SKIPPED;
        }
        throw exception(REVIEW_ILLEGAL_STATE_TRANSITION, "未知成果类型:" + type);
    }

    /** 竞赛按名匹配,缺失自动建(is_auto_added=true);返回竞赛 id */
    private Long resolveCompetition(String competitionName) {
        CompetitionsDO existing = competitionsMapper.selectByCompetitionName(competitionName);
        if (existing != null) {
            return existing.getId();
        }
        CompetitionsDO created = new CompetitionsDO();
        created.setCompetitionName(competitionName);
        created.setWhiteList(false);
        created.setWatchList(false);
        created.setIsAutoAdded(true);
        competitionsMapper.insert(created);
        return created.getId();
    }

    private String materializeAward(PendingAchievementDO entity, Map<String, Object> data) {
        // 幂等:按 file_hash 查业务事实(不靠审计留痕——v2 存量有 164 条 archived 无物化留痕)
        Long exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM awardie_awards WHERE image_hash = ? AND deleted = b'0'",
                Long.class, entity.getFileHash());
        if (exists != null && exists > 0) {
            return "awards#exists";
        }
        String competitionName = str(data.get("competition_name"));
        Long competitionId = resolveCompetition(competitionName);
        Map<String, Object> row = new HashMap<>(24);
        row.put("image_hash", entity.getFileHash());
        row.put("certificate_id", nullable(str(data.get("certificate_id"))));
        row.put("certificate_path", entity.getFilePath());
        row.put("competition_name_in_file", competitionName);
        row.put("track", nullable(str(data.get("track"))));
        row.put("issuer", nullable(str(data.get("issuer"))));
        row.put("province", nullable(str(data.get("province"))));
        row.put("group_name", nullable(str(data.get("group_name"))));
        row.put("winner_name", nullable(str(data.get("winner_name"))));
        row.put("supervisor_name", nullable(str(data.get("supervisor_name"))));
        row.put("award_level", nullable(str(data.get("award_level"))));
        row.put("competition_level", nullable(str(data.get("competition_level"))));
        row.put("date", nullable(str(data.get("date"))));
        row.put("project_title", nullable(str(data.get("project_title"))));
        row.put("competition_id", competitionId);
        row.put("submitter_type", entity.getSubmitterType());
        row.put("submitter_id", entity.getSubmitterId());
        row.put("submit_time", entity.getSubmitTime());
        insertByMap("awardie_awards", row);
        Long awardId = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_awards WHERE image_hash = ? ORDER BY id DESC LIMIT 1",
                Long.class, entity.getFileHash());
        // 学生获奖关联(提交人为学生时)
        if (SubmitterTypeResolver.TYPE_STUDENT.equals(entity.getSubmitterType())
                && entity.getSubmitterId() != null) {
            Long linked = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM awardie_award_student_winners WHERE award_id = ? AND student_id = ?",
                    Long.class, awardId, entity.getSubmitterId());
            if (linked == null || linked == 0) {
                insertByMap("awardie_award_student_winners", Map.of(
                        "award_id", awardId, "student_id", entity.getSubmitterId()));
            }
        }
        return "awards#" + awardId;
    }

    private String materializePatent(PendingAchievementDO entity, Map<String, Object> data) {
        String applicationNumber = nullable(str(data.get("application_number")));
        Long exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM awardie_patents WHERE deleted = b'0' AND "
                        + "(application_number = ? OR (application_number IS NULL AND certificate_file = ?))",
                Long.class, applicationNumber, entity.getFilePath());
        if (exists != null && exists > 0) {
            return "patents#exists";
        }
        Map<String, Object> row = new HashMap<>(16);
        row.put("patent_name", str(data.get("patent_name")));
        row.put("patent_type", nullable(str(data.get("patent_type"))));
        row.put("application_number", applicationNumber);
        row.put("inventor", nullable(str(data.get("inventor"))));
        row.put("patentee", nullable(str(data.get("patentee"))));
        row.put("certificate_file", entity.getFilePath());
        row.put("submitter_type", entity.getSubmitterType());
        row.put("submitter_id", entity.getSubmitterId());
        insertByMap("awardie_patents", row);
        Long id = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_patents WHERE certificate_file = ? ORDER BY id DESC LIMIT 1",
                Long.class, entity.getFilePath());
        return "patents#" + id;
    }

    private String materializeSoftware(PendingAchievementDO entity, Map<String, Object> data) {
        String registrationNumber = nullable(str(data.get("registration_number")));
        Long exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM awardie_software_copyrights WHERE deleted = b'0' AND "
                        + "(registration_number = ? OR (registration_number IS NULL AND certificate_file = ?))",
                Long.class, registrationNumber, entity.getFilePath());
        if (exists != null && exists > 0) {
            return "software_copyrights#exists";
        }
        Map<String, Object> row = new HashMap<>(16);
        row.put("software_name", str(data.get("software_name")));
        row.put("software_version", nullable(str(data.get("software_version"))));
        row.put("registration_number", registrationNumber);
        row.put("copyright_owner", nullable(str(data.get("copyright_owner"))));
        row.put("certificate_file", entity.getFilePath());
        row.put("submitter_type", entity.getSubmitterType());
        row.put("submitter_id", entity.getSubmitterId());
        row.put("submit_time", LocalDateTime.now());
        insertByMap("awardie_software_copyrights", row);
        Long id = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_software_copyrights WHERE certificate_file = ? ORDER BY id DESC LIMIT 1",
                Long.class, entity.getFilePath());
        return "software_copyrights#" + id;
    }

    private String materializeOther(PendingAchievementDO entity, Map<String, Object> data) {
        Long exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM awardie_other_files WHERE file_hash = ? AND deleted = b'0'",
                Long.class, entity.getFileHash());
        if (exists != null && exists > 0) {
            return "other_files#exists";
        }
        Map<String, Object> row = new HashMap<>(12);
        // v1 语义:成果名即描述
        row.put("file_name", str(data.get("title")));
        row.put("file_path", entity.getFilePath());
        row.put("file_hash", entity.getFileHash());
        row.put("description", str(data.get("title")));
        row.put("submitter_type", entity.getSubmitterType());
        row.put("submitter_id", entity.getSubmitterId());
        row.put("submit_time", entity.getSubmitTime());
        insertByMap("awardie_other_files", row);
        Long id = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_other_files WHERE file_hash = ? ORDER BY id DESC LIMIT 1",
                Long.class, entity.getFileHash());
        return "other_files#" + id;
    }

    /** 插入(Map 键为代码内常量,值参数化;表名同样为代码内常量) */
    private void insertByMap(String table, Map<String, Object> row) {
        List<String> cols = List.copyOf(row.keySet());
        String placeholders = String.join(", ", Collections.nCopies(cols.size(), "?"));
        jdbcTemplate.update("INSERT INTO " + table + " (" + String.join(", ", cols) + ") VALUES ("
                + placeholders + ")", row.values().toArray());
    }

    /** 状态机守卫:仅 pending 可审 */
    private PendingAchievementDO requirePending(Long id) {
        PendingAchievementDO entity = pendingMapper.selectById(id);
        if (entity == null) {
            throw exception(PENDING_ACHIEVEMENT_NOT_EXISTS);
        }
        if (!PendingSubmissionService.STATUS_PENDING.equals(entity.getStatus())) {
            throw exception(REVIEW_ILLEGAL_STATE_TRANSITION, entity.getStatus());
        }
        return entity;
    }

    /** 写一条审核留痕 */
    private void audit(PendingAchievementDO entity, int actionType, Long operatorId, String operatorCode,
            String operatorName, String message, String comment) {
        AchievementAuditLogDO log = new AchievementAuditLogDO();
        log.setAchievementId(entity.getId());
        log.setAchievementKind(entity.getAchievementType());
        log.setActionType(actionType);
        log.setActionResult(ACTION_RESULT_OK);
        log.setOperatorId(operatorId);
        log.setOperatorCode(operatorCode == null ? "" : operatorCode);
        log.setOperatorName(operatorName == null ? "" : operatorName);
        log.setChangeDetail(changeDetailJson(message, comment));
        auditMapper.insert(log);
    }

    /** change_detail 用 Jackson 序列化(不用手拼——引号/换行安全) */
    private String changeDetailJson(String message, String comment) {
        try {
            Map<String, Object> detail = new HashMap<>(4);
            detail.put("message", message);
            detail.put("comment", comment == null ? "" : comment);
            return MAPPER.writeValueAsString(detail);
        } catch (Exception e) {
            throw new IllegalStateException("留痕详情序列化失败", e);
        }
    }

    private static Map<String, Object> parseData(String dataJson) {
        try {
            return MAPPER.readValue(dataJson == null || dataJson.isBlank() ? "{}" : dataJson,
                    new TypeReference<Map<String, Object>>() {
                    });
        } catch (Exception e) {
            throw new IllegalArgumentException("achievement_data 不是合法 JSON");
        }
    }

    private static String str(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    /** 空串转 NULL:防撞 UNIQUE 约束(同 v2) */
    private static String nullable(String value) {
        return value == null || value.isBlank() ? null : value;
    }

}
