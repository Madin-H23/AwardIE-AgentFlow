package cn.iocoder.yudao.module.business.framework.security;

import org.bouncycastle.crypto.generators.SCrypt;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Primary;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * AwardIE 口令编码器(批2:scrypt 兼容 + BCrypt 新生)。
 *
 * 背景:v2 存量 1834 条口令为 werkzeug scrypt 格式("scrypt:32768:8:1$salt$hexhash"),
 * ETL 原样迁入后需能直接登录;芋道原生 BCrypt。matches() 按前缀分发:
 * - scrypt:* → BouncyCastle SCrypt 逐参复算(参数从哈希串解析),常量时间比较;
 * - 其余($2* 等)→ 委托 BCryptPasswordEncoder。
 * encode() 恒为 BCrypt(新口令/升级后的统一格式);upgradeEncoding(scrypt)=true
 * (与 v2 的"恒 false"不同——v1/v2/v3 各自独立数据库,ADR-0002 推论的上游约束在 v3 不适用)。
 *
 * **Bean 命名=crucial**:芋道 {@code AdminUserServiceImpl} 等用 {@code @Resource} 按名注入 PasswordEncoder,
 * 目标 bean 名 "passwordEncoder"。本 bean 保持默认名(awardiePasswordEncoder)+@Primary;上游同名 bean 由
 * {@link PasswordEncoderBeanOverride} 摘除后,@Resource 按名落空会回退按类型注入,唯一候选即本 bean
 * (切勿把本 bean 也命名 passwordEncoder——自动配置在 ConfigurationClassPostProcessor 内注册,BFPP 来不及
 * 摘除,同名直接 BeanDefinitionOverrideException)。
 *
 * 移植自 v2 {@code com.awardie.auth.security.WerkzeugCompatPasswordEncoder},去其 bcrypt 历史兜底分支。
 *
 * @author AwardIE
 */
@Primary
@Component
public class AwardiePasswordEncoder implements PasswordEncoder {

    /** v2 存量 werkzeug scrypt 哈希前缀 */
    private static final String SCRYPT_PREFIX = "scrypt:";
    /** BCrypt 哈希前缀 */
    private static final String BCRYPT_PREFIX = "$2";

    private static final Pattern SCRYPT = Pattern.compile("^scrypt:(\\d+):(\\d+):(\\d+)\\$([^$]+)\\$([0-9a-fA-F]+)$");

    private final BCryptPasswordEncoder bcrypt;

    public AwardiePasswordEncoder(@Value("${yudao.security.password-encoder-length:4}") int strength) {
        this.bcrypt = new BCryptPasswordEncoder(strength);
    }

    @Override
    public String encode(CharSequence rawPassword) {
        return bcrypt.encode(rawPassword);
    }

    @Override
    public boolean matches(CharSequence rawPassword, String encodedPassword) {
        if (encodedPassword == null) {
            return false;
        }
        if (encodedPassword.startsWith(BCRYPT_PREFIX)) {
            return bcrypt.matches(rawPassword, encodedPassword);
        }
        Matcher m = SCRYPT.matcher(encodedPassword);
        if (!m.matches()) {
            return false;
        }
        int n = Integer.parseInt(m.group(1));
        int r = Integer.parseInt(m.group(2));
        int p = Integer.parseInt(m.group(3));
        byte[] salt = m.group(4).getBytes(StandardCharsets.UTF_8);
        byte[] expected = hexToBytes(m.group(5));
        byte[] actual = SCrypt.generate(
                rawPassword.toString().getBytes(StandardCharsets.UTF_8), salt, n, r, p, expected.length);
        return MessageDigest.isEqual(expected, actual);
    }

    @Override
    public boolean upgradeEncoding(String encodedPassword) {
        return encodedPassword != null && encodedPassword.startsWith(SCRYPT_PREFIX);
    }

    private static byte[] hexToBytes(String hex) {
        int len = hex.length() / 2;
        byte[] out = new byte[len];
        for (int i = 0; i < len; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }
}
