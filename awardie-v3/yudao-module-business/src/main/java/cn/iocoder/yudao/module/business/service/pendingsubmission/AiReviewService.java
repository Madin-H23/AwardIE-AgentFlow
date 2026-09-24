package cn.iocoder.yudao.module.business.service.pendingsubmission;

import cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission.PendingAchievementDO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.validation.annotation.Validated;

import java.util.ArrayList;
import java.util.List;

/**
 * AI 审核建议(批5):fake/grpc 双模式,不阻塞人工审核
 *
 * <p>fake 模式:依据提交时落库的 validation_result 给出确定性建议(开发/CI 无 Worker 进程时);
 * grpc 模式:调 Python Worker 的 ExtractAndReview——Worker stub 属批7(模板+AI 抽取)一并引入,
 * 故本批 grpc 模式**一律降级为人工审**(decision=need_manual + 4003),不向用户抛错
 * (BR-2:AI 建议仅辅助参考;v2 同款口径)。
 *
 * @author AwardIE
 */
@Service
@Validated
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
    /** grpc 模式标识(ai.review.mode) */
    private static final String MODE_GRPC = "grpc";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Value("${ai.review.mode:fake}")
    private String mode;

    /**
     * AI 建议
     *
     * @param entity 待审成果
     * @return 建议(decision/issuesJson/suggestion/code/message)
     */
    public Suggestion suggest(PendingAchievementDO entity) {
        if (MODE_GRPC.equalsIgnoreCase(mode)) {
            // Worker gRPC stub 属批7;在此之前 grpc 模式按"不可达"处理,降级不抛错
            return degraded("AI 服务尚未接入(批7 引入 Worker gRPC),已转为人工审");
        }
        return fakeSuggestion(entity);
    }

    private Suggestion fakeSuggestion(PendingAchievementDO entity) {
        List<String> issues = issuesOf(entity);
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
        JsonNode validation = readJson(entity.getValidationResult());
        if (validation == null) {
            return issues;
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
