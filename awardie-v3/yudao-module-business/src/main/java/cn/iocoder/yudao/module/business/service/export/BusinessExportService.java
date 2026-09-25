package cn.iocoder.yudao.module.business.service.export;

import jakarta.annotation.Resource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.validation.annotation.Validated;

import java.util.ArrayList;
import java.util.List;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.EXPORT_TOO_MANY_ROWS;

/**
 * 数据导出 Service(批9)
 *
 * <p>本批只做两类(数据链完整):竞赛年度汇总、学生获奖明细。教师个人导出缺教师关系表
 * (前置债),学生个人导出属批10 学生端门户。
 *
 * <p>SQL 全部走 JdbcTemplate 并显式带 {@code deleted = b'0' AND tenant_id = ?}
 * (不经租户拦截器,同 StatsService 的理由)。行数超限**报错而非静默截断**——静默截断会让
 * 收件人拿到不完整数据却毫无察觉。
 *
 * @author AwardIE
 */
@Service
@Validated
public class BusinessExportService {

    /** 导出行数上限(可配):超过即报错,避免一次性拉爆内存 */
    @Value("${awardie.export.max-rows:10000}")
    private int maxRows;

    @Resource
    private JdbcTemplate jdbcTemplate;

    /**
     * 竞赛 × 年份 × 获奖等级汇总
     *
     * <p>年份为空时用固定文本"未填写"占位(v2 用 '-' 排序会把它当字符串混排;这里显式标注,
     * 排序按 年份 NULLS LAST 语义——MySQL 用 {@code year IS NULL} 显式排后)。
     *
     * @param tenantId 租户编号
     * @return 汇总行(按年份倒序、同年份按数量倒序)
     */
    public List<CompetitionSummaryRow> getCompetitionSummary(Long tenantId) {
        String sql = """
                SELECT COALESCE(c.competition_name, '未关联') AS competition,
                       a.year AS year,
                       a.award_level AS awardLevel,
                       COUNT(*) AS count
                FROM awardie_awards a
                LEFT JOIN awardie_competitions c
                       ON a.competition_id = c.id AND c.deleted = b'0' AND c.tenant_id = ?
                WHERE a.deleted = b'0' AND a.tenant_id = ?
                GROUP BY COALESCE(c.competition_name, '未关联'), a.year, a.award_level
                ORDER BY (a.year IS NULL) ASC, a.year DESC, count DESC
                LIMIT ?
                """;
        List<CompetitionSummaryRow> rows = jdbcTemplate.query(sql, (rs, rowNum) -> {
            CompetitionSummaryRow row = new CompetitionSummaryRow();
            row.setCompetition(rs.getString("competition"));
            int year = rs.getInt("year");
            row.setYear(rs.wasNull() ? null : year);
            row.setAwardLevel(rs.getString("awardLevel"));
            row.setCount(rs.getLong("count"));
            return row;
        }, tenantId, tenantId, maxRows + 1);
        assertRowLimit(rows.size());
        return rows;
    }

    /**
     * 学生获奖明细
     *
     * <p>学号取 {@code u.username}(v3 的 username 就是学号);v2 取的是 users.id,
     * 导出内容是内部数字 ID 而非学号——本批修正。
     *
     * <p>行数天然去重:v3 关联表有 {@code UNIQUE(award_id, student_id)},同一学生同一奖状
     * 只有一行,v2 无唯一约束时 {@code COUNT(*)} 会重复计数(那个缺陷不继承)。
     *
     * @param tenantId 租户编号
     * @return 明细行(按学号、年份倒序)
     */
    public List<StudentAwardRow> getStudentAffairs(Long tenantId) {
        String sql = """
                SELECT u.username AS studentNo,
                       u.nickname AS studentName,
                       COALESCE(c.competition_name, '未关联') AS competition,
                       a.award_level AS awardLevel,
                       a.year AS year
                FROM awardie_award_student_winners w
                INNER JOIN system_users u
                       ON w.student_id = u.id AND u.deleted = b'0' AND u.tenant_id = ?
                INNER JOIN awardie_awards a
                       ON w.award_id = a.id AND a.deleted = b'0' AND a.tenant_id = ?
                LEFT JOIN awardie_competitions c
                       ON a.competition_id = c.id AND c.deleted = b'0' AND c.tenant_id = ?
                WHERE w.deleted = b'0' AND w.tenant_id = ?
                ORDER BY u.username ASC, (a.year IS NULL) ASC, a.year DESC
                LIMIT ?
                """;
        List<StudentAwardRow> rows = jdbcTemplate.query(sql, (rs, rowNum) -> {
            StudentAwardRow row = new StudentAwardRow();
            row.setStudentNo(rs.getString("studentNo"));
            row.setStudentName(rs.getString("studentName"));
            row.setCompetition(rs.getString("competition"));
            row.setAwardLevel(rs.getString("awardLevel"));
            int year = rs.getInt("year");
            row.setYear(rs.wasNull() ? null : year);
            return row;
        }, tenantId, tenantId, tenantId, tenantId, maxRows + 1);
        assertRowLimit(rows.size());
        return rows;
    }

    /**
     * 判行数上限
     *
     * <p>上限已通过 SQL 的 {@code LIMIT maxRows + 1} **前置到查询**:
     * 否则百万行结果会全部进堆才抛错,起不到"防拖垮服务器"的作用。
     * 多取一行只为区分"恰好等于上限"与"超过上限",报错语义不变(仍不静默截断)。
     *
     * @param size 实际取到的行数
     */
    private void assertRowLimit(int size) {
        if (size > maxRows) {
            throw exception(EXPORT_TOO_MANY_ROWS, size, maxRows);
        }
    }

    /** 供 XLSX 导出用:竞赛汇总的列(与 CSV 保持同序) */
    public static String[] competitionSummaryHeader() {
        return new String[]{"竞赛", "年份", "获奖等级", "数量"};
    }

    /** 竞赛汇总行转字符串数组(列序与 {@link #competitionSummaryHeader()} 严格对应) */
    public static String[] competitionSummaryCells(CompetitionSummaryRow row) {
        return new String[]{
                row.getCompetition(),
                row.getYear() == null ? "未填写" : String.valueOf(row.getYear()),
                row.getAwardLevel(),
                String.valueOf(row.getCount())};
    }

    /** 学生明细的列 */
    public static String[] studentAffairsHeader() {
        return new String[]{"学号", "姓名", "竞赛", "获奖等级", "年份"};
    }

    /** 学生明细行转字符串数组(列序与 {@link #studentAffairsHeader()} 严格对应) */
    public static String[] studentAffairsCells(StudentAwardRow row) {
        return new String[]{
                row.getStudentNo(),
                row.getStudentName(),
                row.getCompetition(),
                row.getAwardLevel(),
                row.getYear() == null ? "未填写" : String.valueOf(row.getYear())};
    }

    /** 竞赛汇总 DTO 列表转 CSV 行(不依赖 Map 迭代顺序,v2 的错列根源) */
    public static List<String[]> competitionSummaryCells(List<CompetitionSummaryRow> rows) {
        List<String[]> cells = new ArrayList<>(rows.size());
        for (CompetitionSummaryRow row : rows) {
            cells.add(competitionSummaryCells(row));
        }
        return cells;
    }

    /** 学生明细 DTO 列表转 CSV 行 */
    public static List<String[]> studentAffairsCells(List<StudentAwardRow> rows) {
        List<String[]> cells = new ArrayList<>(rows.size());
        for (StudentAwardRow row : rows) {
            cells.add(studentAffairsCells(row));
        }
        return cells;
    }

}
