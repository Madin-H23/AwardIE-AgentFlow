package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission.PendingAchievementDO;
import cn.iocoder.yudao.module.business.dal.mysql.pendingsubmission.PendingAchievementMapper;
import cn.iocoder.yudao.module.system.dal.dataobject.permission.MenuDO;
import cn.iocoder.yudao.module.system.dal.dataobject.user.AdminUserDO;
import cn.iocoder.yudao.module.system.dal.mysql.permission.MenuMapper;
import cn.iocoder.yudao.module.system.dal.mysql.user.AdminUserMapper;
import cn.iocoder.yudao.module.system.service.permission.PermissionService;
import cn.iocoder.yudao.server.YudaoServerApplication;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.util.Comparator;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 批4 待审成果提交流集成测试(MockMvc + Bearer + tenant 1,test 库隔离)。
 *
 * <p>夹具用真实魔术字节构造(jpg/png/pdf),不用默认假文件——避免"因默认值巧合通过"。
 * 文件根注入 target/test-files/pending,用例间清理。
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        // 独立 Redis 库(默认 0 是 dev 服务在用):权限缓存键不含库标识,共用会互相污染
        "spring.data.redis.database=1",
        "awardie.file.root=target/test-files/pending"
})
@AutoConfigureMockMvc
class PendingSubmissionControllerTest {

    private static final String BASE = "/admin-api/business/pending-achievements";
    private static final long TENANT_ID = 1L;
    private static final long STUDENT_ROLE_ID = 102L;   // awardie_student(批2)
    private static final long TEACHER_ROLE_ID = 101L;   // awardie_teacher
    private static final String STUDENT = "submitteststu";
    private static final String OTHER_STUDENT = "submitteststu2";
    private static final String TEACHER = "submittesttea";
    private static final String PASSWORD = "Sub@Test#2026";

    private static final byte[] JPEG_BYTES = {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0, 0x11, 0x22};
    private static final byte[] PNG_BYTES = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
    private static final byte[] PDF_BYTES = {0x25, 0x50, 0x44, 0x46, 0x2D, 0x31, 0x2E, 0x37};
    private static final String VALID_AWARD_JSON =
            "{\"competition_name\":\"挑战杯\",\"award_level\":\"一等奖\",\"winner_name\":\"张三\",\"date\":\"2024-05-01\"}";
    /** 提交流所需权限点(测试自播种时按 permission 反查菜单 id) */
    private static final List<String> PENDING_PERMISSIONS = List.of(
            "business:pending-achievement:create",
            "business:pending-achievement:query",
            "business:pending-achievement:delete");

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private PendingAchievementMapper mapper;
    @Autowired
    private AdminUserMapper userMapper;
    @Autowired
    private MenuMapper menuMapper;
    @Autowired
    private PermissionService permissionService;

    private final ObjectMapper om = new ObjectMapper();
    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();
    private String studentToken;
    private String otherToken;
    private String teacherToken;

