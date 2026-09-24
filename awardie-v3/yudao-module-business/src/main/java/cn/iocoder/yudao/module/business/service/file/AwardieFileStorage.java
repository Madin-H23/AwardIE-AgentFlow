package cn.iocoder.yudao.module.business.service.file;

import cn.iocoder.yudao.module.business.enums.ErrorCodeConstants;
import cn.iocoder.yudao.module.business.service.reference.FileReferenceChecker;
import jakarta.annotation.Resource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;
import java.util.Set;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;

/**
 * AwardIE 文件存储(批4):目录存储 + SHA-256 去重 + 三校验
 *
 * <p>为何不复用芋道 infra 文件模块:它的上传路径不做魔术字节校验、不做 sha256 去重,
 * 大小限制依赖云服务商——三校验与去重是 AwardIE 自 v1 以来的业务硬要求,不能丢。
 *
 * <p>存储根参数化:默认 files/v3,测试注入 target/test-files(避免污染开发目录与 CWD 分裂)。
 *
 * @author AwardIE
 */
@Component
public class AwardieFileStorage {

    /** 文件大小上限 10MB(沿 v1/v2) */
    public static final long MAX_SIZE = 10L * 1024 * 1024;
    /** sha256 文件名取前 16 位(v2 行为) */
    private static final int FILE_NAME_HASH_LENGTH = 16;

    /** 扩展名白名单(v2:jpg/jpeg/png/pdf) */
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of("jpg", "jpeg", "png", "pdf");
    /** 存储扩展名 → Content-Type(存前已过白名单,扩展名可信) */
    private static final Map<String, String> CONTENT_TYPES = Map.of(
            "jpg", "image/jpeg", "jpeg", "image/jpeg", "png", "image/png", "pdf", "application/pdf");
    private static final String DEFAULT_CONTENT_TYPE = "application/octet-stream";

    private static final byte[] JPEG = {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF};
    private static final byte[] PNG = {(byte) 0x89, 0x50, 0x4E, 0x47};
    private static final byte[] PDF = {0x25, 0x50, 0x44, 0x46};

    private final Path root;

    @Resource
    private FileReferenceChecker referenceChecker;

    public AwardieFileStorage(@Value("${awardie.file.root:files/v3}") String root) {
        this.root = Path.of(root).toAbsolutePath().normalize();
    }

    /** 供纯单测注入引用检查器(Spring 容器里由 @Resource 注入) */
    void setReferenceChecker(FileReferenceChecker referenceChecker) {
        this.referenceChecker = referenceChecker;
    }

    /**
     * 落盘结果
     *
     * @param relativePath 相对存储根的路径
     * @param sha256       内容哈希(小写 hex)
     * @param size         字节数
     */
    public record StoredFile(String relativePath, String sha256, long size) {
    }

    /**
     * 白名单扩展名 + 大小上限 + 魔术字节三校验(顺序沿 v1:先类型后大小再内容)
     *
     * @param filename 原始文件名(取扩展名)
     * @param bytes    文件内容
     */
    public void assertAllowed(String filename, byte[] bytes) {
        if (!ALLOWED_EXTENSIONS.contains(extOf(filename))) {
            throw exception(ErrorCodeConstants.FILE_TYPE_NOT_ALLOWED);
        }
        if (bytes.length > MAX_SIZE) {
            throw exception(ErrorCodeConstants.FILE_TOO_LARGE);
        }
        if (!magicMatches(bytes)) {
            throw exception(ErrorCodeConstants.FILE_CONTENT_MISMATCH);
        }
    }

    /**
     * 落盘(同内容同扩展名覆盖写,内容一致故无副作用——即 v2 的 sha256 去重)
     *
     * @param filename 原始文件名(取扩展名)
     * @param bytes    文件内容
     * @return 落盘结果
     * @throws IOException 写盘失败
     */
    public StoredFile store(String filename, byte[] bytes) throws IOException {
        Files.createDirectories(root);
        String sha256 = hashOf(bytes);
        String target = sha256.substring(0, FILE_NAME_HASH_LENGTH) + "." + extOf(filename);
        Path dest = root.resolve(target).normalize();
        if (!dest.startsWith(root)) {
            throw exception(ErrorCodeConstants.FILE_PATH_ILLEGAL);
        }
        try (InputStream in = new java.io.ByteArrayInputStream(bytes)) {
            Files.copy(in, dest, StandardCopyOption.REPLACE_EXISTING);
        }
        return new StoredFile(root.relativize(dest).toString().replace('\\', '/'), sha256, bytes.length);
    }

