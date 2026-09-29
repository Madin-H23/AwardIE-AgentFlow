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
 * <p><b>维度现状</b>:实验室维度批16 已上(byLaboratory);教师维度批20 已上
 * (byTeacher,口径=文本匹配 FIND_IN_SET + 同名编号约定,不依赖关系表);
 * **年份维度仍未做**——物化链不写 year(欠账 D-16 剩余项),切流存量 194/197 条
 * 带 year、新审核通过行不带,做出来口径会随时间漂移,待物化链补齐后再上。
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
        Map<String, Long> category = categoryCounts(tenantId);
        vo.setCategory(category);
        // 成果总数 = 五类合计(与 VO 契约一致)。批14 前端实测发现本字段从未被赋值,
        // 页面「成果总数」恒 0 —— 五类分类表有数、汇总卡却是 0,根因之一就是这条漏写。
        summary.setAwardsTotal(category.values().stream().mapToLong(Long::longValue).sum());
        return vo;
    }

    /**
     * 教师维度:各教师的指导获奖数与本人教师证书数(批20,D-17)。
     *
     * <p>口径与教师指导成果页(TeacherAchievementController)完全一致:
     * supervisor_name / winner_name 归一化「，/、/空格」→「,」后 <b>FIND_IN_SET 精确成员比较</b>,
     * 非子串包含——张三1 不命中 张三12、王五 不命中 王五平。同名教师按
     * 编号约定区分(2026-09-29 用户拍板:同名出现时全员编号张三1/张三2、不留裸名,
     * 编号同时落在账号昵称与奖状 supervisor_name 两处;当前 40 名教师零同名,约定备用)。
     *
     * <p>行集 = 全部在职教师账号(role code=awardie_teacher),0 指导的教师也列出
     * (管理者要看到"谁还没有成果",只列有数的会掩盖这个信息)。
     * 两个计数用相关子查询而非两路 LEFT JOIN:同一行可能同时是指导与获奖人,
     * JOIN 会让两列互相乘积,相关子查询天然各算各的。
     *
     * @param tenantId 租户编号
     * @return 行:name(教师名) / supervised(指导获奖数) / ownAwards(本人教师证书数)
     */
    public List<Map<String, Object>> teacherBreakdown(Long tenantId) {
        // ⚠️ u.nickname 必须显式 COLLATE 对齐业务列:system_users 是芋道原生表
        // (utf8mb4_unicode_ci),awardie_* 建表继承 MySQL8 默认(utf8mb4_0900_ai_ci),
        // FIND_IN_SET 在这里做的是**列对列**比较,两种 collation 直接混用报
        // "Illegal mix of collations"(实测);TeacherAchievementController 的同名匹配
        // 是参数对列,走连接默认 collation,不受影响。
        String sql = """
                SELECT u.nickname AS name,
                       (SELECT COUNT(*) FROM awardie_awards a
                         WHERE a.deleted = b'0' AND a.tenant_id = u.tenant_id
                           AND FIND_IN_SET(u.nickname COLLATE utf8mb4_0900_ai_ci, REPLACE(REPLACE(REPLACE(
                               a.supervisor_name, '，', ','), '、', ','), ' ', '')) > 0) AS supervised,
                       (SELECT COUNT(*) FROM awardie_awards a
                         WHERE a.deleted = b'0' AND a.tenant_id = u.tenant_id
                           AND a.granted_role = '教师'
                           AND FIND_IN_SET(u.nickname COLLATE utf8mb4_0900_ai_ci, REPLACE(REPLACE(REPLACE(
                               a.winner_name, '，', ','), '、', ','), ' ', '')) > 0) AS ownAwards
                FROM system_users u
                JOIN system_user_role ur ON ur.user_id = u.id AND ur.deleted = b'0'
                JOIN system_role r ON r.id = ur.role_id AND r.deleted = b'0' AND r.code = 'awardie_teacher'
                WHERE u.deleted = b'0' AND u.tenant_id = ?
                ORDER BY supervised DESC, ownAwards DESC, name ASC
                """;
        return jdbcTemplate.queryForList(sql, tenantId);
    }

    /**
     * 实验室维度:各实验室的获奖数(批16,D-16 前置债之一)。
     *
     * <p>按 awardie_laboratories 全量左联计数,无实验室的归入「未归属」桶 ——
     * 与竞赛 Top 的「未关联」同语义。v1 的 stats 也有该维度;切流后 194/197 条
     * 奖状带 laboratory_id,数据可用。
     *
     * @param tenantId 租户编号
     * @return 键=实验室名(或「未归属」),值=获奖数;LinkedHashMap 保序
     */
    public Map<String, Long> laboratoryBreakdown(Long tenantId) {
        String sql = """
                SELECT COALESCE(l.name, '未归属') AS name, COUNT(*) AS total
                FROM awardie_awards a
                LEFT JOIN awardie_laboratories l
                       ON a.laboratory_id = l.id AND l.deleted = b'0' AND l.tenant_id = ?
                WHERE a.deleted = b'0' AND a.tenant_id = ?
                GROUP BY COALESCE(l.name, '未归属')
                ORDER BY total DESC, name ASC
                """;
        Map<String, Long> out = new LinkedHashMap<>();
        jdbcTemplate.queryForList(sql, tenantId, tenantId).forEach(row ->
                out.put(String.valueOf(row.get("name")), ((Number) row.get("total")).longValue()));
        return out;
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
