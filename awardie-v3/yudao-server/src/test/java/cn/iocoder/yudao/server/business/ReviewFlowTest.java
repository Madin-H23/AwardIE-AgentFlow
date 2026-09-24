package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission.PendingAchievementDO;
import cn.iocoder.yudao.module.business.dal.mysql.audit.AchievementAuditLogMapper;
import cn.iocoder.yudao.module.business.dal.mysql.competition.CompetitionsMapper;
import cn.iocoder.yudao.module.business.dal.mysql.pendingsubmission.PendingAchievementMapper;
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

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 批5 审核流集成测试:状态机 + 物化 + 审计 + 时间线 + AI 建议。
 *
 * <p>播种走带 @CacheEvict 的授权 API(见 PendingSubmissionControllerTest 同注:芋道权限三级
 * Redis 缓存,直插授权表会拿到上一轮残留权限集 → 403)。
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        "awardie.file.root=target/test-files/review"
})
@AutoConfigureMockMvc
class ReviewFlowTest {

    private static final String BASE = "/admin-api/business/pending-achievements";
    private static final long TENANT_ID = 1L;
    private static final long STUDENT_ROLE = 102L;
    private static final long TEACHER_ROLE = 101L;
    private static final String STUDENT = "revstu1";
    private static final String OTHER = "revstu2";
    private static final String TEACHER = "revtea1";
    private static final String PASSWORD = "Rev@Test#26";
    private static final List<String> REVIEW_PERMISSIONS = List.of(
            "business:pending-achievement:create", "business:pending-achievement:query",
            "business:pending-achievement:review", "business:pending-achievement:delete");

    private static final byte[] JPEG = {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0, 0x21, 0x22};
    private static final String AWARD_JSON =
            "{\"competition_name\":\"审核流测试竞赛\",\"award_level\":\"一等奖\",\"winner_name\":\"李四\",\"date\":\"2024-06-01\"}";

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private PendingAchievementMapper pendingMapper;
    @Autowired
    private CompetitionsMapper competitionMapper;
    @Autowired
    private AchievementAuditLogMapper auditMapper;
    @Autowired
    private AdminUserMapper userMapper;
    @Autowired
    private MenuMapper menuMapper;
    @Autowired
    private PermissionService permissionService;

    private final ObjectMapper om = new ObjectMapper();
    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();
    private String studentToken;
    private String otherToken;
    private String teacherToken;

