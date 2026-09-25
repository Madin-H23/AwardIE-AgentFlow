package cn.iocoder.yudao.server.business;

import cn.idev.excel.annotation.ExcelProperty;
import cn.idev.excel.FastExcelFactory;
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
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
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

import java.io.ByteArrayOutputStream;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

/**
 * 批8 大创域集成测试:Excel 导入(preview token / 幂等 / 经费换算 / 学生关联)+ status 校准 + 越权面
 *
 * <p>测试纪律(批7 立):只改用户→角色绑定(assignUserRole),菜单归属由 SQL 负责;
 * 独立 Redis 库 1 与 dev 服务隔离;清理用**物理 DELETE**(MyBatis-Plus 逻辑删除会留
 * deleted=1 行,后续"取第一条"会拿到历史行导致断言落空——批7 踩过三例)。
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        "spring.data.redis.database=1"
})
@AutoConfigureMockMvc
class InnovationImportTest {

    private static final String BASE = "/admin-api/business/innovations";
    private static final long TENANT_ID = 1L;
    private static final long ADMIN_ROLE = 100L;
    private static final long TEACHER_ROLE = 101L;
    private static final long STUDENT_ROLE = 102L;
    private static final String ADMIN = "innovadm1";
    private static final String TEACHER = "innovtea1";
    private static final String STUDENT = "innovstu1";
    private static final String PASSWORD = "Innov@Test#26";
    private static final List<String> ADMIN_PERMISSIONS = List.of(
            "business:innovation:query", "business:innovation:create",
            "business:innovation:import", "business:innovation:update",
            "business:innovation:calibrate");
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
        seedStudentIdUsers();
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

    /**
     * 播种学号用户
     *
     * <p>CI 的 test 库是全新库,不含学生数据(学生由批2 ETL 从 v2 迁,CI 建库不跑 ETL),
     * 所以"按学号关联学生"在本测试里必须自己播种用户,否则关联恒为 0。
     * 真实系统里这些用户由 ETL 提供。
     */
    private void seedStudentIdUsers() {
        for (String studentId : List.of("212206030", "212206016")) {
            if (userMapper.selectCount(new LambdaQueryWrapper<AdminUserDO>()
                    .eq(AdminUserDO::getUsername, studentId)) > 0) {
                continue;
            }
            AdminUserDO user = new AdminUserDO();
            user.setUsername(studentId);
            user.setPassword(bcrypt.encode(PASSWORD));
            user.setNickname("学生" + studentId);
            user.setStatus(0);
            user.setTenantId(TENANT_ID);
            userMapper.insert(user);
        }
    }

    private void cleanTables() {
        jdbcTemplate.update("DELETE FROM awardie_innovation_project_students");
        jdbcTemplate.update("DELETE FROM awardie_innovation_projects");
    }

    private void seedUser(String username, long roleId, List<String> permissions) {
        AdminUserDO user = new AdminUserDO();
        user.setUsername(username);
        user.setPassword(bcrypt.encode(PASSWORD));
        user.setNickname("大创测试-" + username);
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
        assertThat(menuIds).as("大创权限点缺失——请先执行 awardie-business-menus.sql + awardie-user-domain.sql")
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

    // ========== 测试 xlsx 构造 ==========

    /** 测试用行:表头名与生产 DTO 的 @ExcelProperty 完全一致 */
    @Data
    @AllArgsConstructor
    @NoArgsConstructor
    static class XlsxRow {
        @ExcelProperty("项目编号")
        private String projectNo;
        @ExcelProperty("项目名称")
        private String projectName;
        @ExcelProperty("项目类型")
        private String projectType;
        @ExcelProperty("起始日期")
        private String startDate;
        @ExcelProperty("结束日期")
        private String endDate;
        @ExcelProperty("负责人姓名")
        private String leaderName;
        @ExcelProperty("负责人学号")
        private String leaderId;
        @ExcelProperty("其他成员")
        private String otherMembers;
        @ExcelProperty("指导教师")
        private String supervisors;
        @ExcelProperty("经费")
        private String funding;
    }

    /** 导入模板的十列表头(与生产 DTO 的 @ExcelProperty 一致) */
    private static final List<String> HEADERS = List.of("项目编号", "项目名称", "项目类型", "起始日期",
            "结束日期", "负责人姓名", "负责人学号", "其他成员", "指导教师", "经费");

    private MockMultipartFile xlsx(String filename, List<XlsxRow> rows) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        FastExcelFactory.write(out, XlsxRow.class).sheet().doWrite(rows);
        return new MockMultipartFile("file", filename,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", out.toByteArray());
    }

    /** 用自定义表头文字写 xlsx(表头错误类用例用) */
    private MockMultipartFile xlsxWithHeader(List<String> header, List<XlsxRow> rows) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        List<List<String>> head = header.stream().map(List::of).toList();
        List<List<Object>> data = rows.stream()
                .map(r -> List.<Object>of(
                        nz(r.getProjectNo()), nz(r.getProjectName()), nz(r.getProjectType()),
                        nz(r.getStartDate()), nz(r.getEndDate()), nz(r.getLeaderName()),
                        nz(r.getLeaderId()), nz(r.getOtherMembers()), nz(r.getSupervisors()),
                        nz(r.getFunding())))
                .toList();
        FastExcelFactory.write(out).head(head).sheet().doWrite(data);
        return new MockMultipartFile("file", "自定义表头.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", out.toByteArray());
    }

    private static String nz(String v) {
        return v == null ? "" : v;
    }

    private XlsxRow validRow(String no, String name) {
        return new XlsxRow(no, name, "省级", "2025-01-01", "2026-12-31",
                "莫未文", "212206030", "江圣(212206016)", "王五", "2.5");
    }

    private JsonNode preview(MockMultipartFile file) throws Exception {
        return call(multipart(BASE + "/import/preview").file(file).headers(headers(adminToken)));
    }

    private JsonNode confirm(String token) throws Exception {
        return call(post(BASE + "/import/confirm").headers(headers(adminToken)).param("token", token));
    }

    // ========== 导入 ==========

    @Test
    void importHappyPath() throws Exception {
        JsonNode prev = preview(xlsx("大创.xlsx", List.of(validRow("DC-001", "智能审稿助手"))));
        assertThat(prev.path("code").asInt()).isZero();
        assertThat(prev.at("/data/rowCount").asInt()).isEqualTo(1);
        assertThat(prev.at("/data/errorCount").asInt()).isZero();
        // 首行回显(防线之三):十列内容按序可见
        assertThat(prev.at("/data/firstRowEcho")).hasSize(10);
        assertThat(prev.at("/data/firstRowEcho/0").asText()).isEqualTo("DC-001");

        JsonNode result = confirm(prev.at("/data/token").asText());
        assertThat(result.path("code").asInt()).isZero();
        assertThat(result.at("/data/imported").asInt()).isEqualTo(1);
        assertThat(result.at("/data/skipped").asInt()).isZero();

        // 库行落库 + 默认值
        var row = jdbcTemplate.queryForMap(
                "SELECT status, submitter_type, project_type, funding_amount, tenant_id"
                        + " FROM awardie_innovation_projects WHERE project_no = 'DC-001'");
        assertThat(row.get("status")).isEqualTo("进行中");
        assertThat(row.get("submitter_type")).isEqualTo("admin");
        assertThat(row.get("project_type")).isEqualTo("省级");
        assertThat(row.get("tenant_id")).isEqualTo(TENANT_ID);
    }

    @Test
    void fundingIsConvertedFromWanToYuan() throws Exception {
        // 决策 C:Excel 填万元(2.5),库里存元(25000)
        JsonNode prev = preview(xlsx("经费.xlsx", List.of(validRow("DC-FUND", "经费测试"))));
        assertThat(confirm(prev.at("/data/token").asText()).at("/data/imported").asInt()).isEqualTo(1);
        var funding = jdbcTemplate.queryForObject(
                "SELECT funding_amount FROM awardie_innovation_projects WHERE project_no = 'DC-FUND'",
                java.math.BigDecimal.class);
        assertThat(funding).isEqualByComparingTo("25000.00");
    }

    @Test
    void importCreatesStudentAssociations() throws Exception {
        // 决策 B-lite:负责人 + 可解析学号的成员都建关联
        JsonNode prev = preview(xlsx("关联.xlsx", List.of(validRow("DC-LINK", "关联测试"))));
        JsonNode result = confirm(prev.at("/data/token").asText());
        assertThat(result.at("/data/imported").asInt()).isEqualTo(1);
        // 负责人 + 成员(江圣 212206016)——两个学号都需在 system_users 存在
        long leaderRows = countAssociations("leader");
        long memberRows = countAssociations("member");
        assertThat(leaderRows + memberRows).as("至少应建立 leader 关联").isPositive();
    }

    private long countAssociations(String role) {
        Long n = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM awardie_innovation_project_students WHERE role = ?", Long.class, role);
        return n == null ? 0 : n;
    }

    @Test
    void tokenIsSingleUse() throws Exception {
        JsonNode prev = preview(xlsx("一次性.xlsx", List.of(validRow("DC-ONCE", "一次性令牌"))));
        String token = prev.at("/data/token").asText();
        assertThat(confirm(token).at("/data/imported").asInt()).isEqualTo(1);
        // 第二次用同一 token 必须失败——否则点两下会导入两遍
        JsonNode second = confirm(token);
        assertThat(second.path("code").asInt()).isNotZero();
    }

    @Test
    void tamperedRowsAreIgnored() throws Exception {
        // v2 缺陷:confirm 完全信任客户端 rows。v3 的 confirm 只收 token,
        // 请求里塞 rows 参数也应完全不影响入库内容。
        JsonNode prev = preview(xlsx("防篡改.xlsx", List.of(validRow("DC-SAFE", "原始项目"))));
        String token = prev.at("/data/token").asText();
        JsonNode forged = call(post(BASE + "/import/confirm").headers(headers(adminToken))
                .param("token", token)
                .param("rows", "[{\"projectName\":\"被篡改的项目\"}]"));
        assertThat(forged.path("code").asInt()).isZero();
        // 库里的项目名必须是原始的,不是请求里塞的
        String name = jdbcTemplate.queryForObject(
                "SELECT project_name FROM awardie_innovation_projects WHERE project_no = 'DC-SAFE'", String.class);
        assertThat(name).isEqualTo("原始项目");
    }

    @Test
    void duplicateProjectNoIsSkipped() throws Exception {
        // 首次导入
        JsonNode first = preview(xlsx("首次.xlsx", List.of(validRow("DC-DUP", "首次"))));
        assertThat(confirm(first.at("/data/token").asText()).at("/data/imported").asInt()).isEqualTo(1);
        // 同编号再传一次:跳过,不新增
        JsonNode second = preview(xlsx("重复.xlsx", List.of(validRow("DC-DUP", "再来一次"))));
        JsonNode result = confirm(second.at("/data/token").asText());
        assertThat(result.at("/data/imported").asInt()).isZero();
        assertThat(result.at("/data/skipped").asInt()).isEqualTo(1);
        assertThat(result.at("/data/errors/0").asText()).contains("已存在");
        // 库中仍只有一行,且是首次导入的内容(重复的那次没覆盖)
        assertThat(jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM awardie_innovation_projects WHERE project_no = 'DC-DUP'", Long.class))
                .isEqualTo(1L);
        assertThat(jdbcTemplate.queryForObject(
                "SELECT project_name FROM awardie_innovation_projects WHERE project_no = 'DC-DUP'", String.class))
                .isEqualTo("首次");
    }

    @Test
    void rowLevelErrorsDoNotBlockOtherRows() throws Exception {
        XlsxRow bad = new XlsxRow("DC-BAD", "", "省级", "2025-01-01", "2026-12-31",
                "张三", "212206030", "", "王五", "1");
        JsonNode prev = preview(xlsx("混合.xlsx", List.of(bad, validRow("DC-GOOD", "好项目"))));
        assertThat(prev.at("/data/errorCount").asInt()).isEqualTo(1);
        JsonNode result = confirm(prev.at("/data/token").asText());
        assertThat(result.at("/data/imported").asInt()).isEqualTo(1);
        assertThat(result.at("/data/skipped").asInt()).isEqualTo(1);
    }

    @Test
    void invalidFundingIsRowError() throws Exception {
        XlsxRow bad = new XlsxRow("DC-BADF", "经费非法", "省级", "2025-01-01", "2026-12-31",
                "张三", "212206030", "", "王五", "两百万");
        JsonNode prev = preview(xlsx("经费非法.xlsx", List.of(bad)));
        assertThat(prev.at("/data/errorCount").asInt()).isEqualTo(1);
        assertThat(prev.at("/data/rows/0/error").asText()).contains("经费");
    }

    @Test
    void invalidProjectTypeIsRowError() {
        XlsxRow bad = new XlsxRow("DC-BADT", "类型非法", "市级", "2025-01-01", "2026-12-31",
                "张三", "212206030", "", "王五", "1");
        try {
            JsonNode prev = preview(xlsx("类型非法.xlsx", List.of(bad)));
            assertThat(prev.at("/data/errorCount").asInt()).isEqualTo(1);
        } catch (Exception e) {
            throw new AssertionError("用例不应抛异常", e);
        }
    }

    // ========== status 校准 ==========

    @Test
    void calibrateOnlyMarksExpiredOngoingProjects() throws Exception {
        String today = java.time.LocalDate.now(java.time.ZoneId.of("Asia/Shanghai")).toString();
        String past = java.time.LocalDate.now().minusYears(1).toString();
        seedProject("过期项目", "进行中", past);
        seedProject("当天项目", "进行中", today);
        seedProject("终止项目", "终止", past);
        seedProject("已结题项目", "已结题", past);
        seedProject("无日期项目", "进行中", null);

        JsonNode result = call(post(BASE + "/calibrate-status").headers(headers(adminToken)));
        assertThat(result.path("code").asInt()).isZero();
        // 候选 = 进行中且结束日期非空 = 过期/当天/无日期中的前两个(无日期不进候选)
        assertThat(result.at("/data/considered").asInt()).isEqualTo(2);
        assertThat(result.at("/data/calibrated").asInt()).isEqualTo(1);
        assertThat(statusOf("过期项目")).isEqualTo("已结题");
        assertThat(statusOf("当天项目")).isEqualTo("进行中");   // 当天不校准
        assertThat(statusOf("终止项目")).isEqualTo("终止");     // 终止不动
        assertThat(statusOf("已结题项目")).isEqualTo("已结题"); // 已结题不动
    }

    @Test
    void calibrateIsIdempotent() throws Exception {
        String past = java.time.LocalDate.now().minusYears(1).toString();
        seedProject("幂等项目", "进行中", past);
        assertThat(call(post(BASE + "/calibrate-status").headers(headers(adminToken)))
                .at("/data/calibrated").asInt()).isEqualTo(1);
        // 第二次:已结题行不再进候选
        assertThat(call(post(BASE + "/calibrate-status").headers(headers(adminToken)))
                .at("/data/calibrated").asInt()).isZero();
        assertThat(statusOf("幂等项目")).isEqualTo("已结题");
    }

    @Test
    void calibrateCountsUnparsedDates() throws Exception {
        seedProject("待定项目", "进行中", "待定");
        JsonNode result = call(post(BASE + "/calibrate-status").headers(headers(adminToken)));
        assertThat(result.at("/data/skippedUnparsed").asInt()).isEqualTo(1);
        assertThat(statusOf("待定项目")).isEqualTo("进行中"); // 不猜,不改
    }

    private void seedProject(String name, String status, String endDate) {
        // 注意:v3 大创表没有 language / need_translate 列(v2 有,见 00-需求 F6)
        jdbcTemplate.update("INSERT INTO awardie_innovation_projects (project_name, status, end_date, tenant_id)"
                + " VALUES (?, ?, ?, 1)", name, status, endDate);
    }

    private String statusOf(String name) {
        return jdbcTemplate.queryForObject(
                "SELECT status FROM awardie_innovation_projects WHERE project_name = ?", String.class, name);
    }

    // ========== 越权面 ==========

    @Test
    void badHeaderIsRejected() throws Exception {
        // 表头改字:强类型读取对缺列/多列/列序变化都不报错,必须自己比对原始表头
        MockMultipartFile file = xlsxWithHeader(List.of("项目编号", "项目名", "项目类型"),
                List.of(new XlsxRow("DC-H1", "错字表头", "省级", "", "", "", "", "", "", "")));
        JsonNode body = preview(file);
        assertThat(body.path("code").asInt()).isNotZero();
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM awardie_innovation_projects", Long.class))
                .as("表头错误不应入库").isZero();
    }

    @Test
    void missingColumnIsRejected() throws Exception {
        // 少一列(缺"经费"):FastExcel 缺列不报错会静默按默认导入,必须拦住
        List<String> header = new java.util.ArrayList<>(HEADERS);
        header.remove("经费");
        MockMultipartFile file = xlsxWithHeader(header,
                List.of(new XlsxRow("DC-H2", "缺列", "省级", "", "", "", "", "", "", "")));
        assertThat(preview(file).path("code").asInt()).isNotZero();
    }

    @Test
    void tooManyRowsRejected() throws Exception {
        // 行数上限:1000 行上限,1001 行必须明确拒绝(不截断)
        List<XlsxRow> rows = new java.util.ArrayList<>();
        for (int i = 0; i < 1001; i++) {
            rows.add(validRow("BULK-" + i, "批量项目" + i));
        }
        assertThat(preview(xlsx("超行.xlsx", rows)).path("code").asInt()).isNotZero();
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM awardie_innovation_projects", Long.class))
                .isZero();
    }

    @Test
    void tokenCannotBeUsedByAnotherOperator() throws Exception {
        // security-audit H-1:token 必须绑定租户+操作人,否则泄露后可被他人拿去 confirm
        JsonNode prev = preview(xlsx("跨主体.xlsx", List.of(validRow("DC-X", "跨主体测试"))));
        String token = prev.at("/data/token").asText();
        // 同一租户、不同操作人:invalid
        JsonNode asOther = call(post(BASE + "/import/confirm").headers(headers(teacherToken))
                .param("token", token));
        assertThat(asOther.path("code").asInt()).as("他人不得使用该 token").isNotZero();
        assertThat(jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM awardie_innovation_projects WHERE project_no = 'DC-X'", Long.class))
                .as("不应入库").isZero();
    }

    @Test
    void invalidDateIsRowError() throws Exception {
        XlsxRow bad = new XlsxRow("DC-BADD", "日期非法", "省级", "2025-01-01", "2025年13月",
                "张三", "212206030", "", "王五", "1");
        JsonNode prev = preview(xlsx("日期非法.xlsx", List.of(bad)));
        assertThat(prev.at("/data/errorCount").asInt()).isEqualTo(1);
        assertThat(prev.at("/data/rows/0/error").asText()).contains("结束日期");
    }

    @Test
    void negativeFundingIsRowError() throws Exception {
        XlsxRow bad = new XlsxRow("DC-NEG", "负经费", "省级", "2025-01-01", "2026-12-31",
                "张三", "212206030", "", "王五", "-1");
        assertThat(preview(xlsx("负经费.xlsx", List.of(bad))).at("/data/errorCount").asInt()).isEqualTo(1);
    }

    @Test
    void blankProjectNoIsRowError() throws Exception {
        // 编号是幂等键:空编号会让唯一索引失效(允许多行 NULL),重复文件能反复导入
        XlsxRow bad = new XlsxRow("", "无编号", "省级", "2025-01-01", "2026-12-31",
                "张三", "212206030", "", "王五", "1");
        assertThat(preview(xlsx("无编号.xlsx", List.of(bad))).at("/data/errorCount").asInt()).isEqualTo(1);
    }

    @Test
    void vaultInnovationUpdateCarriesTenantAndDeletedCondition() throws Exception {
        // security-audit H-2:通用成果库的 innovation 分支走 JdbcTemplate(不经租户拦截器),
        // UPDATE 必须带 tenant_id + deleted=0。验证方式:造一条属于**别的租户**的项目,
        // 用本租户管理员改它——带条件时改不动(影响 0 行 → 报记录不存在)。
        seedProject("他租户项目", "进行中", "2026-12-31");
        long id = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_innovation_projects WHERE project_name = '他租户项目'", Long.class);
        jdbcTemplate.update("UPDATE awardie_innovation_projects SET tenant_id = 2 WHERE id = ?", id);

        JsonNode body = call(post("/admin-api/business/vault/innovation/" + id + "/update")
                .headers(headers(adminToken)).content("{\"status\":\"已结题\"}"));
        assertThat(body.path("code").asInt()).as("跨租户更新应失败").isNotZero();
        assertThat(statusOf("他租户项目")).as("他租户的行不应被改动").isEqualTo("进行中");
    }

    @Test
    void teacherAndStudentHaveNoInnovationAccess() throws Exception {
        seedProject("越权项目", "进行中", "2026-12-31");
        long id = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_innovation_projects WHERE project_name = '越权项目'", Long.class);
        for (String token : List.of(teacherToken, studentToken)) {
            assertThat(call(get(BASE + "/page").headers(headers(token))).path("code").asInt()).isEqualTo(403);
            assertThat(call(get(BASE + "/get").headers(headers(token)).param("id", String.valueOf(id)))
                    .path("code").asInt()).isEqualTo(403);
            assertThat(call(put(BASE + "/update").headers(headers(token)).param("id", String.valueOf(id))
                    .content("{\"status\":\"已结题\"}")).path("code").asInt()).isEqualTo(403);
            assertThat(call(post(BASE + "/calibrate-status").headers(headers(token)))
                    .path("code").asInt()).isEqualTo(403);
        }
    }

}
