package com.awardie.admin;

import java.io.ByteArrayOutputStream;
import java.util.List;
import java.util.Map;

import org.apache.poi.ss.usermodel.BorderStyle;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellStyle;
import org.apache.poi.ss.usermodel.FillPatternType;
import org.apache.poi.ss.usermodel.Font;
import org.apache.poi.ss.usermodel.IndexedColors;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** xlsx 模板化报告(#41,对照 v1 export_utils 产物样式:表头底色/边框/列宽)。 */
@Service
public class XlsxReportService {

    private final JdbcTemplate jdbc;

    public XlsxReportService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 系年度总结:汇总 sheet(竞赛×年份×等级)+明细 sheet。 */
    public byte[] departmentSummary(Integer year) {
        String where = year != null ? " WHERE a.year = ?" : "";
        Object[] args = year != null ? new Object[] {year} : new Object[0];
        List<Map<String, Object>> summary = jdbc.queryForList("""
                SELECT c.competition_name AS col1, COALESCE(a.year::TEXT, '-') AS col2,
                       a.award_level AS col3, COUNT(*) AS col4
                FROM awards a INNER JOIN competitions c ON a.competition_id = c.id
                """ + where + """
                 GROUP BY 1, 2, 3 ORDER BY 2 DESC, 4 DESC
                """, args);
        List<Map<String, Object>> detail = jdbc.queryForList("""
                SELECT c.competition_name AS col1, a.winner_name AS col2, a.award_level AS col3,
                       COALESCE(a.year::TEXT, '-') AS col4, a.competition_level AS col5
                FROM awards a LEFT JOIN competitions c ON a.competition_id = c.id
                """ + where + """
                 ORDER BY a.id DESC LIMIT 500
                """, args);
        try (XSSFWorkbook wb = new XSSFWorkbook()) {
            CellStyle head = headerStyle(wb);
            CellStyle body = bodyStyle(wb);
            Sheet s1 = wb.createSheet("年度汇总");
            writeSheet(s1, head, body,
                    new String[] {"竞赛", "年份", "获奖等级", "数量"}, summary);
            Sheet s2 = wb.createSheet("获奖明细");
            writeSheet(s2, head, body,
                    new String[] {"竞赛", "获奖人", "获奖等级", "年份", "竞赛级别"}, detail);
            return toBytes(wb);
        } catch (Exception e) {
            throw new IllegalStateException("xlsx 生成失败:" + e.getMessage(), e);
        }
    }

    /** 学生事务明细。 */
    public byte[] studentAffairs() {
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT w.student_id::TEXT AS col1, u.name AS col2,
                       c.competition_name AS col3, a.award_level AS col4, COALESCE(a.year::TEXT, '-') AS col5
                FROM award_student_winners w
                INNER JOIN users u ON w.student_id = u.id
                INNER JOIN awards a ON w.award_id = a.id
                LEFT JOIN competitions c ON a.competition_id = c.id
                ORDER BY w.student_id, a.year DESC NULLS LAST
                """);
        try (XSSFWorkbook wb = new XSSFWorkbook()) {
            CellStyle head = headerStyle(wb);
            CellStyle body = bodyStyle(wb);
            writeSheet(wb.createSheet("学生获奖明细"), head, body,
                    new String[] {"学号", "姓名", "竞赛", "获奖等级", "年份"}, rows);
            return toBytes(wb);
        } catch (Exception e) {
            throw new IllegalStateException("xlsx 生成失败:" + e.getMessage(), e);
        }
    }

    /** 教师个人(指导成果)。 */
    public byte[] teacherPersonal() {
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT u.login_code AS col1, u.name AS col2,
                       c.competition_name AS col3, a.award_level AS col4, COALESCE(a.year::TEXT, '-') AS col5
                FROM award_supervisors s
                INNER JOIN users u ON s.teacher_id = u.id
                INNER JOIN awards a ON s.award_id = a.id
                LEFT JOIN competitions c ON a.competition_id = c.id
                ORDER BY u.login_code, a.year DESC NULLS LAST
                """);
        try (XSSFWorkbook wb = new XSSFWorkbook()) {
            CellStyle head = headerStyle(wb);
            CellStyle body = bodyStyle(wb);
            writeSheet(wb.createSheet("教师指导成果"), head, body,
                    new String[] {"工号", "姓名", "竞赛", "获奖等级", "年份"}, rows);
            return toBytes(wb);
        } catch (Exception e) {
            throw new IllegalStateException("xlsx 生成失败:" + e.getMessage(), e);
        }
    }

    private void writeSheet(Sheet sheet, CellStyle head, CellStyle body, String[] header,
            List<Map<String, Object>> rows) {
        Row h = sheet.createRow(0);
        for (int i = 0; i < header.length; i++) {
            Cell c = h.createCell(i);
            c.setCellValue(header[i]);
            c.setCellStyle(head);
            sheet.setColumnWidth(i, 18 * 256);
        }
        int r = 1;
        for (Map<String, Object> row : rows) {
            Row line = sheet.createRow(r++);
            List<Object> vals = row.values().stream().toList();
            for (int i = 0; i < header.length; i++) {
                Cell c = line.createCell(i);
                Object v = i < vals.size() ? vals.get(i) : null;
                c.setCellValue(v == null ? "" : String.valueOf(v));
                c.setCellStyle(body);
            }
        }
    }

    private CellStyle headerStyle(XSSFWorkbook wb) {
        CellStyle style = wb.createCellStyle();
        Font font = wb.createFont();
        font.setBold(true);
        font.setColor(IndexedColors.WHITE.getIndex());
        style.setFont(font);
        style.setFillForegroundColor(IndexedColors.ROYAL_BLUE.getIndex());
        style.setFillPattern(FillPatternType.SOLID_FOREGROUND);
        border(style);
        return style;
    }

    private CellStyle bodyStyle(XSSFWorkbook wb) {
        CellStyle style = wb.createCellStyle();
        border(style);
        return style;
    }

    private void border(CellStyle style) {
        style.setBorderTop(BorderStyle.THIN);
        style.setBorderBottom(BorderStyle.THIN);
        style.setBorderLeft(BorderStyle.THIN);
        style.setBorderRight(BorderStyle.THIN);
    }

    private byte[] toBytes(XSSFWorkbook wb) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        wb.write(out);
        return out.toByteArray();
    }
}
