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

/** #11 审核闭环:状态机 pending→archived/rejected + BR-5 + 时间线 RBAC。 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class ReviewLoopTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    private static final byte[] PNG_BYTES = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 9, 9};

    private String cookie(String account) {
        return loginAs(account, account.equals("admin") ? "Mayy123" : "P@ss301");
    }

    private String studentCookie() {
        return cookie("212306413");
    }

    private int submitAsStudent() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        String ck = studentCookie(); // 只调一次:两次调用=两次匿名签发,token 必失配
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        byte[] tail = String.valueOf(System.nanoTime()).getBytes(StandardCharsets.UTF_8);
        byte[] bytes = new byte[PNG_BYTES.length + tail.length];
        System.arraycopy(PNG_BYTES, 0, bytes, 0, PNG_BYTES.length);
        System.arraycopy(tail, 0, bytes, PNG_BYTES.length, tail.length);
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(bytes) {
            @Override
            public String getFilename() {
                return "review-loop.png";
            }
        });
        form.add("achievement_type", "award");
        form.add("data", "{\"competition_name\":\"闭环测试赛\",\"award_level\":\"一等奖\","
                + "\"winner_name\":\"陈品天\",\"date\":\"2025-06\"}");
        ResponseEntity<String> resp = rest.postForEntity("/api/v2/student/submit",
                new HttpEntity<>(form, headers), String.class);
        String body = resp.getBody();
        return Integer.parseInt(body.replaceAll(".*\"id\":(\\d+).*", "$1"));
    }

    private ResponseEntity<String> review(String cookie, int id, String action, String comment) {
        return postJson("/api/v2/teacher/review/" + id,
                Map.of("action", action, "comment", comment == null ? "" : comment), cookie);
    }

    @org.junit.jupiter.api.BeforeEach
    void seedBase() {
        seedAccounts();
    }

    @Test
    @Order(1)
    void submitWritesAuditAction1() {
        int id = submitAsStudent();
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie("212306413"));
        ResponseEntity<String> timeline = rest.exchange("/api/v2/student/timeline/" + id,
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(timeline.getBody()).contains("\"actionType\":1").contains("提交成果");
    }

    @Test
    @Order(2)
    void approveArchivesAndWritesAudit6() {
        int id = submitAsStudent();
        String body = review(cookie("02110606"), id, "approve", "材料齐全").getBody();
        assertThat(body).contains("\"code\":0").contains("\"status\":\"archived\"");
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie("212306413"));
        ResponseEntity<String> timeline = rest.exchange("/api/v2/student/timeline/" + id,
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(timeline.getBody()).contains("\"actionType\":6").contains("审核通过");
    }

    @Test
    @Order(3)
    void rejectRequiresComment() {
        int id = submitAsStudent();
        String body = review(cookie("02110606"), id, "reject", "").getBody();
        assertThat(body).contains("BR-5");
    }

    @Test
    @Order(4)
    void rejectSetsRejectedWithComment() {
        int id = submitAsStudent();
        String body = review(cookie("02110606"), id, "reject", "证书编号不清晰,请重传").getBody();
        assertThat(body).contains("\"code\":0").contains("\"status\":\"rejected\"")
                .contains("证书编号不清晰");
    }

    @Test
    @Order(5)
    void br5ResubmitAfterRejectAllowed() {
        int id = submitAsStudent();
        assertThat(review(cookie("02110606"), id, "reject", "需补指导教师").getBody()).contains("\"code\":0");
        // BR-5:同文件(被驳回行不参与 pending 去重)修改后重新提交 → 新 pending 行
        String ckBr5 = studentCookie();
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", ckBr5);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ckBr5));
        byte[] same = ("same-bytes-for-br5-" + System.nanoTime()).getBytes(StandardCharsets.UTF_8);
        byte[] head = {(byte) 0x89, 0x50, 0x4E, 0x47};
        byte[] bytes = new byte[head.length + same.length];
        System.arraycopy(head, 0, bytes, 0, head.length);
        System.arraycopy(same, 0, bytes, head.length, same.length);
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(bytes) {
            @Override
            public String getFilename() {
                return "br5.png";
            }
        });
        form.add("achievement_type", "award");
        form.add("data", "{\"competition_name\":\"闭环测试赛\",\"award_level\":\"一等奖\","
                + "\"winner_name\":\"陈品天\",\"date\":\"2025-06\",\"supervisor_name\":\"已补\"}");
        ResponseEntity<String> resp = rest.postForEntity("/api/v2/student/submit",
                new HttpEntity<>(form, headers), String.class);
        assertThat(resp.getBody()).contains("\"code\":0").contains("\"status\":\"pending\"");
    }

    @Test
    @Order(6)
    void doubleReviewBlockedByStateMachine() {
        int id = submitAsStudent();
        assertThat(review(cookie("02110606"), id, "approve", "").getBody()).contains("\"code\":0");
        String again = review(cookie("02110606"), id, "approve", "再次").getBody();
        assertThat(again).contains("状态机非法流转");
    }

    @Test
    @Order(6)
    void materializeWritesAwardsAndIdempotent() {
        int id = submitAsStudent();
        assertThat(review(cookie("02110606"), id, "approve", "通过").getBody()).contains("\"code\":0");
        // 物化:awards 出现对应行(image_hash=文件 sha),学生关联建立
        Integer awardId = jdbc.queryForObject(
                "SELECT a.id FROM awards a JOIN award_student_winners w ON w.award_id=a.id "
                + "WHERE a.image_hash=(SELECT file_hash FROM pending_achievements WHERE id=?)",
                Integer.class, id);
        assertThat(awardId).isNotNull();
        // 幂等:重复批准不重复入库
        Integer before = jdbc.queryForObject("SELECT COUNT(*) FROM awards", Integer.class);
        review(cookie("02110606"), id, "approve", "重复"); // 状态机拒绝,不该有副作用
        // 直接验证 audit 8 只有一条(入库留痕幂等)
        Integer m = jdbc.queryForObject(
                "SELECT COUNT(*) FROM achievement_audit_log WHERE achievement_id=? AND action_type=8",
                Integer.class, id);
        assertThat(m).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM awards", Integer.class)).isEqualTo(before);
    }

    @Test
    @Order(6)
    void studentSeesOwnAwards() {
        int id = submitAsStudent();
        review(cookie("02110606"), id, "approve", "");
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie("212306413"));
        ResponseEntity<String> resp = rest.exchange("/api/v2/student/awards",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(resp.getBody()).contains("闭环测试赛");
    }

    @Test
    @Order(7)
    void teacherPendingListCarriesSubmitterName() {
        int id = submitAsStudent();
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie("02110606"));
        ResponseEntity<String> resp = rest.exchange("/api/v2/teacher/pending",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        // 提交者姓名批:join users 键名契约(陈品天=212306413)
        assertThat(resp.getBody()).contains("\"submitterName\"").contains("陈品天");
    }

    @Test
    @Order(7)
    void studentCannotReview() {
        int id = submitAsStudent();
        String body = review(cookie("212306413"), id, "approve", "").getBody();
        assertThat(body).contains("需要 teacher 角色");
    }

    @Test
    @Order(8)
    void approveCarriesCertificatePathToAward() {
        int id = submitAsStudent();
        assertThat(review(cookie("02110606"), id, "approve", "带图入库").getBody()).contains("\"code\":0");
        // 批 2 证书链:物化时 pending.file_path → awards.certificate_path
        Integer awardId = jdbc.queryForObject(
                "SELECT a.id FROM awards a JOIN pending_achievements p ON a.image_hash = p.file_hash "
                        + "WHERE p.id = ? AND a.certificate_path IS NOT NULL", Integer.class, id);
        // 编辑页证书图回显:inline 200
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", cookie("admin"));
        ResponseEntity<byte[]> img = rest.exchange("/api/v2/admin/awards/" + awardId + "/certificate",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), byte[].class);
        assertThat(img.getStatusCode().value()).isEqualTo(200);
        // 无证书的 award → 404(模板图片端点同语义)
        ResponseEntity<String> missing = rest.exchange("/api/v2/admin/awards/999999/certificate",
                org.springframework.http.HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(missing.getStatusCode().value()).isEqualTo(404);
    }
}
