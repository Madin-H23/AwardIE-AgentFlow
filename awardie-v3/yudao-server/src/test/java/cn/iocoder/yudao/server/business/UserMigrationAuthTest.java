package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.system.dal.dataobject.user.AdminUserDO;
import cn.iocoder.yudao.module.system.dal.mysql.user.AdminUserMapper;
import cn.iocoder.yudao.server.YudaoServerApplication;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.bouncycastle.crypto.generators.SCrypt;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;

/**
 * 批2 用户域集成测试:scrypt 存量口令兼容 + 登录自动升级 BCrypt。
 *
 * 场景(对应 00-需求 R1):ETL 原样迁入的 scrypt 用户,用 v2 原口令登录 → 成功且哈希升级为
 * BCrypt($2 前缀)→ 二次登录仍成功;bcrypt 用户(新生/已升级)不受影响。
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        "spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.dynamic.datasource.master.username=awardie_v3"
})
@AutoConfigureMockMvc
class UserMigrationAuthTest {

    private static final long TENANT_ID = 1L;
    private static final String SCRYPT_USER = "scryptmig001";
    private static final String SCRYPT_PASSWORD = "V2Pass@123";
    private static final String BCRYPT_USER = "bcryptmig001";
    private static final String BCRYPT_PASSWORD = "V3Pass@123";

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private AdminUserMapper userMapper;

    private final ObjectMapper om = new ObjectMapper();

    @BeforeEach
    void seedUsers() {
        TenantContextHolder.setTenantId(TENANT_ID);
        deleteIfExists(SCRYPT_USER);
        deleteIfExists(BCRYPT_USER);
        // scrypt 用户:用 v2 werkzeug 同参数生成存量格式哈希
        AdminUserDO scryptUser = new AdminUserDO();
        scryptUser.setUsername(SCRYPT_USER);
        scryptUser.setPassword(werkzeugScrypt(SCRYPT_PASSWORD));
        scryptUser.setNickname("scrypt 迁移用户");
        scryptUser.setStatus(0);
        scryptUser.setTenantId(TENANT_ID);
        userMapper.insert(scryptUser);
        // bcrypt 用户:新生格式
        AdminUserDO bcryptUser = new AdminUserDO();
        bcryptUser.setUsername(BCRYPT_USER);
        bcryptUser.setPassword(new BCryptPasswordEncoder().encode(BCRYPT_PASSWORD));
        bcryptUser.setNickname("bcrypt 用户");
        bcryptUser.setStatus(0);
        bcryptUser.setTenantId(TENANT_ID);
        userMapper.insert(bcryptUser);
    }

    @AfterEach
    void clearTenant() {
        TenantContextHolder.clear();
    }

    private void deleteIfExists(String username) {
        AdminUserDO exist = userMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getUsername, username));
        if (exist != null) {
            userMapper.deleteById(exist.getId());
        }
    }

    /** v2 werkzeug scrypt 格式("scrypt:32768:8:1$salt$hex"),与 WerkzeugCompatPasswordEncoder.encode 同参。 */
    private static String werkzeugScrypt(String raw) {
        String alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
        java.security.SecureRandom random = new java.security.SecureRandom();
        int saltLength = 16;
        StringBuilder salt = new StringBuilder(saltLength);
        for (int i = 0; i < saltLength; i++) {
            salt.append(alphabet.charAt(random.nextInt(alphabet.length())));
        }
        byte[] dk = SCrypt.generate(raw.getBytes(StandardCharsets.UTF_8),
                salt.toString().getBytes(StandardCharsets.UTF_8), 32768, 8, 1, 64);
        StringBuilder hex = new StringBuilder(dk.length * 2);
        for (byte b : dk) {
            hex.append(String.format("%02x", b));
        }
        return "scrypt:32768:8:1$" + salt + "$" + hex;
    }

    private JsonNode login(String username, String password) throws Exception {
        MvcResult result = mockMvc.perform(post("/admin-api/system/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("tenant-id", "1")
                        .content("{\"username\":\"" + username + "\",\"password\":\"" + password + "\"}"))
                .andReturn();
        return om.readTree(result.getResponse().getContentAsString());
    }

    @Test
    void scryptUserLogsInAndUpgradesToBcrypt() throws Exception {
        // 迁入态断言:前缀为 scrypt
        assertThat(userMapper.selectByUsername(SCRYPT_USER).getPassword()).startsWith("scrypt:");
        // 1) v2 原口令登录成功
        JsonNode first = login(SCRYPT_USER, SCRYPT_PASSWORD);
        assertThat(first.path("code").asInt()).isZero();
        assertThat(first.path("data").path("accessToken").asText()).isNotBlank();
        // 2) 登录后自动升级为 BCrypt(HTTP 请求后租户上下文被过滤器清,断言前重设)
        TenantContextHolder.setTenantId(TENANT_ID);
        assertThat(userMapper.selectByUsername(SCRYPT_USER).getPassword()).startsWith("$2");
        // 3) 二次登录(升级后的 BCrypt)仍成功
        JsonNode second = login(SCRYPT_USER, SCRYPT_PASSWORD);
        assertThat(second.path("code").asInt()).isZero();
    }

    @Test
    void bcryptUserUnaffected() throws Exception {
        JsonNode resp = login(BCRYPT_USER, BCRYPT_PASSWORD);
        assertThat(resp.path("code").asInt()).isZero();
        TenantContextHolder.setTenantId(TENANT_ID);
        assertThat(userMapper.selectByUsername(BCRYPT_USER).getPassword()).startsWith("$2");
    }
}
