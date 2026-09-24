package cn.iocoder.yudao.module.business.service.reference;

import cn.hutool.core.collection.CollUtil;
import cn.iocoder.yudao.framework.common.exception.ErrorCode;
import jakarta.annotation.Resource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;

/**
 * 基础数据域删除前的引用检查(v3 逻辑删除下 FK 永不触发,这是删除保护的唯一防线)
 *
 * <p>口径(批3 决策):表不存在则跳过——成果表在批4-8 才陆续建,建好后无需改代码即自动生效;
 * 引用行 deleted=1 视为已删,不阻断(与 v3 逻辑删除语义一致)。
 *
 * <p>安全:表名与列名只来自代码内常量清单({@link #COMPETITION_REFERENCES} /
 * {@link #LABORATORY_REFERENCES}),不接受任何外部输入;拼接前再过一次标识符白名单正则。
 *
 * @author AwardIE
 */
@Component
public class AchievementReferenceChecker {

    /** 竞赛引用方:成果(competition_id NOT NULL)+ 奖状模板;表在批6/7 建 */
    public static final Map<String, String> COMPETITION_REFERENCES = references(
            "awardie_awards", "competition_id",
            "awardie_templates", "competition_id");

    /**
     * 实验室引用方:四类成果 + 其他文件(v2 同有 FK,一并保护);
     * 实验室关联表(laboratory_downloads/images/instructors/students/assistants)与
     * user_photos 在批4 建成后再追加进本清单。
     */
    public static final Map<String, String> LABORATORY_REFERENCES = references(
            "awardie_awards", "laboratory_id",
            "awardie_patents", "laboratory_id",
            "awardie_software_copyrights", "laboratory_id",
            "awardie_innovation_projects", "laboratory_id",
            "awardie_other_files", "laboratory_id");

    /** SQL 标识符白名单:只允许小写字母与下划线,杜绝拼接注入 */
    private static final Pattern IDENTIFIER = Pattern.compile("[a-z][a-z0-9_]{0,63}");
    /** 引用清单以 表名,列名 成对传入,步长为两 */
    private static final int REFERENCE_ENTRY_STRIDE = 2;

    @Resource
    private JdbcTemplate jdbcTemplate;

    /**
     * 校验目标记录未被引用;被引用时抛业务异常,消息带出表名与行数
     *
     * @param id        被删除的主键
     * @param reference 引用清单(表名 → 引用列名)
     * @param errorCode 被引用时的业务错误码
     */
    public void validateNoReference(Long id, Map<String, String> reference, ErrorCode errorCode) {
        validateNoReference(List.of(id), reference, errorCode);
    }

    /**
     * 批量校验(批量删除用):每张引用表只查一次,避免逐 id 重复查 information_schema
     *
     * @param ids       被删除的主键列表
     * @param reference 引用清单(表名 → 引用列名)
     * @param errorCode 被引用时的业务错误码
     */
    public void validateNoReference(List<Long> ids, Map<String, String> reference, ErrorCode errorCode) {
        if (CollUtil.isEmpty(ids)) {
            return;
        }
        for (Map.Entry<String, String> entry : reference.entrySet()) {
            String table = entry.getKey();
            String column = entry.getValue();
            checkIdentifier(table);
            checkIdentifier(column);
            if (!tableExists(table)) {
                // 引用表尚未建(批4-8 逐批落地),跳过;表建成后本检查自动生效
                continue;
            }
            String placeholders = String.join(", ", Collections.nCopies(ids.size(), "?"));
            String sql = "SELECT COUNT(*) FROM " + table + " WHERE " + column + " IN (" + placeholders + ")"
                    + (columnExists(table, "deleted") ? " AND deleted = 0" : "");
            Long count = jdbcTemplate.queryForObject(sql, Long.class, ids.toArray());
            if (count != null && count > 0) {
                throw exception(errorCode, table + " 引用 " + count + " 条");
            }
        }
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
        return map;
    }

}
