package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import cn.iocoder.yudao.module.business.dal.dataobject.laboratory.LaboratoriesDO;
import cn.iocoder.yudao.module.business.dal.mysql.competition.CompetitionsMapper;
import cn.iocoder.yudao.module.business.dal.mysql.laboratory.LaboratoriesMapper;
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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 批3 删除前引用检查测试(建临时引用表实证三条路径)。
 *
 * 三条路径(对应 01-spec Testing Decisions):
 * 1. 引用存在(deleted=0)→ 拒绝,消息含表名与行数;
 * 2. 引用行 deleted=1 → 放行(逻辑删除不阻断);
 * 3. 引用表不存在 → 放行(批4-8 成果表未建时不误拒)。
 *
 * 临时表用真实成果表名(awardie_awards / awardie_patents),测试后删除;
 * 批6/8 建成真实成果表后,本测试的临时表方案须改为直接用真实表(已在 02-实施 记录)。
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3"
})
@AutoConfigureMockMvc
class ReferenceCheckTest {

    private static final String COMP_BASE = "/admin-api/business/competitions";
    private static final String LAB_BASE = "/admin-api/business/laboratories";
    private static final long TENANT_ID = 1L;
    private static final String TEST_USERNAME = "refcheckadmin";
    private static final String TEST_PASSWORD = "Ref@Test#2026";

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private CompetitionsMapper competitionsMapper;
    @Autowired
    private LaboratoriesMapper laboratoriesMapper;
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
        competitionsMapper.delete(null);
        laboratoriesMapper.delete(null);
        dropReferenceTables();
    }

    @AfterEach
    void cleanup() {
        dropReferenceTables();
        TenantContextHolder.clear();
    }

    private void dropReferenceTables() {
        jdbcTemplate.execute("DROP TABLE IF EXISTS awardie_awards");
        jdbcTemplate.execute("DROP TABLE IF EXISTS awardie_patents");
    }

    private void createAwardsTable() {
        jdbcTemplate.execute("CREATE TABLE awardie_awards ("
                + "id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                + "competition_id BIGINT NULL, laboratory_id BIGINT NULL, "
                + "deleted BIT(1) NOT NULL DEFAULT b'0')");
    }

    private void createPatentsTable() {
        jdbcTemplate.execute("CREATE TABLE awardie_patents ("
                + "id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                + "laboratory_id BIGINT NULL, "
                + "deleted BIT(1) NOT NULL DEFAULT b'0')");
    }

    private void seedTestUser() {
        AdminUserDO existing = userMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getUsername, TEST_USERNAME));
        Long userId;
        if (existing == null) {
            AdminUserDO user = new AdminUserDO();
            user.setUsername(TEST_USERNAME);
            user.setPassword(bcrypt.encode(TEST_PASSWORD));
            user.setNickname("引用检查测试用户");
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
            ur.setRoleId(1L);
            userRoleMapper.insert(ur);
        }
    }

    private String loginToken(String username, String password) throws Exception {
        JsonNode body = call(post("/admin-api/system/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .header("tenant-id", "1")
                .content("{\"username\":\"" + username + "\",\"password\":\"" + password + "\"}"));
        return body.path("data").path("accessToken").asText();
    }

    private JsonNode json(MvcResult result) throws Exception {
        return om.readTree(result.getResponse().getContentAsString());
    }

    /** 执行请求并重设租户上下文(HTTP 结束后芋道租户过滤器会清空) */
    private JsonNode call(MockHttpServletRequestBuilder builder) throws Exception {
        MvcResult result = mockMvc.perform(builder).andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        return json(result);
    }

    private HttpHeaders authHeaders() {
        HttpHeaders h = new HttpHeaders();
        h.setBearerAuth(token);
        h.set("tenant-id", "1");
        h.setContentType(MediaType.APPLICATION_JSON);
        return h;
    }

    private CompetitionsDO newCompetition(String name) {
        CompetitionsDO row = new CompetitionsDO();
        row.setCompetitionName(name);
        row.setWhiteList(false);
        row.setWatchList(false);
        competitionsMapper.insert(row);
        return row;
    }

    private LaboratoriesDO newLaboratory(String name) {
        LaboratoriesDO row = new LaboratoriesDO();
        row.setName(name);
        laboratoriesMapper.insert(row);
        return row;
    }

    @Test
    void competitionDeleteRejectedWhenReferencedByAward() throws Exception {
        CompetitionsDO competition = newCompetition("被引用的竞赛");
        createAwardsTable();
        jdbcTemplate.update("INSERT INTO awardie_awards (competition_id, deleted) VALUES (?, b'0')",
                competition.getId());

        JsonNode body = call(delete(COMP_BASE + "/delete").headers(authHeaders())
                .param("id", String.valueOf(competition.getId())));
        assertThat(body.path("code").asInt()).isEqualTo(1003001002);
        assertThat(body.path("msg").asText()).contains("awardie_awards").contains("1 条");
        // DB 终态:竞赛仍在(未删)
        assertThat(competitionsMapper.selectById(competition.getId())).isNotNull();
    }

    @Test
    void competitionDeleteAllowedWhenReferenceLogicallyDeleted() throws Exception {
        CompetitionsDO competition = newCompetition("引用已删的竞赛");
        createAwardsTable();
        jdbcTemplate.update("INSERT INTO awardie_awards (competition_id, deleted) VALUES (?, b'1')",
                competition.getId());

        assertThat(call(delete(COMP_BASE + "/delete").headers(authHeaders())
                .param("id", String.valueOf(competition.getId()))).path("code").asInt()).isEqualTo(0);
        assertThat(competitionsMapper.selectById(competition.getId())).isNull();
    }

    @Test
    void competitionDeleteAllowedWhenReferenceTableMissing() throws Exception {
        // awardie_awards 不存在(批6 前真实状态)→ 跳过检查,不误拒
        CompetitionsDO competition = newCompetition("无引用表的竞赛");
        assertThat(call(delete(COMP_BASE + "/delete").headers(authHeaders())
                .param("id", String.valueOf(competition.getId()))).path("code").asInt()).isEqualTo(0);
        assertThat(competitionsMapper.selectById(competition.getId())).isNull();
    }

    @Test
    void laboratoryDeleteRejectedWhenReferencedByAward() throws Exception {
        LaboratoriesDO lab = newLaboratory("被引用的实验室");
        createAwardsTable();
        jdbcTemplate.update("INSERT INTO awardie_awards (laboratory_id, deleted) VALUES (?, b'0')", lab.getId());

        JsonNode body = call(delete(LAB_BASE + "/delete").headers(authHeaders())
                        .param("id", String.valueOf(lab.getId())));
        assertThat(body.path("code").asInt()).isEqualTo(1003000002);
        assertThat(body.path("msg").asText()).contains("awardie_awards");
        assertThat(laboratoriesMapper.selectById(lab.getId())).isNotNull();
    }

    @Test
    void laboratoryDeleteRejectedWhenReferencedByPatent() throws Exception {
        LaboratoriesDO lab = newLaboratory("被专利引用的实验室");
        createPatentsTable();
        jdbcTemplate.update("INSERT INTO awardie_patents (laboratory_id, deleted) VALUES (?, b'0')", lab.getId());

        JsonNode body = call(delete(LAB_BASE + "/delete").headers(authHeaders())
                        .param("id", String.valueOf(lab.getId())));
        assertThat(body.path("code").asInt()).isEqualTo(1003000002);
        assertThat(body.path("msg").asText()).contains("awardie_patents");
    }

    @Test
    void laboratoryDeleteAllowedWhenReferenceLogicallyDeleted() throws Exception {
        LaboratoriesDO lab = newLaboratory("引用已删的实验室");
        createAwardsTable();
        jdbcTemplate.update("INSERT INTO awardie_awards (laboratory_id, deleted) VALUES (?, b'1')", lab.getId());

        assertThat(call(delete(LAB_BASE + "/delete").headers(authHeaders())
                .param("id", String.valueOf(lab.getId()))).path("code").asInt()).isEqualTo(0);
        assertThat(laboratoriesMapper.selectById(lab.getId())).isNull();
    }

    @Test
    void deleteListRejectedAtomicallyWhenOneReferenced() throws Exception {
        CompetitionsDO free = newCompetition("可删的竞赛");
        CompetitionsDO referenced = newCompetition("被引用的竞赛乙");
        createAwardsTable();
        jdbcTemplate.update("INSERT INTO awardie_awards (competition_id, deleted) VALUES (?, b'0')",
                referenced.getId());

        JsonNode body = call(delete(COMP_BASE + "/delete-list").headers(authHeaders())
                .param("ids", String.valueOf(free.getId()), String.valueOf(referenced.getId())));
        assertThat(body.path("code").asInt()).isEqualTo(1003001002);
        // 原子性:前一条未被删(事务回滚)
        assertThat(competitionsMapper.selectById(free.getId())).isNotNull();
        assertThat(competitionsMapper.selectById(referenced.getId())).isNotNull();
    }
}
