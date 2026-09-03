package com.awardie;

import awardie.ai.AiServiceOuterClass;
import com.awardie.admin.AdminTemplateDetailController;
import com.awardie.aireview.AiWorkerClient;
import com.awardie.submission.FileStorageService;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.authentication.TestingAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * 架构票交付物 5(页面批次):模板试测端点 grpc 分支的键名契约单测(mode/fields/ocrText)。
 * 纯 Mockito 直构控制器,不起 Spring 容器;fake 分支由 AdminTemplateDetailTest 集成覆盖。
 */
class AdminTemplateDetailControllerTest {

    private static final TestingAuthenticationToken ADMIN =
            new TestingAuthenticationToken("admin", "n/a", "ROLE_ADMIN");

    @Test
    void grpcModeExtractsSampleImageAndKeepsKeyContract() throws Exception {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        AiWorkerClient client = mock(AiWorkerClient.class);
        FileStorageService storage = mock(FileStorageService.class);
        AdminTemplateDetailController c = new AdminTemplateDetailController(jdbc, "grpc", client, storage);
        Map<String, Object> row = Map.of(
                "se", "{\"竞赛名称\":\"X\"}",
                "sample_image_path", "files/v2/abc123.png");
        when(jdbc.queryForList(anyString(), eq(5))).thenReturn(List.of(row));
        when(storage.readAll("files/v2/abc123.png")).thenReturn(new byte[]{1, 2, 3});
        AiServiceOuterClass.ExtractTemplateResponse resp =
                AiServiceOuterClass.ExtractTemplateResponse.newBuilder()
                        .setCode(0).setMessage("ok")
                        .setDataJson("{\"获奖等级\":\"一等奖\"}")
                        .setOcrText("OCR文本").build();
        when(client.extractTemplate(any(), anyString(), anyString(), anyBoolean(), anyBoolean(),
                anyString(), anyLong())).thenReturn(resp);

        var out = c.test(5, ADMIN);

        assertEquals(0, out.code());
        assertEquals("grpc", out.data().get("mode"));
        assertEquals("{\"获奖等级\":\"一等奖\"}", out.data().get("fields"));
        assertEquals("OCR文本", out.data().get("ocrText"));
    }

    @Test
    void grpcModeWithoutSampleImageReturns4000() throws Exception {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        AiWorkerClient client = mock(AiWorkerClient.class);
        FileStorageService storage = mock(FileStorageService.class);
        AdminTemplateDetailController c = new AdminTemplateDetailController(jdbc, "grpc", client, storage);
        Map<String, Object> row = new java.util.HashMap<>();
        row.put("se", "{}");
        row.put("sample_image_path", null);
        when(jdbc.queryForList(anyString(), eq(5))).thenReturn(List.of(row));

        var out = c.test(5, ADMIN);

        assertEquals(4000, out.code());
        assertTrue(out.message().contains("样本图片"));
    }

    @Test
    void testMissingTemplateReturns4004() throws Exception {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        AiWorkerClient client = mock(AiWorkerClient.class);
        FileStorageService storage = mock(FileStorageService.class);
        AdminTemplateDetailController c = new AdminTemplateDetailController(jdbc, "grpc", client, storage);
        when(jdbc.queryForList(anyString(), eq(5))).thenReturn(List.of());

        var out = c.test(5, ADMIN);

        assertEquals(4004, out.code());
    }
}
