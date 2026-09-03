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

    private final Path root;

    public record StoredFile(String relativePath, String sha256, long size) {}

    /** 批 3:存储根参数化(默认 files/v2);测试注入 target/test-files,根除与运行后端的两处 CWD 分裂。 */
    public FileStorageService(@org.springframework.beans.factory.annotation.Value("${files.root:files/v2}") String root) {
        this.root = Path.of(root);
    }

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

    /** 按相对路径读回文件字节(批 1 文件域收敛:templates 样本图等只存路径的域共用)。 */
    public byte[] readAll(String relativePath) throws IOException {
        return Files.readAllBytes(resolve(relativePath));
    }

    /** 存储扩展名 → Content-Type(存储前经 assertAllowed 白名单,扩展名即可信)。 */
    public String contentTypeOf(String relativePath) {
        return switch (extOf(relativePath)) {
            case "jpg", "jpeg" -> "image/jpeg";
            case "png" -> "image/png";
            case "pdf" -> "application/pdf";
            default -> "application/octet-stream";
        };
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
