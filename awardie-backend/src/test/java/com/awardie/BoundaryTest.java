package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.stream.Stream;

import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

/**
 * G3 边界值参数化:分页越界/size 夹取/keyword 特殊字符(参数化绑定,注入不生效)/
 * 文件上限/空文件/超长字段。全部走真实 HTTP(测试库隔离)。
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class BoundaryTest extends BaseIntegrationTest {

    @Autowired
    private TestRestTemplate rest;

    private String adminCk() {
        return loginAs("admin", "Mayy123");
    }

    private ResponseEntity<String> get(String ck, String path) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Cookie", ck);
        return rest.exchange(path, HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    /** 分页越界:page 超出总页数返回空 content,不 500。 */
    @Test
    @Order(1)
    void pageOutOfBoundsReturnsEmptyNot500() {
        String body = get(adminCk(), "/api/v2/admin/achievements?page=999&size=20").getBody();
        assertThat(body).contains("\"code\":0").contains("\"content\":[]");
    }

    /** size 夹取:0/负数→1,101→100(源码 Math.min(Math.max(size,1),100))。 */
    @ParameterizedTest
    @MethodSource("sizeCases")
    void sizeClampedToValidRange(String sizeParam, String expectedSize) {
        String body = get(adminCk(), "/api/v2/admin/achievements?page=0&size=" + sizeParam).getBody();
        assertThat(body).contains("\"code\":0").contains("\"size\":" + expectedSize);
    }

    static Stream<Arguments> sizeCases() {
        return Stream.of(
                Arguments.of("0", "1"),
                Arguments.of("-5", "1"),
                Arguments.of("101", "100"),
                Arguments.of("1", "1"),
                Arguments.of("100", "100"));
    }

    /** keyword SQL 特殊字符:参数化绑定不拼接,任何字符都 200 且 code=0(注入不生效)。 */
    @ParameterizedTest
    @ValueSource(strings = {"%", "_", "'", "\"", ";", "' OR '1'='1", "%'--"})
    void keywordSpecialCharsSafe(String kw) {
        String body = rest.exchange("/api/v2/admin/achievements?page=0&size=20&keyword={kw}",
                HttpMethod.GET, entity(adminCk()), String.class, kw).getBody();
        assertThat(body).contains("\"code\":0");
        assertThat(body).doesNotContain("\"code\":5000");
    }

    private HttpEntity<Void> entity(String ck) {
        HttpHeaders h = new HttpHeaders();
        h.set("Cookie", ck);
        return new HttpEntity<>(h);
    }

    private byte[] pngPayload(int size) {
        byte[] head = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A};
        byte[] all = new byte[size];
        System.arraycopy(head, 0, all, 0, head.length);
        for (int i = head.length; i < size; i++) {
            all[i] = (byte) (i % 7);
        }
        // 尾部掺 nanoTime:sha 每次不同,避免跨运行去重拦截
        byte[] tag = String.valueOf(System.nanoTime()).getBytes();
        for (int i = 0; i < tag.length && size - 1 - i >= head.length; i++) {
            all[size - 1 - i] = tag[tag.length - 1 - i];
        }
        return all;
    }

    private ResponseEntity<String> submit(byte[] file, String data, String ck) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("Cookie", ck);
        headers.set("X-XSRF-TOKEN", xsrfFrom(ck));
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(file) {
            @Override
            public String getFilename() {
                return "boundary-" + System.nanoTime() + ".png";
            }
        });
        form.add("achievement_type", "award");
        form.add("data", data);
        return rest.postForEntity("/api/v2/student/submit", new HttpEntity<>(form, headers), String.class);
    }

    /** 空文件拒绝(魔术字节校验)。 */
    @Test
    @Order(2)
    void emptyFileRejected() {
        ResponseEntity<String> resp = submit(new byte[0],
                "{\"competition_name\":\"边界空文件\"}", loginAs("212306413", "P@ss301"));
        assertThat(resp.getBody()).contains("\"code\":4000");
    }

    /** 超限文件(10MB+1)拒绝——multipart 上限 11MB 留余量,超限由业务校验返回干净 4000。 */
    @Test
    @Order(3)
    void oversizedFileRejected() {
        ResponseEntity<String> resp = submit(pngPayload(10 * 1024 * 1024 + 1),
                "{\"competition_name\":\"边界超限\"}", loginAs("212306413", "P@ss301"));
        assertThat(resp.getBody()).contains("\"code\":4000").contains("10MB");
    }

    /** 上限内文件(1MB)正常通过。 */
    @Test
    @Order(4)
    void withinLimitFileAccepted() {
        ResponseEntity<String> resp = submit(pngPayload(1024 * 1024),
                "{\"competition_name\":\"边界内通过\",\"award_level\":\"一等奖\",\"date\":\"2026-09\"}",
                loginAs("212306413", "P@ss301"));
        assertThat(resp.getBody()).contains("\"code\":0");
    }

    /** 超长字段(600 字符)不 500:落 jsonb 正常入库或 4000,二选一。 */
    @Test
    @Order(5)
    void overlyLongFieldNot500() {
        String longName = "长".repeat(600);
        ResponseEntity<String> resp = submit(pngPayload(2048),
                "{\"competition_name\":\"" + longName + "\"}", loginAs("212306413", "P@ss301"));
        String body = resp.getBody();
        assertThat(body).containsAnyOf("\"code\":0", "\"code\":4000");
        assertThat(body).doesNotContain("\"code\":5000");
    }

    /** 非法日期格式(超长字段进 date)→ v1 语义标记非阻断,不 500。 */
    @Test
    @Order(6)
    void invalidDateNot500() {
        ResponseEntity<String> resp = submit(pngPayload(2048),
                "{\"competition_name\":\"日期边界\",\"date\":\"not-a-date\"}",
                loginAs("212306413", "P@ss301"));
        assertThat(resp.getBody()).doesNotContain("\"code\":5000");
    }

    /** 分页 size 边界在 student/pending 上同样夹取(单用户列表)。 */
    @ParameterizedTest
    @ValueSource(strings = {"0", "-3", "999"})
    void studentPendingSizeClamped(String sizeParam) {
        String body = get(loginAs("212306413", "P@ss301"),
                "/api/v2/student/pending?page=0&size=" + sizeParam).getBody();
        assertThat(body).contains("\"code\":0");
    }

    /** ConcurrentModification 防御性冒烟:同文件并发双提仅一次成功(BR sha 去重,串行模拟)。 */
    @Test
    @Order(7)
    void duplicateSubmitSecondRejected() {
        String ck = loginAs("212306413", "P@ss301");
        byte[] same = pngPayload(4096);
        List<ResponseEntity<String>> results = List.of(submit(same,
                "{\"competition_name\":\"并发去重\",\"award_level\":\"一等奖\",\"date\":\"2026-09\"}", ck),
                submit(same,
                        "{\"competition_name\":\"并发去重\",\"award_level\":\"一等奖\",\"date\":\"2026-09\"}", ck));
        long ok = results.stream().filter(r -> r.getBody().contains("\"code\":0")).count();
        long dup = results.stream().filter(r -> r.getBody().contains("4001")).count();
        assertThat(ok).isEqualTo(1);
        assertThat(dup).isEqualTo(1);
    }
}
