package com.awardie.admin;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** 数据导出(#31,对照 v1 admin_export):三张 CSV(UTF-8 BOM);xlsx 模板报告挂账(见对照记录)。 */
@RestController
@RequestMapping("/api/v2/admin/export")
public class AdminExportController {

    private final JdbcTemplate jdbc;
    private final XlsxReportService xlsx;

    public AdminExportController(JdbcTemplate jdbc, XlsxReportService xlsx) {
        this.jdbc = jdbc;
        this.xlsx = xlsx;
    }

    /** 系年度总结:按竞赛×获奖年份的汇总。format=xlsx|csv(#41 默认 xlsx)。 */
    @GetMapping("/department-summary.csv")
    public ResponseEntity<byte[]> departmentSummary(Authentication auth,
            @RequestParam(required = false) Integer year) {
        requireAdmin(auth);
        String where = year != null ? " WHERE a.year = ?" : "";
        Object[] args = year != null ? new Object[] {year} : new Object[0];
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT c.competition_name AS competition, COALESCE(a.year::TEXT, '-') AS year,
                       a.award_level AS award_level, COUNT(*) AS count
                FROM awards a INNER JOIN competitions c ON a.competition_id = c.id
                """ + where + """
                 GROUP BY 1, 2, 3 ORDER BY 2 DESC, 4 DESC
                """, args);
        String[] header = {"竞赛", "年份", "获奖等级", "数量"};
        return csv(rows, header, "department-summary");
    }

    /** #41:xlsx 报告(带样式)。 */
    @GetMapping("/department-summary.xlsx")
    public ResponseEntity<byte[]> departmentSummaryXlsx(Authentication auth,
            @RequestParam(required = false) Integer year) {
        requireAdmin(auth);
        return xlsxFile("department-summary", xlsx.departmentSummary(year));
    }

    /** 学生事务 CSV(次选格式保留)。 */
    @GetMapping("/student-affairs.csv")
    public ResponseEntity<byte[]> studentAffairs(Authentication auth) {
        requireAdmin(auth);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT w.student_id AS student_id, u.name AS student_name,
                       c.competition_name AS competition, a.award_level AS award_level,
                       COALESCE(a.year::TEXT, '-') AS year
                FROM award_student_winners w
                INNER JOIN users u ON w.student_id = u.id
                INNER JOIN awards a ON w.award_id = a.id
                LEFT JOIN competitions c ON a.competition_id = c.id
                ORDER BY w.student_id, a.year DESC NULLS LAST
                """);
        String[] header = {"学号", "姓名", "竞赛", "获奖等级", "年份"};
        return csv(rows, header, "student-affairs");
    }

    /** #41:学生事务 xlsx。 */
    @GetMapping("/student-affairs.xlsx")
    public ResponseEntity<byte[]> studentAffairsXlsx(Authentication auth) {
        requireAdmin(auth);
        return xlsxFile("student-affairs", xlsx.studentAffairs());
    }

    /** 教师个人 CSV(次选格式保留)。 */
    @GetMapping("/teacher-personal.csv")
    public ResponseEntity<byte[]> teacherPersonal(Authentication auth) {
        requireAdmin(auth);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT u.login_code AS teacher_code, u.name AS teacher_name,
                       c.competition_name AS competition, a.award_level AS award_level,
                       COALESCE(a.year::TEXT, '-') AS year, '指导教师' AS relation
                FROM award_supervisors s
                INNER JOIN users u ON s.teacher_id = u.id
                INNER JOIN awards a ON s.award_id = a.id
                LEFT JOIN competitions c ON a.competition_id = c.id
                ORDER BY u.login_code, a.year DESC NULLS LAST
                """);
        String[] header = {"工号", "姓名", "竞赛", "获奖等级", "年份", "关系"};
        return csv(rows, header, "teacher-personal");
    }

    /** #41:教师个人 xlsx。 */
    @GetMapping("/teacher-personal.xlsx")
    public ResponseEntity<byte[]> teacherPersonalXlsx(Authentication auth) {
        requireAdmin(auth);
        return xlsxFile("teacher-personal", xlsx.teacherPersonal());
    }

    private ResponseEntity<byte[]> xlsxFile(String name, byte[] body) {
        String filename = name + "-" + java.time.LocalDate.now() + ".xlsx";
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .contentType(MediaType.parseMediaType(
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                .body(body);
    }

    @SuppressWarnings("unchecked")
    private ResponseEntity<byte[]> csv(List<Map<String, Object>> rows, String[] header, String name) {
        StringBuilder sb = new StringBuilder();
        sb.append('\ufeff'); // UTF-8 BOM:Excel 直开不乱码
        sb.append(String.join(",", header)).append("\r\n");
        for (Map<String, Object> row : rows) {
            var values = row.values().stream().map(v -> {
                String s = v == null ? "" : String.valueOf(v);
                return s.contains(",") || s.contains("\"") || s.contains("\n")
                        ? '"' + s.replace("\"", "\"\"") + '"'
                        : s;
            }).toList();
            sb.append(String.join(",", values)).append("\r\n");
        }
        byte[] body = sb.toString().getBytes(StandardCharsets.UTF_8);
        String filename = name + "-" + java.time.LocalDate.now() + ".csv";
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .contentType(MediaType.parseMediaType("text/csv;charset=UTF-8"))
                .body(body);
    }

    private void requireAdmin(Authentication auth) {
        for (GrantedAuthority a : auth.getAuthorities()) {
            if (a.getAuthority().equals("ROLE_ADMIN")) {
                return;
            }
        }
        throw new org.springframework.security.access.AccessDeniedException("需要 admin 角色");
    }
}
