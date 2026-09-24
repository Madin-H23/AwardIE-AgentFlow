package cn.iocoder.yudao.module.business.service.file;

import cn.iocoder.yudao.framework.common.exception.ServiceException;
import cn.iocoder.yudao.module.business.service.reference.FileReferenceChecker;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * 批4 文件域单测 + 批7 删除能力:三校验 + sha256 去重 + 路径越界防护 + contentType 映射 +
 * 删除幂等 + 内容寻址下的"删前查引用"。
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
    private FileReferenceChecker referenceChecker;

    @BeforeEach
    void setUp() throws IOException {
        storage = new AwardieFileStorage(TEST_ROOT);
        referenceChecker = mock(FileReferenceChecker.class);
        storage.setReferenceChecker(referenceChecker);
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

    // ========== 批7:删除能力 ==========

    @Test
    void sha256HexMatchesStoreHashWithoutWritingFile() throws IOException {
        String hash = storage.sha256Hex(PDF_BYTES);
        assertThat(hash).hasSize(64);
        // 只算哈希不落盘:目录里不应出现任何文件
        Path root = Path.of(TEST_ROOT);
        java.util.List<Path> filesOnDisk = Files.exists(root) ? listFiles(root) : java.util.List.of();
        assertThat(filesOnDisk).as("只算哈希不应落盘").isEmpty();
        // 与 store 返回的哈希一致(去重前置依赖两者相等)
        assertThat(storage.store("a.pdf", PDF_BYTES).sha256()).isEqualTo(hash);
    }

    @Test
    void deleteRemovesFile() throws IOException {
        AwardieFileStorage.StoredFile stored = storage.store("a.jpg", JPEG_BYTES);
        assertThat(Files.exists(storage.resolve(stored.relativePath()))).isTrue();
        storage.delete(stored.relativePath());
        assertThat(Files.exists(storage.resolve(stored.relativePath()))).isFalse();
    }

    @Test
    void deleteIsIdempotentForMissingFile() throws IOException {
        // 幂等:删不存在的文件不抛异常(补偿逻辑可能被重复触发)
        storage.delete("never-existed.jpg");
        storage.delete("never-existed.jpg");
    }

    @Test
    void deleteRejectsDirectoryTraversal() {
        assertThatThrownBy(() -> storage.delete("../../etc/passwd"))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("非法文件路径");
    }

    @Test
    void deleteIfUnreferencedRemovesWhenNoReference() throws IOException {
        AwardieFileStorage.StoredFile stored = storage.store("a.jpg", JPEG_BYTES);
        when(referenceChecker.isReferenced(stored.relativePath())).thenReturn(false);
        assertThat(storage.deleteIfUnreferenced(stored.relativePath())).isTrue();
        assertThat(Files.exists(storage.resolve(stored.relativePath()))).isFalse();
    }

    @Test
    void deleteIfUnreferencedKeepsFileStillReferenced() throws IOException {
        // 内容寻址的核心保护:同内容文件可能正被别的记录引用,此时绝不能删
        AwardieFileStorage.StoredFile stored = storage.store("a.jpg", JPEG_BYTES);
        when(referenceChecker.isReferenced(stored.relativePath())).thenReturn(true);
        assertThat(storage.deleteIfUnreferenced(stored.relativePath())).isFalse();
        assertThat(Files.exists(storage.resolve(stored.relativePath()))).isTrue();
        assertThat(storage.readAll(stored.relativePath())).isEqualTo(JPEG_BYTES);
    }

    // ========== 批7:引用清单完整性(清单漏表 = 补偿删除会误删) ==========

    @Test
    void filePathReferenceListCoversEveryPathColumn() {
        // 规格要求覆盖全部存路径的表;列名不统一,漏一条就会误删别人还在用的文件。
        // 这里把清单钉死:新增存文件的表时必须同步加进来,否则本例会红。
        assertThat(cn.iocoder.yudao.module.business.service.reference.FileReferenceChecker.FILE_PATH_REFERENCES)
                .containsEntry("awardie_pending_achievements", "file_path")
                .containsEntry("awardie_laboratory_downloads", "file_path")
                .containsEntry("awardie_laboratory_images", "image_path")
                .containsEntry("awardie_awards", "certificate_path")
                // 专利/软著的证书列名是 certificate_file(不是 file_path/certificate_path)
                .containsEntry("awardie_patents", "certificate_file")
                .containsEntry("awardie_software_copyrights", "certificate_file")
                .containsEntry("awardie_other_files", "file_path")
                .containsEntry("awardie_templates", "sample_image_path");
        // 清单不可变:运行期被改坏会让补偿逻辑失去防护
        assertThatThrownBy(() -> cn.iocoder.yudao.module.business.service.reference.FileReferenceChecker
                .FILE_PATH_REFERENCES.put("x", "y"))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    private java.util.List<Path> listFiles(Path root) throws IOException {
        try (Stream<Path> walk = Files.walk(root)) {
            return walk.filter(Files::isRegularFile).toList();
        }
    }
}
