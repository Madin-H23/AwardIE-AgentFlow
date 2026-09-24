package cn.iocoder.yudao.module.business.service.template;

import cn.iocoder.yudao.module.business.dal.dataobject.template.TemplatesDO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.grpc.StatusRuntimeException;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.validation.annotation.Validated;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception0;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.TEMPLATE_JSON_INVALID;

/**
 * 证书模板 AI 辅助(批7):试测 / 创建前抽取 / 生成 prompt
 *
 * <p>两种模式(单一开关 awardie.ai.worker.mode,取代批5 的 ai.review.mode):
 * fake 走确定性桩(开发与 CI 无需 Worker 进程),grpc 调真 Python Worker。
 *
 * <p><b>双层判错</b>(本域最容易踩的坑):Python Worker 把业务错误码写在响应体的 code 字段里
 * (server.py 两个方法都没调 context.abort),gRPC transport status 恒为 OK。所以:
 * 只捕获 StatusRuntimeException 会把所有 4000/4003/4004/5xxx 漏成"成功返回空数据";
 * 只看 resp.getCode() 又漏掉连接失败/超时。两条都要判。
 *
 * @author AwardIE
 */
@Service
@Validated
public class TemplateAiService {

    /** Worker 业务码:规则 JSON 非法 */
    public static final int WORKER_CODE_RULE_INVALID = 4000;
    /** Worker 业务码:AI 依赖不可用 */
    public static final int WORKER_CODE_AI_UNAVAILABLE = 4003;
    /** Worker 业务码:图片不可读或抽取失败 */
    public static final int WORKER_CODE_IMAGE_INVALID = 4004;
    /** AI 免责声明(BR-2:AI 输出仅辅助参考) */
    public static final String DISCLAIMER = "AI 建议仅辅助参考,以管理员白名单与人工审核为准(BR-2)";
    /** 桩模式标识 */
    public static final String MODE_FAKE = "fake";
    /** 真 Worker 模式标识 */
    public static final String MODE_GRPC = "grpc";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Resource
    private cn.iocoder.yudao.module.business.framework.grpc.AiWorkerClient workerClient;
    @Resource
    private cn.iocoder.yudao.module.business.framework.grpc.AiWorkerProperties workerProperties;
    @Resource
    private TemplateService templateService;
    @Resource
    private cn.iocoder.yudao.module.business.service.file.AwardieFileStorage fileStorage;

    /**
     * 模板试测:用已保存的样本图跑一次抽取
     *
     * @param template 模板
     * @param imageBytes 样本图字节
     * @param filename 样本图原始文件名
     * @return 抽取结果(mode/dataJson/ocrText)
     */
    public Map<String, Object> testTemplate(TemplatesDO template, byte[] imageBytes, String filename) {
        if (!workerProperties.isGrpcMode()) {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("mode", MODE_FAKE);
            out.put("dataJson", template.getSampleExtracted() == null ? "{}" : template.getSampleExtracted());
            out.put("ocrText", template.getSampleText() == null ? "" : template.getSampleText());
            out.put("disclaimer", DISCLAIMER);
            return out;
        }
        String traceId = "tpl-test-" + shortTrace();
        try {
            var resp = workerClient.extractTemplate(imageBytes, filename,
                    templateService.buildRuleJson(template), traceId,
                    workerProperties.getExtractTimeoutSeconds());
            // Worker 业务码原样透传(4000 规则非法 / 4003 AI 不可用 / 4004 图片问题 / 5xxx 内部)
            throwIfWorkerFailed(resp.getCode(), resp.getMessage());
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("mode", MODE_GRPC);
            out.put("dataJson", resp.getDataJson());
            out.put("ocrText", resp.getOcrText());
            out.put("disclaimer", DISCLAIMER);
            return out;
        } catch (StatusRuntimeException e) {
            // 传输层异常(连接失败/超时)统一映射 4003,与 v2 一致
            throw exception0(WORKER_CODE_AI_UNAVAILABLE,
                    "AI Worker 不可用({}),请稍后重试", e.getStatus().getCode());
        }
    }

