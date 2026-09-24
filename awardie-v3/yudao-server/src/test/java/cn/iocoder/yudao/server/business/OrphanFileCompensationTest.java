package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
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

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 批7 孤儿文件补偿集成测试(清偿批4 挂账)。
 *
 * <p>三条要验的不变式:
 * <ol>
 *   <li>重复提交**不落盘**(去重前置的效果,用文件系统目录清单断言,不是只看数据库);</li>
 *   <li>落盘后入库失败 → 文件被回收;</li>
 *   <li>回收不误删——同内容文件仍被别的记录引用时必须保留。</li>
 * </ol>
 *
 * @author AwardIE
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3",
        "spring.data.redis.database=1",
        // 独立存储根:文件按内容寻址,若与其它测试类共用根,同内容字节会落同一路径,
        // 别的测试类建的引用行会让本类的"删前查引用"判定仍被引用(代码正确但测试互相污染)
        "awardie.file.root=target/test-files/orphan"
})
@AutoConfigureMockMvc
class OrphanFileCompensationTest {

    private static final String BASE = "/admin-api/business/pending-achievements";
    private static final String FILE_ROOT = "target/test-files/orphan";
    private static final long TENANT_ID = 1L;
    private static final long STUDENT_ROLE = 102L;
    private static final String STUDENT = "orphstu1";
    private static final String PASSWORD = "Orph@Test#26";
    private static final List<String> PERMISSIONS = List.of("business:pending-achievement:create");
    private static final String VALID_JSON = "{\"competition_name\":\"孤儿测试竞赛\",\"winner_name\":\"张三\"}";
    private static final byte[] JPEG = {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0, 0x55, 0x66};
    /**
     * 本类独占的 JPEG 字节:文件按内容寻址,若与其它测试类共用同一段字节会落同一路径,
     * 对方测试造的引用行会让本类"删前查引用"判定仍被引用 —— 代码正确但用例互相污染。
     * 独占字节从根上避免撞路径。
     */
    private static final byte[] EXCLUSIVE_JPEG =
            {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0, (byte) 0x7A, (byte) 0x7B, (byte) 0x7C};

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
    private PendingAchievementMapper pendingMapper;
    @Autowired
    private cn.iocoder.yudao.module.business.service.pendingsubmission.PendingSubmissionService
            pendingSubmissionService;
    @Autowired
    private cn.iocoder.yudao.module.business.service.template.TemplateService templateService;
    @Autowired
    private cn.iocoder.yudao.module.business.service.file.AwardieFileStorage fileStorage;
    @Autowired
    private org.springframework.transaction.support.TransactionTemplate transactionTemplate;

    private final ObjectMapper om = new ObjectMapper();
    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();
    private String studentToken;

    @BeforeEach
    void setUp() throws Exception {
        TenantContextHolder.setTenantId(TENANT_ID);
        seedUser();
        studentToken = login();
        TenantContextHolder.setTenantId(TENANT_ID);
        // 共享库:模板表与竞赛表也必须在 BeforeEach 清。本类的共享引用用例会往模板表插行,
        // 若上一轮 @AfterEach 因异常未执行,残留会让本轮"无引用应回收"用例查到引用而正确地不删 ——
        // 代码没错但用例互相污染。BeforeEach 与 AfterEach 双清才自洽。
        cleanBusinessTables();
        clearFiles();
    }

    @AfterEach
    void clean() {
        cleanBusinessTables();
        clearFiles();
        TenantContextHolder.clear();
    }

    /**
     * 共享库清理:待审表、模板表(共享引用用例会插行)、竞赛表
     *
     * <p>待审表必须**物理删**:pendingMapper.delete(null) 是 MyBatis-Plus 逻辑删除,
     * 行会永久残留(deleted=1),后续用例里"取第一条待审行"就会拿到历史行,断言落空。
     * 测试要的是干净起点,不是软删。
     */
    private void cleanBusinessTables() {
        jdbcTemplate.update("DELETE FROM awardie_pending_achievements");
        jdbcTemplate.update("DELETE FROM awardie_achievement_audit_log");
        jdbcTemplate.update("DELETE FROM awardie_templates");
        jdbcTemplate.update("DELETE FROM awardie_competitions");
    }

