package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.service.pendingsubmission.AiReviewService;
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
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 批7 gRPC 降级测试:审核流 AI 建议在 grpc 模式但 Worker 不可达时,
 * 必须转人工审 + 4003 + 免责声明仍在,且**快速返回不挂死**。
 *
 * <p>本类与其它集成测试类属性不同(grpc 模式 + 指向不可达端口),故独立成类。
 * 独立上下文是有意的代价:芋道 @SpringBootTest 不复用上下文,多一个上下文启动慢一些,
 * 但换来"grpc 模式真的被走到"的真实验证——用同一上下文改配置是测不到的。
 *
 * <p>port=1 保证连不上(不是本机 Worker 的 50060,也不需要真的起一个坏服务)。
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        "spring.data.redis.database=1",
        "awardie.file.root=target/test-files/grpc-degrade",
        "awardie.ai.worker.mode=grpc",
        "awardie.ai.worker.host=127.0.0.1",
        "awardie.ai.worker.port=1",
        // 短 deadline:证明"不可达"是快速失败而非等到超时
        "awardie.ai.worker.review-timeout-seconds=3",
        "awardie.ai.worker.extract-timeout-seconds=3",
        "awardie.ai.worker.prompt-timeout-seconds=3"
})
@AutoConfigureMockMvc
class AiWorkerGrpcDegradeTest {

    private static final String SUBMIT_BASE = "/admin-api/business/pending-achievements";
    private static final String TEMPLATE_BASE = "/admin-api/business/templates";
    private static final long TENANT_ID = 1L;
    private static final long TEACHER_ROLE = 101L;
    private static final long ADMIN_ROLE = 100L;
    private static final String TEACHER = "grpctea1";
    private static final String ADMIN = "grpcadm1";
    private static final String PASSWORD = "Grpc@Test#26";
    private static final List<String> TEACHER_PERMISSIONS = List.of(
            "business:pending-achievement:query", "business:pending-achievement:review");
    private static final List<String> ADMIN_PERMISSIONS = List.of(
            "business:templates:query", "business:templates:create");

