package cn.iocoder.yudao.module.business.framework.grpc;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * AI Worker 连接参数(批7)
 *
 * <p>默认值与 v2 一致(127.0.0.1:50060;Python Worker server.py 硬编码该监听地址,
 * 无 host/port 环境变量开关——本类只是让 Java 侧可配,Worker 侧仍需改代码才能换地址)。
 *
 * <p>三个 deadline 分别对齐 v2 实测值:抽取要跑 OCR+LLM 故 120s,prompt 是本地拼串 60s,
 * 审核流是 LangGraph 全链 320s。上界 600s 是防手滑配成 0/负数——gRPC 语义是"立即过期",
 * 会让所有 Worker 调用恒失败且错误信息难懂。
 *
 * @author AwardIE
 */
@Data
@Validated
@ConfigurationProperties(prefix = "awardie.ai.worker")
public class AiWorkerProperties {

    /** 模式:fake(确定性桩,默认)/ grpc(调真 Worker) */
    private String mode = "fake";
    /** Worker 主机 */
    private String host = "127.0.0.1";
    /** Worker 端口 */
    private int port = 50060;
    /** 模板抽取(ExtractTemplate)超时秒数 */
    @Min(1)
    @Max(600)
    private int extractTimeoutSeconds = 120;
    /** prompt 生成(GeneratePrompt)超时秒数 */
    @Min(1)
    @Max(600)
    private int promptTimeoutSeconds = 60;
    /** 审核流(ExtractAndReview)超时秒数 */
    @Min(1)
    @Max(600)
    private int reviewTimeoutSeconds = 320;

    /**
     * 是否为 grpc 模式(大小写不敏感,沿 v2 口径)
     *
     * <p>非 grpc 的值一律当 fake:默认与未知值都走确定性桩,不会因为一个拼错的配置
     * 就让每次 AI 调用变成 120s 超时(实测 grpc 不可达时调用要等 deadline 结束)。
     */
    public boolean isGrpcMode() {
        return "grpc".equalsIgnoreCase(mode);
    }

}
