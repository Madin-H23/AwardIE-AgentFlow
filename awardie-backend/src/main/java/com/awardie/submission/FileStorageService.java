package com.awardie.submission;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.HexFormat;

import org.springframework.stereotype.Service;

/** v2 文件存储:files/v2/ 目录,SHA-256 去重,下载一律 attachment(BR-7)。 */
@Service
public class FileStorageService {

    public static final long MAX_SIZE = 10L * 1024 * 1024; // 10MB,沿 v1
    private static final byte[] JPEG = {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF};
    private static final byte[] PNG = {(byte) 0x89, 0x50, 0x4E, 0x47};
    private static final byte[] PDF = {0x25, 0x50, 0x44, 0x46};

    private final Path root = Path.of("files", "v2");

    public record StoredFile(String relativePath, String sha256, long size) {}

    /** 白名单扩展名 + 大小上限 + 魔术字节三校验(顺序沿 v1:先类型后内容)。 */
    public void assertAllowed(String filename, byte[] bytes) {
        String ext = extOf(filename);
        if (!ext.matches("jpg|jpeg|png|pdf")) {
            throw new IllegalArgumentException("不支持的文件类型,仅允许 jpg/jpeg/png/pdf");
        }
        if (bytes.length > MAX_SIZE) {
            throw new IllegalArgumentException("文件超过 10MB 上限");
        }
        if (!magicMatches(bytes)) {
            throw new IllegalArgumentException("文件内容与扩展名不符(魔术字节校验失败)");
        }
    }

    public StoredFile store(String filename, byte[] bytes) throws IOException {
        Files.createDirectories(root);
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IllegalStateException("JVM 缺少 SHA-256", e);
        }
        String sha256 = HexFormat.of().formatHex(digest.digest(bytes));
        String target = sha256.substring(0, 16) + "." + extOf(filename);
        Path dest = root.resolve(target);
        Files.copy(new java.io.ByteArrayInputStream(bytes), dest, StandardCopyOption.REPLACE_EXISTING);
        return new StoredFile(dest.toString(), sha256, bytes.length);
    }

    public Path resolve(String relativePath) {
        Path p = Path.of(relativePath).normalize();
        if (!p.startsWith(root)) {
            throw new IllegalArgumentException("非法路径");
        }
        return p;
    }

    private boolean magicMatches(byte[] bytes) {
        return startsWith(bytes, JPEG) || startsWith(bytes, PNG) || startsWith(bytes, PDF);
    }

    private boolean startsWith(byte[] data, byte[] prefix) {
        if (data.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (data[i] != prefix[i]) {
                return false;
            }
        }
        return true;
    }

    private String extOf(String filename) {
        int dot = filename == null ? -1 : filename.lastIndexOf('.');
        return dot < 0 ? "" : filename.substring(dot + 1).toLowerCase();
    }
}
