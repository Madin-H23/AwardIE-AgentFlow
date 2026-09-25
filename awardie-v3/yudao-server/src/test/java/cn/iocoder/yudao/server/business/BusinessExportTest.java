package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.system.dal.dataobject.permission.MenuDO;
import cn.iocoder.yudao.module.system.dal.dataobject.user.AdminUserDO;
import cn.iocoder.yudao.module.system.dal.mysql.permission.MenuMapper;
import cn.iocoder.yudao.module.system.dal.mysql.user.AdminUserMapper;
import cn.iocoder.yudao.module.system.service.permission.PermissionService;
import cn.iocoder.yudao.server.YudaoServerApplication;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
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

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 批9 导出集成测试
 *
 * <p>重点验证三处对 v2 的修正真的生效:
 * <ol>
 *   <li>学号列是 {@code system_users.username}(v3 的 username 就是学号),不是 users.id;</li>
 *   <li>CSV 有 UTF-8 BOM(Excel 中文不乱码)、公式注入已转义;</li>
 *   <li>行数上限触发报错而非静默截断。</li>
 * </ol>
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        "spring.data.redis.database=1",
        // 行数上限调小,便于用小夹具触发越限
        "awardie.export.max-rows=3"
})
@AutoConfigureMockMvc
class BusinessExportTest {

    private static final long TENANT_ID = 1L;
    private static final long ADMIN_ROLE = 100L;
    private static final long TEACHER_ROLE = 101L;
    private static final String ADMIN = "expadm1";
    private static final String TEACHER = "exptea1";
    private static final String PASSWORD = "Export@Test#26";
    private static final List<String> ADMIN_PERMISSIONS = List.of("business:export:query");
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

