package cn.iocoder.yudao.module.business.service.innovation;

import cn.hutool.core.util.StrUtil;
import cn.iocoder.yudao.framework.excel.core.util.ExcelUtils;
import cn.iocoder.yudao.module.business.dal.dataobject.innovation.InnovationProjectDO;
import cn.iocoder.yudao.module.business.dal.mysql.innovation.InnovationProjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.INNOVATION_IMPORT_BAD_HEADER;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.INNOVATION_IMPORT_PARSE_FAILED;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.INNOVATION_IMPORT_TOO_MANY_ROWS;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.INNOVATION_PREVIEW_INVALID;

/**
 * 大创 xlsx 导入(批8)
 *
 * <p>对照 v2 InnovationImportService,修四处缺陷:
 * <ol>
 *   <li><b>伪 sha256 校验</b> → 改服务端 preview 缓存 + 一次性 token,confirm 不再信任客户端 rows;</li>
 *   <li><b>无事务</b> → confirm 整体一个事务,结构性失败整批回滚;</li>
 *   <li><b>无行数上限/无表头校验</b> → 上限 1000 行(超限明确拒绝而非截断)、表头文字必须匹配;</li>
 *   <li><b>经费非法静默置 null</b> → 非法即行级错误。</li>
 * </ol>
 *
 * <p>保留 v2 语义:固定十列按索引读、只读第一个 sheet、首行表头、项目编号为幂等键、
 * 行级错误不阻断其它行、导入默认"进行中" + submitter_type=admin + 类型空时默认院级。
 *
 * @author AwardIE
 */
@Service
@Validated
@Slf4j
public class InnovationImportService {

    /** 固定十列的表头文字(顺序即列序,与 v2 导入页说明一致) */
    public static final List<String> EXPECTED_HEADER = List.of(
            "项目编号", "项目名称", "项目类型", "起始日期", "结束日期",
            "负责人姓名", "负责人学号", "其他成员", "指导教师", "经费");
    /** 导入行数上限(超出明确拒绝,不截断) */
    public static final int MAX_ROWS = 1000;
    /** 项目类型白名单(v2 CHECK 约束口径) */
    private static final Set<String> PROJECT_TYPES = Set.of("国家级", "省级", "院级");
    /** 项目类型缺省值(v2 导入时空值默认院级) */
    private static final String DEFAULT_PROJECT_TYPE = "院级";
    /** 经费换算:导入按万元填,库内存元(用户 2026-09-25 决策 C) */
    private static final BigDecimal WAN_TO_YUAN = new BigDecimal("10000");
    /** 经费上界:对齐列类型 DECIMAL(12,2),超出会在写库阶段让整批 confirm 回滚 */
    private static final BigDecimal MAX_FUNDING_YUAN = new BigDecimal("9999999999.99");

    @Resource
    private InnovationProjectMapper projectMapper;
    @Resource
    private InnovationImportCache importCache;
    @Resource
    private InnovationStudentMatcher studentMatcher;

