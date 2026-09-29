package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.module.system.service.permission.PermissionService;
import cn.iocoder.yudao.module.system.dal.dataobject.user.AdminUserDO;
import cn.iocoder.yudao.module.system.dal.dataobject.permission.MenuDO;
import cn.iocoder.yudao.module.system.dal.mysql.permission.MenuMapper;
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

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 教师维度统计与姓名精确匹配(批20,D-17)。
 *
 * <p>锁死 <b>FIND_IN_SET 精确成员匹配</b>的语义边界——这是它替代子串 LIKE 的全部理由:
 * <ul>
 *   <li>编号陷阱:教师「张三1」不得命中名单里的「张三12」(同名编号约定的前提)</li>
 *   <li>子串陷阱:教师「王五」不得命中「王五平」</li>
 *   <li>名单归一:半角逗号/全角逗号/顿号/空格分隔的多人名单都能精确命中本人</li>
 *   <li>本人证书:winner_name 命中须以 granted_role='教师' 为前提,学生证书不算</li>
 * </ul>
 *
 * <p>同时覆盖 /business/teacher/achievements/my(教师端,权限 vault:query)与
 * /business/stats/by-teacher(管理端,权限 stats:query)两个入口——两者必须同口径,
 * 统计页与教师「我的成果」页的数字才会一致。
 *
 * <p>Map 型端点(jdbc 直出)断言必须覆盖键名——键名就是契约(批5 起纪律)。
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        "spring.data.redis.database=1"
})
@AutoConfigureMockMvc
class TeacherDimensionTest {

    private static final long TENANT_ID = 1L;
    private static final long ADMIN_ROLE = 100L;
    private static final long TEACHER_ROLE = 101L;
    private static final String ADMIN = "tdmadmin1";
    private static final String TEACHER_NUMBERED = "tdmteach1";
    private static final String TEACHER_PLAIN = "tdmteach2";
    private static final String PASSWORD = "Tdm@Test#26";
    /** 夹具教师的昵称即匹配名:编号名与裸名各一 */
    private static final String NICK_NUMBERED = "张三1";
    private static final String NICK_PLAIN = "王五";
    /** 夹具 awards 的唯一标记,清理与断言都靠它圈定范围,不碰他人数据 */
    private static final String MARK = "TDM-";

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
    private String numberedToken;
    private String plainToken;

    @BeforeEach
    void setUp() throws Exception {
        cleanAwards();
        seedTeacher(TEACHER_NUMBERED, NICK_NUMBERED);
        seedTeacher(TEACHER_PLAIN, NICK_PLAIN);
        seedUser(ADMIN, ADMIN_ROLE, "批20测试-" + ADMIN, List.of("business:stats:query"));
        adminToken = login(ADMIN);
        numberedToken = login(TEACHER_NUMBERED);
        plainToken = login(TEACHER_PLAIN);

        // awards 夹具:competition_name_in_file 用 MARK 前缀唯一标记,断言按标记找 id
        // 编号陷阱(3):「张三12」在名单里,不得被「张三1」命中
        seedAward(MARK + "01-精确单名", "张三1", "学生甲", null);
        seedAward(MARK + "02-逗号名单", "李四,张三1", "学生乙", null);
        seedAward(MARK + "03-编号陷阱", "李四，张三12", "学生丙", null);
        // 子串陷阱(4):「王五平」不得被「王五」命中
        seedAward(MARK + "04-子串陷阱", "王五平,赵六", "学生丁", null);
        seedAward(MARK + "05-顿号名单", "王五、李四", "学生戊", null);
        // 本人证书:winner_name 命中须 granted_role='教师'(7 是学生证书,不算)
        seedAward(MARK + "06-教师本人", null, "张三1", "教师");
        seedAward(MARK + "07-学生同名", null, "张三1", "学生");
        seedAward(MARK + "08-王五本人", null, "王五", "教师");
    }

    @AfterEach
    void clean() {
        cleanAwards();
        cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder.clear();
    }

