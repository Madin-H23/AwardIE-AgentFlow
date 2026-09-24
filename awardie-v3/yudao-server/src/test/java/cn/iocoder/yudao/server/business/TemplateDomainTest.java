package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
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
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

/**
 * 批7 模板域 + AI 抽取集成测试:CRUD + 唯一性 + 编辑白名单 + 删除 + 样本图 + AI 三端点 +
 * 越权面 + 批3 预留的竞赛引用保护首次实证。
 *
 * <p>播种纪律(批6 立):只改用户→角色绑定(assignUserRole),菜单归属由 SQL 负责;
 * 独立 Redis 库 1 与 dev 服务隔离;断言键名即契约。
 *
 * <p>AI 端点不依赖真 Worker:fake 模式验桩契约;grpc 降级用不可达端口验 4003 + 快速返回。
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        "spring.data.redis.database=1",
        "awardie.file.root=target/test-files/template"
})
@AutoConfigureMockMvc
class TemplateDomainTest {

    private static final String BASE = "/admin-api/business/templates";
    private static final long TENANT_ID = 1L;
    private static final long ADMIN_ROLE = 100L;
    private static final String ADMIN = "tpladm1";
    private static final String TEACHER = "tpltea1";
    private static final String STUDENT = "tplstu1";
    private static final String PASSWORD = "Tpl@Test#26";
    private static final List<String> ADMIN_PERMISSIONS = List.of(
            "business:templates:query", "business:templates:create",
            "business:templates:update", "business:templates:delete");
    /** 教师/学生无模板权限(模板域是 admin 专属,v2 同) */
    private static final List<String> STUDENT_PERMISSIONS = List.of("business:pending-achievement:query");

    /** 真实 PNG 魔术字节(不用默认假文件,避免"因默认值巧合通过") */
    private static final byte[] PNG = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x11, 0x22};

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
    private cn.iocoder.yudao.module.business.service.template.TemplateService templateService;
    @Autowired
    private org.springframework.transaction.support.TransactionTemplate transactionTemplate;

    private final ObjectMapper om = new ObjectMapper();
    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();
    private String adminToken;
    private String teacherToken;
    private String studentToken;

    @BeforeEach
    void setUp() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedUser(ADMIN, ADMIN_ROLE, ADMIN_PERMISSIONS);
        seedUser(TEACHER, 101L, STUDENT_PERMISSIONS);
        seedUser(STUDENT, 102L, STUDENT_PERMISSIONS);
        adminToken = login(ADMIN);
        teacherToken = login(TEACHER);
        studentToken = login(STUDENT);
        TenantContextHolder.setTenantId(TENANT_ID);
        cleanTables();
    }

    @AfterEach
    void clean() {
        cleanTables();
        TenantContextHolder.clear();
    }

    private void cleanTables() {
        // 共享库:必须连待审表一起清。本测试会往待审表插"共享引用行"验引用保护,
        // 残留会让后续用例的样本图被判为"仍被引用"而正确地不删 —— 代码没错但测试互相污染。
        jdbcTemplate.update("DELETE FROM awardie_pending_achievements");
        jdbcTemplate.update("DELETE FROM awardie_templates");
        jdbcTemplate.update("DELETE FROM awardie_competitions");
        cleanTestFiles();
    }

    private void cleanTestFiles() {
        Path root = Path.of("target/test-files/template").toAbsolutePath();
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
        user.setNickname("模板测试-" + username);
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
        assertThat(menuIds).as("模板权限点缺失——请先执行 awardie-business-menus.sql + awardie-user-domain.sql")
                .hasSize(permissions.size());
        // 只改用户→角色绑定;菜单归属由 SQL 负责(assignRoleMenu 是全量替换,会抹掉他人授权)
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

    private MockMultipartFile pngFile() {
        return new MockMultipartFile("file", "样本图.png", MediaType.IMAGE_PNG_VALUE, PNG);
    }

    private String createDataJson(long competitionId, String role) {
        return "{\"competitionId\":" + competitionId + ",\"grantedRole\":\"" + role + "\"}";
    }

    private cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateCreateReqVO createReqVO(
            long competitionId, String role) {
        cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateCreateReqVO req =
                new cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateCreateReqVO();
        req.setCompetitionId(competitionId);
        req.setGrantedRole(role);
        req.setLanguage("zh");
        req.setNeedTranslate(false);
        return req;
    }

    /** 存储根下的实际文件清单(用于断言孤儿文件是否被回收) */
    private List<Path> testFiles() throws IOException {
        Path root = Path.of("target/test-files/template").toAbsolutePath();
        if (!Files.exists(root)) {
            return List.of();
        }
        try (Stream<Path> walk = Files.walk(root)) {
            return walk.filter(Files::isRegularFile).toList();
        }
    }

    private long seedCompetition(String name) {
        jdbcTemplate.update("INSERT INTO awardie_competitions (competition_name, tenant_id) VALUES (?, 1)", name);
        return jdbcTemplate.queryForObject("SELECT id FROM awardie_competitions WHERE competition_name = ?"
                + " ORDER BY id DESC LIMIT 1", Long.class, name);
    }

    private long createTemplate(long competitionId, String role) throws Exception {
        MockMultipartFile data = new MockMultipartFile("data", "", MediaType.APPLICATION_JSON_VALUE,
                createDataJson(competitionId, role).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        JsonNode body = call(multipart(BASE + "/create").file(pngFile()).file(data)
                .headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).as("创建应成功: %s", body.path("msg").asText()).isZero();
        return body.at("/data").asLong();
    }

    // ========== 列表与过滤 ==========

    @Test
    void listWithCompetitionAndRoleFilters() throws Exception {
        long compA = seedCompetition("列表竞赛甲");
        long compB = seedCompetition("列表竞赛乙");
        createTemplate(compA, "学生");
        createTemplate(compA, "教师");
        createTemplate(compB, "学生");

        JsonNode all = call(get(BASE + "/page").headers(headers(adminToken)));
        assertThat(all.path("code").asInt()).isZero();
        assertThat(all.at("/data/total").asInt()).isEqualTo(3);

        JsonNode byComp = call(get(BASE + "/page").headers(headers(adminToken))
                .param("competitionId", String.valueOf(compA)));
        assertThat(byComp.at("/data/total").asInt()).isEqualTo(2);

        JsonNode byRole = call(get(BASE + "/page").headers(headers(adminToken))
                .param("grantedRole", "学生"));
        assertThat(byRole.at("/data/total").asInt()).isEqualTo(2);

        JsonNode both = call(get(BASE + "/page").headers(headers(adminToken))
                .param("competitionId", String.valueOf(compA)).param("grantedRole", "学生"));
        assertThat(both.at("/data/total").asInt()).isEqualTo(1);
    }

    @Test
    void listEmptyWhenNoTemplate() throws Exception {
        JsonNode body = call(get(BASE + "/page").headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isZero();
        assertThat(body.at("/data/total").asInt()).isZero();
    }

    // ========== 创建 ==========

    @Test
    void createPersistsTemplateAndSampleImage() throws Exception {
        long comp = seedCompetition("创建竞赛");
        long id = createTemplate(comp, "学生");

        // 库行:tenant_id + granted_role 独立列
        Map<String, Object> row = jdbcTemplate.queryForMap(
                "SELECT competition_id, granted_role, template_type, sample_image_path, tenant_id"
                        + " FROM awardie_templates WHERE id = ?", id);
        assertThat(row.get("competition_id")).isEqualTo(comp);
        assertThat(row.get("granted_role")).isEqualTo("学生");
        assertThat(row.get("template_type")).isEqualTo("AWARD");
        assertThat(row.get("tenant_id")).isEqualTo(TENANT_ID);
        assertThat((String) row.get("sample_image_path")).isNotBlank();

        // 样本图真的落盘了
        Path stored = Path.of("target/test-files/template").toAbsolutePath()
                .resolve((String) row.get("sample_image_path"));
        assertThat(Files.exists(stored)).as("样本图应落盘").isTrue();
    }

    @Test
    void createRejectsDuplicateRoleForSameCompetition() throws Exception {
        long comp = seedCompetition("重复竞赛");
        createTemplate(comp, "学生");

        MockMultipartFile data = new MockMultipartFile("data", "", MediaType.APPLICATION_JSON_VALUE,
                createDataJson(comp, "学生").getBytes(java.nio.charset.StandardCharsets.UTF_8));
        JsonNode body = call(multipart(BASE + "/create").file(pngFile()).file(data)
                .headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isEqualTo(1003006001);
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM awardie_templates", Long.class))
                .isEqualTo(1L);
    }

    @Test
    void createRejectsInvalidRole() throws Exception {
        long comp = seedCompetition("角色竞赛");
        MockMultipartFile data = new MockMultipartFile("data", "", MediaType.APPLICATION_JSON_VALUE,
                createDataJson(comp, "校友").getBytes(java.nio.charset.StandardCharsets.UTF_8));
        JsonNode body = call(multipart(BASE + "/create").file(pngFile()).file(data)
                .headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isEqualTo(1003006002);
    }

    @Test
    void createRejectsUnknownCompetition() throws Exception {
        MockMultipartFile data = new MockMultipartFile("data", "", MediaType.APPLICATION_JSON_VALUE,
                createDataJson(99999999L, "学生").getBytes(java.nio.charset.StandardCharsets.UTF_8));
        JsonNode body = call(multipart(BASE + "/create").file(pngFile()).file(data)
                .headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isEqualTo(1003001000);
    }

    @Test
    void createRejectsNonImageContent() throws Exception {
        long comp = seedCompetition("魔术字节竞赛");
        MockMultipartFile fake = new MockMultipartFile("file", "fake.png", MediaType.IMAGE_PNG_VALUE,
                "这不是图片".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        MockMultipartFile data = new MockMultipartFile("data", "", MediaType.APPLICATION_JSON_VALUE,
                createDataJson(comp, "学生").getBytes(java.nio.charset.StandardCharsets.UTF_8));
        JsonNode body = call(multipart(BASE + "/create").file(fake).file(data)
                .headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isEqualTo(1003003002);
    }

    // ========== 详情 ==========

    @Test
    void detailReturnsStructuredContract() throws Exception {
        long comp = seedCompetition("详情竞赛");
        long id = createTemplate(comp, "学生");

        JsonNode body = call(get(BASE + "/get").headers(headers(adminToken)).param("id", String.valueOf(id)));
        assertThat(body.path("code").asInt()).isZero();
        JsonNode data = body.at("/data");
        // 键名即契约
        assertThat(data.has("id")).isTrue();
        assertThat(data.at("/competitionName").asText()).isEqualTo("详情竞赛");
        assertThat(data.at("/grantedRole").asText()).isEqualTo("学生");
        // JSON 字段是结构化对象/数组,不是 JSON 字符串
        assertThat(data.at("/keywords").isArray()).as("keywords 应为数组").isTrue();
        assertThat(data.at("/sampleExtracted").isObject()).as("sampleExtracted 应为对象").isTrue();
        assertThat(data.at("/hasImage").asBoolean()).isTrue();
    }

    @Test
    void detailMissingTemplateReportsNotExists() throws Exception {
        JsonNode body = call(get(BASE + "/get").headers(headers(adminToken)).param("id", "99999999"));
        assertThat(body.path("code").asInt()).isEqualTo(1003006000);
    }

    // ========== 编辑 ==========

    @Test
    void updateChangesRuleFieldsButNotIdentityFields() throws Exception {
        long comp = seedCompetition("编辑竞赛");
        long id = createTemplate(comp, "学生");

        String payload = "{\"minLength\":12,\"maxLength\":300,\"language\":\"en\","
                + "\"keywords\":[\"新关键词A\",\"新关键词B\"],\"sampleText\":\"新样本文本\"}";
        JsonNode body = call(put(BASE + "/update").headers(headers(adminToken)).param("id", String.valueOf(id))
                .content(payload));
        assertThat(body.path("code").asInt()).isZero();

        Map<String, Object> row = jdbcTemplate.queryForMap(
                "SELECT min_length, max_length, language, keywords, granted_role, competition_id"
                        + " FROM awardie_templates WHERE id = ?", id);
        assertThat(row.get("min_length")).isEqualTo(12);
        assertThat(row.get("max_length")).isEqualTo(300);
        assertThat(row.get("language")).isEqualTo("en");
        assertThat((String) row.get("keywords")).contains("新关键词A");
        // 身份字段不受编辑影响
        assertThat(row.get("granted_role")).isEqualTo("学生");
        assertThat(row.get("competition_id")).isEqualTo(comp);
    }

    @Test
    void updateMissingTemplateReportsNotExists() throws Exception {
        JsonNode body = call(put(BASE + "/update").headers(headers(adminToken)).param("id", "99999999")
                .content("{\"minLength\":1}"));
        assertThat(body.path("code").asInt()).isEqualTo(1003006000);
    }

    // ========== 删除 ==========

    @Test
    void deleteRemovesFromListAndReclaimsSampleImage() throws Exception {
        long comp = seedCompetition("删除竞赛");
        long id = createTemplate(comp, "学生");
        String samplePath = jdbcTemplate.queryForObject(
                "SELECT sample_image_path FROM awardie_templates WHERE id = ?", String.class, id);
        Path stored = Path.of("target/test-files/template").toAbsolutePath().resolve(samplePath);
        assertThat(Files.exists(stored)).isTrue();

        JsonNode body = call(delete(BASE + "/delete").headers(headers(adminToken)).param("id", String.valueOf(id)));
        assertThat(body.path("code").asInt()).isZero();

        // 逻辑删除:行仍在库但 deleted=1
        assertThat(jdbcTemplate.queryForObject("SELECT deleted FROM awardie_templates WHERE id = ?",
                String.class, id)).isEqualTo("1");
        // 列表不再出现
        assertThat(call(get(BASE + "/page").headers(headers(adminToken))).at("/data/total").asInt()).isZero();
        // 样本图被回收
        assertThat(Files.exists(stored)).as("样本图应被回收").isFalse();
    }

    @Test
    void deleteKeepsSharedSampleImageStillReferencedByOtherRecord() throws Exception {
        long comp = seedCompetition("共享图竞赛");
        long id = createTemplate(comp, "学生");
        String samplePath = jdbcTemplate.queryForObject(
                "SELECT sample_image_path FROM awardie_templates WHERE id = ?", String.class, id);
        Path stored = Path.of("target/test-files/template").toAbsolutePath().resolve(samplePath);
        // 另一张表引用同一路径(内容寻址下完全可能:同图既是模板样本图又是待审文件)
        jdbcTemplate.update("INSERT INTO awardie_pending_achievements (achievement_type, achievement_data,"
                + " submitter_type, submitter_id, submit_time, status, file_path, file_hash, version, tenant_id)"
                + " VALUES ('award', '{}', 'student', 900001, NOW(), 'pending', ?, 'sharedhash', 1, 1)",
                samplePath);

        JsonNode body = call(delete(BASE + "/delete").headers(headers(adminToken)).param("id", String.valueOf(id)));
        // 删除接口本身要成功(否则"文件还在"可以靠删除失败蒙混过关)
        assertThat(body.path("code").asInt()).as("删除应成功").isZero();
        assertThat(jdbcTemplate.queryForObject("SELECT deleted FROM awardie_templates WHERE id = ?",
                String.class, id)).as("模板应已逻辑删除").isEqualTo("1");
        // 仍被待审引用 → 文件必须保留
        assertThat(Files.exists(stored)).as("被其他记录引用的文件不得误删").isTrue();
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM awardie_pending_achievements"
                + " WHERE file_path = ?", Long.class, samplePath)).as("引用行仍在").isEqualTo(1L);
    }

    @Test
    void createReclaimsSampleImageWhenInsertFails() throws Exception {
        // 事务在落盘之后回滚 → 样本图必须被回收,不得留孤儿
        long comp = seedCompetition("回滚竞赛");
        transactionTemplate.executeWithoutResult(status -> {
            try {
                templateService.createTemplate(createReqVO(comp, "学生"), "回滚样本.png", PNG);
            } catch (IOException e) {
                throw new IllegalStateException(e);
            }
            status.setRollbackOnly();
        });
        assertThat(testFiles()).as("回滚后样本图应被回收").isEmpty();
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM awardie_templates", Long.class))
                .as("回滚后不应有模板行").isZero();
    }

    @Test
    void createRejectsNegativeOrReversedLengths() throws Exception {
        long comp = seedCompetition("长度竞赛");
        for (String payload : List.of(
                "{\"competitionId\":" + comp + ",\"grantedRole\":\"学生\",\"minLength\":-1}",
                "{\"competitionId\":" + comp + ",\"grantedRole\":\"学生\",\"maxLength\":-5}",
                "{\"competitionId\":" + comp + ",\"grantedRole\":\"学生\",\"minLength\":100,\"maxLength\":10}")) {
            MockMultipartFile data = new MockMultipartFile("data", "", MediaType.APPLICATION_JSON_VALUE,
                    payload.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            JsonNode body = call(multipart(BASE + "/create").file(pngFile()).file(data)
                    .headers(headers(adminToken)));
            assertThat(body.path("code").asInt()).as("非法长度区间应被拒: %s", payload).isEqualTo(1003006004);
        }
    }

    @Test
    void updateStripsReservedRoleKeyFromDefaultFields() throws Exception {
        long comp = seedCompetition("保留键竞赛");
        long id = createTemplate(comp, "学生");
        // 试图通过 defaultFields 塞入 granted_role(独立列是唯一事实源)
        JsonNode body = call(put(BASE + "/update").headers(headers(adminToken)).param("id", String.valueOf(id))
                .content("{\"defaultFields\":{\"granted_role\":\"教师\",\"issuer\":\"某单位\"}}"));
        assertThat(body.path("code").asInt()).isZero();
        String defaultFields = jdbcTemplate.queryForObject(
                "SELECT default_fields FROM awardie_templates WHERE id = ?", String.class, id);
        assertThat(defaultFields).as("保留键应被剔除").doesNotContain("granted_role");
        assertThat(defaultFields).as("其他键应保留").contains("issuer");
        // 独立列不受影响
        assertThat(jdbcTemplate.queryForObject("SELECT granted_role FROM awardie_templates WHERE id = ?",
                String.class, id)).isEqualTo("学生");
    }

    @Test
    void deleteMissingTemplateReportsNotExists() throws Exception {
        JsonNode body = call(delete(BASE + "/delete").headers(headers(adminToken)).param("id", "99999999"));
        assertThat(body.path("code").asInt()).isEqualTo(1003006000);
    }

    @Test
    void competitionWithTemplateCannotBeDeleted() throws Exception {
        // 批3 预留的引用保护首次实证:awardie_templates 表一建成即自动生效
        long comp = seedCompetition("被引用竞赛");
        createTemplate(comp, "学生");
        JsonNode body = call(delete("/admin-api/business/competitions/delete").headers(headers(adminToken))
                .param("id", String.valueOf(comp)));
        assertThat(body.path("code").asInt()).as("有模板引用的竞赛不应被删除").isEqualTo(1003001002);
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM awardie_competitions WHERE id = ?",
                Long.class, comp)).isEqualTo(1L);
    }

    // ========== 样本图回显 ==========

    @Test
    void sampleImageRoundTrip() throws Exception {
        long comp = seedCompetition("回显竞赛");
        long id = createTemplate(comp, "学生");
        MvcResult result = mockMvc.perform(get(BASE + "/image").headers(headers(adminToken))
                .param("id", String.valueOf(id))).andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        assertThat(result.getResponse().getStatus()).isEqualTo(200);
        assertThat(result.getResponse().getContentType()).contains("image/png");
        assertThat(result.getResponse().getContentAsByteArray()).isEqualTo(PNG);
    }

    @Test
    void sampleImageLostFileReportsError() throws Exception {
        long comp = seedCompetition("丢图竞赛");
        long id = createTemplate(comp, "学生");
        // 物理文件被外部删掉(存量死引用)
        cleanTestFiles();
        JsonNode body = call(get(BASE + "/image").headers(headers(adminToken)).param("id", String.valueOf(id)));
        assertThat(body.path("code").asInt()).isEqualTo(1003006006);
    }

    // ========== AI 三端点(fake 模式) ==========

    @Test
    void aiEndpointsFakeModeReturnStableStub() throws Exception {
        long comp = seedCompetition("AI竞赛");
        long id = createTemplate(comp, "学生");

        JsonNode test = call(post(BASE + "/test").headers(headers(adminToken)).param("id", String.valueOf(id)));
        assertThat(test.path("code").asInt()).isZero();
        assertThat(test.at("/data/mode").asText()).isEqualTo("fake");
        assertThat(test.at("/data/disclaimer").asText()).contains("辅助参考");

        MockMultipartFile file = new MockMultipartFile("file", "s.png", MediaType.IMAGE_PNG_VALUE, PNG);
        JsonNode extract = call(multipart(BASE + "/extract-for-create").file(file)
                .headers(headers(adminToken)));
        assertThat(extract.path("code").asInt()).isZero();
        assertThat(extract.at("/data/mode").asText()).isEqualTo("fake");

        JsonNode prompt = call(post(BASE + "/generate-prompt").headers(headers(adminToken))
                .param("ruleJson", "{\"keywords\":[\"奖状\"]}").param("sampleText", "样例"));
        assertThat(prompt.path("code").asInt()).isZero();
        assertThat(prompt.at("/data/mode").asText()).isEqualTo("fake");
        assertThat(prompt.at("/data/prompt").asText()).contains("样例");
    }

    @Test
    void generatePromptRejectsMalformedRuleJson() throws Exception {
        JsonNode body = call(post(BASE + "/generate-prompt").headers(headers(adminToken))
                .param("ruleJson", "{broken").param("sampleText", "x"));
        assertThat(body.path("code").asInt()).isEqualTo(1003006003);
    }

    @Test
    void testWithoutSampleImageReportsError() throws Exception {
        // 直接插一条无样本图的模板(存量脏数据形态)
        long comp = seedCompetition("无图竞赛");
        jdbcTemplate.update("INSERT INTO awardie_templates (template_type, competition_id, granted_role,"
                + " min_length, max_length, keywords, language, need_translate, tenant_id)"
                + " VALUES ('AWARD', ?, '学生', 0, 0, '[]', 'zh', b'0', 1)", comp);
        long id = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_templates WHERE competition_id = ? ORDER BY id DESC LIMIT 1",
                Long.class, comp);
        JsonNode body = call(post(BASE + "/test").headers(headers(adminToken)).param("id", String.valueOf(id)));
        assertThat(body.path("code").asInt()).isEqualTo(1003006005);
    }

    // ========== 权限面 ==========

    @Test
    void teacherAndStudentHaveNoTemplateAccess() throws Exception {
        long comp = seedCompetition("越权竞赛");
        long id = createTemplate(comp, "学生");
        for (String token : List.of(teacherToken, studentToken)) {
            // 全部九个端点(6 CRUD + 样本图 + 3 AI)都必须 403
            assertThat(call(get(BASE + "/page").headers(headers(token))).path("code").asInt()).isEqualTo(403);
            assertThat(call(get(BASE + "/get").headers(headers(token)).param("id", String.valueOf(id)))
                    .path("code").asInt()).isEqualTo(403);
            MockMultipartFile createData = new MockMultipartFile("data", "", MediaType.APPLICATION_JSON_VALUE,
                    createDataJson(comp, "教师").getBytes(java.nio.charset.StandardCharsets.UTF_8));
            assertThat(call(multipart(BASE + "/create").file(pngFile()).file(createData)
                    .headers(headers(token))).path("code").asInt()).isEqualTo(403);
            assertThat(call(put(BASE + "/update").headers(headers(token)).param("id", String.valueOf(id))
                    .content("{\"minLength\":1}")).path("code").asInt()).isEqualTo(403);
            assertThat(call(delete(BASE + "/delete").headers(headers(token)).param("id", String.valueOf(id)))
                    .path("code").asInt()).isEqualTo(403);
            assertThat(call(get(BASE + "/image").headers(headers(token)).param("id", String.valueOf(id)))
                    .path("code").asInt()).isEqualTo(403);
            assertThat(call(post(BASE + "/test").headers(headers(token)).param("id", String.valueOf(id)))
                    .path("code").asInt()).isEqualTo(403);
            assertThat(call(multipart(BASE + "/extract-for-create").file(pngFile())
                    .headers(headers(token))).path("code").asInt()).isEqualTo(403);
            assertThat(call(post(BASE + "/generate-prompt").headers(headers(token))
                    .param("sampleText", "x")).path("code").asInt()).isEqualTo(403);
        }
    }

}
