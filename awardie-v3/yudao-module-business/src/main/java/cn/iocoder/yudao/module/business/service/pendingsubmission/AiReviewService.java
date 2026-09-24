package cn.iocoder.yudao.module.business.service.pendingsubmission;

import cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission.PendingAchievementDO;
import cn.iocoder.yudao.module.business.framework.grpc.AiWorkerClient;
import cn.iocoder.yudao.module.business.framework.grpc.AiWorkerProperties;
import cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto;
import cn.iocoder.yudao.module.business.service.file.AwardieFileStorage;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.grpc.StatusRuntimeException;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.validation.annotation.Validated;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.UUID;

/**
 * AI 审核建议(批5 建,批7 接真 Worker):fake/grpc 双模式,不阻塞人工审核
 *
 * <p>fake 模式:依据提交时落库的 validation_result 给出确定性建议(开发/CI 无 Worker 进程时);
 * grpc 模式:调 Python Worker 的 ExtractAndReview(server-streaming),消费到 final 事件后映射为
 * 同一份 Suggestion 契约。
 *
 * <p>降级口径(BR-2:AI 建议仅辅助参考;与批5/v2 一致,未变):流中断、超时、拿不到 final 事件、
 * Worker 业务码非 0,一律转人工审(need_manual + 4003 + 免责声明),不向用户抛错。
 *
 * @author AwardIE
 */
@Service
@Validated
@Slf4j
public class AiReviewService {

    /** Worker 不可用降级码(沿 v1/v2 语义) */
    public static final int DEGRADED_CODE = 4003;
    /** 决策:通过 */
    public static final String DECISION_PASS = "pass";
    /** 决策:驳回 */
    public static final String DECISION_REJECT = "reject";
    /** 决策:需人工审(Worker 不可用/无法判定) */
    public static final String DECISION_NEED_MANUAL = "need_manual";
    /** 问题明细 JSON 数组的键 */
    private static final String KEY_CONTENT_ISSUES = "content_issues";
    private static final String KEY_COMPLETENESS_ISSUES = "completeness_issues";
    private static final String KEY_IS_VALID = "is_valid";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Resource
    private AiWorkerProperties workerProperties;
    @Resource
    private AiWorkerClient workerClient;
    @Resource
    private AwardieFileStorage fileStorage;

    /**
     * AI 建议
     *
     * @param entity 待审成果
     * @return 建议(decision/issuesJson/suggestion/code/message)
     */
    public Suggestion suggest(PendingAchievementDO entity) {
        // 只有待审状态的成果才需要 AI 建议:已归档/已驳回的结论已定,
        // 再调一次 Worker 纯属浪费,且可能给出与最终审核结论冲突的建议
        if (!PendingSubmissionService.STATUS_PENDING.equals(entity.getStatus())) {
            return new Suggestion(DECISION_NEED_MANUAL, "[]",
                    "该成果已审结(" + entity.getStatus() + "),无需 AI 建议。" + ReviewService.AI_DISCLAIMER,
                    0, "非待审状态", false);
        }
        if (workerProperties.isGrpcMode()) {
            return grpcSuggestion(entity);
        }
        return fakeSuggestion(entity);
    }

    /**
     * grpc 模式:调 Worker 的 ExtractAndReview 流,读到 final 事件即映射为 Suggestion
     *
     * <p>双层判错:先判响应体 code(Python 侧未 abort,transport status 恒 OK),
     * 再捕获迭代期的 StatusRuntimeException(流中断/超时)。
     */
    private Suggestion grpcSuggestion(PendingAchievementDO entity) {
        String filePath;
        try {
            // Worker 与本服务同机,需绝对路径才能读到文件
            filePath = fileStorage.resolve(entity.getFilePath()).toString();
        } catch (Exception e) {
            return degraded("成果文件缺失或路径非法,无法调用 AI");
        }
        String traceId = "review-" + UUID.randomUUID().toString().substring(0, 8);
        try {
            Iterator<AiServiceProto.WorkflowEvent> events = workerClient.extractAndReview(filePath, traceId,
                    workerProperties.getReviewTimeoutSeconds());
            AiServiceProto.ReviewFinal finalEvent = null;
            while (events.hasNext()) {
                AiServiceProto.WorkflowEvent event = events.next();
                if (event.hasFinal()) {
                    finalEvent = event.getFinal();
                    // 拿到 final 立刻停:final 是流的终态事件,继续消费只会等到 deadline
                    // (最坏 320s),且 Worker 若在发完 final 后异常断开,会把已拿到的合法
                    // 结论误降级为人工审
                    break;
                }
            }
            if (finalEvent == null) {
                log.warn("[ai-review] trace={} 未收到 final 事件,转人工审", traceId);
                return degraded("AI 未返回最终结论,已转为人工审");
            }
            if (finalEvent.getCode() != 0) {
                log.warn("[ai-review] trace={} Worker 业务码={} msg={}", traceId,
                        finalEvent.getCode(), finalEvent.getMessage());
                return degraded("AI 返回错误码 " + finalEvent.getCode() + ":" + finalEvent.getMessage());
            }
            return new Suggestion(mapDecision(finalEvent.getDecision()), finalEvent.getIssuesJson(),
                    finalEvent.getSuggestion() + ReviewService.AI_DISCLAIMER,
                    0, "grpc 模式", false);
        } catch (StatusRuntimeException e) {
            log.warn("[ai-review] trace={} Worker 传输异常 status={}", traceId, e.getStatus().getCode());
            return degraded("AI Worker 不可用(" + e.getStatus().getCode() + "),已转为人工审");
        } catch (Exception e) {
            log.warn("[ai-review] trace={} 调用异常", traceId, e);
            return degraded("AI 调用异常(" + e.getClass().getSimpleName() + "),已转为人工审");
        }
    }

