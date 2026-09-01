package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

/** #40/#41/#42 批 5:图片批量导入/xlsx 报告/日志实时流。断言结构层(CI 空库兼容)。 */
class AdminBatchStreamTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private String adminCk() {
        return loginAs("admin", "Mayy123");
    }

    private byte[] png(String marker) {
        byte[] head = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A};
        // 尾部掺 nanoTime:sha 每次不同,避免跨运行的 sha 去重干扰
        byte[] tail = (marker + "-" + System.nanoTime()).getBytes(StandardCharsets.UTF_8);
        byte[] all = new byte[head.length + tail.length];
        System.arraycopy(head, 0, all, 0, head.length);
        System.arraycopy(tail, 0, all, head.length, tail.length);
        return all;
    }

    private ResponseEntity<String> batch(List<byte[]> files, String ck) {
        return batch(files, ck, String.valueOf(System.nanoTime()));
    }

    private ResponseEntity<String> batch(List<byte[]> files, String ck, String marker) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        int idx = 0;
        for (byte[] f : files) {
            final byte[] data = f;
            final String fname = "batch-" + marker + "-" + (idx++) + ".png";
            form.add("files", new ByteArrayResource(data) {
                @Override
                public String getFilename() {
                    return fname;
                }
            });
        }
        return rest.exchange("/api/v2/admin/import/awards/batch",
                HttpMethod.POST, new HttpEntity<>(form, headers), String.class);
    }

    @Test
    void batchImportPerItemResults() {
        String ck = adminCk();
        String marker = String.valueOf(System.nanoTime());
        byte[] fileA = png("A");
        byte[] fileB = png("B");
        ResponseEntity<String> resp = batch(
                List.of(fileA, fileB, "not-a-payload".getBytes(StandardCharsets.UTF_8)),
                ck, marker);
        String body = resp.getBody();
        assertThat(body).contains("\"code\":0")
                .contains("已入库")
                .contains("拒绝"); // 第三张非图片被三校验拒绝(文件名由服务端时间戳生成,断言不依赖)
        // admin pending 落库(结构断言,不依赖具体 id)
        Integer n = jdbc.queryForObject(
                "SELECT COUNT(*) FROM pending_achievements WHERE submitter_type='admin' "
                        + "AND achievement_data::text LIKE ?",
                Integer.class, "%" + marker + "%");
        assertThat(n).isGreaterThanOrEqualTo(2);
        // 同文件重复导入 → sha 跳过(逐张 not ok)
        ResponseEntity<String> again = batch(List.of(fileA), ck, marker);
        assertThat(again.getBody()).contains("跳过");
    }

    @Test
    void xlsxReportsDownloadable() {
        String ck = adminCk();
        for (String name : new String[] {"department-summary.xlsx?year=2026",
                "student-affairs.xlsx", "teacher-personal.xlsx"}) {
            HttpHeaders headers = new HttpHeaders();
            headers.set("Cookie", ck);
            ResponseEntity<byte[]> resp = rest.exchange("/api/v2/admin/export/" + name,
                    HttpMethod.GET, new HttpEntity<>(headers), byte[].class);
            assertThat(resp.getStatusCode().value()).isEqualTo(200);
            assertThat(resp.getHeaders().getFirst("Content-Disposition")).contains(".xlsx");
            assertThat(resp.getBody()).isNotNull().isNotEmpty();
            // xlsx 魔数 PK
            assertThat(resp.getBody()[0]).isEqualTo((byte) 'P');
            assertThat(resp.getBody()[1]).isEqualTo((byte) 'K');
        }
    }

    @Test
    void logStreamEmitsAnchor() {
        String ck = adminCk();
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", ck);
        // timeoutMillis=3000:3 秒后服务端 complete,响应可断言(生产默认 0=长连)
        ResponseEntity<String> resp = rest.exchange(
                "/api/v2/admin/logs/stream?afterId=0&timeoutMillis=3000",
                HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(200);
        assertThat(resp.getBody()).contains("event:anchor").contains("lastId");
    }

    @Test
    void nonAdminForbidden() {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", loginAs("212306413", "P@ss301"));
        ResponseEntity<String> resp = rest.exchange("/api/v2/admin/logs/stream?afterId=0",
                HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(403);
    }
}
