package cn.iocoder.yudao.module.business.service.vault;

import cn.iocoder.yudao.module.business.service.reference.AchievementReferenceChecker;
import jakarta.annotation.Resource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.VAULT_RECORD_IN_USE;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.VAULT_RECORD_NOT_EXISTS;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.VAULT_TYPE_INVALID;

/**
 * 成果库(批6):五类已入库成果的分页列表 + 行编辑 + 行删除,语义对照 v2 AdminVaultController(Fix-C)
 *
 * <p>v2 的 VaultSpec 用枚举白名单固化"表名/名称列/SELECT 列",杜绝字符串拼接注入面;v3 沿用该
 * 思路:类型 → 规格的映射是代码内枚举,SQL 里只出现枚举里的表名列名,值一律参数化。
 *
 * @author AwardIE
 */
@Service
@Validated
public class AchievementVaultService {

    @Resource
    private JdbcTemplate jdbcTemplate;
    @Resource
    private AchievementReferenceChecker referenceChecker;

    /** 五类成果的表/名称列/列表列白名单(同 v2 VaultSpec) */
    public enum VaultSpec {
        /** 获奖成果 */
        AWARDS("awardie_awards", "competition_name_in_file",
                "id, competition_name_in_file AS name, competition_level, award_level, "
                        + "winner_name, supervisor_name, year, is_abnormal, laboratory_id"),
        /** 专利 */
        PATENTS("awardie_patents", "patent_name",
                "id, patent_name AS name, patent_type, application_number, patentee, inventor, laboratory_id"),
        /** 软件著作权 */
        SOFTWARE("awardie_software_copyrights", "software_name",
                "id, software_name AS name, software_version, registration_number, copyright_owner, laboratory_id"),
        /** 大创项目 */
        INNOVATION("awardie_innovation_projects", "project_name",
                "id, project_no, project_name AS name, project_type, student_leader_name, supervisors, status, laboratory_id"),
        /** 其他成果文件 */
        OTHER("awardie_other_files", "file_name",
                "id, file_name AS name, file_type, file_size, description, laboratory_id");

        private final String table;
        private final String nameColumn;
        private final String columns;

        VaultSpec(String table, String nameColumn, String columns) {
            this.table = table;
            this.nameColumn = nameColumn;
            this.columns = columns;
        }

        public String table() {
            return table;
        }

        public String nameColumn() {
            return nameColumn;
        }

        public String columns() {
            return columns;
        }

        /**
         * 按类型取规格
         *
         * @param type 成果类型
         * @return 规格
         */
        public static VaultSpec of(String type) {
            return switch (type) {
                case "award" -> AWARDS;
                case "patent" -> PATENTS;
                case "software" -> SOFTWARE;
                case "innovation" -> INNOVATION;
                case "other" -> OTHER;
                default -> throw exception(VAULT_TYPE_INVALID);
            };
        }
    }