    @BeforeEach
    void setUp() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedUser(STUDENT, STUDENT_ROLE);
        seedUser(OTHER, STUDENT_ROLE);
        seedUser(TEACHER, TEACHER_ROLE);
        studentToken = login(STUDENT);
        otherToken = login(OTHER);
        teacherToken = login(TEACHER);
        TenantContextHolder.setTenantId(TENANT_ID);
        cleanAll();
    }

    @AfterEach
    void clean() {
        cleanAll();
        TenantContextHolder.clear();
    }

    private void cleanAll() {
        for (String t : List.of("awardie_pending_achievements", "awardie_achievement_audit_log",
                "awardie_awards", "awardie_award_student_winners", "awardie_patents",
                "awardie_software_copyrights", "awardie_other_files")) {
            jdbcTemplate.execute("DELETE FROM " + t);
        }
        competitionMapper.delete(null);
        clearFiles();
    }

    private void clearFiles() {
        Path root = Path.of("target/test-files/review");
        if (!Files.exists(root)) {
            return;
        }
        try (Stream<Path> walk = Files.walk(root)) {
            walk.sorted(Comparator.reverseOrder()).forEach(p -> {
                try {
                    Files.deleteIfExists(p);
                } catch (Exception ignored) {
                    // 清理失败不阻塞
                }
            });
        } catch (Exception ignored) {
            // 目录不存在
        }
    }

    private void seedUser(String username, long roleId) {
        AdminUserDO user = new AdminUserDO();
        user.setUsername(username);
        user.setPassword(bcrypt.encode(PASSWORD));
        user.setNickname("审核测试-" + username);
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
        Set<Long> menuIds = REVIEW_PERMISSIONS.stream()
                .map(menuMapper::selectListByPermission)
                .flatMap(List::stream)
                .map(MenuDO::getId)
                .collect(java.util.stream.Collectors.toSet());
        assertThat(menuIds).as("待审成果权限点应存在于 test 库菜单表").hasSize(REVIEW_PERMISSIONS.size());
        permissionService.assignRoleMenu(roleId, menuIds);
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
        return h;
    }

    /** 提交一条成果(返回 pending id) */
    private long submit(String token, String type, String dataJson, byte[] fileBytes) throws Exception {
        MockMultipartFile file = new MockMultipartFile("file", "r.jpg", "image/jpeg", fileBytes);
        JsonNode body = call(multipart(BASE + "/submit").file(file)
                .param("achievementType", type).param("data", dataJson).headers(headers(token)));
        assertThat(body.path("code").asInt()).as("提交应成功: %s", body.path("msg").asText()).isEqualTo(0);
        return body.at("/data/id").asLong();
    }

    private JsonNode review(String token, long id, String action, String comment) throws Exception {
        return call(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
                .post(BASE + "/" + id + "/review").headers(headers(token))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"action\":\"" + action + "\",\"comment\":\"" + comment + "\"}"));
    }

    private long count(String table) {
        Long n = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM " + table + " WHERE deleted = b'0'", Long.class);
        return n == null ? 0 : n;
    }

    @Test
    void approveMaterializesAwardAndCreatesCompetition() throws Exception {
        long id = submit(studentToken, "award", AWARD_JSON, JPEG);
        JsonNode body = review(teacherToken, id, "approve", "证书清晰,通过");
        assertThat(body.path("code").asInt()).isEqualTo(0);
        assertThat(body.at("/data/status").asText()).isEqualTo("archived");

        assertThat(count("awardie_awards")).isEqualTo(1);
        // 竞赛按名自动建且 is_auto_added=true(v2 同)
        CompetitionsDO comp = competitionMapper.selectByCompetitionName("审核流测试竞赛");
        assertThat(comp).isNotNull();
        assertThat(comp.getIsAutoAdded()).isTrue();
        // 学生获奖关联
        assertThat(count("awardie_award_student_winners")).isEqualTo(1);
        // 审计:提交 1 + 通过 6 + 物化 8
        assertThat(auditMapper.selectCountByAchievementAndAction(id, 1).intValue()).isEqualTo(1);
        assertThat(auditMapper.selectCountByAchievementAndAction(id, 6).intValue()).isEqualTo(1);
        assertThat(auditMapper.selectCountByAchievementAndAction(id, 8).intValue()).isEqualTo(1);
    }

    @Test
    void approvePatentSoftwareOtherMaterialize() throws Exception {
        long p1 = submit(studentToken, "patent",
                "{\"patent_name\":\"审核流专利\",\"application_number\":\"CN7654321\",\"patent_type\":\"发明专利\"}",
                withTail(JPEG, (byte) 0x31));
        review(teacherToken, p1, "approve", "专利材料齐全");
        assertThat(count("awardie_patents")).isEqualTo(1);

        long p2 = submit(studentToken, "software",
                "{\"software_name\":\"审核流软著\",\"registration_number\":\"2024SR12345\"}",
                withTail(JPEG, (byte) 0x32));
        review(teacherToken, p2, "approve", "软著材料齐全");
        assertThat(count("awardie_software_copyrights")).isEqualTo(1);

        long p3 = submit(studentToken, "other", "{\"title\":\"审核流其他成果\"}",
                withTail(JPEG, (byte) 0x33));
        review(teacherToken, p3, "approve", "其他成果已归档");
        assertThat(count("awardie_other_files")).isEqualTo(1);
    }

    @Test
    void approveInnovationDoesNotMaterialize() throws Exception {
        long id = submit(studentToken, "innovation", "{\"project_name\":\"审核流大创\"}",
                withTail(JPEG, (byte) 0x34));
        JsonNode body = review(teacherToken, id, "approve", "大创走 Excel 通道");
        assertThat(body.path("code").asInt()).isEqualTo(0);
        // 大创不物化(v1/v2 语义),但留痕存在
        assertThat(count("awardie_awards") + count("awardie_patents")
                + count("awardie_software_copyrights") + count("awardie_other_files")).isZero();
        assertThat(auditMapper.selectCountByAchievementAndAction(id, 8).intValue()).isEqualTo(1);
    }

    @Test
    void rejectRequiresCommentAndMarksRejected() throws Exception {
        long id = submit(studentToken, "award", AWARD_JSON, JPEG);
        // 空原因驳回 → 拒绝
        JsonNode noComment = review(teacherToken, id, "reject", "");
        assertThat(noComment.path("code").asInt()).isEqualTo(1003004001);
        // 状态未变
        assertThat(pendingMapper.selectById(id).getStatus()).isEqualTo("pending");

        JsonNode rejected = review(teacherToken, id, "reject", "证书不清晰,请重新上传");
        assertThat(rejected.path("code").asInt()).isEqualTo(0);
        assertThat(pendingMapper.selectById(id).getStatus()).isEqualTo("rejected");
        assertThat(auditMapper.selectCountByAchievementAndAction(id, 7).intValue()).isEqualTo(1);
        // 驳回不物化
        assertThat(count("awardie_awards")).isZero();
    }

    @Test
    void reviewNonPendingRejectedByStateMachine() throws Exception {
        long id = submit(studentToken, "award", AWARD_JSON, JPEG);
        PendingAchievementDO row = pendingMapper.selectById(id);
        row.setStatus("archived");
        pendingMapper.updateById(row);
        JsonNode body = review(teacherToken, id, "approve", "再审一次");
        assertThat(body.path("code").asInt()).isEqualTo(1003004000);
    }

    @Test
    void approveIsIdempotentByBusinessFact() throws Exception {
        long id = submit(studentToken, "award", AWARD_JSON, JPEG);
        review(teacherToken, id, "approve", "第一次通过");
        // 人工把状态重置为 pending(模拟重复审批路径),再审一次:业务事实已存在 → 不重复物化
        PendingAchievementDO row = pendingMapper.selectById(id);
        row.setStatus("pending");
        pendingMapper.updateById(row);
        JsonNode second = review(teacherToken, id, "approve", "重复审批");
        assertThat(second.path("code").asInt()).isEqualTo(0);
        assertThat(count("awardie_awards")).as("幂等:成果表应仍只有 1 行").isEqualTo(1);
        assertThat(count("awardie_award_student_winners")).isEqualTo(1);
    }

    @Test
    void timelineVisibleToOwnerAndStaffOnly() throws Exception {
        long id = submit(studentToken, "award", AWARD_JSON, JPEG);
        review(teacherToken, id, "approve", "通过");
        // 本人可见
        JsonNode owner = call(get(BASE + "/" + id + "/timeline").headers(headers(studentToken)));
        assertThat(owner.path("code").asInt()).isEqualTo(0);
        assertThat(owner.at("/data").size()).isGreaterThanOrEqualTo(3);
        // 教师可见
        JsonNode teacher = call(get(BASE + "/" + id + "/timeline").headers(headers(teacherToken)));
        assertThat(teacher.path("code").asInt()).isEqualTo(0);
        // 另一学生不可见
        JsonNode other = call(get(BASE + "/" + id + "/timeline").headers(headers(otherToken)));
        assertThat(other.path("code").asInt()).isEqualTo(1003004002);
    }

    @Test
    void teacherPendingListJoinsSubmitterName() throws Exception {
        submit(studentToken, "award", AWARD_JSON, JPEG);
        JsonNode list = call(get(BASE + "/teacher-pending-list").headers(headers(teacherToken))
                .param("status", "pending"));
        assertThat(list.path("code").asInt()).isEqualTo(0);
        assertThat(list.at("/data/0/submitterName").asText()).contains("审核测试-" + STUDENT);
        assertThat(list.at("/data/0/achievementType").asText()).isEqualTo("award");
    }

    @Test
    void aiSuggestFakeAndGrpcDegrade() throws Exception {
        long good = submit(studentToken, "award", AWARD_JSON, JPEG);
        JsonNode fake = call(get(BASE + "/" + good + "/ai-suggest").headers(headers(teacherToken)));
        assertThat(fake.path("code").asInt()).isEqualTo(0);
        assertThat(fake.at("/data/decision").asText()).isEqualTo("pass");
        assertThat(fake.at("/data/suggestion").asText()).contains("AI 建议仅辅助参考");

        // 字段有问题 → reject 建议
        long bad = submit(studentToken, "award", "{\"competition_name\":\"缺字段\"}",
                withTail(JPEG, (byte) 0x35));
        JsonNode badSuggest = call(get(BASE + "/" + bad + "/ai-suggest").headers(headers(teacherToken)));
        assertThat(badSuggest.at("/data/decision").asText()).isEqualTo("reject");
        assertThat(badSuggest.at("/data/issuesJson").asText()).contains("winner_name");
    }

    private byte[] withTail(byte[] base, byte extra) {
        byte[] out = new byte[base.length + 1];
        System.arraycopy(base, 0, out, 0, base.length);
        out[base.length] = extra;
        return out;
    }
}
