package com.awardie.common;

import java.time.Instant;

/**
 * 统一响应包装(借鉴 it-ops-service CommonResult,5 字段)。
 * 成功 code=0;业务错误码沿 v1 体系(如 4003=AI 不可用)。
 */
public record ApiResponse<T>(int code, String message, T data, String traceId, String timestamp) {

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data, TraceIdFilter.currentTraceId(), Instant.now().toString());
    }

    public static <T> ApiResponse<T> ok(T data, String message) {
        return new ApiResponse<>(0, message, data, TraceIdFilter.currentTraceId(), Instant.now().toString());
    }

    public static <T> ApiResponse<T> error(int code, String message) {
        return new ApiResponse<>(code, message, null, TraceIdFilter.currentTraceId(), Instant.now().toString());
    }
}
