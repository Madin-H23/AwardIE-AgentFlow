package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import cn.iocoder.yudao.module.business.dal.mysql.competition.CompetitionsMapper;
import cn.iocoder.yudao.module.system.dal.dataobject.permission.UserRoleDO;
import cn.iocoder.yudao.module.system.dal.dataobject.user.AdminUserDO;
import cn.iocoder.yudao.module.system.dal.mysql.permission.UserRoleMapper;
import cn.iocoder.yudao.module.system.dal.mysql.user.AdminUserMapper;
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

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

/**
 * 批3 竞赛域 API 级测试(沿用批1 MockMvc 范式:test 库隔离 + 自播种用户真登录 + tenant-id 1)。
 *
 * 覆盖:CRUD 全链路 / q 模糊命中与未命中 / 名单筛选 / 名称唯一拒绝(改他人名与排除自身两分支)/
 * is_auto_added 建档恒 false 且 update 不改 / 删除后 get 返 null / 更新已删报错 / 批量删 / 未登录 401。
 *
 * <p>注意:HTTP 请求结束后芋道租户过滤器会清空 TenantContext,故所有请求走 call() 辅助方法,
 * 由它在返回前重设租户,保证测试内 mapper/JdbcTemplate 直操可用。
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
class CompetitionsControllerTest {

    private static final String BASE = "/admin-api/business/competitions";
    private static final long TENANT_ID = 1L;
    private static final String TEST_USERNAME = "comptestadmin";
    private static final String TEST_PASSWORD = "Comp@Test#2026";

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private CompetitionsMapper mapper;
    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private AdminUserMapper userMapper;
    @Autowired
    private UserRoleMapper userRoleMapper;

    private final ObjectMapper om = new ObjectMapper();
    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();
    private String token;

    @BeforeEach
    void loginAndClean() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedTestUser();
        token = loginToken(TEST_USERNAME, TEST_PASSWORD);
        TenantContextHolder.setTenantId(TENANT_ID);
        mapper.delete(null);
    }

    @AfterEach
    void clearTenant() {
        TenantContextHolder.clear();
    }

    /** 执行请求并重设租户上下文(HTTP 结束后租户过滤器会清空) */
    private JsonNode call(MockHttpServletRequestBuilder builder) throws Exception {
        MvcResult result = mockMvc.perform(builder).andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        return om.readTree(result.getResponse().getContentAsString());
    }

    private void seedTestUser() {
        AdminUserDO existing = userMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getUsername, TEST_USERNAME));
        Long userId;
        if (existing == null) {
            AdminUserDO user = new AdminUserDO();
            user.setUsername(TEST_USERNAME);
            user.setPassword(bcrypt.encode(TEST_PASSWORD));
            user.setNickname("竞赛测试用户");
            user.setStatus(0);
            user.setTenantId(TENANT_ID);
            userMapper.insert(user);
            userId = user.getId();
        } else {
            userId = existing.getId();
        }
        if (userRoleMapper.selectCount(new LambdaQueryWrapper<UserRoleDO>()
                .eq(UserRoleDO::getUserId, userId)) == 0) {
            UserRoleDO ur = new UserRoleDO();
            ur.setUserId(userId);
            ur.setRoleId(1L); // super_admin:cleanup 保留,含 competitions 权限点
            userRoleMapper.insert(ur);
        }
    }

    private String loginToken(String username, String password) throws Exception {
        MvcResult result = mockMvc.perform(post("/admin-api/system/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("tenant-id", "1")
                        .content("{\"username\":\"" + username + "\",\"password\":\"" + password + "\"}"))
                .andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        return om.readTree(result.getResponse().getContentAsString()).path("data").path("accessToken").asText();
    }

    private HttpHeaders authHeaders() {
        HttpHeaders h = new HttpHeaders();
        h.setBearerAuth(token);
        h.set("tenant-id", "1");
        h.setContentType(MediaType.APPLICATION_JSON);
        return h;
    }

    private long createCompetition(String name) throws Exception {
        JsonNode body = call(post(BASE + "/create").headers(authHeaders())
                .content("{\"competitionName\":\"" + name + "\",\"officialWebsite\":\"https://x.example\","
                        + "\"organizer\":\"组委会\",\"competitionTime\":\"4-10月\","
                        + "\"participantRequirements\":\"组队报名\",\"gradeCategory\":\"本科组\","
                        + "\"briefDescription\":\"简介文本\",\"aliasList\":\"别名一\\n别名二\","
                        + "\"whiteList\":true,\"watchList\":false}"));
        assertThat(body.path("code").asInt()).isEqualTo(0);
        return body.path("data").asLong();
    }

    @Test
    void createGetPageUpdateDeleteFlow() throws Exception {
        long id = createCompetition("测试竞赛甲");

        JsonNode got = call(get(BASE + "/get").headers(authHeaders()).param("id", String.valueOf(id)));
        assertThat(got.path("code").asInt()).isEqualTo(0);
        assertThat(got.at("/data/competitionName").asText()).isEqualTo("测试竞赛甲");
        assertThat(got.at("/data/whiteList").asBoolean()).isTrue();
        assertThat(got.at("/data/watchList").asBoolean()).isFalse();
        assertThat(got.at("/data/organizer").asText()).isEqualTo("组委会");
        assertThat(got.at("/data/gradeCategory").asText()).isEqualTo("本科组");
        // v2 语义:建档恒 false(SaveReqVO 不暴露该字段,service 强制置 false)
        assertThat(got.at("/data/isAutoAdded").asBoolean()).isFalse();

        JsonNode page = call(get(BASE + "/page").headers(authHeaders())
                .param("pageNo", "1").param("pageSize", "10").param("competitionName", "竞赛甲"));
        assertThat(page.path("code").asInt()).isEqualTo(0);
        assertThat(page.at("/data/list/0/competitionName").asText()).isEqualTo("测试竞赛甲");
        assertThat(page.at("/data/total").asInt()).isEqualTo(1);

        // 全字段更新(v2 详情页全字段编辑;白名单/观察名单也走此端点)
        JsonNode updated = call(put(BASE + "/update").headers(authHeaders())
                .content("{\"id\":" + id + ",\"competitionName\":\"测试竞赛甲改\","
                        + "\"whiteList\":false,\"watchList\":true}"));
        assertThat(updated.path("code").asInt()).isEqualTo(0);
        JsonNode afterUpdate = call(get(BASE + "/get").headers(authHeaders()).param("id", String.valueOf(id)));
        assertThat(afterUpdate.at("/data/competitionName").asText()).isEqualTo("测试竞赛甲改");
        assertThat(afterUpdate.at("/data/whiteList").asBoolean()).isFalse();
        assertThat(afterUpdate.at("/data/watchList").asBoolean()).isTrue();

        assertThat(call(delete(BASE + "/delete").headers(authHeaders()).param("id", String.valueOf(id)))
                .path("code").asInt()).isEqualTo(0);
        // 逻辑删除后 get:芋道约定 code 0 + data null
        JsonNode afterDelete = call(get(BASE + "/get").headers(authHeaders()).param("id", String.valueOf(id)));
        assertThat(afterDelete.path("code").asInt()).isEqualTo(0);
        assertThat(afterDelete.path("data").isNull()).isTrue();
        // 更新已删记录 → 业务错误码 1_003_001_000
        JsonNode updateDeleted = call(put(BASE + "/update").headers(authHeaders())
                .content("{\"id\":" + id + ",\"competitionName\":\"再试一次\","
                        + "\"whiteList\":true,\"watchList\":false}"));
        assertThat(updateDeleted.path("code").asInt()).isEqualTo(1003001000);
    }

    @Test
    void duplicateNameRejected() throws Exception {
        createCompetition("重名竞赛乙");
        JsonNode dup = call(post(BASE + "/create").headers(authHeaders())
                .content("{\"competitionName\":\"重名竞赛乙\",\"whiteList\":false,\"watchList\":false}"));
        assertThat(dup.path("code").asInt()).isEqualTo(1003001001);
        assertThat(dup.path("msg").asText()).contains("竞赛名称已存在");
    }

    @Test
    void updateToExistingNameRejected() throws Exception {
        long kept = createCompetition("保留竞赛丙");
        long renamed = createCompetition("改名竞赛丁");
        JsonNode conflict = call(put(BASE + "/update").headers(authHeaders())
                .content("{\"id\":" + renamed + ",\"competitionName\":\"保留竞赛丙\","
                        + "\"whiteList\":false,\"watchList\":false}"));
        assertThat(conflict.path("code").asInt()).isEqualTo(1003001001);
        // 排除自身:同名改同名(仅改名单)不误判
        JsonNode self = call(put(BASE + "/update").headers(authHeaders())
                .content("{\"id\":" + kept + ",\"competitionName\":\"保留竞赛丙\","
                        + "\"whiteList\":true,\"watchList\":false}"));
        assertThat(self.path("code").asInt()).isEqualTo(0);
    }

    @Test
    void pageKeywordMissReturnsEmpty() throws Exception {
        createCompetition("命中用竞赛戊");
        JsonNode page = call(get(BASE + "/page").headers(authHeaders())
                .param("pageNo", "1").param("pageSize", "10").param("competitionName", "不存在的关键词zzz"));
        assertThat(page.path("code").asInt()).isEqualTo(0);
        assertThat(page.at("/data/list").isEmpty()).isTrue();
    }

    @Test
    void pageFilterByWhiteList() throws Exception {
        createCompetition("白名单竞赛己");
        JsonNode white = call(get(BASE + "/page").headers(authHeaders())
                .param("pageNo", "1").param("pageSize", "10").param("whiteList", "true"));
        assertThat(white.at("/data/list/0/competitionName").asText()).isEqualTo("白名单竞赛己");
        JsonNode nonWhite = call(get(BASE + "/page").headers(authHeaders())
                .param("pageNo", "1").param("pageSize", "10").param("whiteList", "false"));
        assertThat(nonWhite.at("/data/list").isEmpty()).isTrue();
    }

    @Test
    void deleteListRemovesAll() throws Exception {
        long a = createCompetition("批量删竞赛庚");
        long b = createCompetition("批量删竞赛辛");
        JsonNode body = call(delete(BASE + "/delete-list").headers(authHeaders())
                .param("ids", String.valueOf(a), String.valueOf(b)));
        assertThat(body.path("code").asInt()).isEqualTo(0);
        assertThat(mapper.selectById(a)).isNull();
        assertThat(mapper.selectById(b)).isNull();
    }

    @Test
    void isAutoAddedStaysTrueOnUpdate() throws Exception {
        // 直插一条 is_auto_added=1(模拟 OCR 抽取链路置位),update 不得把它改掉
        CompetitionsDO row = new CompetitionsDO();
        row.setCompetitionName("自动建竞赛壬");
        row.setWhiteList(false);
        row.setWatchList(false);
        row.setIsAutoAdded(true);
        mapper.insert(row);
        JsonNode updated = call(put(BASE + "/update").headers(authHeaders())
                .content("{\"id\":" + row.getId() + ",\"competitionName\":\"自动建竞赛壬改\","
                        + "\"whiteList\":true,\"watchList\":false}"));
        assertThat(updated.path("code").asInt()).isEqualTo(0);
        Boolean isAutoAdded = jdbcTemplate.queryForObject(
                "SELECT is_auto_added FROM awardie_competitions WHERE id = ?", Boolean.class, row.getId());
        assertThat(isAutoAdded).isTrue();
    }

    @Test
    void deleteListRejectsOversizedBatch() throws Exception {
        long id = createCompetition("批量上限竞赛");
        StringBuilder ids = new StringBuilder();
        for (int i = 0; i <= 1000; i++) {
            if (i > 0) {
                ids.append(',');
            }
            ids.append(i == 0 ? id : 900000L + i);
        }
        JsonNode body = call(delete(BASE + "/delete-list").headers(authHeaders()).param("ids", ids.toString()));
        assertThat(body.path("code").asInt()).isEqualTo(1003001003);
        // 超限时不得有任何删除发生
        assertThat(mapper.selectById(id)).isNotNull();
    }

    @Test
    void unauthenticatedRejected() throws Exception {
        JsonNode body = call(get(BASE + "/page").header("tenant-id", "1")
                .param("pageNo", "1").param("pageSize", "10"));
        assertThat(body.path("code").asInt()).isEqualTo(401);
    }
}