    /**
     * 预览:解析 xlsx、逐行校验、缓存行数据并返回一次性 token
     *
     * <p>三道防线(批8 决策"方案一 + 两道防线"):
     * <ol>
     *   <li>强类型 DTO 读取:表头文字由 FastExcel 按 {@code @ExcelProperty} 匹配,
     *       对不上就报错——不给人眼核对留风险;</li>
     *   <li>行数上限:超过 {@value #MAX_ROWS} 行明确拒绝;</li>
     *   <li>响应回显首行内容:即便表头全对,也让管理员在预览里核对第一行数据是否被正确分列
     *       (列序调换但名字未变时,强类型读取能过,但回显能让人看出来)。</li>
     * </ol>
     *
     * @param file xlsx 文件
     * @return 预览结果(token + 首行回显 + 逐行校验明细)
     */
    public ImportPreview preview(MultipartFile file, Long tenantId, Long operatorId) {
        if (file == null || file.isEmpty()) {
            throw exception(INNOVATION_IMPORT_PARSE_FAILED);
        }
        // 表头严格校验(防线之一):强类型 DTO 读取对缺列/多列/列序变化都不报错
        // (缺列→字段 null,多余列→忽略,列序变→照读),必须自己比对原始表头文字。
        // 另一半防线是强类型读取本身(列名对不上时字段为 null,行级校验会暴露)。
        List<String> actualHeader;
        try {
            actualHeader = ExcelUtils.readHeader(file);
        } catch (IOException | RuntimeException e) {
            log.warn("[innovation-import] 表头读取失败: {}", e.getMessage());
            throw exception(INNOVATION_IMPORT_PARSE_FAILED);
        }
        List<String> normalizedHeader = actualHeader.stream().map(String::trim).toList();
        if (!EXPECTED_HEADER.equals(normalizedHeader)) {
            // 缺列、多列、列序调换、表头改字——一律结构性拒绝
            log.warn("[innovation-import] 表头不匹配,实际={}", normalizedHeader);
            throw exception(INNOVATION_IMPORT_BAD_HEADER);
        }
        List<InnovationImportRow> raw;
        try {
            raw = ExcelUtils.read(file, InnovationImportRow.class, MAX_ROWS + 1);
        } catch (IOException | RuntimeException e) {
            // 表头已校验过,此时的异常只能是文件本身损坏(如中途截断)
            log.warn("[innovation-import] 文件解析失败: {}", e.getMessage());
            throw exception(INNOVATION_IMPORT_PARSE_FAILED);
        }
        if (raw.size() > MAX_ROWS) {
            throw exception(INNOVATION_IMPORT_TOO_MANY_ROWS, MAX_ROWS);
        }
        List<ImportRow> rows = new ArrayList<>(raw.size());
        for (int i = 0; i < raw.size(); i++) {
            rows.add(parseRow(i + 2, raw.get(i))); // +2:1-based 行号,跳过表头
        }
        // token 绑定租户与操作人:否则 A 的 token 泄露后 B 能用它把 A 的数据写进 B 的库
        String token = importCache.put(List.copyOf(rows), tenantId, operatorId);
        int errorCount = (int) rows.stream().filter(r -> r.error() != null).count();
        return new ImportPreview(token, rows.size(), errorCount, firstRowEcho(raw), rows);
    }

    /** 回显首行内容:让管理员在预览里核对分列是否正确(防线之三) */
    private List<String> firstRowEcho(List<InnovationImportRow> raw) {
        if (raw.isEmpty()) {
            return List.of();
        }
        InnovationImportRow first = raw.get(0);
        return List.of(
                StrUtil.nullToEmpty(first.getProjectNo()),
                StrUtil.nullToEmpty(first.getProjectName()),
                StrUtil.nullToEmpty(first.getProjectType()),
                StrUtil.nullToEmpty(first.getStartDate()),
                StrUtil.nullToEmpty(first.getEndDate()),
                StrUtil.nullToEmpty(first.getLeaderName()),
                StrUtil.nullToEmpty(first.getLeaderId()),
                StrUtil.nullToEmpty(first.getOtherMembers()),
                StrUtil.nullToEmpty(first.getSupervisors()),
                StrUtil.nullToEmpty(first.getFunding()));
    }

