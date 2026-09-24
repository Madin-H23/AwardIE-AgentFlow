package cn.iocoder.yudao.module.business.service.reference;

import jakarta.annotation.Resource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * 文件路径引用检查(批7)
 *
 * <p>为什么需要它:文件存储是**内容寻址**(sha256 前 16 位 + 扩展名),同一内容落同一路径。
 * 所以"删除一个文件"绝不能只看发起删除的那个业务行——同一文件可能正被别的记录引用:
 * 同内容的另一个待审行(含已归档/已驳回)、物化后的成果证书、其他成果文件、实验室附件、模板样本图。
 * 无条件删会打断别人的数据,故任何补偿式删除都必须先问"还有谁在用"。
 *
 * <p>口径与 {@link AchievementReferenceChecker} 一致:表不存在则跳过(逐批建表期)、
 * 有 deleted 列则 deleted=0 才算引用、标识符白名单、值参数化。
 *
 * <p>与引用检查器的差别:那边按**主键**查引用(表名 → 引用列都是数字 id),
 * 这边按**路径字符串**查,且列名不统一(pending/other/lab 用 file_path,lab 图片用
 * image_path,award 证书用 certificate_path,专利/软著证书用 certificate_file,
 * 模板样本图用 sample_image_path),故按"表:列"配对。
 *
 * @author AwardIE
 */
@Component
public class FileReferenceChecker {

    /**
     * 全域文件路径引用清单(表名 → 路径列名)
     *
     * <p>新增存文件的表时**必须**在此登记,否则该表引用不会被识别,补偿删除会误删。
     * 列名不统一:多数是 file_path,实验室图片是 image_path,成果证书是
     * certificate_path,专利/软著证书是 certificate_file,模板样本图是 sample_image_path。
     */
    public static final Map<String, String> FILE_PATH_REFERENCES = references(
            "awardie_pending_achievements", "file_path",
            "awardie_laboratory_downloads", "file_path",
            "awardie_laboratory_images", "image_path",
            "awardie_awards", "certificate_path",
            "awardie_patents", "certificate_file",
            "awardie_software_copyrights", "certificate_file",
            "awardie_other_files", "file_path",
            "awardie_templates", "sample_image_path");

    /** SQL 标识符白名单:只允许小写字母与下划线,杜绝拼接注入 */
    private static final Pattern IDENTIFIER = Pattern.compile("[a-z][a-z0-9_]{0,63}");
    /** 引用清单以 表名,列名 成对传入,步长为两 */
    private static final int REFERENCE_ENTRY_STRIDE = 2;

    @Resource
    private JdbcTemplate jdbcTemplate;

    /**
     * 该文件路径是否仍被任何业务记录引用
     *
     * @param relativePath 相对存储根的文件路径
     * @return true=仍被引用(不可删);false=无引用(可删)
     */
    public boolean isReferenced(String relativePath) {
        if (relativePath == null || relativePath.isBlank()) {
            return false;
        }
        for (Map.Entry<String, String> entry : FILE_PATH_REFERENCES.entrySet()) {
            String table = entry.getKey();
            String column = entry.getValue();
            checkIdentifier(table);
            checkIdentifier(column);
            // 表或列尚未建时跳过(逐批落地);建成后本检查自动生效
            if (!tableExists(table) || !columnExists(table, column)) {
                continue;
            }
            String sql = "SELECT COUNT(*) FROM " + table + " WHERE " + column + " = ?"
                    + (columnExists(table, "deleted") ? " AND deleted = 0" : "");
            Long count = jdbcTemplate.queryForObject(sql, Long.class, relativePath);
            if (count != null && count > 0) {
                return true;
            }
        }
        return false;
    }

    private boolean tableExists(String table) {
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?",
                Long.class, table);
        return count != null && count > 0;
    }

    private boolean columnExists(String table, String column) {
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                        + "AND TABLE_NAME = ? AND COLUMN_NAME = ?",
                Long.class, table, column);
        return count != null && count > 0;
    }

    private static void checkIdentifier(String identifier) {
        if (identifier == null || !IDENTIFIER.matcher(identifier).matches()) {
            throw new IllegalArgumentException("非法的表/列标识符: " + identifier);
        }
    }

    private static Map<String, String> references(String... pairs) {
        Map<String, String> map = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += REFERENCE_ENTRY_STRIDE) {
            map.put(pairs[i], pairs[i + 1]);
        }
        return Collections.unmodifiableMap(map);
    }

}
