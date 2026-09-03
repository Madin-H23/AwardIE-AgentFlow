package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.Map;

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

/** Fix-TP 模板创建/详情/试测端点测试(测试库 awardie_test,自给自足)。 */
class AdminTemplateDetailTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private static final MediaType MULTIPART = MediaType.MULTIPART_FORM_DATA;

    private String adminCk() {
        return loginAs("admin", "Mayy123");
    }

    private ResponseEntity<String> get(String ck, String path) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", ck);
        return rest.exchange(path, HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    private ResponseEntity<String> put(String ck, String path, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        return rest.exchange(path, HttpMethod.PUT, new HttpEntity<>(body, headers), String.class);
    }

    private ResponseEntity<String> post(String ck, String path) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        return rest.exchange(path, HttpMethod.POST, new HttpEntity<>("{}", headers), String.class);
    }

    private Integer seedCompetition() {
        jdbc.update("INSERT INTO competitions (competition_name) VALUES ('FixTP竞赛') ON CONFLICT (competition_name) DO NOTHING");
        return jdbc.queryForObject("SELECT id FROM competitions WHERE competition_name = 'FixTP竞赛'", Integer.class);
    }

    private ResponseEntity<String> createTemplate(String ck, Integer compId, String grantedRole) {
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new ByteArrayResource(new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0, 'f', 'a', 'k', 'e', '-', 'j', 'p', 'e', 'g'}) {
            @Override
            public String getFilename() {
                return "sample.jpg";
            }
        });
        body.add("competitionId", String.valueOf(compId));
        body.add("grantedRole", grantedRole);
        body.add("sampleExtracted", "{\"award_level\":\"一等奖\"}");
        body.add("sampleText", "FixTP 样本文本");
        body.add("keywords", "FixTP竞赛\n蓝桥杯");
        body.add("language", "zh");
        body.add("needTranslate", "false");
        body.add("minLength", "5");
        body.add("maxLength", "200");
        body.add("defaultFields", "{}");
        body.add("llmFields", "{}");
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MULTIPART);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        return rest.exchange("/api/v2/admin/templates/create", HttpMethod.POST,
                new HttpEntity<>(body, headers), String.class);
    }

    @Test
    void createDetailImageUpdate() {
        Integer compId = seedCompetition();
        // 每轮清重建:老运行遗留的模板可能无 sample_image_path(批 1 前旧代码产物),复用会污染断言
        jdbc.update("DELETE FROM templates WHERE competition_id = ?", compId);
        ResponseEntity<String> first = createTemplate(adminCk(), compId, "学生");
        assertThat(first.getBody()).contains("\"code\":0").contains("创建成功");
        Integer id = jdbc.queryForObject(
                "SELECT id FROM templates WHERE competition_id = ? ORDER BY id DESC LIMIT 1", Integer.class, compId);
        // 键名级契约(detail 聚合)
        String body = get(adminCk(), "/api/v2/admin/templates/" + id + "/detail").getBody();
        assertThat(body).contains("\"code\":0")
                .contains("\"templateType\"").contains("\"keywords\"").contains("\"llmFields\"")
                .contains("\"hasImage\"").contains("\"competitionName\"")
                .contains("FixTP竞赛");
        // 图片字节往返
        ResponseEntity<byte[]> img = rest.exchange("/api/v2/admin/templates/" + id + "/image",
                HttpMethod.GET, new HttpEntity<>(headersWithCookie(adminCk())), byte[].class);
        assertThat(img.getStatusCode().value()).isEqualTo(200);
        assertThat(new String(img.getBody(), StandardCharsets.UTF_8)).contains("fake-jpeg");
        // 唯一性:同竞赛同角色
        assertThat(createTemplate(adminCk(), compId, "学生").getBody()).contains("4009");
        // 必填:角色非法
        assertThat(createTemplate(adminCk(), compId, "管理员").getBody()).contains("4000");
        // 404
        assertThat(get(adminCk(), "/api/v2/admin/templates/999999/detail").getBody()).contains("4004");
    }

    private HttpHeaders headersWithCookie(String ck) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", ck);
        return headers;
    }

    @Test
    void updateAndFakeTest() {
        Integer compId = seedCompetition();
        createTemplate(adminCk(), compId, "教师");
        Integer id = jdbc.queryForObject(
                "SELECT id FROM templates WHERE competition_id = ? ORDER BY id DESC LIMIT 1", Integer.class, compId);
        ResponseEntity<String> resp = put(adminCk(), "/api/v2/admin/templates/" + id, java.util.Map.of(
                "minLength", 10,
                "maxLength", 300,
                "keywords", java.util.List.of("FixTP竞赛", "新关键词"),
                "sampleText", "更新后的样本文本",
                "sampleExtracted", "{\"award_level\":\"二等奖\"}",
                "defaultFields", "{}",
                "llmFields", "{}",
                "language", "en",
                "needTranslate", true));
        assertThat(resp.getBody()).contains("\"code\":0").contains("已更新");
        org.springframework.jdbc.core.JdbcTemplate template = jdbc;
        Map<String, Object> row = template.queryForMap(
                "SELECT min_length, language, need_translate, sample_text FROM templates WHERE id = ?", id);
        assertThat(row.get("min_length")).isEqualTo(10);
        assertThat(row.get("language")).isEqualTo("en");
        assertThat(row.get("need_translate")).isEqualTo(Boolean.TRUE);
        assertThat(row.get("sample_text")).isEqualTo("更新后的样本文本");
        // fake 试测:确定性回显(test 端点为 POST)
        String testBody = post(adminCk(), "/api/v2/admin/templates/" + id + "/test").getBody();
        assertThat(testBody).contains("\"code\":0").contains("\"mode\":\"fake\"").contains("二等奖");
        // 403
        String stu = loginAs("212306413", "P@ss301");
        assertThat(get(stu, "/api/v2/admin/templates/" + id + "/detail").getStatusCode().value()).isEqualTo(403);
    }

    /** 架构票落地:extract-for-create / generate-prompt-for-create 两端点(fake 桩,键名级契约)。 */
    @Test
    void extractAndPromptFakeStubs() {
        // extract-for-create:multipart 样本图 → mode/dataJson/ocrText 键名契约
        // (cookie 与 XSRF token 必须同源:adminCk() 每次调用都是独立登录,先存变量)
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new ByteArrayResource(new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0, 'f', 'a', 'k', 'e', '-', 'j', 'p', 'e', 'g'}) {
            @Override
            public String getFilename() {
                return "extract.jpg";
            }
        });
        String ck = adminCk();
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MULTIPART);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        ResponseEntity<String> ext = rest.exchange("/api/v2/admin/templates/extract-for-create",
                HttpMethod.POST, new HttpEntity<>(body, headers), String.class);
        assertThat(ext.getBody()).contains("\"code\":0")
                .contains("\"mode\":\"fake\"").contains("\"dataJson\"").contains("\"ocrText\"")
                .contains("竞赛名称");
        // 必填:缺文件 4000
        assertThat(rest.exchange("/api/v2/admin/templates/extract-for-create", HttpMethod.POST,
                new HttpEntity<>(new LinkedMultiValueMap<String, Object>(), headers), String.class)
                .getBody()).contains("4000");
        // generate-prompt-for-create:mode/prompt 键名契约
        assertThat(post(adminCk(), "/api/v2/admin/templates/generate-prompt-for-create").getBody())
                .contains("\"code\":0").contains("\"mode\":\"fake\"").contains("\"prompt\"");
        // 403:学生越权
        String stu = loginAs("212306413", "P@ss301");
        assertThat(post(stu, "/api/v2/admin/templates/generate-prompt-for-create").getStatusCode().value())
                .isEqualTo(403);
    }
}