    /**
     * 只算内容哈希,不落盘
     *
     * <p>用于提交链的"去重前置":去重判据是 file_hash,而哈希可由字节直接算出,
     * 不必先落盘就知道是否重复——这消除了"重复提交"这个最常见的孤儿文件场景。
     *
     * @param bytes 文件内容
     * @return 内容哈希(小写 hex)
     */
    public String sha256Hex(byte[] bytes) {
        return hashOf(bytes);
    }

    /**
     * 解析相对路径为绝对路径,并防目录穿越
     *
     * <p>删除能力加入后多了一道防线:空串与 "." 会解析成存储根目录本身,
     * 若被 delete 命中就是删整个存储根,故这里直接拒绝。
     *
     * @param relativePath 相对存储根的路径
     * @return 绝对路径
     */
    public Path resolve(String relativePath) {
        if (relativePath == null || relativePath.isBlank()) {
            throw exception(ErrorCodeConstants.FILE_PATH_ILLEGAL);
        }
        Path resolved = root.resolve(relativePath).normalize();
        if (!resolved.startsWith(root) || resolved.equals(root)) {
            throw exception(ErrorCodeConstants.FILE_PATH_ILLEGAL);
        }
        return resolved;
    }

    /**
     * 读回文件字节
     *
     * @param relativePath 相对存储根的路径
     * @return 文件内容
     * @throws IOException 读盘失败
     */
    public byte[] readAll(String relativePath) throws IOException {
        return Files.readAllBytes(resolve(relativePath));
    }

    /**
     * 存储扩展名 → Content-Type(存前已过白名单,扩展名可信)
     *
     * @param relativePath 相对存储根的路径
     * @return Content-Type
     */
    public String contentTypeOf(String relativePath) {
        return CONTENT_TYPES.getOrDefault(extOf(relativePath), DEFAULT_CONTENT_TYPE);
    }

    /**
     * 删除文件(幂等:文件不存在不报错)
     *
     * <p>内容寻址的坑:同内容同扩展名共用一个路径,直接删可能打断其他记录的引用。
     * 补偿式删除请走 {@link #deleteIfUnreferenced};只有确认独占时才用本方法。
     *
     * @param relativePath 相对存储根的路径
     * @throws IOException 删除失败
     */
    public void delete(String relativePath) throws IOException {
        Files.deleteIfExists(resolve(relativePath));
    }

    /**
     * 仅当该路径无任何业务记录引用时才删除(内容寻址下的安全删除)
     *
     * <p>用于两类补偿:提交入库失败回滚、模板删除回收样本图。两者都可能出现
     * "同内容文件已被别的记录引用"的情况,故删前必须查引用。
     *
     * @param relativePath 相对存储根的路径
     * @return true=已删除(或本来不存在);false=仍被引用,已保留
     * @throws IOException 删除失败
     */
    public boolean deleteIfUnreferenced(String relativePath) throws IOException {
        if (referenceChecker.isReferenced(relativePath)) {
            return false;
        }
        delete(relativePath);
        return true;
    }

    private static String hashOf(byte[] bytes) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(bytes));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("JVM 缺少 SHA-256", e);
        }
    }

    private static boolean magicMatches(byte[] bytes) {
        return startsWith(bytes, JPEG) || startsWith(bytes, PNG) || startsWith(bytes, PDF);
    }

    private static boolean startsWith(byte[] data, byte[] prefix) {
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

    private static String extOf(String filename) {
        int dot = filename == null ? -1 : filename.lastIndexOf('.');
        return dot < 0 ? "" : filename.substring(dot + 1).toLowerCase();
    }

}