    /**
     * 确认导入:凭 token 取回服务端缓存的行并入库
     *
     * @param token      预览令牌(一次性)
     * @param tenantId   租户编号
     * @param operatorId 操作人编号(写入 submitter_id)
     * @return 导入结果
     */
    @Transactional(rollbackFor = Exception.class)
    public ImportResult confirm(String token, Long tenantId, Long operatorId) {
        List<ImportRow> rows = importCache.consume(token, tenantId, operatorId);
        if (rows == null) {
            // token 无效/过期/已使用/主体不匹配——这正是 v2 伪校验修好后的行为:
            // 客户端篡改或重放都进不来,跨租户拿别人 token 也进不来
            throw exception(INNOVATION_PREVIEW_INVALID);
        }
        int imported = 0;
        int skipped = 0;
        int studentsLinked = 0;
        int studentsUnmatched = 0;
        List<String> errors = new ArrayList<>();
        List<Long> projectIds = new ArrayList<>();
        List<ImportRow> inserted = new ArrayList<>();

        for (ImportRow row : rows) {
            if (row.error() != null) {
                skipped++;
                errors.add("第 " + row.rowNo() + " 行:" + row.error());
                continue;
            }
            if (projectMapper.selectByProjectNo(row.projectNo(), tenantId) != null) {
                // v2 幂等:编号重复跳过。注意 errors[] 也记一条(沿 v2 语义),
                // 前端展示时要把 skipped 与 errors 分开看,否则重复行会显得像失败。
                skipped++;
                errors.add("第 " + row.rowNo() + " 行:项目编号 " + row.projectNo() + " 已存在,跳过");
                continue;
            }
            InnovationProjectDO entity = toEntity(row, tenantId, operatorId);
            try {
                projectMapper.insert(entity);
            } catch (DuplicateKeyException e) {
                // 并发导入同一编号:唯一键兜住,不整批失败
                skipped++;
                errors.add("第 " + row.rowNo() + " 行:项目编号 " + row.projectNo() + " 已存在,跳过");
                continue;
            }
            imported++;
            projectIds.add(entity.getId());
            inserted.add(row);
        }

        // 学生关联:逐行尽力匹配,不匹配计入 unmatched 而不阻断(决策 B-lite)
        for (int i = 0; i < inserted.size(); i++) {
            InnovationStudentMatcher.LinkOutcome outcome =
                    studentMatcher.linkStudents(inserted.get(i), projectIds.get(i), tenantId);
            studentsLinked += outcome.linked();
            studentsUnmatched += outcome.unmatched();
        }

        // 不打 token 明文(security-audit H-1:token 会进访问日志/浏览器历史,日志再打一遍是放大泄露面)
        log.info("[innovation-import] 确认导入:租户={} 操作人={} 共 {} 行,成功 {} 跳过 {} 关联 {} 未匹配 {}",
                tenantId, operatorId, rows.size(), imported, skipped, studentsLinked, studentsUnmatched);
        return new ImportResult(imported, skipped, errors, studentsLinked, studentsUnmatched);
    }

    private ImportRow parseRow(int rowNo, InnovationImportRow cells) {
        String projectNo = StrUtil.trim(StrUtil.nullToEmpty(cells.getProjectNo()));
        String projectName = StrUtil.trim(StrUtil.nullToEmpty(cells.getProjectName()));
        String projectType = StrUtil.trim(StrUtil.nullToEmpty(cells.getProjectType()));
        String startDate = StrUtil.trim(StrUtil.nullToEmpty(cells.getStartDate()));
        String endDate = StrUtil.trim(StrUtil.nullToEmpty(cells.getEndDate()));
        String leaderName = StrUtil.trim(StrUtil.nullToEmpty(cells.getLeaderName()));
        String leaderId = StrUtil.trim(StrUtil.nullToEmpty(cells.getLeaderId()));
        String otherMembers = StrUtil.trim(StrUtil.nullToEmpty(cells.getOtherMembers()));
        String supervisors = StrUtil.trim(StrUtil.nullToEmpty(cells.getSupervisors()));
        String fundingRaw = StrUtil.trim(StrUtil.nullToEmpty(cells.getFunding()));

        String error = null;
        if (StrUtil.isBlank(projectNo)) {
            // 编号是导入幂等键:空编号会让唯一索引失效(允许多行 NULL),重复文件能反复导入
            error = "项目编号不能为空";
        } else if (projectNo.length() > 50) {
            error = "项目编号不能超过 50 字符";
        } else if (StrUtil.isBlank(projectName)) {
            error = "项目名称不能为空";
        } else if (projectName.length() > 200) {
            error = "项目名称不能超过 200 字符";
        } else if (StrUtil.isNotBlank(projectType) && !PROJECT_TYPES.contains(projectType)) {
            error = "项目类型非法,仅允许 国家级/省级/院级";
        } else if (StrUtil.isNotBlank(startDate) && InnovationStatusService.parseLooseDate(startDate) == null) {
            error = "起始日期格式非法";
        } else if (StrUtil.isNotBlank(endDate) && InnovationStatusService.parseLooseDate(endDate) == null) {
            error = "结束日期格式非法";
        } else if (StrUtil.isNotBlank(fundingRaw) && parseFunding(fundingRaw) == null) {
            error = "经费格式非法,应为非负数字";
        }
        return new ImportRow(rowNo, projectNo, projectName, projectType, startDate, endDate,
                leaderName, leaderId, otherMembers, supervisors, fundingRaw, error);
    }

