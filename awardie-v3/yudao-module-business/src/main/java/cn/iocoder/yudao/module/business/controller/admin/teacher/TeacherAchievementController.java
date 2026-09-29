package cn.iocoder.yudao.module.business.controller.admin.teacher;

import cn.iocoder.yudao.framework.apilog.core.annotation.ApiAccessLog;
import cn.iocoder.yudao.framework.common.pojo.CommonResult;
import cn.iocoder.yudao.framework.common.util.http.HttpUtils;
import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.service.export.CsvWriter;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static cn.iocoder.yudao.framework.common.pojo.CommonResult.success;
import static cn.iocoder.yudao.framework.security.core.util.SecurityFrameworkUtils.getLoginUserId;

/**
 * 管理后台 - 教师指导成果(批16,对齐 v1 /teacher/achievements)
 *
 * <p><b>关系口径 = v1 的文本匹配,不是关系表</b>:v1 源码注释明说「避免依赖
 * award_supervisors 表(导入时人名匹配失败会导致该表为空)」,实际按
 * {@code supervisor_name 含教师名} 或 {@code winner_name 含教师名且 granted_role=教师}
 * 匹配(教师名可能以逗号/顿号出现在多人名单中)。v3 沿用此口径 ——
 * 这同时是 D-04(教师指导成果只有前端过滤,教师绕过 UI 可读全租户)的服务端修复:
 * 前端改为调本端点后,过滤发生在 SQL,越权读不再可能。
 *
 * <p><b>租户隔离是硬要求</b>:JdbcTemplate 不经 MyBatis-Plus 租户拦截器(批7 实证),
 * 每条 SQL 显式带 {@code deleted = b'0' AND tenant_id = ?}。
 */
@Tag(name = "管理后台 - AwardIE 教师指导成果")
@RestController
@RequestMapping("/business/teacher/achievements")
@Validated
public class TeacherAchievementController {

    @Resource
    private JdbcTemplate jdbcTemplate;

    /** 上限防拖库(与导出服务同一量级;正常一个教师的指导成果远小于此) */
    private static final int MAX_ROWS = 5000;

    @GetMapping("/my")
    @Operation(summary = "获得当前教师的指导成果列表(服务端按教师过滤)")
    @PreAuthorize("@ss.hasPermission('business:vault:query')")
    public CommonResult<List<Map<String, Object>>> my(@RequestParam(value = "year", required = false) Integer year) {
        Long tenantId = TenantContextHolder.getRequiredTenantId();
        String teacherName = currentTeacherName(tenantId);
        if (teacherName == null) {
            return success(List.of());
        }
        return success(queryByTeacherName(teacherName, year, tenantId));
    }

    @GetMapping("/my.csv")
    @Operation(summary = "导出当前教师指导成果(CSV,对齐 v1 data_export)")
    @ApiAccessLog(operateType = cn.iocoder.yudao.framework.apilog.core.enums.OperateTypeEnum.EXPORT,
            operateName = "导出教师指导成果CSV")
    @PreAuthorize("@ss.hasPermission('business:vault:query')")
    public void exportMyCsv(HttpServletResponse response,
                            @RequestParam(value = "year", required = false) Integer year) throws IOException {
        Long tenantId = TenantContextHolder.getRequiredTenantId();
        String teacherName = currentTeacherName(tenantId);
        String[] header = {"竞赛", "获奖等级", "获奖人", "指导教师", "年份", "教师角色"};
        List<String[]> rows = teacherName == null ? List.of() : queryByTeacherName(teacherName, year, tenantId)
                .stream().map(r -> new String[]{
                        str(r.get("competition")),
                        str(r.get("awardLevel")),
                        str(r.get("winnerName")),
                        str(r.get("supervisorName")),
                        str(r.get("year")),
                        str(r.get("role"))
                }).toList();
        writeCsv(response, "my-achievements", header, rows);
    }

    // ---------------- 内部 ----------------

    /** 当前登录用户的教师姓名;非教师或查无此人返回 null(调用方回空列表,不报错) */
    private String currentTeacherName(Long tenantId) {
        Long userId = getLoginUserId();
        List<String> names = jdbcTemplate.queryForList(
                "SELECT nickname FROM system_users WHERE id = ? AND deleted = b'0' AND tenant_id = ?",
                String.class, userId, tenantId);
        return names.isEmpty() ? null : names.get(0).trim();
    }

