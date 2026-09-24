package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.dal.dataobject.laboratory.LaboratoriesDO;
import cn.iocoder.yudao.module.business.dal.mysql.laboratory.LaboratoriesMapper;
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
 * 批4 实验室关联域测试:详情聚合 + 下载列表 + 四张关联表进删除引用检查(批3 挂账衔接项)。
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
class LaboratoryAssetsTest {

    private static final String BASE = "/admin-api/business/laboratories";
    private static final long TENANT_ID = 1L;
    private static final String TEST_USERNAME = "labassetsadmin";
    /** 芋道登录校验密码长度 4-16 位 */
    private static final String TEST_PASSWORD = "LabAst@Test#26";
    private static final List<String> LAB_PERMISSIONS = List.of(
            "business:laboratories:query", "business:laboratories:delete");

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private LaboratoriesMapper labMapper;
    @Autowired
    private AdminUserMapper userMapper;
    @Autowired
    private MenuMapper menuMapper;
    @Autowired
    private PermissionService permissionService;

    private final ObjectMapper om = new ObjectMapper();
    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();
    private String token;

    @BeforeEach
    void setUp() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedUser();
        token = login();
        TenantContextHolder.setTenantId(TENANT_ID);
        labMapper.delete(null);
        clearAssets();
    }

    @AfterEach
    void clean() {
        clearAssets();
        TenantContextHolder.clear();
    }

    private void clearAssets() {
        for (String table : List.of("awardie_laboratory_downloads", "awardie_laboratory_images",
                "awardie_laboratory_instructors", "awardie_laboratory_students")) {
            jdbcTemplate.execute("DELETE FROM " + table);
        }
    }

    private void seedUser() {
        AdminUserDO user = new AdminUserDO();
        user.setUsername(TEST_USERNAME);
        user.setPassword(bcrypt.encode(TEST_PASSWORD));
        user.setNickname("实验室资产测试");
        user.setStatus(0);
        user.setTenantId(TENANT_ID);
        AdminUserDO existing = userMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getUsername, TEST_USERNAME));
        Long userId;
        if (existing == null) {
            userMapper.insert(user);
            userId = user.getId();
        } else {
            // 每次播种都重置口令:否则上一轮遗留的用户带着旧口令,登录必然失败
            userId = existing.getId();
            existing.setPassword(user.getPassword());
            userMapper.updateById(existing);
        }
        Set<Long> menuIds = LAB_PERMISSIONS.stream()
                .map(menuMapper::selectListByPermission)
                .flatMap(List::stream)
                .map(MenuDO::getId)
                .collect(Collectors.toSet());
        assertThat(menuIds).as("实验室权限点缺失——请先执行 awardie-business-menus.sql + awardie-user-domain.sql")
                .hasSize(LAB_PERMISSIONS.size());
        permissionService.assignUserRole(userId, Set.of(1L));
    }

    private String login() throws Exception {
        MvcResult result = mockMvc.perform(post("/admin-api/system/auth/login")
                        .contentType(MediaType.APPLICATION_JSON).header("tenant-id", "1")
                        .content("{\"username\":\"" + TEST_USERNAME + "\",\"password\":\"" + TEST_PASSWORD + "\"}"))
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

    private HttpHeaders authHeaders() {
        HttpHeaders h = new HttpHeaders();
        h.setBearerAuth(token);
        h.set("tenant-id", "1");
        return h;
    }

    private LaboratoriesDO newLab(String name) {
        LaboratoriesDO row = new LaboratoriesDO();
        row.setName(name);
        labMapper.insert(row);
        return row;
    }

    @Test
    void detailAggregatesInstructorsStudentsAndDownloadCount() throws Exception {
        LaboratoriesDO lab = newLab("资产聚合实验室");
        jdbcTemplate.update("INSERT INTO awardie_laboratory_instructors (laboratory_id, teacher_id, tenant_id)"
                + " VALUES (?, ?, 1)", lab.getId(), 900001L);
        jdbcTemplate.update("INSERT INTO awardie_laboratory_students (laboratory_id, student_id, tenant_id)"
                + " VALUES (?, ?, 1)", lab.getId(), 900002L);
        // 关联的是不存在的用户 id:v2 同构(详情端点按 id join,join 不到就不出现在列表)
        jdbcTemplate.update("INSERT INTO awardie_laboratory_downloads"
                + " (laboratory_id, file_path, file_title, display_order, tenant_id) VALUES (?, ?, ?, 1, 1)",
                lab.getId(), "abc.pdf", "手册");

        JsonNode detail = call(get(BASE + "/detail").headers(authHeaders()).param("id", String.valueOf(lab.getId())));
        assertThat(detail.path("code").asInt()).isEqualTo(0);
        assertThat(detail.at("/data/name").asText()).isEqualTo("资产聚合实验室");
        assertThat(detail.at("/data/downloadCount").asInt()).isEqualTo(1);
        // awardie_awards 批6 才建,当前恒 0(不静默假装有数据)
        assertThat(detail.at("/data/awardCount").asInt()).isEqualTo(0);
        assertThat(detail.at("/data/instructors").isArray()).isTrue();
        assertThat(detail.at("/data/students").isArray()).isTrue();
    }

    @Test
    void detailOfMissingLabReportsNotExists() throws Exception {
        JsonNode detail = call(get(BASE + "/detail").headers(authHeaders()).param("id", "99999999"));
        assertThat(detail.path("code").asInt()).isEqualTo(1003000000);
    }

    @Test
    void downloadsOrderedByDisplayOrderThenIdDesc() throws Exception {
        LaboratoriesDO lab = newLab("下载排序实验室");
        jdbcTemplate.update("INSERT INTO awardie_laboratory_downloads"
                + " (laboratory_id, file_path, file_title, display_order, tenant_id) VALUES (?, ?, ?, 2, 1)",
                lab.getId(), "a.pdf", "第二");
        jdbcTemplate.update("INSERT INTO awardie_laboratory_downloads"
                + " (laboratory_id, file_path, file_title, display_order, tenant_id) VALUES (?, ?, ?, 1, 1)",
                lab.getId(), "b.pdf", "第一");
        JsonNode list = call(get(BASE + "/downloads").headers(authHeaders()).param("id", String.valueOf(lab.getId())));
        assertThat(list.path("code").asInt()).isEqualTo(0);
        assertThat(list.at("/data/0/fileTitle").asText()).isEqualTo("第一");
        assertThat(list.at("/data/1/fileTitle").asText()).isEqualTo("第二");
    }

    @Test
    void labDeleteRejectedWhenAssociationTablesHaveRows() throws Exception {
        // 四张关联表各建一行,逐一验证删除被拒(批3 引用清单衔接项)
        record Case(String table, String sql) {
        }
        List<Case> cases = List.of(
                new Case("downloads", "INSERT INTO awardie_laboratory_downloads"
                        + " (laboratory_id, file_path, tenant_id) VALUES (?, 'x.pdf', 1)"),
                new Case("images", "INSERT INTO awardie_laboratory_images"
                        + " (laboratory_id, image_path, tenant_id) VALUES (?, 'x.png', 1)"),
                new Case("instructors", "INSERT INTO awardie_laboratory_instructors"
                        + " (laboratory_id, teacher_id, tenant_id) VALUES (?, 900003, 1)"),
                new Case("students", "INSERT INTO awardie_laboratory_students"
                        + " (laboratory_id, student_id, tenant_id) VALUES (?, 900004, 1)"));
        for (Case c : cases) {
            clearAssets();
            LaboratoriesDO lab = newLab("被" + c.table() + "引用的实验室");
            jdbcTemplate.update(c.sql(), lab.getId());
            JsonNode body = call(delete(BASE + "/delete").headers(authHeaders())
                    .param("id", String.valueOf(lab.getId())));
            assertThat(body.path("code").asInt()).as("%s 引用应拒绝删除", c.table()).isEqualTo(1003000002);
            assertThat(body.path("msg").asText()).contains("awardie_laboratory_" + c.table());
            assertThat(labMapper.selectById(lab.getId())).as("%s 引用时实验室应仍在", c.table()).isNotNull();
        }
    }

    @Test
    void labDeleteAllowedWhenAssociationRowsLogicallyDeleted() throws Exception {
        LaboratoriesDO lab = newLab("下载已删的实验室");
        jdbcTemplate.update("INSERT INTO awardie_laboratory_downloads"
                + " (laboratory_id, file_path, tenant_id, deleted) VALUES (?, 'x.pdf', 1, b'1')", lab.getId());
        // downloads 有 deleted 列 → deleted=1 的引用行不阻断
        JsonNode body = call(delete(BASE + "/delete").headers(authHeaders())
                .param("id", String.valueOf(lab.getId())));
        assertThat(body.path("code").asInt()).isEqualTo(0);
    }

    @Test
    void labDeleteAllowedWhenOnlyUndeletedRowsInNoDeletedTable() throws Exception {
        // instructors/students 无 deleted 列(纯关联表),有行即视为引用——本例验证清空后放行
        LaboratoriesDO lab = newLab("无关联的实验室");
        JsonNode body = call(delete(BASE + "/delete").headers(authHeaders())
                .param("id", String.valueOf(lab.getId())));
        assertThat(body.path("code").asInt()).isEqualTo(0);
    }
}
