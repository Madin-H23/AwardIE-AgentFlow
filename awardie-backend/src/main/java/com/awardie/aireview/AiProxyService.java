package com.awardie.aireview;

import java.util.Iterator;
import java.util.List;

import io.grpc.StatusRuntimeException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.awardie.submission.PendingAchievementEntity;

import awardie.ai.AiServiceOuterClass;

/**
 * AI 建议代理:fake/grpc 双模式(ai.worker.mode)。
 *
 * grpc 模式:透传 Worker 流事件;Stream removed/不可用 → 降级事件(4003,人工审),不抛给用户。
 * fake 模式:确定性事件序列(开发/CI 无 Worker 进程时使用)。
 */
@Service
public class AiProxyService {

    public record AiEvent(String kind, String node, String text, Integer code, String message) {
        public static AiEvent node(String node) {
            return new AiEvent("node", node, null, null, null);
        }

        public static AiEvent delta(String text) {
            return new AiEvent("delta", null, text, null, null);
        }

        public static AiEvent finalOk(String decision, String issuesJson, String suggestion) {
            return new AiEvent("final", null, null, 0, decision + "|" + issuesJson + "|" + suggestion);
        }

        public static AiEvent degraded(String message) {
            return new AiEvent("final", null, null, 4003, message);
        }
    }

    private final AiWorkerClient client;
    private final String mode;

    public AiProxyService(AiWorkerClient client, @Value("${ai.worker.mode:fake}") String mode) {
        this.client = client;
        this.mode = mode;
    }

    public boolean isFake() {
        return "fake".equalsIgnoreCase(mode);
    }

    /** 建议 = Worker 对该 pending 文件做 extract_and_review;事件序列(有限)。 */
    public Iterator<AiEvent> suggest(PendingAchievementEntity pending) {
        if (isFake()) {
            return List.of(
                    AiEvent.node("extraction"),
                    AiEvent.delta("抽取完成,校验 5 个字段……"),
                    AiEvent.node("review"),
                    AiEvent.delta("字段完整性与白名单校验通过。"),
                    AiEvent.finalOk("pass", "[]", "AI 建议仅辅助参考:字段完整,建议通过。")).iterator();
        }
        try {
            Iterator<AiServiceOuterClass.WorkflowEvent> it = client.extractAndReview(
                    pending.getFilePath(), "t-" + pending.getId(), 320); // >300s:Nginx 硬条目对齐
            return new Iterator<>() {
                @Override
                public boolean hasNext() {
                    try {
                        return it.hasNext();
                    } catch (StatusRuntimeException e) {
                        return true; // 注入降级事件
                    }
                }

                @Override
                public AiEvent next() {
                    try {
                        AiServiceOuterClass.WorkflowEvent evt = it.next();
                        return switch (evt.getEventCase()) {
                            case NODE -> AiEvent.node(evt.getNode().getNode());
                            case DELTA -> AiEvent.delta(evt.getDelta().getText());
                            case FINAL -> AiEvent.finalOk(evt.getFinal().getDecision(),
                                    evt.getFinal().getIssuesJson(), evt.getFinal().getSuggestion());
                            default -> AiEvent.node("unknown");
                        };
                    } catch (StatusRuntimeException e) { // Stream removed / UNAVAILABLE → 降级
                        return AiEvent.degraded("AI Worker 不可用(" + e.getStatus().getCode() + "),请人工审核");
                    }
                }
            };
        } catch (Exception e) { // Worker 进程未起等连接级失败
            return List.of(AiEvent.degraded("AI Worker 连接失败,请人工审核")).iterator();
        }
    }
}
