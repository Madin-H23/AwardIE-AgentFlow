package cn.iocoder.yudao.module.business.framework.grpc;

import cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceGrpc;
import cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto;
import com.google.protobuf.ByteString;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.Iterator;
import java.util.concurrent.TimeUnit;

/**
 * AI Worker gRPC 客户端(批7;契约见 src/main/proto/ai_service.proto)
 *
 * <p>关键设计(三条,每条都对应一类真实故障):
 * <ol>
 *   <li><b>懒连接</b>:构造 channel 不发起连接(grpc-java 行为),Worker 未启动时应用照样起来,
 *       失败推迟到第一次业务调用,由调用方按双层判错契约处理;</li>
 *   <li><b>双层判错在调用方</b>:Worker 把业务码写在响应体 code 字段里(Python 侧没调
 *       context.abort),gRPC transport status 恒 OK;故本类只做传输不做码判定,
 *       调用方必须先判 resp.getCode(),再捕获 StatusRuntimeException 映射 4003。</li>
 *   <li><b>netty-shaded</b>:芋道自带 Netty 4.2,非 shaded 版 grpc-netty 会与之抢版本。</li>
 * </ol>
 *
 * <p>keepAlive 开启;读超时由 deadline 控制(直连场景不走 Nginx,故不依赖
 * grpc_read_timeout)。本类由 Spring 管理生命周期,容器关闭时 close。
 *
 * @author AwardIE
 */
@Component
@EnableConfigurationProperties(AiWorkerProperties.class)
public class AiWorkerClient implements AutoCloseable {

    private final ManagedChannel channel;
    private final AiServiceGrpc.AiServiceBlockingStub stub;

    public AiWorkerClient(AiWorkerProperties properties) {
        // 明文传输:本机/内网部署,mTLS 属后续部署加固项
        this.channel = ManagedChannelBuilder.forAddress(properties.getHost(), properties.getPort())
                .usePlaintext()
                .keepAliveTime(30, TimeUnit.SECONDS)
                .keepAliveTimeout(10, TimeUnit.SECONDS)
                .build();
        this.stub = AiServiceGrpc.newBlockingStub(channel);
    }

    /**
     * 模板样本图抽取(契约 ExtractTemplate)
     *
     * @param image             样本图原始字节
     * @param filename          原始文件名(Worker 据此推断临时文件后缀以选 OCR 引擎)
     * @param templateRuleJson  模板规则 JSON。**当前 Worker 不消费该字段**(固定走默认 award
     *                          prompt),v2 因此恒传 "{}";这里仍把真实规则传过去,是为了
     *                          Worker 将来支持规则化抽取时 Java 侧无需再改。传值与传 "{}"
     *                          对当前 Worker 行为完全一致。
     * @param traceId           链路追踪号
     * @param deadlineSeconds   超时秒数
     * @return Worker 响应(调用方负责判 getCode())
     */
    public AiServiceProto.ExtractTemplateResponse extractTemplate(byte[] image, String filename,
            String templateRuleJson, String traceId, int deadlineSeconds) {
        return stub.withDeadlineAfter(deadlineSeconds, TimeUnit.SECONDS)
                .extractTemplate(AiServiceProto.ExtractTemplateRequest.newBuilder()
                        .setImage(ByteString.copyFrom(image))
                        .setFilename(filename == null ? "" : filename)
                        .setTemplateRuleJson(templateRuleJson == null ? "{}" : templateRuleJson)
                        .setUseOcrCache(true)
                        .setUseLlmCache(true)
                        .setTraceId(traceId)
                        .build());
    }

    /**
     * 抽取 prompt 生成(契约 GeneratePrompt;Worker 侧纯本地拼串,不耗 OCR/LLM)
     *
     * @param templateRuleJson 模板规则 JSON
     * @param sampleText       样本文本
     * @param traceId          链路追踪号
     * @param deadlineSeconds  超时秒数
     * @return Worker 响应(调用方负责判 getCode())
     */
    public AiServiceProto.GeneratePromptResponse generatePrompt(String templateRuleJson, String sampleText,
            String traceId, int deadlineSeconds) {
        return stub.withDeadlineAfter(deadlineSeconds, TimeUnit.SECONDS)
                .generatePrompt(AiServiceProto.GeneratePromptRequest.newBuilder()
                        .setTemplateRuleJson(templateRuleJson == null ? "{}" : templateRuleJson)
                        .setSampleText(sampleText == null ? "" : sampleText)
                        .setTraceId(traceId)
                        .build());
    }

    /**
     * 抽取+审核全链流式(契约 ExtractAndReview);调用方消费到 final 事件并自行处理
     * StatusRuntimeException(流中断/超时都在迭代时才抛)
     *
     * @param filePath        成果文件绝对路径(Worker 与本服务同机可读)
     * @param traceId         链路追踪号
     * @param deadlineSeconds 超时秒数
     * @return 事件迭代器
     */
    public Iterator<AiServiceProto.WorkflowEvent> extractAndReview(String filePath, String traceId,
            int deadlineSeconds) {
        return stub.withDeadlineAfter(deadlineSeconds, TimeUnit.SECONDS)
                .extractAndReview(AiServiceProto.ExtractRequest.newBuilder()
                        .setFilePath(filePath)
                        .setUseOcrCache(true)
                        .setUseLlmCache(true)
                        .setTraceId(traceId)
                        .build());
    }

    @Override
    public void close() {
        channel.shutdown();
    }

}
