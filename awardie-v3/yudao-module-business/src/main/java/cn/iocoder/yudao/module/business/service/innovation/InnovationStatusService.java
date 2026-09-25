package cn.iocoder.yudao.module.business.service.innovation;

import cn.iocoder.yudao.module.business.dal.dataobject.innovation.InnovationProjectDO;
import cn.iocoder.yudao.module.business.dal.mysql.innovation.InnovationProjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;

import java.time.DateTimeException;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 大创 status 方向2:按结束日期批量校准(批8)
 *
 * <p>v2 于 2026-09-22 实现并验收(方向1+2 清偿)。本类是等价迁移,语义边界逐条对齐:
 * <ul>
 *   <li>只选 {@code status='进行中'} 的行——终止/已结题永不被覆盖(顺序幂等,可重复点击);</li>
 *   <li>判定线 = {@code end_date} <b>严格早于</b>今天(Asia/Shanghai);当天=项目最后一天,不校准;</li>
 *   <li>end_date 是 VARCHAR 且存量格式混杂({@code 2025-06} / {@code 2024.5.1} /
 *       {@code 2025年6月} …),MySQL 无法直接 STR_TO_DATE 统一,故在 Java 侧宽松解析;</li>
 *   <li>不可识别(待定/只有年份/13 月/2 月 30 日)→ <b>跳过并计数,绝不猜</b>;</li>
 *   <li>更新带 {@code AND status='进行中'} 实现 compare-and-set,并发校准不会互相覆盖;
 *       v2 的 UPDATE 只按 id,两次并发会都选中同一批行(v2 已知边界,v3 收紧)。</li>
 * </ul>
 *
 * @author AwardIE
 */
@Service
@Validated
@Slf4j
public class InnovationStatusService {

    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");

    /** 数值日期:2025-06 / 2024.5.1 / 2025-06-30 / 2025/6/1(缺省月日=1,沿 v2 月首日语义) */
    private static final Pattern NUMERIC = Pattern.compile("^(\\d{4})[-/.](\\d{1,2})(?:[-/.](\\d{1,2}))?$");

    /** 中文日期:2025年6月 / 2025年6月30日 */
    private static final Pattern CHINESE = Pattern.compile("^(\\d{4})年(\\d{1,2})月(\\d{1,2})?日?$");

    @Resource
    private InnovationProjectMapper projectMapper;

    /**
     * 校准:把结束日期已过的"进行中"项目批量标记"已结题"
     *
     * @param tenantId 租户编号
     * @return 校准结果(considered/calibrated/skippedUnparsed/calibratedIds)
     */
    @Transactional(rollbackFor = Exception.class)
    public CalibrationResult calibrateEndedProjects(Long tenantId) {
        LocalDate today = LocalDate.now(ZONE);
        List<InnovationProjectDO> candidates = projectMapper.selectCalibrateCandidates(tenantId);
        List<Long> calibratedIds = new ArrayList<>();
        int skipped = 0;
        for (InnovationProjectDO row : candidates) {
            LocalDate end = parseLooseDate(row.getEndDate());
            if (end == null) {
                skipped++;
            } else if (end.isBefore(today)) {
                // compare-and-set:并发时后到的那条影响 0 行,不会盖掉别人已改的状态
                if (projectMapper.markFinished(row.getId(), tenantId) > 0) {
                    calibratedIds.add(row.getId());
                }
            }
        }
        log.info("[innovation-calibrate] 租户 {}:候选 {} 校准 {} 跳过无法识别 {}",
                tenantId, candidates.size(), calibratedIds.size(), skipped);
        return new CalibrationResult(candidates.size(), calibratedIds.size(), skipped, calibratedIds);
    }

    /**
     * 宽松日期解析:覆盖存量 VARCHAR 日期的混杂格式;不可识别(含 13 月/2 月 30 日)返回 null
     *
     * @param raw 日期原文
     * @return 解析结果;无法识别返回 null(调用方计入 skipped,不猜)
     */
    public static LocalDate parseLooseDate(String raw) {
        if (raw == null || raw.isBlank()) {
            return null;
        }
        String value = raw.trim();
        Matcher m = NUMERIC.matcher(value);
        if (!m.matches()) {
            m = CHINESE.matcher(value);
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
            // 13 月 / 2 月 30 日 / 年份超界等非法值
            return null;
        }
    }

    /**
     * 校准结果
     *
     * @param considered       候选行数(进行中且结束日期非空)
     * @param calibrated       实际校准行数
     * @param skippedUnparsed  日期不可识别而跳过的行数
     * @param calibratedIds    被校准的项目编号
     */
    public record CalibrationResult(int considered, int calibrated, int skippedUnparsed,
                                    List<Long> calibratedIds) {
    }

}