    private static final byte[] PNG = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x33, 0x44};
    private static final String AWARD_JSON = "{\"competition_name\":\"降级测试竞赛\",\"winner_name\":\"张三\"}";

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private AdminUserMapper userMapper;
    @Autowired
    private MenuMapper menuMapper;
    @Autowired
    private PermissionService permissionService;
    @Autowired
    private AiReviewService aiReviewService;

    private final ObjectMapper om = new ObjectMapper();
    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();
    private String teacherToken;
    private String adminToken;

    @BeforeEach
    void setUp() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedUser(TEACHER, TEACHER_ROLE, TEACHER_PERMISSIONS);
        seedUser(ADMIN, ADMIN_ROLE, ADMIN_PERMISSIONS);
        teacherToken = login(TEACHER);
        adminToken = login(ADMIN);
        TenantContextHolder.setTenantId(TENANT_ID);
        cleanTables();
    }

    @AfterEach
    void clean() {
        cleanTables();
        TenantContextHolder.clear();
    }

    private void cleanTables() {
        jdbcTemplate.update("DELETE FROM awardie_achievement_audit_log");
        jdbcTemplate.update("DELETE FROM awardie_pending_achievements");
        jdbcTemplate.update("DELETE FROM awardie_templates");
        jdbcTemplate.update("DELETE FROM awardie_competitions");
        Path root = Path.of("target/test-files/grpc-degrade").toAbsolutePath();
        if (!Files.exists(root)) {
            return;
        }
        try (Stream<Path> walk = Files.walk(root)) {
            walk.sorted(java.util.Comparator.reverseOrder()).forEach(p -> {
                try {
                    Files.deleteIfExists(p);
                } catch (IOException ignored) {
                    // 清理失败不阻塞断言
                }
            });
        } catch (IOException ignored) {
            // 同上
        }
    }

    private void seedUser(String username, long roleId, List<String> permissions) {
        AdminUserDO user = new AdminUserDO();
        user.setUsername(username);
        user.setPassword(bcrypt.encode(PASSWORD));
        user.setNickname("降级测试-" + username);
        user.setStatus(0);
        user.setTenantId(TENANT_ID);
        AdminUserDO existing = userMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getUsername, username));
        Long userId;
        if (existing == null) {
            userMapper.insert(user);
            userId = user.getId();
        } else {
            userId = existing.getId();
            existing.setPassword(user.getPassword());
            userMapper.updateById(existing);
        }
        Set<Long> menuIds = permissions.stream()
                .map(menuMapper::selectListByPermission)
                .flatMap(List::stream)
                .map(MenuDO::getId)
                .collect(Collectors.toSet());
        assertThat(menuIds).as("权限点缺失——请先执行 awardie-business-menus.sql + awardie-user-domain.sql")
                .hasSize(permissions.size());
        permissionService.assignUserRole(userId, Set.of(roleId));
    }

    private String login(String username) throws Exception {
        MvcResult result = mockMvc.perform(post("/admin-api/system/auth/login")
                        .contentType(MediaType.APPLICATION_JSON).header("tenant-id", "1")
                        .content("{\"username\":\"" + username + "\",\"password\":\"" + PASSWORD + "\"}"))
                .andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        JsonNode body = om.readTree(result.getResponse().getContentAsString());
        assertThat(body.at("/data/accessToken").asText())
                .as("登录应成功: %s", body.path("msg").asText()).isNotEmpty();
        return body.at("/data/accessToken").asText();
    }

    private JsonNode call(MockHttpServletRequestBuilder builder) throws Exception {
        MvcResult result = mockMvc.perform(builder).andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        return om.readTree(result.getResponse().getContentAsString());
    }

    private HttpHeaders headers(String token) {
        HttpHeaders h = new HttpHeaders();
        h.setBearerAuth(token);
        h.set("tenant-id", "1");
        h.setContentType(MediaType.APPLICATION_JSON);
        return h;
    }

    private long submit(String token) throws Exception {
        MockMultipartFile file = new MockMultipartFile("file", "降级样本.png",
                MediaType.IMAGE_PNG_VALUE, PNG);
        JsonNode body = call(multipart(SUBMIT_BASE + "/submit")
                .file(file)
                .param("achievementType", "award")
                .param("data", AWARD_JSON)
                .headers(headers(token)));
        assertThat(body.path("code").asInt()).as("提交应成功: %s", body.path("msg").asText()).isZero();
        return body.at("/data/id").asLong();
    }

    @Test
    void aiSuggestDegradesToManualWhenWorkerUnreachable() throws Exception {
        long id = submit(teacherToken);
        long start = System.currentTimeMillis();
        JsonNode body = call(get(SUBMIT_BASE + "/" + id + "/ai-suggest").headers(headers(teacherToken)));
        long elapsed = System.currentTimeMillis() - start;

        assertThat(body.path("code").asInt()).isZero();
        // Worker 不可达 → 转人工审,不抛错
        assertThat(body.at("/data/decision").asText()).isEqualTo("need_manual");
        assertThat(body.at("/data/code").asInt()).isEqualTo(4003);
        assertThat(body.at("/data/degraded").asBoolean()).isTrue();
        // BR-2 免责声明必须仍在
        assertThat(body.at("/data/suggestion").asText()).contains("AI 建议仅辅助参考");
        // 不可达是快速失败,不能挂死:deadline=3s,留足余量给 MockMvc 开销
        assertThat(elapsed).as("不可达应快速返回,不应挂死").isLessThan(15_000L);
    }

    @Test
    void templateAiEndpointReturnsWorkerUnavailableCode() throws Exception {
        // 模板域 AI 端点在 Worker 不可达时返回明确业务错误(不 500、不挂死)
        jdbcTemplate.update("INSERT INTO awardie_competitions (competition_name, tenant_id)"
                + " VALUES ('降级模板竞赛', 1)");
        long comp = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_competitions WHERE competition_name = '降级模板竞赛' ORDER BY id DESC LIMIT 1",
                Long.class);
        MockMultipartFile data = new MockMultipartFile("data", "", MediaType.APPLICATION_JSON_VALUE,
                ("{\"competitionId\":" + comp + ",\"grantedRole\":\"学生\"}")
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8));
        MockMultipartFile file = new MockMultipartFile("file", "模板样本.png", MediaType.IMAGE_PNG_VALUE, PNG);
        JsonNode created = call(multipart(TEMPLATE_BASE + "/create").file(file).file(data)
                .headers(headers(adminToken)));
        assertThat(created.path("code").asInt()).isZero();
        long templateId = created.at("/data").asLong();

        long start = System.currentTimeMillis();
        JsonNode tested = call(post(TEMPLATE_BASE + "/test").headers(headers(adminToken))
                .param("id", String.valueOf(templateId)));
        long elapsed = System.currentTimeMillis() - start;

        // 传输层异常(连接拒绝)按契约映射 4003,与 v2 一致;不能是未捕获异常 500,
        // 更不能是领域错误码(那会丢掉"这是 AI 依赖不可达"这个语义)
        assertThat(tested.path("code").asInt()).isEqualTo(4003);
        assertThat(tested.path("code").asInt()).as("不能是未捕获异常 500").isNotEqualTo(500);
        assertThat(elapsed).as("不可达应快速返回").isLessThan(15_000L);
    }

    @Test
    void aiWorkerClientIsLazySoAppStartsWithoutWorker() {
        // 应用已在 Worker 不可达的情况下成功启动(本类能跑起来本身就是证据);
        // 再直接断言客户端 bean 存在且未抛错,覆盖"懒连接"这一设计意图
        assertThat(aiReviewService).isNotNull();
    }

}