    /** 表存在性(批5 起成果表陆续建,列表端点对未建表类型跳过而非 500) */
    private boolean tableExists(String table) {
        Long n = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?",
                Long.class, table);
        return n != null && n > 0;
    }

    /**
     * 五类分页列表(关键词按名称模糊;对照 v2 vault/{type})
     *
     * @param type    成果类型
     * @param pageNo  页码
     * @param pageSize 每页条数
     * @param keyword 名称关键词
     * @param tenantId 租户
     * @return 分页结果(list/total)
     */
    public Map<String, Object> list(String type, Integer pageNo, Integer pageSize, String keyword, Long tenantId) {
        VaultSpec spec = VaultSpec.of(type);
        if (!tableExists(spec.table())) {
            Map<String, Object> empty = new LinkedHashMap<>(4);
            empty.put("list", List.of());
            empty.put("total", 0L);
            return empty;
        }
        int page = Math.max(pageNo == null ? 1 : pageNo, 1);
        int size = Math.min(Math.max(pageSize == null ? 20 : pageSize, 1), 100);
        StringBuilder where = new StringBuilder(" WHERE deleted = b'0' AND tenant_id = ?");
        java.util.List<Object> args = new java.util.ArrayList<>();
        args.add(tenantId);
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND ").append(spec.nameColumn()).append(" LIKE ?");
            args.add("%" + keyword.trim() + "%");
        }
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM " + spec.table() + where, Long.class, args.toArray());
        java.util.List<Object> listArgs = new java.util.ArrayList<>(args);
        listArgs.add(size);
        listArgs.add((long) (page - 1) * size);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT " + spec.columns() + " FROM " + spec.table() + where
                        + " ORDER BY id DESC LIMIT ? OFFSET ?", listArgs.toArray());
        Map<String, Object> result = new LinkedHashMap<>(4);
        result.put("list", rows);
        result.put("total", total == null ? 0L : total);
        return result;
    }

    /**
     * 行编辑:awards 核心字段(award_level/winner_name/supervisor_name/laboratory_id,对照 v2 Fix-C)
     *
     * @param type 成果类型
     * @param id   记录编号
     * @param fields 可更新字段(键为列名白名单内)
     * @return 影响行数
     */
    @Transactional(rollbackFor = Exception.class)
    public int update(String type, Long id, Map<String, Object> fields) {
        VaultSpec spec = VaultSpec.of(type);
        if (!tableExists(spec.table())) {
            throw exception(VAULT_RECORD_NOT_EXISTS);
        }
        // 列名白名单:仅允许各表的可编辑列,杜绝任意列注入
        List<String> editable = editableColumns(spec);
        List<String> cols = new java.util.ArrayList<>();
        List<Object> vals = new java.util.ArrayList<>();
        for (Map.Entry<String, Object> e : fields.entrySet()) {
            if (editable.contains(e.getKey())) {
                cols.add(e.getKey());
                vals.add(e.getValue());
            }
        }
        if (cols.isEmpty()) {
            throw exception(VAULT_RECORD_NOT_EXISTS);
        }
        String setClause = String.join(", ", cols.stream().map(c -> c + " = ?").toList());
        vals.add(id);
        int n = jdbcTemplate.update("UPDATE " + spec.table() + " SET " + setClause + " WHERE id = ?",
                vals.toArray());
        if (n == 0) {
            throw exception(VAULT_RECORD_NOT_EXISTS);
        }
        return n;
    }

    /**
     * 行删除:引用检查(引用表未建则跳过)
     *
     * @param type 成果类型
     * @param id   记录编号
     * @param tenantId 租户
     * @return 影响行数
     */
    @Transactional(rollbackFor = Exception.class)
    public int delete(String type, Long id, Long tenantId) {
        VaultSpec spec = VaultSpec.of(type);
        if (!tableExists(spec.table())) {
            throw exception(VAULT_RECORD_NOT_EXISTS);
        }
        // 大创被项目学生关联引用、成果被实验室关联引用——按表分派引用清单
        Map<String, String> references = referenceMapFor(spec);
        referenceChecker.validateNoReference(id, references, VAULT_RECORD_IN_USE);
        int n = jdbcTemplate.update("DELETE FROM " + spec.table() + " WHERE id = ? AND tenant_id = ?",
                id, tenantId);
        if (n == 0) {
            throw exception(VAULT_RECORD_NOT_EXISTS);
        }
        return n;
    }

    /** 各类成果的引用清单(引用表未建时 checker 自动跳过) */
    private Map<String, String> referenceMapFor(VaultSpec spec) {
        return switch (spec) {
            case AWARDS -> Map.of("awardie_award_student_winners", "award_id");
            case INNOVATION -> Map.of("awardie_innovation_project_students", "project_id");
            default -> Map.of();
        };
    }

    /** 各表可编辑列白名单 */
    private List<String> editableColumns(VaultSpec spec) {
        return switch (spec) {
            case AWARDS -> List.of("competition_level", "award_level", "winner_name", "supervisor_name",
                    "year", "group_name", "province", "is_abnormal", "laboratory_id");
            case PATENTS -> List.of("patent_type", "application_number", "publication_number", "inventor",
                    "patentee", "application_date", "laboratory_id");
            case SOFTWARE -> List.of("software_version", "registration_number", "copyright_owner",
                    "certificate_no", "registration_date", "laboratory_id");
            case INNOVATION -> List.of("project_name", "project_type", "start_date", "end_date",
                    "student_leader_name", "supervisors", "status", "laboratory_id");
            case OTHER -> List.of("file_name", "description", "laboratory_id");
        };
    }

}