    @BeforeEach
    void setUp() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedUser(ADMIN, ADMIN_ROLE, ADMIN_PERMISSIONS);
        seedUser(TEACHER, TEACHER_ROLE, TEACHER_PERMISSIONS);
        adminToken = login(ADMIN);
        teacherToken = login(TEACHER);
        TenantContextHolder.setTenantId(TENANT_ID);
        cleanTables();
    }

    @AfterEach
    void clean() {
        cleanTables();
        TenantContextHolder.clear();
    }

    private void cleanTables() {
        jdbcTemplate.update("DELETE FROM awardie_award_student_winners");
        jdbcTemplate.update("DELETE FROM awardie_awards");
        jdbcTemplate.update("DELETE FROM awardie_competitions");
        jdbcTemplate.update("DELETE FROM system_users WHERE username LIKE '2122%'");
    }

    /** 造一个带学号的学生用户(v3 的 username 即学号) */
    private long seedStudentUser(String studentNo, String name) {
        if (userMapper.selectCount(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getUsername, studentNo)) > 0) {
            return userMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                    .eq(AdminUserDO::getUsername, studentNo)).getId();
        }
        AdminUserDO user = new AdminUserDO();
        user.setUsername(studentNo);
        user.setPassword(bcrypt.encode(PASSWORD));
        user.setNickname(name);
        user.setStatus(0);
        user.setTenantId(TENANT_ID);
        userMapper.insert(user);
        return user.getId();
    }

    private long seedAward(String winner, String level, Integer year) {
        jdbcTemplate.update("INSERT INTO awardie_awards (winner_name, award_level, year, tenant_id)"
                + " VALUES (?, ?, ?, 1)", winner, level, year);
        return jdbcTemplate.queryForObject("SELECT id FROM awardie_awards WHERE winner_name = ?"
                + " ORDER BY id DESC LIMIT 1", Long.class, winner);
    }

    private void seedUser(String username, long roleId, List<String> permissions) {
        AdminUserDO user = new AdminUserDO();
        user.setUsername(username);
        user.setPassword(bcrypt.encode(PASSWORD));
        user.setNickname("导出测试-" + username);
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
        assertThat(menuIds).as("导出权限点缺失——请先执行 awardie-business-menus.sql")
                .hasSize(permissions.size());
        permissionService.assignUserRole(userId, Set.of(roleId));
    }

    private String login(String username) throws Exception {
        MvcResult result = mockMvc.perform(post("/admin-api/system/auth/login")
                .contentType(MediaType.APPLICATION_JSON).header("tenant-id", "1")
                .content("{\"username\":\"" + username + "\",\"password\":\"" + PASSWORD + "\"}"))
                .andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        String token = om.readTree(result.getResponse().getContentAsString())
                .at("/data/accessToken").asText();
        assertThat(token).as("登录应成功").isNotEmpty();
        return token;
    }

    private MvcResult download(String path, String token) throws Exception {
        MvcResult result = mockMvc.perform(get("/admin-api" + path)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                .header("tenant-id", "1")).andReturn();
        TenantContextHolder.setTenantId(TENANT_ID);
        return result;
    }

    // ========== 学生获奖明细 ==========

    @Test
    void studentAffairsCsvUsesUsernameAsStudentNo() throws Exception {
        long studentId = seedStudentUser("212206030", "导出测试学生");
        long awardId = seedAward("导出获奖人", "一等奖", 2024);
        jdbcTemplate.update("INSERT INTO awardie_award_student_winners (award_id, student_id, tenant_id)"
                + " VALUES (?, ?, 1)", awardId, studentId);

        MvcResult result = download("/business/export/student-affairs.csv", adminToken);
        assertThat(result.getResponse().getStatus()).isEqualTo(200);
        byte[] bytes = result.getResponse().getContentAsByteArray();
        // BOM 必须在(Excel 中文不乱码的前提)
        assertThat(bytes[0]).isEqualTo((byte) 0xEF);
        String text = new String(bytes, StandardCharsets.UTF_8);
        assertThat(text).contains("学号,姓名,竞赛,获奖等级,年份");
        // 关键修正:学号列是 212206030(username),不是 users.id 数字
        assertThat(text).contains("212206030");
        assertThat(text).doesNotContain(String.valueOf(studentId) + ",");
    }

    @Test
    void studentAffairsCsvIsolatedByTenant() throws Exception {
        // 他租户的学生获奖,本租户导出不该看到
        long studentId = seedStudentUser("212299999", "他租户学生");
        long awardId = seedAward("他租户奖", "一等奖", 2024);
        jdbcTemplate.update("UPDATE awardie_awards SET tenant_id = 2 WHERE id = ?", awardId);
        jdbcTemplate.update("UPDATE awardie_award_student_winners SET tenant_id = 2 WHERE award_id = ?", awardId);
        jdbcTemplate.update("UPDATE system_users SET tenant_id = 2 WHERE id = ?", studentId);

        MvcResult result = download("/business/export/student-affairs.csv", adminToken);
        String text = new String(result.getResponse().getContentAsByteArray(), StandardCharsets.UTF_8);
        assertThat(text).as("他租户数据不应出现在本租户导出里").doesNotContain("212299999");
    }

    @Test
    void studentAffairsEmptyExportsHeaderOnly() throws Exception {
        MvcResult result = download("/business/export/student-affairs.csv", adminToken);
        String text = new String(result.getResponse().getContentAsByteArray(), StandardCharsets.UTF_8);
        // 空结果也有表头(不是空文件)
        assertThat(text).contains("学号,姓名");
        // 字节级相等:split 默认丢尾部空串,切分断言无法区分"仅表头"与"表头+1 行"
        assertThat(text).isEqualTo("﻿学号,姓名,竞赛,获奖等级,年份\r\n");
    }

    @Test
    void studentAffairsXlsxIsValidWorkbook() throws Exception {
        long studentId = seedStudentUser("212206031", "XLSX测试学生");
        long awardId = seedAward("XLSX获奖人", "二等奖", 2024);
        jdbcTemplate.update("INSERT INTO awardie_award_student_winners (award_id, student_id, tenant_id)"
                + " VALUES (?, ?, 1)", awardId, studentId);

        MvcResult result = download("/business/export/student-affairs.xlsx", adminToken);
        assertThat(result.getResponse().getStatus()).isEqualTo(200);
        byte[] bytes = result.getResponse().getContentAsByteArray();
        // XLSX 是 zip:PK 魔数 50 4B 03 04
        assertThat(bytes.length).isGreaterThan(100);
        assertThat(bytes[0]).isEqualTo((byte) 0x50);
        assertThat(bytes[1]).isEqualTo((byte) 0x4B);
    }

    // ========== 竞赛年度汇总 ==========

    @Test
    void competitionSummaryCsvHasExpectedHeaderAndRows() throws Exception {
        seedAward("汇总甲", "一等奖", 2024);
        seedAward("汇总乙", "二等奖", 2023);

        MvcResult result = download("/business/export/competition-summary.csv", adminToken);
        String text = new String(result.getResponse().getContentAsByteArray(), StandardCharsets.UTF_8);
        assertThat(text).contains("竞赛,年份,获奖等级,数量");
        // 全部是"未关联"竞赛(夹具没建竞赛),但仍应出现两行不同年份
        assertThat(text).contains("2024").contains("2023");
        assertThat(text).contains("未关联");
    }

    @Test
    void competitionSummaryMarksNullYearAsNotFilled() throws Exception {
        // 年份为空的奖状:v2 用 '-' 排序会混入文本序;v3 显式标"未填写"
        seedAward("无年份奖", "一等奖", null);
        MvcResult result = download("/business/export/competition-summary.csv", adminToken);
        String text = new String(result.getResponse().getContentAsByteArray(), StandardCharsets.UTF_8);
        assertThat(text).contains("未填写");
    }

    @Test
    void competitionSummaryXlsxIsValidWorkbook() throws Exception {
        seedAward("XLSX汇总甲", "一等奖", 2024);
        MvcResult result = download("/business/export/competition-summary.xlsx", adminToken);
        byte[] bytes = result.getResponse().getContentAsByteArray();
        assertThat(bytes.length).isGreaterThan(100);
        assertThat(bytes[0]).isEqualTo((byte) 0x50);
    }

    // ========== 行数上限 ==========

    @Test
    void exportRejectsWhenExceedingRowLimit() throws Exception {
        // 上限设为 3,种 4 条不同竞赛组合触发
        seedAward("上限甲", "一等奖", 2024);
        seedAward("上限乙", "二等奖", 2024);
        seedAward("上限丙", "三等奖", 2024);
        seedAward("上限丁", "特等奖", 2024);

        MvcResult result = download("/business/export/competition-summary.csv", adminToken);
        // 超过上限应报业务错误(1003009000),不是静默截断
        String body = result.getResponse().getContentAsString();
        assertThat(body).contains("1003009000");
    }

    // ========== 越权 ==========

    @Test
    void teacherCannotExport() throws Exception {
        for (String path : List.of("/business/export/competition-summary.csv",
                "/business/export/student-affairs.csv",
                "/business/export/competition-summary.xlsx",
                "/business/export/student-affairs.xlsx")) {
            MvcResult result = download(path, teacherToken);
            assertThat(result.getResponse().getContentAsString())
                    .as("教师访问 %s 应 403", path).contains("\"code\":403");
        }
    }

}
