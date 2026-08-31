package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.xssf.usermodel.XSSFSheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
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

/** #34 大创 xlsx 导入:preview→confirm 全链(POI 构造夹具)+幂等+RBAC。 */
class InnovationImportTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    /** POI 构造 xlsx 夹具:表头+两有效行+一缺名称行;编号带时间戳便于重复跑。 */
    private byte[] buildXlsx(String suffix) {
        try (XSSFWorkbook wb = new XSSFWorkbook();
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            XSSFSheet sheet = wb.createSheet("大创");
            Row head = sheet.createRow(0);
            for (int i = 0; i < 10; i++) {
                head.createCell(i);
            }
            String no = "IMP-" + suffix;
            Row r1 = sheet.createRow(1);
            r1.createCell(0).setCellValue(no);
            r1.createCell(1).setCellValue("导入测试项目" + suffix);
            r1.createCell(2).setCellValue("省级");
            r1.createCell(3).setCellValue("2026-03");
            r1.createCell(4).setCellValue("2027-03");
            r1.createCell(5).setCellValue("张三");
            r1.createCell(6).setCellValue("2123000001");
            r1.createCell(7).setCellValue("李四、王五");
            r1.createCell(8).setCellValue("黄巧云");
            r1.createCell(9).setCellValue(2.5);
            Row r2 = sheet.createRow(2);
            r2.createCell(0).setCellValue("");
            r2.createCell(1).setCellValue(""); // 缺名称 → 行级错误
            wb.write(out);
            return out.toByteArray();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private ResponseEntity<String> preview(byte[] xlsx, String ck) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(xlsx) {
            @Override
            public String getFilename() {
                return "innovation.xlsx";
            }
        });
        return rest.exchange("/api/v2/admin/import/innovation/preview",
                HttpMethod.POST, new HttpEntity<>(form, headers), String.class);
    }

    @Test
    void previewConfirmAndIdempotent() {
        String ck = loginAs("admin", "Mayy123");
        String suffix = String.valueOf(System.nanoTime());
        ResponseEntity<String> preview = preview(buildXlsx(suffix), ck);
        assertThat(preview.getBody())
                .contains("\"code\":0").contains("\"sha256\"").contains("导入测试项目" + suffix);

        // 确认导入:从预览 JSON 里取回行(测试直接构造同构行;error 行被拒)
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        Map<String, Object> row = new java.util.HashMap<>();
        row.put("rowNo", 1);
        row.put("projectNo", "IMP-" + suffix);
        row.put("projectName", "导入测试项目" + suffix);
        row.put("projectType", "省级");
        row.put("startDate", "2026-03");
        row.put("endDate", "2027-03");
        row.put("leaderName", "张三");
        row.put("leaderId", "2123000001");
        row.put("otherMembers", "李四、王五");
        row.put("supervisors", "黄巧云");
        row.put("funding", 2.5);
        row.put("error", "");
        ResponseEntity<String> confirm = rest.exchange("/api/v2/admin/import/innovation/confirm",
                HttpMethod.POST, new HttpEntity<>(Map.of("sha256", "x", "rows", List.of(row)), headers), String.class);
        assertThat(confirm.getBody()).contains("\"code\":0").contains("\"imported\":1").contains("导入完成");

        Integer projectId = jdbc.queryForObject(
                "SELECT id FROM innovation_projects WHERE project_no=?", Integer.class, "IMP-" + suffix);
        assertThat(projectId).isNotNull();
        // CHECK 强制 admin 通道
        assertThat(jdbc.queryForObject(
                "SELECT submitter_type FROM innovation_projects WHERE id=?", String.class, projectId))
                .isEqualTo("admin");
        // 其他成员写为 jsonb 数组
        assertThat(jdbc.queryForObject(
                "SELECT other_members::text FROM innovation_projects WHERE id=?", String.class, projectId))
                .contains("李四");

        // 重复导入:同编号 → 跳过(幂等)
        ResponseEntity<String> again = rest.exchange("/api/v2/admin/import/innovation/confirm",
                HttpMethod.POST, new HttpEntity<>(Map.of("sha256", "x", "rows", List.of(row)), headers), String.class);
        assertThat(again.getBody()).contains("已存在").contains("跳过");
    }

    @Test
    void nonAdminForbidden() {
        byte[] xlsx = buildXlsx(String.valueOf(System.nanoTime()));
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", loginAs("212306413", "P@ss301"));
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(xlsx) {
            @Override
            public String getFilename() {
                return "innovation.xlsx";
            }
        });
        ResponseEntity<String> resp = rest.exchange("/api/v2/admin/import/innovation/preview",
                HttpMethod.POST, new HttpEntity<>(form, headers), String.class);
        assertThat(resp.getStatusCode().value()).isEqualTo(403);
    }
}
