package com.awardie.auth.security;

import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.bouncycastle.crypto.generators.SCrypt;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * werkzeug scrypt 完全兼容编码器(v1 存量 1834 条口令与 v2 新编口令统一格式)。
 *
 * matches 按前缀分发:scrypt:* → BouncyCastle scrypt 逐参复算;$2* → BCrypt(历史残留兜底)。
 * encode 恒为 **werkzeug scrypt 格式**("scrypt:32768:8:1$salt$hexhash",salt 为随机 ASCII 原文)——
 * 双库共存期(ADR-0002)v1 Flask 仍要登录同一批用户,改写为裸 BCrypt 会使 v1 失能(实测 werkzeug
 * "Invalid hash method"),故 v2 不做任何格式升级:upgradeEncoding 恒 false。
 */
@Component
public class WerkzeugCompatPasswordEncoder implements PasswordEncoder {

    private static final Pattern SCRYPT = Pattern.compile("^scrypt:(\\d+):(\\d+):(\\d+)\\$([^$]+)\\$([0-9a-fA-F]+)$");
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final String SALT_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();

    @Override
    public String encode(CharSequence rawPassword) {
        StringBuilder salt = new StringBuilder(16);
        for (int i = 0; i < 16; i++) {
            salt.append(SALT_ALPHABET.charAt(RANDOM.nextInt(SALT_ALPHABET.length())));
        }
        byte[] dk = SCrypt.generate(
                rawPassword.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8),
                salt.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8), 32768, 8, 1, 64);
        StringBuilder hex = new StringBuilder(dk.length * 2);
        for (byte b : dk) {
            hex.append(String.format("%02x", b));
        }
        return "scrypt:32768:8:1$" + salt + "$" + hex;
    }

    @Override
    public boolean matches(CharSequence rawPassword, String encodedPassword) {
        if (encodedPassword == null) {
            return false;
        }
        if (encodedPassword.startsWith("$2")) {
            return bcrypt.matches(rawPassword, encodedPassword);
        }
        Matcher m = SCRYPT.matcher(encodedPassword);
        if (!m.matches()) {
            return false;
        }
        int n = Integer.parseInt(m.group(1));
        int r = Integer.parseInt(m.group(2));
        int p = Integer.parseInt(m.group(3));
        byte[] salt = m.group(4).getBytes(java.nio.charset.StandardCharsets.UTF_8);
        byte[] expected = hexToBytes(m.group(5));
        byte[] actual = SCrypt.generate(
                rawPassword.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8), salt, n, r, p, expected.length);
        return MessageDigest.isEqual(expected, actual);
    }

    /** 恒 false:双库共存期不得改写口令哈希格式(否则 v1 werkzeug 无法验证,ADR-0002 推论)。 */
    @Override
    public boolean upgradeEncoding(String encodedPassword) {
        return false;
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
