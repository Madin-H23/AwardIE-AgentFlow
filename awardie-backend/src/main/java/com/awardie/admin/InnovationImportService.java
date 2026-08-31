package com.awardie.admin;

import java.io.ByteArrayInputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.xssf.usermodel.XSSFSheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.awardie.auth.UserEntity;

/**
 * 大创项目 xlsx 导入(#34,v1 真语义:大创走 admin 导入通道,CHECK 强制 submitter_type='admin')。
 * 幂等:project_no UNIQUE——重复导入行报"已存在"跳过,不重复写。
 */
@Service
public class InnovationImportService {

    public record ImportRow(int rowNo, String projectNo, String projectName, String projectType,
            String startDate, String endDate, String leaderName, String leaderId,
            String otherMembers, String supervisors, Double funding, String error) {
    }

    private final JdbcTemplate jdbc;

    public InnovationImportService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 解析 xlsx → 行记录(含行级校验错误,不影响其他行)。 */
    public List<ImportRow> parse(byte[] xlsx) {
        List<ImportRow> rows = new ArrayList<>();
        try (XSSFWorkbook wb = new XSSFWorkbook(new ByteArrayInputStream(xlsx))) {
            XSSFSheet sheet = wb.getSheetAt(0);
            Iterator<Row> it = sheet.iterator();
            int rowNo = 0;
            while (it.hasNext()) {
                Row r = it.next();
                rowNo++;
                if (rowNo == 1) {
                    continue; // 表头行
                }
                String[] c = new String[10];
                for (int i = 0; i < 10; i++) {
                    Cell cell = r.getCell(i);
                    if (cell == null) {
                        c[i] = "";
                    } else if (i == 9 && cell.getCellType() == org.apache.poi.ss.usermodel.CellType.NUMERIC) {
                        c[i] = String.valueOf(cell.getNumericCellValue());
                    } else {
                        c[i] = cell.getCellType() == org.apache.poi.ss.usermodel.CellType.NUMERIC
                                ? String.valueOf((long) cell.getNumericCellValue())
                                : cell.toString().trim();
                    }
                }
                String error = validate(c);
                Double funding = c[9].isBlank() ? null : tryDouble(c[9]);
                rows.add(new ImportRow(rowNo, c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8], funding, error));
            }
        } catch (Exception e) {
            throw new IllegalArgumentException("xlsx 解析失败:" + e.getMessage());
        }
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("xlsx 无数据行(首行视为表头)");
        }
        return rows;
    }

    private String validate(String[] c) {
        if (c[1] == null || c[1].isBlank()) {
            return "项目名称必填";
        }
        if (c[2] != null && !c[2].isBlank()
                && !java.util.List.of("国家级", "省级", "院级").contains(c[2])) {
            return "项目类型须为 国家级/省级/院级";
        }
        return null;
    }

    private Double tryDouble(String s) {
        try {
            return Double.valueOf(s);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    public record ImportResult(int imported, int skipped, List<String> errors) {}

    /** 确认导入:仅写无 error 的行;project_no 冲突=已存在跳过;留痕 system_event_log。 */
    public ImportResult importRows(List<ImportRow> rows, UserEntity operator) {
        int imported = 0;
        int skipped = 0;
        List<String> errors = new ArrayList<>();
        for (ImportRow r : rows) {
            if (r.error() != null && !r.error().isBlank()) {
                errors.add("第" + r.rowNo() + "行:" + r.error());
                continue;
            }
            if (r.projectNo() == null || r.projectNo().isBlank()) {
                errors.add("第" + r.rowNo() + "行:项目编号必填(幂等依赖编号)");
                continue;
            }
            try {
                jdbc.update("""
                        INSERT INTO innovation_projects
                            (project_no, project_name, project_type, start_date, end_date,
                             student_leader_name, student_leader_id, other_members, supervisors,
                             funding_amount, status, submitter_type, submitter_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?,
                                COALESCE(?::jsonb, '[]'::jsonb), ?, ?, '进行中', 'admin', ?)
                        """,
                        r.projectNo(), r.projectName(),
                        r.projectType() == null || r.projectType().isBlank() ? "院级" : r.projectType(),
                        r.startDate(), r.endDate(), r.leaderName(), r.leaderId(),
                        membersJson(r.otherMembers()), r.supervisors(), r.funding(), operator.getId());
                imported++;
            } catch (org.springframework.dao.DuplicateKeyException e) {
                skipped++;
                errors.add("第" + r.rowNo() + "行:项目编号 " + r.projectNo() + " 已存在,跳过");
            }
        }
        jdbc.update("""
                INSERT INTO system_event_log (event_category, event_level, event_message, operator_code, detail)
                VALUES ('upload', 'info', ?, ?, ?::jsonb)
                """, "大创导入:成功 " + imported + " 行,跳过 " + skipped, operator.getLoginCode(),
                "{\"rows\":" + rows.size() + ",\"imported\":" + imported + "}");
        return new ImportResult(imported, skipped, errors);
    }

    private String membersJson(String members) {
        if (members == null || members.isBlank()) {
            return null;
        }
        String[] names = members.split("[、,;，；]");
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < names.length; i++) {
            String n = names[i].trim().replace("\"", "");
            if (n.isEmpty()) {
                continue;
            }
            sb.append(i == 0 ? "" : ",").append('"').append(n).append('"');
        }
        return sb.append("]").toString();
    }

    /** 文件指纹(预览回传校验用,防上传/导入内容不一致)。 */
    public String sha256(byte[] data) {
        try {
            var d = MessageDigest.getInstance("SHA-256");
            return java.util.HexFormat.of().formatHex(d.digest(data));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    public Map<String, Object> preview(byte[] xlsx) {
        return Map.of("sha256", sha256(xlsx), "rows", parse(xlsx));
    }
}
