package cn.iocoder.yudao.module.business.service.file;

import cn.iocoder.yudao.framework.common.exception.ServiceException;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 批4 文件域单测:三校验 + sha256 去重 + 路径越界防护 + contentType 映射。
 *
 * <p>纯 JUnit(不起 Spring 上下文),存储根指向 target/test-files/awardie-file。
 * 夹具用真实魔术字节构造(jpg/png/pdf),不用默认假文件——避免"因默认值巧合通过"。
 *
 * @author AwardIE
 */
class AwardieFileStorageTest {

    private static final String TEST_ROOT = "target/test-files/awardie-file";

    private static final byte[] JPEG_BYTES = {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0, 0x01, 0x02};
    private static final byte[] PNG_BYTES = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
    private static final byte[] PDF_BYTES = {0x25, 0x50, 0x44, 0x46, 0x2D, 0x31, 0x2E, 0x37};

    private AwardieFileStorage storage;

    @BeforeEach
    void setUp() throws IOException {
        storage = new AwardieFileStorage(TEST_ROOT);
        Path root = Path.of(TEST_ROOT);
        if (Files.exists(root)) {
            try (Stream<Path> walk = Files.walk(root)) {
                walk.sorted(Comparator.reverseOrder()).forEach(p -> {
                    try {
                        Files.deleteIfExists(p);
                    } catch (IOException ignored) {
                        // 清理失败不阻塞断言
                    }
                });
            }
        }
    }

    @AfterEach
    void tearDown() {
        // 单测无外部状态需清理,文件在 @BeforeEach 已清
    }

    @Test
    void storeWritesFileWithHashName() throws IOException {
        AwardieFileStorage.StoredFile stored = storage.store("证书.pdf", PDF_BYTES);
        assertThat(stored.sha256()).hasSize(64);
        assertThat(stored.size()).isEqualTo(PDF_BYTES.length);
        assertThat(stored.relativePath()).endsWith(".pdf");
        assertThat(Files.exists(storage.resolve(stored.relativePath()))).isTrue();
        assertThat(storage.readAll(stored.relativePath())).isEqualTo(PDF_BYTES);
    }

    @Test
    void storeSameContentTwiceHitsSamePath() throws IOException {
        AwardieFileStorage.StoredFile first = storage.store("a.jpg", JPEG_BYTES);
        AwardieFileStorage.StoredFile second = storage.store("b.jpg", JPEG_BYTES);
        // sha256 去重:同内容同扩展名 → 同一路径
        assertThat(second.relativePath()).isEqualTo(first.relativePath());
        assertThat(second.sha256()).isEqualTo(first.sha256());
    }

    @Test
    void assertAllowedRejectsNonWhitelistExtension() {
        assertThatThrownBy(() -> storage.assertAllowed("note.txt", PDF_BYTES))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("仅允许 jpg/jpeg/png/pdf");
    }

    @Test
    void assertAllowedRejectsOversize() {
        byte[] tooBig = new byte[(int) AwardieFileStorage.MAX_SIZE + 1];
        System.arraycopy(PDF_BYTES, 0, tooBig, 0, PDF_BYTES.length);
        assertThatThrownBy(() -> storage.assertAllowed("big.pdf", tooBig))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("10MB");
    }

    @Test
    void assertAllowedRejectsMagicMismatch() {
        // 扩展名 pdf 但内容是文本 → 魔术字节不符
        assertThatThrownBy(() -> storage.assertAllowed("fake.pdf", "not a pdf".getBytes()))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("魔术字节");
    }

    @Test
    void assertAllowedAcceptsRealMagicBytes() {
        storage.assertAllowed("a.jpg", JPEG_BYTES);
        storage.assertAllowed("a.png", PNG_BYTES);
        storage.assertAllowed("a.pdf", PDF_BYTES);
    }

    @Test
    void resolveRejectsDirectoryTraversal() {
        assertThatThrownBy(() -> storage.resolve("../../etc/passwd"))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("非法文件路径");
    }

    @Test
    void contentTypeOfMapsExtensions() {
        assertThat(storage.contentTypeOf("x.jpg")).isEqualTo("image/jpeg");
        assertThat(storage.contentTypeOf("x.jpeg")).isEqualTo("image/jpeg");
        assertThat(storage.contentTypeOf("x.png")).isEqualTo("image/png");
        assertThat(storage.contentTypeOf("x.pdf")).isEqualTo("application/pdf");
        assertThat(storage.contentTypeOf("x.bin")).isEqualTo("application/octet-stream");
    }
}
