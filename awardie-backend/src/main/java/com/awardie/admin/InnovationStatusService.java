package com.awardie.admin;

import java.time.DateTimeException;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.awardie.auth.UserEntity;

/**
 * 大创项目状态校准(挂账清偿,方向2):结束日期已过的「进行中」项目批量标记「已结题」。
 *
 * 背景:v1 诊断(2026-08-25)证实 20 条全「进行中」系数据治理现状(从未有人逐条改状态),
 * 而非代码 bug——导入默认「进行中」+管理员不进编辑页,合力造成。本服务提供一次性批量校准入口。
 *
 * 语义边界:
 * - 只选 status='进行中' 的行——终止/已结题永不被覆盖(幂等,可重复点击);
 * - 判定线=end_date 严格早于今天(Asia/Shanghai),结束日期=当天=项目最后一天,不校准;
 * - end_date 为 TEXT 且存量格式混杂(2025-06 / 2024.5.1 / 2025年6月 …),PG 无法直接 ::date,
 *   故在 Java 侧宽松解析,不可识别→跳过并计数,绝不猜。
 */
@Service
public class InnovationStatusService {

    public record CalibrationResult(int considered, int calibrated, int skippedUnparsed, List<Integer> calibratedIds) {}

    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");

    /** 数值日期:2025-06 / 2024.5.1 / 2025-06-30 / 2025/6/1(缺省月日=1)。 */
    private static final Pattern NUMERIC = Pattern.compile("^(\\d{4})[-/.](\\d{1,2})(?:[-/.](\\d{1,2}))?$");

    /** 中文日期:2025年6月 / 2025年6月30日。 */
    private static final Pattern CHINESE = Pattern.compile("^(\\d{4})年(\\d{1,2})月(\\d{1,2})?日?$");

    private final JdbcTemplate jdbc;

    public InnovationStatusService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 校准:返回 considered=候选行数(进行中且有非空 end_date)、calibrated=实校准数、skippedUnparsed=日期不可识别数。 */
    @Transactional
    public CalibrationResult calibrateEndedProjects(UserEntity operator) {
        LocalDate today = LocalDate.now(ZONE);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT id, end_date FROM innovation_projects
                WHERE status = '进行中' AND end_date IS NOT NULL AND btrim(end_date) <> ''
                """);
        List<Integer> ids = new ArrayList<>();
        int skipped = 0;
        for (Map<String, Object> r : rows) {
            String raw = r.get("end_date") == null ? null : String.valueOf(r.get("end_date"));
            LocalDate end = parseLooseDate(raw);
            if (end == null) {
                skipped++;
            } else if (end.isBefore(today)) {
                ids.add(((Number) r.get("id")).intValue());
            }
        }
        for (Integer id : ids) {
            jdbc.update("UPDATE innovation_projects SET status = '已结题', updated_at = NOW() WHERE id = ?", id);
        }
        jdbc.update("""
                INSERT INTO system_event_log (event_category, event_level, event_message, operator_code, detail)
                VALUES ('system', 'info', ?, ?, ?::jsonb)
                """, "大创状态校准:校准 " + ids.size() + " 条,跳过无法识别 " + skipped + " 条",
                operator.getLoginCode(), detailJson(ids.size(), skipped, ids));
        return new CalibrationResult(rows.size(), ids.size(), skipped, ids);
    }

    /** detail JSON 手拼(与 InnovationImportService 同范式;ids 为整数,无转义面)。 */
    private String detailJson(int calibrated, int skipped, List<Integer> ids) {
        StringBuilder sb = new StringBuilder("{\"calibrated\":").append(calibrated)
                .append(",\"skippedUnparsed\":").append(skipped)
                .append(",\"ids\":[");
        for (int i = 0; i < ids.size(); i++) {
            sb.append(i == 0 ? "" : ",").append(ids.get(i));
        }
        return sb.append("]}").toString();
    }

    /** 宽松日期解析:覆盖存量 TEXT 日期的混杂格式;不可识别(含 13 月/2 月 30 日等非法值)→ null。 */
    static LocalDate parseLooseDate(String raw) {
        if (raw == null || raw.isBlank()) {
            return null;
        }
        Matcher m = NUMERIC.matcher(raw.trim());
        if (!m.matches()) {
            m = CHINESE.matcher(raw.trim());
        }
        if (!m.matches()) {
            return null;
        }
        try {
            int year = Integer.parseInt(m.group(1));
            int month = Integer.parseInt(m.group(2));
            int day = m.group(3) == null ? 1 : Integer.parseInt(m.group(3));
            return LocalDate.of(year, month, day);
        } catch (NumberFormatException | DateTimeException e) {
            return null;
        }
    }
}
