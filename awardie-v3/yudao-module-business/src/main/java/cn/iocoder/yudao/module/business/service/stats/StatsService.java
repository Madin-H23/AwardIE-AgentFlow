package cn.iocoder.yudao.module.business.service.stats;

import cn.iocoder.yudao.module.business.controller.admin.stats.vo.CompetitionRankingVO;
import cn.iocoder.yudao.module.business.controller.admin.stats.vo.StatsOverviewRespVO;
import jakarta.annotation.Resource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.validation.annotation.Validated;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 统计分析 Service(批9)
 *
 * <p><b>租户隔离是硬要求</b>:本服务走 JdbcTemplate,**不经 MyBatis-Plus 租户拦截器**
 * (批7 security-audit 已实证过这点,并在通用成果库的 update 上踩过一次跨租户漏洞)。
 * 故每条 SQL 都显式带 {@code deleted = b'0' AND tenant_id = ?}。
 *
 * <p><b>计数用 Long 而非 Integer</b>:v2 用 Integer.class 接 COUNT,超过 Integer.MAX_VALUE
 * 会转换异常变 500;芋道 PageResult.total 本身也是 Long。
 *
 * <p><b>不做年份/实验室/教师维度</b>:依赖 v3 尚未写入的字段(year/laboratory_id/granted_role),
 * 现在做只会返回空。已记为前置债(00-需求 F1/F2/F3)。
 *
 * @author AwardIE
 */
@Service
@Validated
public class StatsService {

    /** 竞赛战果 Top N(v2 同值) */
    private static final int TOP_COMPETITION_LIMIT = 12;
    /** 无竞赛关联的成果归入的桶名(v2 同值) */
    private static final String UNLINKED_BUCKET = "未关联";

    @Resource
    private JdbcTemplate jdbcTemplate;

    /**
     * 统计总览:汇总 + 五类分类
     *
     * @param tenantId 租户编号
     * @return 总览
     */
    public StatsOverviewRespVO getOverview(Long tenantId) {
        StatsOverviewRespVO vo = new StatsOverviewRespVO();
        StatsOverviewRespVO.Summary summary = new StatsOverviewRespVO.Summary();
        summary.setPendingSubmit(count("""
                SELECT COUNT(*) FROM awardie_pending_achievements
                WHERE status = 'pending' AND deleted = b'0' AND tenant_id = ?
                """, tenantId));
        summary.setUsersTotal(countUser(tenantId));
        summary.setCompetitionsTotal(count("""
                SELECT COUNT(*) FROM awardie_competitions
                WHERE deleted = b'0' AND tenant_id = ?
                """, tenantId));
        summary.setWhitelist(count("""
                SELECT COUNT(*) FROM awardie_competitions
                WHERE white_list = b'1' AND deleted = b'0' AND tenant_id = ?
                """, tenantId));
        vo.setSummary(summary);
        vo.setCategory(categoryCounts(tenantId));
        return vo;
    }

    /**
     * 五类成果分类计数
     *
     * @param tenantId 租户编号
     * @return 分类计数(LinkedHashMap 保固定顺序,前端按序渲染)
     */
    public Map<String, Long> categoryCounts(Long tenantId) {
        Map<String, Long> category = new LinkedHashMap<>();
        category.put("award", count("""
                SELECT COUNT(*) FROM awardie_awards
                WHERE deleted = b'0' AND tenant_id = ?
                """, tenantId));
        category.put("patent", count("""
                SELECT COUNT(*) FROM awardie_patents
                WHERE deleted = b'0' AND tenant_id = ?
                """, tenantId));
        category.put("software", count("""
                SELECT COUNT(*) FROM awardie_software_copyrights
                WHERE deleted = b'0' AND tenant_id = ?
                """, tenantId));
        category.put("innovation", count("""
                SELECT COUNT(*) FROM awardie_innovation_projects
                WHERE deleted = b'0' AND tenant_id = ?
                """, tenantId));
        category.put("other", count("""
                SELECT COUNT(*) FROM awardie_other_files
                WHERE deleted = b'0' AND tenant_id = ?
                """, tenantId));
        return category;
    }

    /**
     * 竞赛战果 Top12
     *
     * <p>两个要点:
     * <ul>
     *   <li>{@code LEFT JOIN} + {@code COALESCE(...,'未关联')} 保留无主成果(v2 已如此);</li>
     *   <li><b>加 name ASC 二级排序</b>——v2 只有 {@code ORDER BY total DESC},同数时行序由
     *       执行计划决定,截图与对账会漂。补确定性排序是修 v2 缺陷。</li>
     * </ul>
     *
     * @param tenantId 租户编号
     * @return Top 列表
     */
    public List<CompetitionRankingVO> getCompetitionRanking(Long tenantId) {
        String sql = """
                SELECT COALESCE(c.competition_name, ?) AS name, COUNT(*) AS total
                FROM awardie_awards a
                LEFT JOIN awardie_competitions c
                       ON a.competition_id = c.id AND c.deleted = b'0' AND c.tenant_id = ?
                WHERE a.deleted = b'0' AND a.tenant_id = ?
                GROUP BY COALESCE(c.competition_name, ?)
                ORDER BY total DESC, name ASC
                LIMIT ?
                """;
        return jdbcTemplate.query(sql, (rs, rowNum) -> {
            CompetitionRankingVO vo = new CompetitionRankingVO();
            vo.setName(rs.getString("name"));
            vo.setTotal(rs.getLong("total"));
            return vo;
        }, UNLINKED_BUCKET, tenantId, tenantId, UNLINKED_BUCKET, TOP_COMPETITION_LIMIT);
    }

    /**
     * 用户数(芋道 system_users 表;逻辑删除列名是 deleted,租户列 tenant_id)
     *
     * @param tenantId 租户编号
     * @return 用户数
     */
    private Long countUser(Long tenantId) {
        Long n = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM system_users WHERE deleted = b'0' AND tenant_id = ?",
                Long.class, tenantId);
        return n == null ? 0L : n;
    }

    /** 统一计数:null 归零(COUNT 不会返 null,统一处理避免各处重复判空) */
    private Long count(String sql, Long tenantId) {
        Long n = jdbcTemplate.queryForObject(sql, Long.class, tenantId);
        return n == null ? 0L : n;
    }

}