    @BeforeEach
    void setUp() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedUser(STUDENT, STUDENT_ROLE_ID);
        seedUser(OTHER_STUDENT, STUDENT_ROLE_ID);
        seedUser(TEACHER, TEACHER_ROLE_ID);
        studentToken = login(STUDENT);
        otherToken = login(OTHER_STUDENT);
        teacherToken = login(TEACHER);
        TenantContextHolder.setTenantId(TENANT_ID);
        mapper.delete(null);
        clearFiles();
    }

    @AfterEach
    void clean() {
        clearFiles();
        TenantContextHolder.clear();
    }

    private void clearFiles() {
        Path root = Path.of("target/test-files/pending");
        if (!Files.exists(root)) {
            return;
        }
        try (Stream<Path> walk = Files.walk(root)) {
            walk.sorted(Comparator.reverseOrder()).forEach(p -> {
                try {
                    Files.deleteIfExists(p);
                } catch (Exception ignored) {
                    // 清理失败不阻塞断言
                }
            });
        } catch (Exception ignored) {
            // 目录不存在
        }
    }

    /**
     * 播种用户并授权。用带 @CacheEvict 的两个 API 而非直插关联表:
     * 芋道权限链走 Redis 三级缓存(user_role_ids → menu_role_ids → permission_menu_ids),
     * 直插 system_user_role/system_role_menu 不会驱逐缓存,会拿到上一轮残留的空权限集 → 403。
     * 这样播种后无论缓存处于什么状态都自洽(CI 与本地同款)。
     */
    private void seedUser(String username, long roleId) {
        AdminUserDO existing = userMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getUsername, username));
        Long userId;
        if (existing == null) {
            AdminUserDO user = new AdminUserDO();
            user.setUsername(username);
            user.setPassword(bcrypt.encode(PASSWORD));
            user.setNickname("提交测试-" + username);
            user.setStatus(0);
            user.setTenantId(TENANT_ID);
            userMapper.insert(user);
            userId = user.getId();
        } else {
            userId = existing.getId();
        }
        Set<Long> menuIds = PENDING_PERMISSIONS.stream()
                .map(menuMapper::selectListByPermission)
                .flatMap(List::stream)
                .map(MenuDO::getId)
                .collect(Collectors.toSet());
        assertThat(menuIds).as("待审成果权限点缺失——请先执行 awardie-business-menus.sql + awardie-user-domain.sql")
                .hasSize(PENDING_PERMISSIONS.size());
        permissionService.assignUserRole(userId, Set.of(roleId));
    }

    private String login(String username) throws Exception {
        MvcResult result = mockMvc.perform(post("/admin-api/system/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("tenant-id", "1")
                        .content("{\"username\":\"" + username + "\",\"password\":\"" + PASSWORD + "\"}"))
                .andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        JsonNode body = om.readTree(result.getResponse().getContentAsString());
        String token = body.path("data").path("accessToken").asText();
        assertThat(token).as("登录应成功: %s", body.path("msg").asText()).isNotEmpty();
        return token;
    }

    /** 执行请求并重设租户上下文(HTTP 结束后芋道租户过滤器会清空) */
    private JsonNode call(MockHttpServletRequestBuilder builder) throws Exception {
        MvcResult result = mockMvc.perform(builder).andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        return om.readTree(result.getResponse().getContentAsString());
    }

    private HttpHeaders authHeaders(String token) {
        HttpHeaders h = new HttpHeaders();
        h.setBearerAuth(token);
        h.set("tenant-id", "1");
        return h;
    }

    private MockMultipartFile file(String name, byte[] bytes) {
        return new MockMultipartFile("file", name, MediaType.APPLICATION_OCTET_STREAM_VALUE, bytes);
    }

    private JsonNode submit(String token, MockMultipartFile file, String type, String data) throws Exception {
        return call(multipart(BASE + "/submit").file(file)
                .param("achievementType", type)
                .param("data", data)
                .headers(authHeaders(token)));
    }

    @Test
    void submitFiveAchievementTypes() throws Exception {
        // award(jpg)
        JsonNode award = submit(studentToken, file("award.jpg", JPEG_BYTES), "award", VALID_AWARD_JSON);
        assertThat(award.path("code").asInt()).isEqualTo(0);
        assertThat(award.at("/data/achievementType").asText()).isEqualTo("award");
        assertThat(award.at("/data/status").asText()).isEqualTo("pending");
        assertThat(award.at("/data/validationResult").asText()).contains("\"is_valid\":true");
        assertThat(award.at("/data/fileHash").asText()).hasSize(64);

        // patent(pdf) —— 申请号 CN 开头且≥5 位
        JsonNode patent = submit(studentToken, file("patent.pdf", PDF_BYTES), "patent",
                "{\"patent_name\":\"一种发明\",\"application_number\":\"CN12345678\",\"patent_type\":\"发明专利\"}");
        assertThat(patent.at("/data/validationResult").asText()).contains("\"is_valid\":true");

        // software(png) —— 登记号 20 开头且 11 位
        JsonNode software = submit(studentToken, file("software.png", PNG_BYTES), "software",
                "{\"software_name\":\"某系统\",\"registration_number\":\"2024SR2002865\"}");
        assertThat(software.at("/data/validationResult").asText()).contains("\"is_valid\":true");

        // innovation / other
        assertThat(submit(studentToken, file("inno.jpg", withTail(JPEG_BYTES, (byte) 0x41)), "innovation",
                "{\"project_name\":\"大创项目\"}").at("/data/achievementType").asText()).isEqualTo("innovation");
        assertThat(submit(studentToken, file("other.pdf", withTail(PDF_BYTES, (byte) 0x42)), "other",
                "{\"title\":\"某成果\"}").at("/data/achievementType").asText()).isEqualTo("other");

        assertThat(mapper.selectCount(null)).isEqualTo(5);
    }

    private byte[] withTail(byte[] base, byte extra) {
        byte[] out = new byte[base.length + 1];
        System.arraycopy(base, 0, out, 0, base.length);
        out[base.length] = extra;
        return out;
    }

    @Test
    void missingFieldDoesNotBlockSubmission() throws Exception {
        // 缺 winner_name:字段问题不阻断(校验结果落库供审核参考,沿 v2)
        JsonNode body = submit(studentToken, file("incomplete.jpg", JPEG_BYTES), "award",
                "{\"competition_name\":\"挑战杯\",\"award_level\":\"一等奖\",\"date\":\"2024-05-01\"}");
        assertThat(body.path("code").asInt()).isEqualTo(0);
        assertThat(body.at("/data/validationResult").asText())
                .contains("\"is_valid\":false")
                .contains("winner_name");
    }

    @Test
    void duplicatePendingFileRejected() throws Exception {
        MockMultipartFile file = file("dup.jpg", JPEG_BYTES);
        assertThat(submit(studentToken, file, "award", VALID_AWARD_JSON).path("code").asInt()).isEqualTo(0);
        JsonNode dup = submit(studentToken, file, "award", VALID_AWARD_JSON);
        assertThat(dup.path("code").asInt()).isEqualTo(1003002001);
        assertThat(mapper.selectCount(null)).isEqualTo(1);
    }

    @Test
    void teacherSubmissionUsesTeacherType() throws Exception {
        JsonNode body = submit(teacherToken, file("tea.jpg", JPEG_BYTES), "award", VALID_AWARD_JSON);
        assertThat(body.path("code").asInt()).isEqualTo(0);
        PendingAchievementDO row = mapper.selectOne(
                new LambdaQueryWrapper<PendingAchievementDO>().eq(PendingAchievementDO::getId, body.at("/data/id").asLong()));
        // submitter_type 由服务端按角色推导,不信任前端
        assertThat(row.getSubmitterType()).isEqualTo("teacher");
    }

    @Test
    void unknownTypeRejected() throws Exception {
        JsonNode body = submit(studentToken, file("x.jpg", JPEG_BYTES), "unknown-type", "{}");
        assertThat(body.path("code").asInt()).isEqualTo(1003002005);
    }

    @Test
    void withdrawByOwnerSucceeds() throws Exception {
        JsonNode created = submit(studentToken, file("w.jpg", JPEG_BYTES), "award", VALID_AWARD_JSON);
        long id = created.at("/data/id").asLong();
        JsonNode body = call(delete(BASE + "/withdraw").headers(authHeaders(studentToken)).param("id", String.valueOf(id)));
        assertThat(body.path("code").asInt()).isEqualTo(0);
        assertThat(mapper.selectById(id)).isNull();
    }

    @Test
    void withdrawByOtherStudentForbidden() throws Exception {
        JsonNode created = submit(studentToken, file("f.jpg", JPEG_BYTES), "award", VALID_AWARD_JSON);
        long id = created.at("/data/id").asLong();
        JsonNode body = call(delete(BASE + "/withdraw").headers(authHeaders(otherToken)).param("id", String.valueOf(id)));
        assertThat(body.path("code").asInt()).isEqualTo(1003002004);
        assertThat(mapper.selectById(id)).isNotNull();
    }

    @Test
    void withdrawNonPendingRejected() throws Exception {
        JsonNode created = submit(studentToken, file("np.jpg", JPEG_BYTES), "award", VALID_AWARD_JSON);
        long id = created.at("/data/id").asLong();
        PendingAchievementDO row = mapper.selectById(id);
        row.setStatus("archived");
        mapper.updateById(row);
        TenantContextHolder.setTenantId(TENANT_ID);
        JsonNode body = call(delete(BASE + "/withdraw").headers(authHeaders(studentToken)).param("id", String.valueOf(id)));
        assertThat(body.path("code").asInt()).isEqualTo(1003002003);
    }

    @Test
    void downloadByOwnerAndTeacher() throws Exception {
        JsonNode created = submit(studentToken, file("dl.jpg", JPEG_BYTES), "award", VALID_AWARD_JSON);
        long id = created.at("/data/id").asLong();
        MvcResult byOwner = mockMvc.perform(get(BASE + "/download").headers(authHeaders(studentToken))
                .param("id", String.valueOf(id))).andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        assertThat(byOwner.getResponse().getStatus()).isEqualTo(200);
        assertThat(byOwner.getResponse().getHeader("Content-Disposition")).contains("attachment");
        assertThat(byOwner.getResponse().getContentType()).contains("image/jpeg");
        assertThat(byOwner.getResponse().getContentAsByteArray()).isEqualTo(JPEG_BYTES);

        // 教师可下载(初审需要)
        MvcResult byTeacher = mockMvc.perform(get(BASE + "/download").headers(authHeaders(teacherToken))
                .param("id", String.valueOf(id))).andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        assertThat(byTeacher.getResponse().getStatus()).isEqualTo(200);
    }

    @Test
    void downloadByOtherStudentForbidden() throws Exception {
        JsonNode created = submit(studentToken, file("pf.jpg", JPEG_BYTES), "award", VALID_AWARD_JSON);
        long id = created.at("/data/id").asLong();
        JsonNode body = call(get(BASE + "/download").headers(authHeaders(otherToken)).param("id", String.valueOf(id)));
        assertThat(body.path("code").asInt()).isEqualTo(1003002004);
    }

    @Test
    void myPageIsolatesBySubmitter() throws Exception {
        submit(studentToken, file("mine.jpg", JPEG_BYTES), "award", VALID_AWARD_JSON);
        submit(otherToken, file("theirs.jpg", withTail(JPEG_BYTES, (byte) 0x55)), "award", VALID_AWARD_JSON);
        JsonNode mine = call(get(BASE + "/my-page").headers(authHeaders(studentToken))
                .param("pageNo", "1").param("pageSize", "10"));
        assertThat(mine.path("code").asInt()).isEqualTo(0);
        assertThat(mine.at("/data/total").asInt()).isEqualTo(1);
        assertThat(mine.at("/data/list/0/filePath").asText()).contains(".jpg");
    }

    @Test
    void unauthenticatedRejected() throws Exception {
        JsonNode body = call(get(BASE + "/my-page").header("tenant-id", "1")
                .param("pageNo", "1").param("pageSize", "10"));
        assertThat(body.path("code").asInt()).isEqualTo(401);
    }
}