    /**
     * 按 v1 口径查指导成果:supervisor_name 含教师名(多人名单,逗号/顿号分隔)
     * 或 winner_name 含教师名且 granted_role='教师'(教师自己的证书)。
     * 返回 LinkedHashMap(键序稳定,前端契约即键名);同一成果两种身份都命中时,
     * role 取「指导+获奖」。
     */
    private List<Map<String, Object>> queryByTeacherName(String teacherName, Integer year, Long tenantId) {
        String like = "%" + teacherName + "%";
        // 占位符顺序:LEFT JOIN 里 1 个 tenant_id → WHERE 里 1 个 tenant_id → LIKE 1 个 → (year 有值时) 1 个 year
        // 两条查询同构,共用一份参数;year 为 null 时 SQL 无 year 占位符,参数也须同步少一个 ——
        // 首版 args 固定按「带 year」组装,Parameter index out of range (4 > 3),实测当场暴露。
        java.util.List<Object> base = new java.util.ArrayList<>(List.of(tenantId, tenantId, like));
        if (year != null) {
            base.add(year);
        }
        Object[] args = base.toArray();
        String yearCond = year == null ? "" : " AND a.year = ? ";
        // 两条 SQL 分别取「作为指导教师」「作为教师获奖者」,内存里按 id 去重合并 ——
        // 与 v1 的两段查询+去重同构;role 语义在 SQL 里即可区分,合并时不重算
        List<Map<String, Object>> asSupervisor = jdbcTemplate.queryForList("""
                SELECT a.id, COALESCE(c.competition_name, a.competition_name_in_file) AS competition,
                       a.award_level AS awardLevel, a.winner_name AS winnerName,
                       a.supervisor_name AS supervisorName, a.year AS year,
                       '指导' AS role
                FROM awardie_awards a
                LEFT JOIN awardie_competitions c
                       ON a.competition_id = c.id AND c.deleted = b'0' AND c.tenant_id = ?
                WHERE a.deleted = b'0' AND a.tenant_id = ?
                  AND REPLACE(REPLACE(a.supervisor_name, '，', ','), '、', ',') LIKE ?
                """ + yearCond + " ORDER BY a.year DESC, a.id DESC LIMIT " + MAX_ROWS,
                args);
        List<Map<String, Object>> asWinner = jdbcTemplate.queryForList("""
                SELECT a.id, COALESCE(c.competition_name, a.competition_name_in_file) AS competition,
                       a.award_level AS awardLevel, a.winner_name AS winnerName,
                       a.supervisor_name AS supervisorName, a.year AS year,
                       '获奖' AS role
                FROM awardie_awards a
                LEFT JOIN awardie_competitions c
                       ON a.competition_id = c.id AND c.deleted = b'0' AND c.tenant_id = ?
                WHERE a.deleted = b'0' AND a.tenant_id = ?
                  AND REPLACE(REPLACE(a.winner_name, '，', ','), '、', ',') LIKE ?
                  AND a.granted_role = '教师'
                """ + yearCond + " ORDER BY a.year DESC, a.id DESC LIMIT " + MAX_ROWS,
                args);
        Map<Long, Map<String, Object>> merged = new LinkedHashMap<>();
        for (Map<String, Object> r : asSupervisor) {
            merged.put(((Number) r.get("id")).longValue(), r);
        }
        for (Map<String, Object> r : asWinner) {
            Long id = ((Number) r.get("id")).longValue();
            Map<String, Object> prev = merged.get(id);
            if (prev == null) {
                merged.put(id, r);
            } else {
                prev.put("role", "指导+获奖");
            }
        }
        return List.copyOf(merged.values());
    }

    private static String str(Object v) {
        return v == null ? "" : String.valueOf(v);
    }

    /** CSV 写出(与 BusinessExportController.writeCsv 同款:UTF-8 BOM 由 CsvWriter 负责 + 文件名双编码) */
    private void writeCsv(HttpServletResponse response, String name, String[] header, List<String[]> rows)
            throws IOException {
        response.setContentType("text/csv;charset=UTF-8");
        response.setCharacterEncoding("utf-8");
        String filename = name + "-" + LocalDate.now() + ".csv";
        response.setHeader("Content-Disposition",
                "attachment;filename=\"" + filename + "\"; filename*=UTF-8''"
                        + HttpUtils.encodeUtf8(filename));
        response.getOutputStream().write(CsvWriter.write(header, rows));
        response.getOutputStream().flush();
    }
}