    /** Worker 决策值(pass/reject/need_manual)归一到内部三值;未知值一律转人工审 */
    private String mapDecision(String decision) {
        if (DECISION_PASS.equalsIgnoreCase(decision) || DECISION_REJECT.equalsIgnoreCase(decision)) {
            return decision.toLowerCase(java.util.Locale.ROOT);
        }
        return DECISION_NEED_MANUAL;
    }

    private Suggestion fakeSuggestion(PendingAchievementDO entity) {
        List<String> issues;
        try {
            issues = issuesOf(entity);
        } catch (IllegalStateException e) {
            // 落库的校验结果损坏:转人工审,绝不猜
            return degraded(e.getMessage());
        }
        if (issues.isEmpty()) {
            return new Suggestion(DECISION_PASS, "[]",
                    "字段完整性与白名单校验通过,建议通过。" + ReviewService.AI_DISCLAIMER,
                    0, "fake 模式(未接 Worker)", false);
        }
        return new Suggestion(DECISION_REJECT, issuesJson(issues),
                "存在字段问题:" + String.join("; ", issues) + "。" + ReviewService.AI_DISCLAIMER,
                0, "fake 模式(未接 Worker)", false);
    }

    private Suggestion degraded(String message) {
        return new Suggestion(DECISION_NEED_MANUAL, "[]",
                "AI 建议不可用,请人工审核。" + ReviewService.AI_DISCLAIMER,
                DEGRADED_CODE, message, true);
    }

    /** 从提交时落库的 validation_result 读问题清单(fake 模式的唯一事实源,不重算校验) */
    private List<String> issuesOf(PendingAchievementDO entity) {
        List<String> issues = new ArrayList<>();
        String raw = entity.getValidationResult();
        if (raw == null || raw.isBlank()) {
            return issues;
        }
        JsonNode validation = readJson(raw);
        if (validation == null) {
            // 解析失败**不能**当作"没有问题":那会让损坏数据伪装成"字段完整、建议通过",
            // 属于失败开放。显式抛错,由 suggest 入口转人工审。
            throw new IllegalStateException("validation_result 无法解析,拒绝给出 AI 建议");
        }
        if (validation.path(KEY_IS_VALID).asBoolean(false)) {
            return issues;
        }
        collect(validation.path(KEY_CONTENT_ISSUES), issues);
        collect(validation.path(KEY_COMPLETENESS_ISSUES), issues);
        return issues;
    }

    private void collect(JsonNode array, List<String> sink) {
        if (array != null && array.isArray()) {
            array.forEach(node -> sink.add(node.asText()));
        }
    }

    private JsonNode readJson(String json) {
        if (json == null || json.isBlank()) {
            return null;
        }
        try {
            return MAPPER.readTree(json);
        } catch (Exception e) {
            return null;
        }
    }

    private String issuesJson(List<String> issues) {
        try {
            return MAPPER.writeValueAsString(issues.stream()
                    .map(issue -> java.util.Map.of("issue", issue, "severity", "warning"))
                    .toList());
        } catch (Exception e) {
            return "[]";
        }
    }

    /**
     * 建议
     *
     * @param decision   决策(pass/reject/need_manual)
     * @param issuesJson 问题明细 JSON
     * @param suggestion 自然语言建议
     * @param code       0 正常;4003 Worker 降级
     * @param message    提示
     * @param degraded   是否为降级结果
     */
    public record Suggestion(String decision, String issuesJson, String suggestion, int code, String message,
            boolean degraded) {
    }

}