    /**
     * 创建前抽取:还没建模板,只拿样本图试抽
     *
     * @param imageBytes 样本图字节
     * @param filename 样本图原始文件名
     * @param ruleJson 临时规则 JSON(可为空,按 "{}" 处理)
     * @return 抽取结果(mode/dataJson/ocrText)
     */
    public Map<String, Object> extractForCreate(byte[] imageBytes, String filename, String ruleJson) {
        // 三校验在模式分支之前:创建路径就是先校验再落盘,预抽取走同一道门,
        // 否则 fake 模式会接受任意文件、grpc 模式会把任意内容直送 Worker
        fileStorage.assertAllowed(filename, imageBytes);
        if (!workerProperties.isGrpcMode()) {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("mode", MODE_FAKE);
            out.put("dataJson", fakeExtractJson());
            out.put("ocrText", "示例OCR文本(fake 模式,未调用 Worker)");
            out.put("disclaimer", DISCLAIMER);
            return out;
        }
        String traceId = "tpl-extract-" + shortTrace();
        try {
            var resp = workerClient.extractTemplate(imageBytes, filename, normalizeRule(ruleJson), traceId,
                    workerProperties.getExtractTimeoutSeconds());
            throwIfWorkerFailed(resp.getCode(), resp.getMessage());
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("mode", MODE_GRPC);
            out.put("dataJson", resp.getDataJson());
            out.put("ocrText", resp.getOcrText());
            out.put("disclaimer", DISCLAIMER);
            return out;
        } catch (StatusRuntimeException e) {
            throw exception0(WORKER_CODE_AI_UNAVAILABLE,
                    "AI Worker 不可用({}),请稍后重试", e.getStatus().getCode());
        }
    }

    /**
     * 生成抽取 prompt
     *
     * @param ruleJson 模板规则 JSON
     * @param sampleText 样本文本
     * @return prompt 结果(mode/prompt/disclaimer)
     */
    public Map<String, Object> generatePrompt(String ruleJson, String sampleText) {
        String normalized = normalizeRule(ruleJson);
        if (!workerProperties.isGrpcMode()) {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("mode", MODE_FAKE);
            out.put("prompt", "请从以下奖状样本中抽取结构化字段:" + (sampleText == null ? "" : sampleText));
            out.put("disclaimer", DISCLAIMER);
            return out;
        }
        String traceId = "tpl-prompt-" + shortTrace();
        try {
            var resp = workerClient.generatePrompt(normalized, sampleText, traceId,
                    workerProperties.getPromptTimeoutSeconds());
            throwIfWorkerFailed(resp.getCode(), resp.getMessage());
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("mode", MODE_GRPC);
            out.put("prompt", resp.getPrompt());
            out.put("disclaimer", resp.getDisclaimer().isBlank() ? DISCLAIMER : resp.getDisclaimer());
            return out;
        } catch (StatusRuntimeException e) {
            throw exception0(WORKER_CODE_AI_UNAVAILABLE,
                    "AI Worker 不可用({}),请稍后重试", e.getStatus().getCode());
        }
    }

    /** Worker 业务码非 0 时原样透传(不二次包装成领域错误码,那会丢掉 Worker 的语义) */
    private void throwIfWorkerFailed(int code, String message) {
        if (code != 0) {
            throw exception0(code, "AI Worker 返回错误:{}", message);
        }
    }

    /** 规则 JSON 归一:空 → "{}";非法 → 明确业务错误(不让 Worker 返回 4000 才暴露) */
    private String normalizeRule(String ruleJson) {
        if (ruleJson == null || ruleJson.isBlank()) {
            return "{}";
        }
        try (com.fasterxml.jackson.core.JsonParser parser = MAPPER.getFactory().createParser(ruleJson)) {
            JsonNode node = MAPPER.readTree(parser);
            if (node == null || !node.isObject()) {
                throw exception(TEMPLATE_JSON_INVALID, "顶层必须是对象");
            }
            // readTree 只读第一个根节点,`{} garbage` 会被当成合法对象放过;
            // 显式确认后面没有第二个 token 才算完整合法
            if (parser.nextToken() != null) {
                throw exception(TEMPLATE_JSON_INVALID, "存在尾随内容");
            }
            return ruleJson;
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            throw exception(TEMPLATE_JSON_INVALID, e.getOriginalMessage());
        } catch (java.io.IOException e) {
            throw exception(TEMPLATE_JSON_INVALID, "规则 JSON 读取失败");
        }
    }

    private String fakeExtractJson() {
        return "{\"competition_name\":\"示例竞赛\",\"winner_name\":\"示例获奖人\","
                + "\"award_level\":\"一等奖\",\"issuer\":\"示例主办方\"}";
    }

    private String shortTrace() {
        return UUID.randomUUID().toString().substring(0, 8);
    }

}
