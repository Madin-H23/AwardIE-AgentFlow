package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.Map;

import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class StudentSubmissionTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private org.springframework.jdbc.core.JdbcTemplate jdbc;

    private static final byte[] PNG_BYTES = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52, 1, 1, 1, 1};

    private String dataJson() {
        return "{\"competition_name\":\"挑战杯\",\"award_level\":\"省级一等奖\",\"winner_name\":\"测试学生\","
                + "\"date\":\"2025-05\",\"certificate_id\":\"CERT-001\",\"project_title\":\"测试项目\"}";
    }

    private String studentCookie() {
        ResponseEntity<String> resp = post("/api/v2/auth/login", Map.of("account", "212306413", "password", "P@ss301"));
        return cookieOf(resp);
    }

    private String adminCookie() {
        ResponseEntity<String> resp = post("/api/v2/auth/login", Map.of("account", "admin", "password", "Mayy123"));
        return cookieOf(resp);
    }

    private String cookieOf(ResponseEntity<String> resp) {
        return resp.getHeaders().getFirst(HttpHeaders.SET_COOKIE).split(";")[0];
    }

    private ResponseEntity<String> post(String uri, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return rest.postForEntity(uri, new HttpEntity<>(body, headers), String.class);
    }

    private ResponseEntity<String> submitMultipart(String cookie, String filename, byte[] bytes, String data) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", cookie);
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(bytes) {
            @Override
            public String getFilename() {
                return filename;
            }
        });
        form.add("achievement_type", "award");
        form.add("data", data);
        return rest.postForEntity("/api/v2/student/submit", new HttpEntity<>(form, headers), String.class);
    }

    private ResponseEntity<String> get(String uri, String cookie) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie);
        return rest.exchange(uri, org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    private byte[] uniquePng() {
        byte[] tail = String.valueOf(System.nanoTime()).getBytes(StandardCharsets.UTF_8);
        byte[] out = new byte[PNG_BYTES.length + tail.length];
        System.arraycopy(PNG_BYTES, 0, out, 0, PNG_BYTES.length);
        System.arraycopy(tail, 0, out, PNG_BYTES.length, tail.length);
        return out;
    }

    @org.junit.jupiter.api.BeforeEach
    void seedBase() {
        seedAccounts();
    }

    @Test
    @Order(1)
    void submitAwardOk() {
        String body = submitMultipart(studentCookie(), "cert.png", uniquePng(), dataJson()).getBody();
        assertThat(body).contains("\"code\":0").contains("\"status\":\"pending\"").contains("\"isValid\":true");
    }

    @Test
    @Order(2)
    void duplicateFileHashRejected() {
        // 同文件第二次提交(仍 pending)→ 去重拒绝
        byte[] first = uniquePng();
        assertThat(submitMultipart(studentCookie(), "cert.png", first, dataJson()).getBody())
                .contains("\"code\":0");
        String body = submitMultipart(studentCookie(), "cert.png", first, dataJson()).getBody();
        assertThat(body).contains("\"code\":4001").contains("sha256 去重");
    }

    @Test
    @Order(3)
    void magicByteMismatchRejected() {
        // 伪装扩展名:内容是文本,扩展名 .png
        String body = submitMultipart(studentCookie(), "fake.png", "hello world".getBytes(StandardCharsets.UTF_8),
                dataJson()).getBody();
        assertThat(body).contains("魔术字节");
    }

    @Test
    @Order(4)
    void disallowedExtensionRejected() {
        String body = submitMultipart(studentCookie(), "cert.exe", PNG_BYTES, dataJson()).getBody();
        assertThat(body).contains("不支持的文件类型");
    }

    @Test
    @Order(5)
    void invalidDateFormatMarkedNotValid() {
        // v1 语义:date 非法不阻断提交,validation_result.is_valid=false 留待人工
        String bad = "{\"competition_name\":\"挑战杯\",\"award_level\":\"省一\",\"winner_name\":\"张三\",\"date\":\"2099-13\"}";
        String body = submitMultipart(studentCookie(), "cert2.png", uniquePng(), bad).getBody();
        assertThat(body).contains("\"code\":0").contains("\"isValid\":false");
    }

    @Test
    @Order(6)
    void myListShowsOwnSubmissions() {
        String body = get("/api/v2/student/pending", studentCookie()).getBody();
        assertThat(body).contains("挑战杯").contains("pending");
    }

    @Test
    @Order(7)
    void downloadIsAttachment() throws Exception {
        // 从自己的提交列表解析真实 id(自增 id 接续 sqlite_sequence,不是 1)
        String list = get("/api/v2/student/pending", studentCookie()).getBody();
        com.fasterxml.jackson.databind.JsonNode node = new com.fasterxml.jackson.databind.ObjectMapper()
                .readTree(list);
        int id = node.get("data").get(0).get("id").asInt();
        ResponseEntity<byte[]> resp = getBytes("/api/v2/files/" + id + "/download", studentCookie());
        assertThat(resp.getStatusCode().value()).isEqualTo(200);
        assertThat(resp.getHeaders().getFirst(HttpHeaders.CONTENT_DISPOSITION)).contains("attachment");
        assertThat(resp.getBody()).isNotEmpty();
    }

    @Test
    @Order(8)
    void teacherCannotUseStudentEndpoint() {
        // 教师角色提交 → 拒(角色校验)
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", adminCookie());
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(PNG_BYTES) {
            @Override
            public String getFilename() {
                return "t.png";
            }
        });
        form.add("achievement_type", "award");
        form.add("data", dataJson());
        ResponseEntity<String> resp = rest.postForEntity("/api/v2/student/submit",
                new HttpEntity<>(form, headers), String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(403); // AccessDeniedException → 403(角色错误)
        assertThat(resp.getBody()).contains("student");
    }

    @Test
    @Order(9)
    void validationPersistsToGeneratedColumn() {
        // 提交合法数据后,JSONB validation_result → 生成列 is_valid=1(直接 SQL 验证)
        Integer valid = jdbc.queryForObject(
                "SELECT COUNT(*) FROM pending_achievements WHERE is_valid = 1", Integer.class);
        assertThat(valid).isGreaterThanOrEqualTo(1);
    }

    private ResponseEntity<byte[]> getBytes(String uri, String cookie) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie);
        return rest.exchange(uri, org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), byte[].class);
    }
}