    /** 只删本类夹具行(MARK 前缀圈定),不清全表——测试库里还有别的测试类的存量用户 */
    private void cleanAwards() {
        cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder.setTenantId(TENANT_ID);
        jdbcTemplate.update("DELETE FROM awardie_awards WHERE competition_name_in_file LIKE ?", MARK + "%");
    }

    private void seedAward(String marker, String supervisor, String winner, String grantedRole) {
        jdbcTemplate.update("INSERT INTO awardie_awards (competition_name_in_file, supervisor_name,"
                        + " winner_name, granted_role, award_level, tenant_id) VALUES (?, ?, ?, ?, '一等奖', 1)",
                marker, supervisor, winner, grantedRole);
    }

    private Long awardId(String marker) {
        return jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_awards WHERE competition_name_in_file = ?", Long.class, marker);
    }

    /** 教师账号:昵称必须是匹配名本身(不能像批9夹具那样加前缀,否则 FIND_IN_SET 永不命中) */
    private void seedTeacher(String username, String nickname) {
        seedUser(username, TEACHER_ROLE, nickname, List.of("business:vault:query"));
    }

    private void seedUser(String username, long roleId, String nickname, List<String> permissions) {
        AdminUserDO user = new AdminUserDO();
        user.setUsername(username);
        user.setPassword(bcrypt.encode(PASSWORD));
        user.setNickname(nickname);
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
            existing.setNickname(nickname);
            userMapper.updateById(existing);
        }
        Set<Long> menuIds = permissions.stream()
                .map(menuMapper::selectListByPermission)
                .flatMap(List::stream)
                .map(MenuDO::getId)
                .collect(Collectors.toSet());
        assertThat(menuIds).as("权限点缺失——测试库需先跑 awardie-business-menus.sql").hasSize(permissions.size());
        permissionService.assignUserRole(userId, Set.of(roleId));
    }

    private String login(String username) throws Exception {
        MvcResult result = mockMvc.perform(post("/admin-api/system/auth/login")
                        .contentType(MediaType.APPLICATION_JSON).header("tenant-id", "1")
                        .content("{\"username\":\"" + username + "\",\"password\":\"" + PASSWORD + "\"}"))
                .andReturn();
        cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder.setTenantId(TENANT_ID);
        JsonNode body = om.readTree(result.getResponse().getContentAsString());
        assertThat(body.at("/data/accessToken").asText())
                .as("登录应成功: %s", body.path("msg").asText()).isNotEmpty();
        return body.at("/data/accessToken").asText();
    }

    private JsonNode call(MockHttpServletRequestBuilder builder) throws Exception {
        MvcResult result = mockMvc.perform(builder).andReturn();
        cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder.setTenantId(TENANT_ID);
        return om.readTree(result.getResponse().getContentAsString());
    }

    private HttpHeaders headers(String token) {
        HttpHeaders h = new HttpHeaders();
        h.setBearerAuth(token);
        h.set("tenant-id", "1");
        h.setContentType(MediaType.APPLICATION_JSON);
        return h;
    }

    // ========== /business/teacher/achievements/my:教师端精确匹配 ==========

    @Test
    void numberedTeacherMatchesExactlyNotPrefixTraps() throws Exception {
        JsonNode body = call(get("/admin-api/business/teacher/achievements/my").headers(headers(numberedToken)));
        assertThat(body.path("code").asInt()).isZero();
        List<Long> ids = new java.util.ArrayList<>();
        body.at("/data").forEach(row -> ids.add(row.path("id").asLong()));
        // 命中:01(单名) 02(逗号名单) 06(本人教师证书);不命中:03(张三12) 04 05 07(学生同名) 08
        assertThat(ids).as("张三1 只应命中 3 行,张三12 是编号陷阱").containsExactlyInAnyOrder(
                awardId(MARK + "01-精确单名"), awardId(MARK + "02-逗号名单"), awardId(MARK + "06-教师本人"));
    }

    @Test
    void substringTrapIsNotMatched() throws Exception {
        JsonNode body = call(get("/admin-api/business/teacher/achievements/my").headers(headers(plainToken)));
        assertThat(body.path("code").asInt()).isZero();
        List<Long> ids = new java.util.ArrayList<>();
        body.at("/data").forEach(row -> ids.add(row.path("id").asLong()));
        // 命中:05(顿号名单里的王五) 08(本人);04 的「王五平」是子串陷阱,不得命中
        assertThat(ids).containsExactlyInAnyOrder(awardId(MARK + "05-顿号名单"), awardId(MARK + "08-王五本人"));
    }

    @Test
    void roleDistinguishesSupervisorFromOwnAward() throws Exception {
        JsonNode body = call(get("/admin-api/business/teacher/achievements/my").headers(headers(numberedToken)));
        Long ownAwardId = awardId(MARK + "06-教师本人");
        Long supervisedId = awardId(MARK + "01-精确单名");
        // 06 是本人证书 → role=获奖;01 → 指导。键名就是契约,一并断言
        for (JsonNode row : body.at("/data")) {
            assertThat(row.has("role")).as("键名契约:id/competition/awardLevel/winnerName/supervisorName/year/role").isTrue();
            if (row.path("id").asLong() == ownAwardId) {
                assertThat(row.path("role").asText()).isEqualTo("获奖");
            }
            if (row.path("id").asLong() == supervisedId) {
                assertThat(row.path("role").asText()).isEqualTo("指导");
            }
        }
    }

    // ========== /business/stats/by-teacher:管理端维度统计(与教师端同口径) ==========

    @Test
    void teacherBreakdownAgreesWithTeacherEndpoint() throws Exception {
        JsonNode body = call(get("/admin-api/business/stats/by-teacher").headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isZero();
        JsonNode numbered = null;
        JsonNode plain = null;
        for (JsonNode row : body.at("/data")) {
            // Map 型端点:键名就是契约
            assertThat(row.has("name")).isTrue();
            assertThat(row.has("supervised")).isTrue();
            assertThat(row.has("ownAwards")).isTrue();
            if (NICK_NUMBERED.equals(row.path("name").asText())) {
                numbered = row;
            }
            if (NICK_PLAIN.equals(row.path("name").asText())) {
                plain = row;
            }
        }
        // 与教师端 /my 的行数严格一致(同口径的验收判据):张三1=3(2指导+1获奖),王五=2(1+1)
        assertThat(numbered).as("教师维度表必须列出在职教师(0 指导的也列出)").isNotNull();
        assertThat(numbered.path("supervised").asLong()).isEqualTo(2L);
        assertThat(numbered.path("ownAwards").asLong()).isEqualTo(1L);
        assertThat(plain).isNotNull();
        assertThat(plain.path("supervised").asLong()).isEqualTo(1L);
        assertThat(plain.path("ownAwards").asLong()).isEqualTo(1L);
        // 编号陷阱的行(03)属于「张三12」——没有这个教师账号,不应被记到「张三1」头上
        assertThat(numbered.path("supervised").asLong() + numbered.path("ownAwards").asLong())
                .as("张三1 合计必须仍是 3,张三12 的行不得串账").isEqualTo(3L);
    }

    @Test
    void studentCannotCallTeacherEndpoint() throws Exception {
        // D-04 回归:学生(无 vault:query)调教师端点必须 403
        JsonNode body = call(get("/admin-api/business/teacher/achievements/my")
                .headers(headers(loginStubStudent())));
        assertThat(body.path("code").asInt()).isEqualTo(403);
    }

    private String loginStubStudent() throws Exception {
        // 学生用批9 已有的夹具账号不可复用(密码不同),这里现场种一个只读学生
        seedUser("tdmstu1", 102L, "批20测试-学生", List.of("business:pending-achievement:query"));
        return login("tdmstu1");
    }
}
