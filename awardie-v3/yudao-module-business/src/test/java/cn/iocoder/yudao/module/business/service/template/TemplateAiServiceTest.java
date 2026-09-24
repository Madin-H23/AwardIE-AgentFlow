package cn.iocoder.yudao.module.business.service.template;

import cn.iocoder.yudao.framework.common.exception.ServiceException;
import cn.iocoder.yudao.module.business.dal.dataobject.template.TemplatesDO;
import cn.iocoder.yudao.module.business.framework.grpc.AiWorkerClient;
import cn.iocoder.yudao.module.business.framework.grpc.AiWorkerProperties;
import cn.iocoder.yudao.module.business.service.file.AwardieFileStorage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.lang.reflect.Field;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 批7 模板域 AI 服务单测:fake 模式桩契约 + 规则 JSON 归一 + 非法 JSON 前置拦截。
 *
 * <p>纯 JUnit(不起 Spring)。grpc 模式不在此测——它需要真通道或 in-process server,
 * 归集成测试(且 CI 无 Worker,故集成测试只验"不可达 → 4003 降级不崩")。
 *
 * @author AwardIE
 */
class TemplateAiServiceTest {

    private static final byte[] PNG_BYTES = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};

    private TemplateAiService service;
    private AiWorkerProperties properties;

    @BeforeEach
    void setUp() throws Exception {
        service = new TemplateAiService();
        properties = new AiWorkerProperties();
        properties.setMode("fake");
        inject(service, "workerProperties", properties);
        inject(service, "workerClient", Mockito.mock(AiWorkerClient.class));
        // 真实例:三校验必须真跑,mock 掉就测不到"预抽取是否走了同一道门"
        AwardieFileStorage realStorage = new AwardieFileStorage("target/test-files/ai-service");
        java.lang.reflect.Field checkerField = AwardieFileStorage.class.getDeclaredField("referenceChecker");
        checkerField.setAccessible(true);
        checkerField.set(realStorage, Mockito.mock(
                cn.iocoder.yudao.module.business.service.reference.FileReferenceChecker.class));
        inject(service, "fileStorage", realStorage);
        inject(service, "templateService", Mockito.mock(TemplateService.class));
    }

    private void inject(Object target, String field, Object value) throws Exception {
        Field f = TemplateAiService.class.getDeclaredField(field);
        f.setAccessible(true);
        f.set(target, value);
    }

    @Test
    void fakeModeTestTemplateEchoesStoredExtract() {
        TemplatesDO template = new TemplatesDO();
        template.setSampleExtracted("{\"winner_name\":\"张三\"}");
        template.setSampleText("样本文本内容");
        Map<String, Object> out = service.testTemplate(template, PNG_BYTES, "s.png");
        assertThat(out).containsEntry("mode", "fake");
        assertThat(out.get("dataJson").toString()).contains("张三");
        assertThat(out.get("ocrText")).isEqualTo("样本文本内容");
        assertThat(out.get("disclaimer").toString()).contains("辅助参考");
    }

    @Test
    void fakeModeExtractForCreateReturnsStableStub() {
        Map<String, Object> first = service.extractForCreate(PNG_BYTES, "s.png", null);
        Map<String, Object> second = service.extractForCreate(PNG_BYTES, "s.png", null);
        assertThat(first).containsEntry("mode", "fake");
        // 桩必须稳定:同样输入两次给同样结果(否则测试与演示都不可靠)
        assertThat(first.get("dataJson")).isEqualTo(second.get("dataJson"));
        assertThat(first.get("ocrText").toString()).contains("fake 模式");
    }

    @Test
    void fakeModeGeneratePromptIncludesSampleText() {
        Map<String, Object> out = service.generatePrompt(null, "样例文本");
        assertThat(out).containsEntry("mode", "fake");
        assertThat(out.get("prompt").toString()).contains("样例文本");
    }

    @Test
    void generatePromptRejectsMalformedRuleJson() {
        // 非法 JSON 在进 Worker 前就拦(Worker 侧会返 4000,但我们不浪费一次调用)
        assertThatThrownBy(() -> service.generatePrompt("{not json", "x"))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("JSON");
    }

    @Test
    void generatePromptRejectsNonObjectRuleJson() {
        // 顶层必须是对象:Worker 侧对数组/标量会在 .get() 时炸成 5xxx
        assertThatThrownBy(() -> service.generatePrompt("[1,2,3]", "x"))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("对象");
    }

    @Test
    void generatePromptAcceptsEmptyAndValidRule() {
        assertThat(service.generatePrompt(null, "x")).containsEntry("mode", "fake");
        assertThat(service.generatePrompt("  ", "x")).containsEntry("mode", "fake");
        assertThat(service.generatePrompt("{\"keywords\":[\"奖状\"]}", "x")).containsEntry("mode", "fake");
    }

    // ========== 批7 审查新增:三校验前置 + Worker 码透传 ==========

    @Test
    void extractForCreateRejectsNonWhitelistedFileBeforeCallingWorker() throws Exception {
        // 预抽取走创建路径的同一道门:fake 模式也不该接受任意文件
        assertThatThrownBy(() -> service.extractForCreate("not an image".getBytes(), "x.png", null))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("魔术字节");
    }

    @Test
    void extractForCreateRejectsOversizeFile() throws Exception {
        byte[] tooBig = new byte[(int) AwardieFileStorage.MAX_SIZE + 1];
        tooBig[0] = (byte) 0x89;
        assertThatThrownBy(() -> service.extractForCreate(tooBig, "x.png", null))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("10MB");
    }

    @Test
    void workerBusinessCodeIsPassedThroughVerbatim() throws Exception {
        // 4004(图片不可读)必须原样透传,不能被二次包装成领域错误码丢掉语义
        properties.setMode("grpc");
        AiWorkerClient client = Mockito.mock(AiWorkerClient.class);
        inject(service, "workerClient", client);
        Mockito.when(client.extractTemplate(Mockito.any(), Mockito.any(), Mockito.any(), Mockito.any(),
                        Mockito.anyInt()))
                .thenReturn(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto
                        .ExtractTemplateResponse.newBuilder().setCode(4004).setMessage("图片不可读").build());
        assertThatThrownBy(() -> service.extractForCreate(PNG_BYTES, "s.png", null))
                .isInstanceOf(ServiceException.class)
                .satisfies(e -> assertThat(((ServiceException) e).getCode()).isEqualTo(4004));
    }

    @Test
    void workerTransportErrorMapsTo4003() throws Exception {
        properties.setMode("grpc");
        AiWorkerClient client = Mockito.mock(AiWorkerClient.class);
        inject(service, "workerClient", client);
        Mockito.when(client.generatePrompt(Mockito.any(), Mockito.any(), Mockito.any(), Mockito.anyInt()))
                .thenThrow(new io.grpc.StatusRuntimeException(io.grpc.Status.UNAVAILABLE));
        assertThatThrownBy(() -> service.generatePrompt("{}", "x"))
                .isInstanceOf(ServiceException.class)
                .satisfies(e -> assertThat(((ServiceException) e).getCode()).isEqualTo(4003));
    }

}
