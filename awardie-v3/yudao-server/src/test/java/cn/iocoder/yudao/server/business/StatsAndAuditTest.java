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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

/**
 * 批9 统计 + 审计日志集成测试
 *
 * <p><b>与 v2 测试水平的根本差异</b>:v2 的 {@code AdminStatsTest} 只验响应结构不验聚合数值
 * (取证确认:无固定数据夹具),那种测试无法发现 SQL 口径错误。本类用**固定数据夹具逐条锁死
 * 确切数值**——种入 N 条就断言必须等于 N。
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        "spring.data.redis.database=1"
})
@AutoConfigureMockMvc
class StatsAndAuditTest {

    private static final long TENANT_ID = 1L;
    private static final long ADMIN_ROLE = 100L;
    private static final long TEACHER_ROLE = 101L;
    private static final long STUDENT_ROLE = 102L;
    private static final String ADMIN = "statsadm1";
    private static final String TEACHER = "statstea1";
    private static final String STUDENT = "statsstu1";
    private static final String PASSWORD = "Stats@Test#26";
    private static final List<String> ADMIN_PERMISSIONS = List.of(
            "business:stats:query", "business:export:query", "business:logs:query");
    private static final List<String> TEACHER_PERMISSIONS = List.of("business:pending-achievement:query");

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
    private String teacherToken;
    private String studentToken;

    @BeforeEach
    void setUp() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedUser(ADMIN, ADMIN_ROLE, ADMIN_PERMISSIONS);
        seedUser(TEACHER, TEACHER_ROLE, TEACHER_PERMISSIONS);
        seedUser(STUDENT, STUDENT_ROLE, TEACHER_PERMISSIONS);
        adminToken = login(ADMIN);
        teacherToken = login(TEACHER);
        studentToken = login(STUDENT);
        TenantContextHolder.setTenantId(TENANT_ID);
        cleanTables();
        seedFixedData();
    }

    @AfterEach
    void clean() {
        cleanTables();
        TenantContextHolder.clear();
    }

    private void cleanTables() {
        // 物理 DELETE:逻辑删除残留会让后续"取第一条"拿到历史行(批7 踩过三例)
        jdbcTemplate.update("DELETE FROM awardie_achievement_audit_log");
        jdbcTemplate.update("DELETE FROM awardie_award_student_winners");
        jdbcTemplate.update("DELETE FROM awardie_awards");
        jdbcTemplate.update("DELETE FROM awardie_patents");
        jdbcTemplate.update("DELETE FROM awardie_software_copyrights");
        jdbcTemplate.update("DELETE FROM awardie_other_files");
        jdbcTemplate.update("DELETE FROM awardie_innovation_projects");
        jdbcTemplate.update("DELETE FROM awardie_competitions");
    }

    /**
     * 固定夹具:数值全部可预期,用于锁死 SQL 聚合口径
     * <pre>
     * 竞赛:3 个(其中 1 个白名单)
     * awards: 4 条(3 条关联竞赛A/2 条竞赛B、1 条无关联)
     * patents: 2 条  software: 1 条  other: 1 条  innovation: 2 条
     * → category 应为 award=4 patent=2 software=1 other=1 innovation=2
     * → 竞赛Top: 竞赛A=2, 竞赛B=1, 未关联=1
     * </pre>
     */
    private void seedFixedData() {
        Long compA = seedCompetition("竞赛甲", true);
        Long compB = seedCompetition("竞赛乙", false);
        seedCompetition("竞赛丙", false);

        // awards: A 两条 / B 一条 / 无关联一条
        seedAward("A-一", compA, "一等奖", 2024);
        seedAward("A-二", compA, "二等奖", 2024);
        seedAward("B-一", compB, "一等奖", 2023);
        seedAward("无关联奖", null, "三等奖", 2023);

        // 其余四类各若干,用于 category 数值
        seedSimple("awardie_patents", "专利-一");
        seedSimple("awardie_patents", "专利-二");
        seedSimple("awardie_software_copyrights", "软著-一");
        seedSimple("awardie_other_files", "其他-一");
        seedSimple("awardie_innovation_projects", "大创-一", "project_no", "DC-T-1");
        seedSimple("awardie_innovation_projects", "大创-二", "project_no", "DC-T-2");

        // 审计留痕:两条不同动作,用于日志筛选
        seedAudit(1L, "award", 1, "张老师", "提交");
        seedAudit(2L, "patent", 6, "李老师", "通过");
    }

    private Long seedCompetition(String name, boolean whiteList) {
        // white_list 是 BIT(1):必须传 boolean,传字符串 "1" 会报 Data too long
        jdbcTemplate.update("INSERT INTO awardie_competitions (competition_name, white_list, tenant_id)"
                + " VALUES (?, ?, 1)", name, whiteList ? Boolean.TRUE : Boolean.FALSE);
        return jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_competitions WHERE competition_name = ? ORDER BY id DESC LIMIT 1",
                Long.class, name);
    }

    private void seedAward(String winner, Long competitionId, String level, Integer year) {
        jdbcTemplate.update("INSERT INTO awardie_awards (winner_name, competition_id, award_level, year,"
                        + " tenant_id) VALUES (?, ?, ?, ?, 1)",
                winner, competitionId, level, year);
    }

    /** 简单表插入(不同表必填列不同,这里逐表处理) */
    private void seedSimple(String table, String name) {
        seedSimple(table, name, null, null);
    }

    private void seedSimple(String table, String name, String col, String value) {
        switch (table) {
            case "awardie_patents" -> jdbcTemplate.update(
                    "INSERT INTO awardie_patents (patent_name, tenant_id) VALUES (?, 1)", name);
            case "awardie_software_copyrights" -> jdbcTemplate.update(
                    "INSERT INTO awardie_software_copyrights (software_name, tenant_id) VALUES (?, 1)", name);
            case "awardie_other_files" -> jdbcTemplate.update(
                    "INSERT INTO awardie_other_files (file_name, file_path, tenant_id) VALUES (?, ?, 1)",
                    name, name + ".txt");
            case "awardie_innovation_projects" -> jdbcTemplate.update(
                    "INSERT INTO awardie_innovation_projects (project_name, project_no, tenant_id)"
                            + " VALUES (?, ?, 1)", name, value);
            default -> throw new IllegalArgumentException("未支持的表:" + table);
        }
    }

    private void seedAudit(Long achievementId, String kind, int actionType, String operatorName, String remark) {
        jdbcTemplate.update("INSERT INTO awardie_achievement_audit_log (achievement_id, achievement_kind,"
                        + " action_type, action_result, operator_code, operator_name, remark, tenant_id)"
                        + " VALUES (?, ?, ?, 1, ?, ?, ?, 1)",
                achievementId, kind, actionType, operatorName.toLowerCase(), operatorName, remark);
    }

    private void seedUser(String username, long roleId, List<String> permissions) {
        AdminUserDO user = new AdminUserDO();
        user.setUsername(username);
        user.setPassword(bcrypt.encode(PASSWORD));
        user.setNickname("批9测试-" + username);
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
        assertThat(menuIds).as("批9 权限点缺失——请先执行 awardie-business-menus.sql + awardie-user-domain.sql")
                .hasSize(permissions.size());
        permissionService.assignUserRole(userId, Set.of(roleId));
    }

    private String login(String username) throws Exception {
        MvcResult result = mockMvc.perform(
                        org.springframework.test.web.servlet.request.MockMvcRequestBuilders
                                .post("/admin-api/system/auth/login")
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

    // ========== 统计:锁死确切数值 ==========

    @Test
    void overviewCategoryCountsAreExact() throws Exception {
        JsonNode body = call(get("/admin-api/business/stats/overview").headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isZero();
        JsonNode category = body.at("/data/category");
        // 锁死固定夹具的数值——不是"字段存在",是"恰好等于 N"
        assertThat(category.path("award").asLong()).isEqualTo(4L);
        assertThat(category.path("patent").asLong()).isEqualTo(2L);
        assertThat(category.path("software").asLong()).isEqualTo(1L);
        assertThat(category.path("other").asLong()).isEqualTo(1L);
        assertThat(category.path("innovation").asLong()).isEqualTo(2L);
    }

    @Test
    void overviewSummaryIsExact() throws Exception {
        JsonNode body = call(get("/admin-api/business/stats/overview").headers(headers(adminToken)));
        JsonNode summary = body.at("/data/summary");
        assertThat(summary.path("competitionsTotal").asLong()).isEqualTo(3L);
        assertThat(summary.path("whitelist").asLong()).isEqualTo(1L);
        // 竞赛为 3,其中竞赛甲白名单=1
        assertThat(summary.path("whitelist").asLong()).isLessThan(summary.path("competitionsTotal").asLong());
    }

    @Test
    void competitionRankingHasExactOrderAndUnlinkedBucket() throws Exception {
        JsonNode body = call(get("/admin-api/business/stats/by-competition").headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isZero();
        JsonNode list = body.at("/data");
        // 竞赛甲=2,竞赛乙=1,未关联=1 —— 顺序按 total DESC
        assertThat(list.get(0).path("name").asText()).isEqualTo("竞赛甲");
        assertThat(list.get(0).path("total").asLong()).isEqualTo(2L);
        // "未关联"桶必须存在(v2 LEFT JOIN + COALESCE 语义)
        boolean hasUnlinked = false;
        for (JsonNode node : list) {
            if ("未关联".equals(node.path("name").asText())) {
                hasUnlinked = true;
                assertThat(node.path("total").asLong()).isEqualTo(1L);
            }
        }
        assertThat(hasUnlinked).as("无竞赛关联的成果应归入未关联桶").isTrue();
    }

    @Test
    void competitionRankingIsDeterministicForTies() throws Exception {
        // 同数值时按 name 升序(v2 无二级排序,行序随机——截图/对账会漂)
        jdbcTemplate.update("DELETE FROM awardie_awards");
        Long compX = seedCompetition("XXX竞赛", false);
        Long compA = seedCompetition("AAA竞赛", false);
        seedAward("甲", compA, "一等奖", 2024);
        seedAward("乙", compX, "一等奖", 2024);
        JsonNode body = call(get("/admin-api/business/stats/by-competition").headers(headers(adminToken)));
        JsonNode list = body.at("/data");
        assertThat(list).hasSize(2);
        assertThat(list.get(0).path("name").asText()).isEqualTo("AAA竞赛");
        assertThat(list.get(1).path("name").asText()).isEqualTo("XXX竞赛");
    }

    @Test
    void statsEmptyDataReturnsZeroNotError() throws Exception {
        jdbcTemplate.update("DELETE FROM awardie_awards");
        jdbcTemplate.update("DELETE FROM awardie_patents");
        jdbcTemplate.update("DELETE FROM awardie_competitions");
        JsonNode body = call(get("/admin-api/business/stats/overview").headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isZero();
        assertThat(body.at("/data/category/award").asLong()).isZero();
    }

    @Test
    void statsIsolatedByTenant() throws Exception {
        // 种一条 tenant 2 的 award,tenant 1 的统计不该看到它
        jdbcTemplate.update("INSERT INTO awardie_awards (winner_name, award_level, year, tenant_id)"
                + " VALUES ('他租户奖', '一等奖', 2024, 2)");
        JsonNode body = call(get("/admin-api/business/stats/overview").headers(headers(adminToken)));
        // 夹具原本 4 条,加了 1 条他租户后本租户仍应是 4
        assertThat(body.at("/data/category/award").asLong()).isEqualTo(4L);
    }

    // ========== 审计日志 ==========

    @Test
    void auditLogReturnsFixedRowsWithActionLabels() throws Exception {
        JsonNode body = call(get("/admin-api/business/logs/audit").headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isZero();
        assertThat(body.at("/data/total").asLong()).isEqualTo(2L);
        JsonNode first = body.at("/data/list/0");
        // 动作码要有中文标签,不是裸数字
        assertThat(first.path("actionType").asInt()).isNotZero();
        assertThat(first.path("actionLabel").asText()).isNotBlank();
        assertThat(first.path("actionLabel").asText()).isNotEqualTo(String.valueOf(first.path("actionType").asInt()));
    }

    @Test
    void auditLogFiltersByActionType() throws Exception {
        JsonNode body = call(get("/admin-api/business/logs/audit").param("actionType", "6")
                .headers(headers(adminToken)));
        assertThat(body.at("/data/total").asLong()).isEqualTo(1L);
        assertThat(body.at("/data/list/0/actionType").asInt()).isEqualTo(6);
    }

    @Test
    void auditLogFiltersByKind() throws Exception {
        JsonNode body = call(get("/admin-api/business/logs/audit").param("achievementKind", "patent")
                .headers(headers(adminToken)));
        assertThat(body.at("/data/total").asLong()).isEqualTo(1L);
    }

    @Test
    void auditLogFiltersByOperatorKeyword() throws Exception {
        JsonNode body = call(get("/admin-api/business/logs/audit").param("operatorKeyword", "李")
                .headers(headers(adminToken)));
        assertThat(body.at("/data/total").asLong()).isEqualTo(1L);
        assertThat(body.at("/data/list/0/operatorName").asText()).contains("李");
    }

    @Test
    void auditLogIsolatedByTenant() throws Exception {
        // 正样本:本租户留痕必须能查到(证明查询链路通,否则"啥都没有"也能过负样本)
        JsonNode own = call(get("/admin-api/business/logs/audit").headers(headers(adminToken)));
        assertThat(own.at("/data/total").asLong()).isEqualTo(2L);

        // 负样本:种一条 tenant 2 的留痕,本租户不该看到
        seedAudit(999L, "other", 7, "他租户操作人", "他租户驳回");
        jdbcTemplate.update("UPDATE awardie_achievement_audit_log SET tenant_id = 2"
                + " WHERE operator_name = '他租户操作人'");
        JsonNode after = call(get("/admin-api/business/logs/audit").headers(headers(adminToken)));
        assertThat(after.at("/data/total").asLong()).as("他租户留痕不应计入本租户").isEqualTo(2L);
        assertThat(after.at("/data/list/0/operatorName").asText()).isNotEqualTo("他租户操作人");
    }

    @Test
    void auditLogReturnsEmptyForOutOfRangePage() throws Exception {
        // 越界页返回空列表而不是 500(批7 教训:不能靠默认行为)
        JsonNode body = call(get("/admin-api/business/logs/audit")
                .param("pageNo", "99").param("pageSize", "10").headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isZero();
        assertThat(body.at("/data/list")).isEmpty();
        assertThat(body.at("/data/total").asLong()).isEqualTo(2L);
    }

    @Test
    void auditLogPaginates() throws Exception {
        JsonNode page1 = call(get("/admin-api/business/logs/audit").param("pageNo", "1").param("pageSize", "1")
                .headers(headers(adminToken)));
        assertThat(page1.at("/data/list")).hasSize(1);
        assertThat(page1.at("/data/total").asLong()).isEqualTo(2L);
        JsonNode page2 = call(get("/admin-api/business/logs/audit").param("pageNo", "2").param("pageSize", "1")
                .headers(headers(adminToken)));
        assertThat(page2.at("/data/list")).hasSize(1);
        // 两页的行 id 必须不同(真分页,不是重复返回第一页)
        assertThat(page1.at("/data/list/0/id").asLong())
                .isNotEqualTo(page2.at("/data/list/0/id").asLong());
    }

    @Test
    void auditLogEmptyWhenNoMatch() throws Exception {
        JsonNode body = call(get("/admin-api/business/logs/audit").param("operatorKeyword", "不存在的人XYZ")
                .headers(headers(adminToken)));
        assertThat(body.path("code").asInt()).isZero();
        assertThat(body.at("/data/total").asLong()).isZero();
    }

    // ========== 越权 ==========

    @Test
    void teacherAndStudentCannotAccessStatsLogsOrExport() throws Exception {
        for (String token : List.of(teacherToken, studentToken)) {
            assertThat(call(get("/admin-api/business/stats/overview").headers(headers(token)))
                    .path("code").asInt()).isEqualTo(403);
            assertThat(call(get("/admin-api/business/stats/by-competition").headers(headers(token)))
                    .path("code").asInt()).isEqualTo(403);
            assertThat(call(get("/admin-api/business/logs/audit").headers(headers(token)))
                    .path("code").asInt()).isEqualTo(403);
        }
    }

}