    /**
     * 经费解析:万元 → 元(乘 10000)
     *
     * <p>校验非负与 {@code DECIMAL(12,2)} 上界:超界会在数据库写入阶段让**整批**
     * confirm 回滚(v2 缺陷之一),必须在 preview 阶段就转成行级错误。
     *
     * @param raw 经费原文(单位:万元)
     * @return 换算后的元;非法/负数/超界返回 null
     */
    private BigDecimal parseFunding(String raw) {
        BigDecimal yuan;
        try {
            yuan = new BigDecimal(raw).multiply(WAN_TO_YUAN);
        } catch (NumberFormatException e) {
            return null;
        }
        if (yuan.signum() < 0 || yuan.compareTo(MAX_FUNDING_YUAN) > 0) {
            return null;
        }
        return yuan;
    }

    private InnovationProjectDO toEntity(ImportRow row, Long tenantId, Long operatorId) {
        InnovationProjectDO entity = new InnovationProjectDO();
        entity.setProjectNo(StrUtil.blankToDefault(row.projectNo(), null));
        entity.setProjectName(row.projectName());
        entity.setProjectType(StrUtil.blankToDefault(row.projectType(), DEFAULT_PROJECT_TYPE));
        entity.setStartDate(StrUtil.blankToDefault(row.startDate(), null));
        entity.setEndDate(StrUtil.blankToDefault(row.endDate(), null));
        entity.setStudentLeaderName(StrUtil.blankToDefault(row.leaderName(), null));
        entity.setStudentLeaderId(StrUtil.blankToDefault(row.leaderId(), null));
        entity.setOtherMembers(StudentMembers.toJson(row.otherMembers()));
        entity.setSupervisors(StrUtil.blankToDefault(row.supervisors(), null));
        entity.setFundingAmount(parseFunding(row.funding()));
        // v2 导入固定值
        entity.setStatus(InnovationProjectDO.STATUS_ONGOING);
        entity.setSubmitterType("admin");
        entity.setSubmitterId(operatorId);
        entity.setSubmitTime(java.time.LocalDateTime.now());
        entity.setTenantId(tenantId);
        return entity;
    }

    /**
     * 预览结果
     *
     * @param token        一次性令牌(confirm 凭此)
     * @param rowCount     总行数
     * @param errorCount   有校验错误的行数
     * @param firstRowEcho 首行十列内容回显(按 EXPECTED_HEADER 顺序),供管理员核对分列
     * @param rows         逐行明细
     */
    public record ImportPreview(String token, int rowCount, int errorCount,
                                List<String> firstRowEcho, List<ImportRow> rows) {
    }

    /**
     * 导入结果
     *
     * @param imported           成功导入行数
     * @param skipped            跳过行数(行级错误 + 编号重复)
     * @param errors             逐行说明
     * @param studentsLinked     建立的学生关联数
     * @param studentsUnmatched  未能建立任何关联的行数
     */
    public record ImportResult(int imported, int skipped, List<String> errors,
                               int studentsLinked, int studentsUnmatched) {
    }

    /**
     * 解析后的一行
     *
     * @param rowNo        Excel 行号(1-based,跳过表头)
     * @param projectNo    项目编号
     * @param projectName  项目名称
     * @param projectType  项目类型
     * @param startDate    起始日期
     * @param endDate      结束日期
     * @param leaderName   负责人姓名
     * @param leaderId     负责人学号
     * @param otherMembers 其他成员(顿号/逗号/分号分隔)
     * @param supervisors  指导教师
     * @param funding      经费原文(单位:万元)
     * @param error        行级错误;null 表示通过
     */
    public record ImportRow(int rowNo, String projectNo, String projectName, String projectType,
                            String startDate, String endDate, String leaderName, String leaderId,
                            String otherMembers, String supervisors, String funding, String error) {
    }

}
