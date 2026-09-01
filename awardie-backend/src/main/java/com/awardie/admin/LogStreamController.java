package com.awardie.admin;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/** 日志实时流(#42):SSE 增量推送 system_event_log(id>afterId,2s 轮询);应用日志属 v1 Python 资产不迁移。 */
@RestController
@RequestMapping("/api/v2/admin/logs")
public class LogStreamController {

    private final JdbcTemplate jdbc;

    public LogStreamController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(@RequestParam(defaultValue = "0") long afterId,
            @RequestParam(defaultValue = "0") long timeoutMillis,
            Authentication auth) {
        requireAdmin(auth);
        SseEmitter emitter = new SseEmitter(timeoutMillis); // 0=永不超时(浏览器 EventSource);测试传短超时
        AtomicBoolean running = new AtomicBoolean(true);
        Thread worker = new Thread(() -> {
            long lastId = afterId;
            try {
                // 先发一条锚点事件(当前最大 id),前端据此初始化
                Long max = jdbc.queryForObject(
                        "SELECT COALESCE(MAX(id), 0) FROM system_event_log", Long.class);
                lastId = max == null ? 0 : max;
                emitter.send(SseEmitter.event().name("anchor")
                        .data("{\"lastId\":" + lastId + "}"));
                while (running.get()) {
                    Thread.sleep(2000);
                    if (!running.get()) {
                        break;
                    }
                    List<Map<String, Object>> rows = jdbc.queryForList("""
                            SELECT id, event_category, event_level, event_message, trace_id,
                                   operator_code, source_module, created_at
                            FROM system_event_log WHERE id > ? ORDER BY id LIMIT 50
                            """, lastId);
                    for (Map<String, Object> r : rows) {
                        lastId = ((Number) r.get("id")).longValue();
                        emitter.send(SseEmitter.event().name("log").data(toJson(r)));
                    }
                }
                emitter.complete();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (Exception e) {
                emitter.completeWithError(e);
            }
        }, "log-stream");
        worker.setDaemon(true);
        worker.start();
        emitter.onCompletion(() -> running.set(false));
        emitter.onTimeout(() -> running.set(false));
        emitter.onError(e -> running.set(false));
        return emitter;
    }

    private String toJson(Map<String, Object> r) {
        return "{\"id\":" + r.get("id")
                + ",\"level\":\"" + esc(r.get("event_level")) + '"'
                + ",\"category\":\"" + esc(r.get("event_category")) + '"'
                + ",\"message\":\"" + esc(r.get("event_message")) + '"'
                + ",\"trace\":\"" + esc(r.get("trace_id")) + '"'
                + ",\"module\":\"" + esc(r.get("source_module")) + '"'
                + ",\"time\":\"" + (r.get("created_at") == null ? "" : String.valueOf(r.get("created_at")).replace("T", " ").substring(0, 19)) + "\"}";
    }

    private static String esc(Object v) {
        return v == null ? "" : String.valueOf(v)
                .replace("\\", "\\\\").replace("\"", "'").replace("\n", " ");
    }

    private void requireAdmin(Authentication auth) {
        for (GrantedAuthority a : auth.getAuthorities()) {
            if (a.getAuthority().equals("ROLE_ADMIN")) {
                return;
            }
        }
        throw new org.springframework.security.access.AccessDeniedException("需要 admin 角色");
    }
}
