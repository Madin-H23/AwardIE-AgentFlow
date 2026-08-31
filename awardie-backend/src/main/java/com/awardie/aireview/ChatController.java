package com.awardie.aireview;

import java.util.Iterator;

import org.springframework.http.MediaType;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/** AI 智能体协作(#33,对照 v1 智能助手):问答 SSE(fake/grpc 双模式,BR-2 免责声明);登录用户皆可用。 */
@RestController
@RequestMapping("/api/v2/chat")
public class ChatController {

    private final ChatService chat;

    public ChatController(ChatService chat) {
        this.chat = chat;
    }

    /** 问答 SSE:事件流(node/delta/final),前端打字机渲染;final 带 sources 与 BR-2 免责声明。 */
    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(@RequestParam("q") String question, Authentication auth) {
        SseEmitter emitter = new SseEmitter(320_000L); // 与探针 P1 硬条目对齐
        if (auth == null || question == null || question.isBlank()) {
            throw new IllegalArgumentException("问题不能为空");
        }
        Thread worker = new Thread(() -> {
            try {
                for (ChatService.ChatEvent evt : (Iterable<ChatService.ChatEvent>) () -> chat.ask(question)) {
                    emitter.send(SseEmitter.event().name(evt.kind()).data(toJson(evt)));
                    if ("final".equals(evt.kind())) {
                        break;
                    }
                }
                emitter.complete();
            } catch (Exception e) {
                emitter.completeWithError(e);
            }
        }, "chat-stream");
        worker.setDaemon(true);
        worker.start();
        return emitter;
    }

    private String toJson(ChatService.ChatEvent evt) {
        StringBuilder sb = new StringBuilder("{\"kind\":\"").append(evt.kind()).append('"');
        if (evt.node() != null) {
            sb.append(",\"node\":\"").append(evt.node()).append('"');
        }
        if (evt.text() != null) {
            sb.append(",\"text\":\"").append(evt.text().replace("\"", "'").replace("\n", " ")).append('"');
        }
        if (evt.code() != null) {
            sb.append(",\"code\":").append(evt.code());
        }
        if (evt.message() != null) {
            sb.append(",\"message\":\"").append(evt.message().replace("\"", "'").replace("\n", " ")).append('"');
        }
        if (evt.sources() != null) {
            sb.append(",\"sources\":\"").append(evt.sources().replace("\"", "'")).append('"');
        }
        sb.append(",\"disclaimer\":\"AI 回答仅辅助参考(BR-2)\"}");
        return sb.toString();
    }
}
