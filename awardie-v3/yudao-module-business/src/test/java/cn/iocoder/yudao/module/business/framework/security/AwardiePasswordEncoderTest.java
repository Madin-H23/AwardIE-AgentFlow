package cn.iocoder.yudao.module.business.framework.security;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * AwardiePasswordEncoder 纯函数单测(批2):scrypt 存量哈希兼容 + BCrypt 委托。
 */
class AwardiePasswordEncoderTest {

    private final AwardiePasswordEncoder encoder = new AwardiePasswordEncoder(4);

    @Test
    void matchesWerkzeugScryptHash() {
        String hash = werkzeugScrypt("V2Pass@123");
        assertThat(hash).startsWith("scrypt:32768:8:1$");
        assertThat(encoder.matches("V2Pass@123", hash)).isTrue();
        assertThat(encoder.matches("WrongPass", hash)).isFalse();
    }

    /** v2 实测存量哈希(awardie_dev users id=1832,口令 Mayy123;python hashlib.scrypt 已验证匹配) */
    private static final String V2_REAL_HASH =
            "scrypt:32768:8:1$JnaFlMm5m3GR9YNn$7d6f359e70cd5c49c884b94332b82cd7871c6a9b72f27c36dde33975c192ef268c04977724c7f94384221f0eb3627358694084b354cae12df32d5d091c982fbc";

    @Test
    void matchesRealV2Hash() {
        assertThat(encoder.matches("Mayy123", V2_REAL_HASH)).isTrue();
        assertThat(encoder.matches("wrong", V2_REAL_HASH)).isFalse();
    }

    @Test
    void encodeAndMatchesBcrypt() {
        String hash = encoder.encode("V3Pass@123");
        assertThat(hash).startsWith("$2");
        assertThat(encoder.matches("V3Pass@123", hash)).isTrue();
        assertThat(encoder.matches("WrongPass", hash)).isFalse();
    }

    @Test
    void rejectsGarbage() {
        assertThat(encoder.matches("x", null)).isFalse();
        assertThat(encoder.matches("x", "not-a-hash")).isFalse();
        assertThat(encoder.matches("x", "scrypt:bad")).isFalse();
    }

    @Test
    void upgradeEncodingOnlyForScrypt() {
        assertThat(encoder.upgradeEncoding("scrypt:32768:8:1$abc$def")).isTrue();
        assertThat(encoder.upgradeEncoding("$2a$04$abc")).isFalse();
    }

    /** 与 v2 WerkzeugCompatPasswordEncoder.encode 同参生成 werkzeug scrypt 格式。 */
    private static String werkzeugScrypt(String raw) {
        String alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
        SecureRandom random = new SecureRandom();
        int saltLength = 16;
        StringBuilder salt = new StringBuilder(saltLength);
        for (int i = 0; i < saltLength; i++) {
            salt.append(alphabet.charAt(random.nextInt(alphabet.length())));
        }
        byte[] dk = org.bouncycastle.crypto.generators.SCrypt.generate(
                raw.getBytes(StandardCharsets.UTF_8),
                salt.toString().getBytes(StandardCharsets.UTF_8), 32768, 8, 1, 64);
        StringBuilder hex = new StringBuilder(dk.length * 2);
        for (byte b : dk) {
            hex.append(String.format("%02x", b));
        }
        return "scrypt:32768:8:1$" + salt + "$" + hex;
    }
}
