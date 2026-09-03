package com.awardie.aireview;

import java.util.Iterator;
import java.util.concurrent.TimeUnit;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.StatusRuntimeException;
import awardie.ai.AiServiceGrpc;
import awardie.ai.AiServiceOuterClass;

/**
 * AI Worker gRPC 客户端(契约:ai_worker/protos/ai_service.proto)。
 *
 * 探针 P1 硬条目落地:keepAlive 开启;读超时由 Nginx 承担(>=300s),直连场景由 deadline 控制。
 * Stream removed/RST → 抛 StatusRuntimeException,由 AiProxyService 降级为 4003 人工审。
 */
@Component
public class AiWorkerClient implements AutoCloseable {

    private final ManagedChannel channel;
    private final AiServiceGrpc.AiServiceBlockingStub stub;

    public AiWorkerClient(@Value("${ai.worker.host:127.0.0.1}") String host,
            @Value("${ai.worker.port:50060}") int port) {
        this.channel = ManagedChannelBuilder.forAddress(host, port)
                .usePlaintext() // P0 本机/内网;mTLS 为 P3 项
                .keepAliveTime(30, TimeUnit.SECONDS)
                .keepAliveTimeout(10, TimeUnit.SECONDS)
                .build();
        this.stub = AiServiceGrpc.newBlockingStub(channel);
    }

    /** 抽取+审核全链流式;调用方负责把事件映射为 SSE。 */
    public Iterator<AiServiceOuterClass.WorkflowEvent> extractAndReview(String filePath, String traceId,
            long deadlineSeconds) {
        return stub.withDeadlineAfter(deadlineSeconds, TimeUnit.SECONDS)
                .extractAndReview(AiServiceOuterClass.ExtractRequest.newBuilder()
                        .setFilePath(filePath)
                        .setUseOcrCache(true)
                        .setUseLlmCache(true)
                        .setTraceId(traceId)
                        .build());
    }

    public boolean isDead(Iterator<AiServiceOuterClass.WorkflowEvent> it) {
        try {
            it.hasNext();
            return false;
        } catch (StatusRuntimeException e) {
            return true;
        }
    }

    /** AI 问答流(#33,契约 Ask);调用方负责把 AnswerEvent 映射为 SSE。 */
    public Iterator<AiServiceOuterClass.AnswerEvent> ask(String question, String traceId, long deadlineSeconds) {
        return stub.withDeadlineAfter(deadlineSeconds, TimeUnit.SECONDS)
                .ask(AiServiceOuterClass.AskRequest.newBuilder()
                        .setQuestion(question)
                        .setTraceId(traceId)
                        .build());
    }

    /** 模板样本图抽取(架构票,契约 ExtractTemplate);调用方负责 code!=0 的降级语义。 */
    public AiServiceOuterClass.ExtractTemplateResponse extractTemplate(byte[] image, String filename,
            String templateRuleJson, boolean useOcrCache, boolean useLlmCache, String traceId, long deadlineSeconds) {
        return stub.withDeadlineAfter(deadlineSeconds, TimeUnit.SECONDS)
                .extractTemplate(AiServiceOuterClass.ExtractTemplateRequest.newBuilder()
                        .setImage(com.google.protobuf.ByteString.copyFrom(image))
                        .setFilename(filename == null ? "" : filename)
                        .setTemplateRuleJson(templateRuleJson == null ? "" : templateRuleJson)
                        .setUseOcrCache(useOcrCache)
                        .setUseLlmCache(useLlmCache)
                        .setTraceId(traceId)
                        .build());
    }

    /** 模板 prompt 生成(架构票,契约 GeneratePrompt);调用方负责 code!=0 的降级语义。 */
    public AiServiceOuterClass.GeneratePromptResponse generatePrompt(String templateRuleJson, String sampleText,
            String traceId, long deadlineSeconds) {
        return stub.withDeadlineAfter(deadlineSeconds, TimeUnit.SECONDS)
                .generatePrompt(AiServiceOuterClass.GeneratePromptRequest.newBuilder()
                        .setTemplateRuleJson(templateRuleJson == null ? "" : templateRuleJson)
                        .setSampleText(sampleText == null ? "" : sampleText)
                        .setTraceId(traceId)
                        .build());
    }

    @Override
    public void close() {
        channel.shutdown();
    }
}
