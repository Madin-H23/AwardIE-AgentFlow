package cn.iocoder.yudao.module.business.service.laboratory;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import jakarta.annotation.Resource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.validation.annotation.Validated;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.LABORATORIES_NOT_EXISTS;

/**
 * 实验室成员/资产查询(批4):详情聚合与下载列表,语义对照 v2 AdminConsoleController 的实验室段
 *
 * <p>用 JdbcTemplate 直查:四张关联表是纯关联数据(无独立生命周期),不需要 DO/Mapper 全套。
 * JdbcTemplate 不过芋道租户拦截器,故每条查询显式带 tenant_id 条件,值取自租户上下文
 * (不硬编码 1——单租户下等价,但多租户时不会读穿别的租户数据)。
 *
 * @author AwardIE
 */
@Service
@Validated
public class LaboratoryAssetsService {

    @Resource
    private JdbcTemplate jdbcTemplate;
    @Resource
    private LaboratoriesService laboratoriesService;

    /**
     * 实验室详情聚合:基本信息 + 教师 + 学生 + 下载数 + 成果数
     *
     * @param id 实验室编号
     * @return 聚合结果
     */
    public Map<String, Object> getDetail(Long id) {
        if (laboratoriesService.getLaboratories(id) == null) {
            throw exception(LABORATORIES_NOT_EXISTS);
        }
        Map<String, Object> result = new HashMap<>(16);
        Map<String, Object> lab = jdbcTemplate.queryForMap(
                "SELECT id, name, description FROM awardie_laboratories WHERE id = ? AND deleted = b'0'", id);
        result.putAll(lab);
        result.put("instructors", jdbcTemplate.queryForList(
                "SELECT u.id, u.nickname AS name, u.id AS userId FROM awardie_laboratory_instructors li "
                        + "INNER JOIN system_users u ON li.teacher_id = u.id "
                        + "WHERE li.laboratory_id = ? AND li.tenant_id = ? ORDER BY u.id", id, TenantContextHolder.getRequiredTenantId()));
        result.put("students", jdbcTemplate.queryForList(
                "SELECT u.id, u.nickname AS name, u.id AS userId FROM awardie_laboratory_students ls "
                        + "INNER JOIN system_users u ON ls.student_id = u.id "
                        + "WHERE ls.laboratory_id = ? AND ls.tenant_id = ? ORDER BY u.id", id, TenantContextHolder.getRequiredTenantId()));
        result.put("downloadCount", countById("awardie_laboratory_downloads", id));
        // 成果数依赖 awardie_awards 表,批6 建成前恒为 0(不静默假装有数据;批6 补)
        result.put("awardCount", countAchievements(id));
        return result;
    }

    /**
     * 实验室下载文件列表(display_order, id DESC,对照 v2)
     *
     * @param id 实验室编号
     * @return 下载文件列表
     */
    public List<Map<String, Object>> getDownloads(Long id) {
        return jdbcTemplate.queryForList(
                "SELECT id, file_title AS fileTitle, file_name AS fileName, file_size AS fileSize, "
                        + "submitter_type AS submitterType, create_time AS createTime "
                        + "FROM awardie_laboratory_downloads "
                        + "WHERE laboratory_id = ? AND deleted = b'0' AND tenant_id = ? "
                        + "ORDER BY display_order, id DESC", id, TenantContextHolder.getRequiredTenantId());
    }

    private long countById(String table, Long labId) {
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM " + table + " WHERE laboratory_id = ? AND deleted = b'0' AND tenant_id = ?",
                Long.class, labId, TenantContextHolder.getRequiredTenantId());
        return count == null ? 0L : count;
    }

    private long countAchievements(Long labId) {
        // awardie_awards 在批6 才建;表不存在时返回 0(与引用检查同一"表不存在跳过"口径)
        Long exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
                        + "AND TABLE_NAME = 'awardie_awards'", Long.class);
        if (exists == null || exists == 0) {
            return 0L;
        }
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM awardie_awards WHERE laboratory_id = ? AND deleted = b'0' AND tenant_id = ?",
                Long.class, labId, TenantContextHolder.getRequiredTenantId());
        return count == null ? 0L : count;
    }

}
