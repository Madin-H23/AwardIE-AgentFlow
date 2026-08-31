package com.awardie.aireview;

import java.util.Iterator;
import java.util.List;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import awardie.ai.AiServiceOuterClass;
import io.grpc.StatusRuntimeException;

/**
 * AI 问答代理(#33,对照 v1 智能助手):fake/grpc 双模式沿用 #9;
 * Stream removed/不可用 → 降级事件(4003),不抛给用户。
 */
@Service
public class ChatService {

    /** 复用 AiEvent 五字段口径(kind/node/text/code/message),与 teacher-review SSE 前端同构。 */
    public record ChatEvent(String kind, String node, String text, Integer code, String message, String sources) {
        public static ChatEvent node(String node) {
            return new ChatEvent("node", node, null, null, null, null);
        }

        public static ChatEvent delta(String text) {
            return new ChatEvent("delta", null, text, null, null, null);
        }

        public static ChatEvent finalOk(String answer, String sources) {
            return new ChatEvent("final", null, null, 0, answer, sources);
        }

        public static ChatEvent degraded(String message) {
            return new ChatEvent("final", null, null, 4003, message, null);
        }
    }

    private final AiWorkerClient client;
    private final String mode;

    public ChatService(AiWorkerClient client, @Value("${ai.worker.mode:fake}") String mode) {
        this.client = client;
        this.mode = mode;
    }

    public boolean isFake() {
        return "fake".equalsIgnoreCase(mode);
    }

    public Iterator<ChatEvent> ask(String question) {
        String traceId = "chat-" + UUID.randomUUID().toString().substring(0, 8);
        if (isFake()) {
            return List.of(
                    ChatEvent.node("rag"),
                    ChatEvent.delta("已检索知识库……"),
                    ChatEvent.finalOk(
                            "【fake 模式】这是关于「" + question + "」的确定性回答:知识问答链路(RAG 检索→生成)已通,接真实 Worker 后返回检索增强答案。",
                            "[]")).iterator();
        }
        try {
            Iterator<AiServiceOuterClass.AnswerEvent> it = client.ask(question, traceId, 320);
            return new Iterator<>() {
                @Override
                public boolean hasNext() {
                    try {
                        return it.hasNext();
                    } catch (StatusRuntimeException e) {
                        return true;
                    }
                }

                @Override
                public ChatEvent next() {
                    try {
                        AiServiceOuterClass.AnswerEvent evt = it.next();
                        return switch (evt.getEventCase()) {
                            case NODE -> ChatEvent.node(evt.getNode().getNode());
                            case DELTA -> ChatEvent.delta(evt.getDelta().getText());
                            case FINAL -> ChatEvent.finalOk(evt.getFinal().getAnswer(), evt.getFinal().getSourcesJson());
                            default -> ChatEvent.node("unknown");
                        };
                    } catch (StatusRuntimeException e) {
                        return ChatEvent.degraded("AI Worker 不可用(" + e.getStatus().getCode() + "),请稍后重试");
                    }
                }
            };
        } catch (Exception e) {
            return List.of(ChatEvent.degraded("AI Worker 连接失败,请稍后重试")).iterator();
        }
    }
}
