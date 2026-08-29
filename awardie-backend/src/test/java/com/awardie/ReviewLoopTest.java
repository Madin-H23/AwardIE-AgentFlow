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
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<String> resp = rest.postForEntity("/api/v2/auth/login",
                new HttpEntity<>(Map.of("account", account, "password",
                        account.equals("admin") ? "Mayy123" : "P@ss301"), headers), String.class);
        return resp.getHeaders().getFirst(HttpHeaders.SET_COOKIE).split(";")[0];
    }

    private int submitAsStudent() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", cookie("212306413"));
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
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Cookie", cookie);
        return rest.exchange("/api/v2/teacher/review/" + id, org.springframework.http.HttpMethod.POST,
                new HttpEntity<>(Map.of("action", action, "comment", comment == null ? "" : comment),
                        headers),
                String.class);
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
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", cookie("212306413"));
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
    @Order(7)
    void studentCannotReview() {
        int id = submitAsStudent();
        String body = review(cookie("212306413"), id, "approve", "").getBody();
        assertThat(body).contains("需要 teacher 角色");
    }
}