    private void clearFiles() {
        Path root = Path.of(FILE_ROOT);
        if (!Files.exists(root)) {
            return;
        }
        try (Stream<Path> walk = Files.walk(root)) {
            walk.sorted(Comparator.reverseOrder()).forEach(p -> {
                try {
                    Files.deleteIfExists(p);
                } catch (Exception ignored) {
                    // 清理失败不阻塞断言
                }
            });
        } catch (Exception ignored) {
            // 目录不存在
        }
    }

    private List<Path> filesOnDisk() throws IOException {
        Path root = Path.of(FILE_ROOT);
        if (!Files.exists(root)) {
            return List.of();
        }
        try (Stream<Path> walk = Files.walk(root)) {
            return walk.filter(Files::isRegularFile).toList();
        }
    }

    private void seedUser() {
        AdminUserDO user = new AdminUserDO();
        user.setUsername(STUDENT);
        user.setPassword(bcrypt.encode(PASSWORD));
        user.setNickname("孤儿测试-" + STUDENT);
        user.setStatus(0);
        user.setTenantId(TENANT_ID);
        AdminUserDO existing = userMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getUsername, STUDENT));
        Long userId;
        if (existing == null) {
            userMapper.insert(user);
            userId = user.getId();
        } else {
            userId = existing.getId();
            existing.setPassword(user.getPassword());
            userMapper.updateById(existing);
        }
        Set<Long> menuIds = PERMISSIONS.stream()
                .map(menuMapper::selectListByPermission)
                .flatMap(List::stream)
                .map(MenuDO::getId)
                .collect(Collectors.toSet());
        assertThat(menuIds).as("提交流权限点缺失——请先执行 awardie-business.sql + menus + user-domain")
                .hasSize(PERMISSIONS.size());
        permissionService.assignUserRole(userId, Set.of(STUDENT_ROLE));
    }

    private String login() throws Exception {
        MvcResult result = mockMvc.perform(post("/admin-api/system/auth/login")
                        .contentType(MediaType.APPLICATION_JSON).header("tenant-id", "1")
                        .content("{\"username\":\"" + STUDENT + "\",\"password\":\"" + PASSWORD + "\"}"))
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

    private JsonNode submit(String filename, byte[] bytes, String json) throws Exception {
        MockMultipartFile file = new MockMultipartFile("file", filename, MediaType.IMAGE_JPEG_VALUE, bytes);
        return call(multipart(BASE + "/submit").file(file)
                .param("achievementType", "award").param("data", json)
                .headers(headers(studentToken)));
    }

    @Test
    void firstSubmissionWritesExactlyOneFile() throws Exception {
        JsonNode body = submit("首次.jpg", JPEG, VALID_JSON);
        assertThat(body.path("code").asInt()).isZero();
        assertThat(filesOnDisk()).as("首次提交应落一个文件").hasSize(1);
    }

    @Test
    void duplicateSubmissionDoesNotWriteNewFile() throws Exception {
        assertThat(submit("重复.jpg", JPEG, VALID_JSON).path("code").asInt()).isZero();
        long filesAfterFirst = filesOnDisk().size();
        assertThat(filesAfterFirst).isEqualTo(1);

        // 重复提交:去重前置后应在落盘之前就拒,文件数不变
        JsonNode dup = submit("重复-改名.jpg", JPEG, VALID_JSON);
        assertThat(dup.path("code").asInt()).isEqualTo(1003002001);
        assertThat(filesOnDisk()).as("重复提交不应新增文件").hasSize((int) filesAfterFirst);
    }

    @Test
    void rollbackReclaimsOrphanFile() throws Exception {
        // 直接验补偿装置:在事务里调 submit 后强制回滚,文件必须被回收。
        // 这比"模拟孤儿态"更真:走的是真实的 TransactionSynchronization 钩子。
        transactionTemplate.executeWithoutResult(status -> {
            try {
                pendingSubmissionService.submit(1L, "student", "award", "回滚.jpg", EXCLUSIVE_JPEG,
                        VALID_JSON, STUDENT, "孤儿测试");
            } catch (IOException e) {
                throw new IllegalStateException("提交不应在落盘阶段失败", e);
            }
            status.setRollbackOnly();
        });
        assertThat(filesOnDisk()).as("回滚后文件应被回收").isEmpty();
        assertThat(pendingMapper.selectCount(null)).as("回滚后不应有库行").isZero();
    }

    @Test
    void sharedContentFileIsNotReclaimedWhenStillReferenced() throws Exception {
        assertThat(submit("共享.jpg", JPEG, VALID_JSON).path("code").asInt()).isZero();
        List<Path> files = filesOnDisk();
        assertThat(files).hasSize(1);
        String filePath = files.get(0).getFileName().toString();

        // 同一张图也被一张模板引用(内容寻址下完全可能:管理员拿奖状样本图当模板样本)
        jdbcTemplate.update("INSERT INTO awardie_competitions (competition_name, tenant_id)"
                + " VALUES ('共享竞赛', 1)");
        Long comp = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_competitions WHERE competition_name='共享竞赛' ORDER BY id DESC LIMIT 1",
                Long.class);
        jdbcTemplate.update("INSERT INTO awardie_templates (template_type, competition_id, granted_role,"
                + " min_length, max_length, keywords, language, need_translate, sample_image_path, tenant_id)"
                + " VALUES ('AWARD', ?, '学生', 0, 0, '[]', 'zh', b'0', ?, 1)", comp, filePath);
        Long templateId = jdbcTemplate.queryForObject(
                "SELECT id FROM awardie_templates WHERE sample_image_path = ?", Long.class, filePath);

        // 走真实 service 删除:模板逻辑删除 + 样本图回收钩子,回收前必须查引用
        templateService.deleteTemplate(templateId);

        // 模板已删,但文件因"仍被待审行引用"而保留
        assertThat(jdbcTemplate.queryForObject("SELECT deleted FROM awardie_templates WHERE id = ?",
                String.class, templateId)).isEqualTo("1");
        assertThat(Files.exists(Path.of(FILE_ROOT).toAbsolutePath().resolve(filePath)))
                .as("被其他记录引用的文件不得被回收").isTrue();
    }

    @Test
    void unreferencedFileIsReclaimedAfterWithdrawal() throws Exception {
        // 用独占字节:不与其它测试类撞内容寻址路径
        JsonNode submitted = submit("独占.jpg", EXCLUSIVE_JPEG, VALID_JSON);
        assertThat(submitted.path("code").asInt()).isZero();
        // 按本次提交的 id 取路径,不用 LIMIT 1:库里有历史逻辑删除行,取第一条会拿到别人的路径
        long id = submitted.at("/data/id").asLong();
        String ownPath = jdbcTemplate.queryForObject(
                "SELECT file_path FROM awardie_pending_achievements WHERE id = ?", String.class, id);
        Path ownFile = Path.of(FILE_ROOT).toAbsolutePath().resolve(ownPath);
        assertThat(Files.exists(ownFile)).as("提交后文件应存在").isTrue();

        // 撤回后该文件已无任何引用(物理删行,模拟引用彻底消失),回收应放行
        jdbcTemplate.update("DELETE FROM awardie_pending_achievements WHERE id = ?", id);
        fileStorage.deleteIfUnreferenced(ownPath);

        assertThat(Files.exists(ownFile)).as("无引用文件应被回收").isFalse();
    }

}
