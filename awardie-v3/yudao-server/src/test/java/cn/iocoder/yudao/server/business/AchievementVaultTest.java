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
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 批6 成果库集成测试:五类列表 + 行编辑 + 行删除(含引用拒绝)。
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        // 独立 Redis 库(默认 0 是 dev 服务在用):权限缓存键不含库标识,共用会互相污染
        "spring.data.redis.database=1"
})
@AutoConfigureMockMvc
class AchievementVaultTest {

    private static final String BASE = "/admin-api/business/vault";
    private static final long TENANT_ID = 1L;
    private static final long ADMIN_ROLE = 100L; // awardie_admin(成果库是 admin 主责域)
    private static final String ADMIN = "vaultadm1";
    private static final String STUDENT = "vaultstu1";
    private static final String PASSWORD = "Vault@Test#26";
    private static final List<String> VAULT_PERMISSIONS = List.of(
            "business:vault:query", "business:vault:update", "business:vault:delete");
    /** 学生无成果库权限(成果库是 admin 主责域),用于验证越权面 */
    private static final List<String> STUDENT_PERMISSIONS = List.of("business:pending-achievement:query");

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

    private final ObjectMapper om = new ObjectMapper();
    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();
    private String adminToken;
    private String studentToken;

    @BeforeEach
    void setUp() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedUser(ADMIN, ADMIN_ROLE, VAULT_PERMISSIONS);
        seedUser(STUDENT, 102L, STUDENT_PERMISSIONS);
        adminToken = login(ADMIN);
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
        for (String t : List.of("awardie_awards", "awardie_award_student_winners", "awardie_patents",
                "awardie_software_copyrights", "awardie_other_files", "awardie_innovation_projects",
                "awardie_innovation_project_students")) {
            jdbcTemplate.execute("DELETE FROM " + t);
        }
    }

    private void seedUser(String username, long roleId, List<String> permissions) {
        AdminUserDO user = new AdminUserDO();
        user.setUsername(username);
        user.setPassword(bcrypt.encode(PASSWORD));
        user.setNickname("成果库测试-" + username);
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
        assertThat(menuIds).as("成果库权限点缺失——请先执行 awardie-business-menus.sql + awardie-user-domain.sql")
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

    private long seedAward(String name) {
        jdbcTemplate.update("INSERT INTO awardie_awards (competition_name_in_file, award_level, winner_name,"
                + " year, tenant_id) VALUES (?, ?, ?, ?, 1)", name, "一等奖", "测试获奖人", 2024);
        return jdbcTemplate.queryForObject("SELECT id FROM awardie_awards WHERE competition_name_in_file = ?"
                + " ORDER BY id DESC LIMIT 1", Long.class, name);
    }

    @Test
    void listFiveTypes() throws Exception {
        seedAward("列表测试获奖");
        jdbcTemplate.update("INSERT INTO awardie_patents (patent_name, patent_type, tenant_id)"
                + " VALUES (?, ?, 1)", "列表测试专利", "发明专利");
        jdbcTemplate.update("INSERT INTO awardie_software_copyrights (software_name, registration_number, tenant_id)"
                + " VALUES (?, ?, 1)", "列表测试软著", "2024SR99999");
        jdbcTemplate.update("INSERT INTO awardie_other_files (file_name, file_path, tenant_id)"
                + " VALUES (?, ?, 1)", "列表测试其他", "list-other.pdf");
        jdbcTemplate.update("INSERT INTO awardie_innovation_projects (project_name, project_type, status, tenant_id)"
                + " VALUES (?, ?, ?, 1)", "列表测试大创", "省级", "进行中");

        for (String type : List.of("award", "patent", "software", "other", "innovation")) {
            JsonNode body = call(get(BASE + "/" + type).headers(headers(adminToken)));
            assertThat(body.path("code").asInt()).as("type=%s 列表", type).isEqualTo(0);
            assertThat(body.at("/data/total").asInt()).as("type=%s 应有 1 行", type).isEqualTo(1);
        }
    }

    @Test
    void listWithKeywordFilter() throws Exception {
        seedAward("关键词命中获奖");
        seedAward("另一条获奖");
        JsonNode hit = call(get(BASE + "/award").headers(headers(adminToken)).param("keyword", "命中"));
        assertThat(hit.at("/data/total").asInt()).isEqualTo(1);
        JsonNode miss = call(get(BASE + "/award").headers(headers(adminToken)).param("keyword", "不存在zzz"));
        assertThat(miss.at("/data/total").asInt()).isZero();
    }

    @Test
    void invalidTypeRejected() throws Exception {
        JsonNode body = call(get(BASE + "/not-a-type").headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isEqualTo(1003005000);
    }

    @Test
    void updateRowWithinEditableColumns() throws Exception {
        long id = seedAward("编辑测试获奖");
        JsonNode ok = call(post(BASE + "/award/" + id + "/update").headers(headers(adminToken))
                .content("{\"award_level\":\"特等奖\",\"winner_name\":\"新获奖人\",\"year\":2025}"));
        assertThat(ok.path("code").asInt()).isEqualTo(0);
        String level = jdbcTemplate.queryForObject(
                "SELECT award_level FROM awardie_awards WHERE id = ?", String.class, id);
        assertThat(level).isEqualTo("特等奖");

        // 非白名单列被忽略(不报错也不改)
        call(post(BASE + "/award/" + id + "/update").headers(headers(adminToken))
                .content("{\"image_hash\":\"HACKED\"}"));
        String hash = jdbcTemplate.queryForObject(
                "SELECT image_hash FROM awardie_awards WHERE id = ?", String.class, id);
        assertThat(hash).as("非白名单列不应被更新").isNull();
    }

    @Test
    void updateMissingRecordReportsNotExists() throws Exception {
        JsonNode body = call(post(BASE + "/award/99999999/update").headers(headers(adminToken))
                .content("{\"award_level\":\"特等奖\"}"));
        assertThat(body.path("code").asInt()).isEqualTo(1003005001);
    }

    @Test
    void deleteRowAndReferenceGuard() throws Exception {
        long id = seedAward("删除测试获奖");
        assertThat(call(delete(BASE + "/award/" + id).headers(headers(adminToken)))
                .path("code").asInt()).isEqualTo(0);
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM awardie_awards WHERE id = ?",
                Long.class, id)).isZero();

        // 有学生关联引用时拒绝
        long referenced = seedAward("被引用获奖");
        jdbcTemplate.update("INSERT INTO awardie_award_student_winners (award_id, student_id, tenant_id)"
                + " VALUES (?, ?, 1)", referenced, 900001L);
        JsonNode blocked = call(delete(BASE + "/award/" + referenced).headers(headers(adminToken)));
        assertThat(blocked.path("code").asInt()).isEqualTo(1003005002);
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM awardie_awards WHERE id = ?",
                Long.class, referenced)).isEqualTo(1);
    }

    @Test
    void deleteInnovationGuardedByProjectStudents() throws Exception {
        jdbcTemplate.update("INSERT INTO awardie_innovation_projects (project_name, status, tenant_id)"
                + " VALUES (?, ?, 1)", "被引用大创", "进行中");
        long pid = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_innovation_projects WHERE project_name = ?", Long.class, "被引用大创");
        jdbcTemplate.update("INSERT INTO awardie_innovation_project_students (project_id, student_id, tenant_id)"
                + " VALUES (?, ?, 1)", pid, 900002L);
        JsonNode blocked = call(delete(BASE + "/innovation/" + pid).headers(headers(adminToken)));
        assertThat(blocked.path("code").asInt()).isEqualTo(1003005002);
    }

    @Test
    void studentHasNoVaultAccess() throws Exception {
        // 成果库是 admin 主责域:学生三个端点全 403(权限面隔离)
        long id = seedAward("学生不可改");
        assertThat(call(get(BASE + "/award").headers(headers(studentToken))).path("code").asInt()).isEqualTo(403);
        assertThat(call(post(BASE + "/award/" + id + "/update").headers(headers(studentToken))
                .content("{\"award_level\":\"特等奖\"}")).path("code").asInt()).isEqualTo(403);
        assertThat(call(delete(BASE + "/award/" + id).headers(headers(studentToken)))
                .path("code").asInt()).isEqualTo(403);
    }
}
