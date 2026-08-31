package com.awardie.teacher;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.auth.UserEntity;
import com.awardie.auth.UserRepository;

/** 教师门户聚合(Goal D,对照 v1 teacher/dashboard_ref+achievements_ref+data_export)——只读。 */
@RestController
@RequestMapping("/api/v2/teacher/portal")
public class TeacherPortalController {

    private final JdbcTemplate jdbc;
    private final UserRepository users;

    public TeacherPortalController(JdbcTemplate jdbc, UserRepository users) {
        this.jdbc = jdbc;
        this.users = users;
    }

    /** 仪表板:信息卡+计数+最近成果(指导∪获奖,去重)。 */
    @GetMapping("/summary")
    public Map<String, Object> summary(Authentication auth) {
        UserEntity me = requireTeacher(auth);
        Map<String, Object> profile = jdbc.queryForMap(
                "SELECT name, COALESCE(department, '') AS department, login_code AS teacher_id, "
                        + "COALESCE(skills, '') AS skills FROM users WHERE id = ?", me.getId());
        List<String> labs = jdbc.queryForList(
                "SELECT l.name FROM laboratory_instructors li INNER JOIN laboratories l ON li.laboratory_id = l.id "
                        + "WHERE li.teacher_id = ?", String.class, me.getId());
        Integer awardCount = jdbc.queryForObject("""
                SELECT COUNT(DISTINCT award_id) FROM (
                    SELECT award_id FROM award_teacher_winners WHERE teacher_id = ?
                    UNION ALL SELECT award_id FROM award_supervisors WHERE teacher_id = ?
                ) t
                """, Integer.class, me.getId(), me.getId());
        List<String> skills = jdbc.queryForList(
                "SELECT name FROM unnest(string_to_array(?, ',')) AS t(name) WHERE name <> ''", String.class,
                (String) profile.get("skills"));
        List<Map<String, Object>> recent = jdbc.queryForList("""
                SELECT DISTINCT c.competition_name AS competition, a.award_level AS awardLevel,
                       a.year, a.date
                FROM award_supervisors s
                INNER JOIN awards a ON s.award_id = a.id
                LEFT JOIN competitions c ON a.competition_id = c.id
                WHERE s.teacher_id = ?
                ORDER BY a.year DESC NULLS LAST LIMIT 5
                """, me.getId());
        return Map.of(
                "name", profile.get("name"),
                "department", profile.get("department"),
                "teacherId", profile.get("teacher_id"),
                "laboratories", labs,
                "skills", skills,
                "skillsCount", skills.size(),
                "awardCount", awardCount == null ? 0 : awardCount,
                "recentAwards", recent);
    }

    /** 成果展示:三计数+筛选表格(竞赛/年份/竞赛级别/获奖等级;指导∪获奖)。 */
    @GetMapping("/achievements")
    public Map<String, Object> achievements(Authentication auth,
            @RequestParam(required = false) Integer competitionId,
            @RequestParam(required = false) String year,
            @RequestParam(required = false) String competitionLevel,
            @RequestParam(required = false) String awardLevel) {
        UserEntity me = requireTeacher(auth);
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        List<Object> args = new java.util.ArrayList<>();
        if (competitionId != null) {
            where.append(" AND a.competition_id = ?");
            args.add(competitionId);
        }
        if (year != null && !year.isBlank()) {
            where.append(" AND a.year = ?");
            args.add(year.trim());
        }
        if (competitionLevel != null && !competitionLevel.isBlank()) {
            where.append(" AND a.competition_level = ?");
            args.add(competitionLevel.trim());
        }
        if (awardLevel != null && !awardLevel.isBlank()) {
            where.append(" AND a.award_level = ?");
            args.add(awardLevel.trim());
        }
        String scope = """
                INNER JOIN (
                    SELECT DISTINCT award_id FROM award_teacher_winners WHERE teacher_id = %d
                    UNION ALL SELECT award_id FROM award_supervisors WHERE teacher_id = %d
                ) mine ON mine.award_id = a.id
                """.formatted(me.getId(), me.getId());
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT a.id, c.competition_name AS competition, a.competition_level AS level,
                       a.award_level AS awardLevel, a.year, a.winner_name AS winnerName
                FROM awards a
                LEFT JOIN competitions c ON a.competition_id = c.id
                """ + scope + where + " ORDER BY a.year DESC NULLS LAST, a.id DESC LIMIT 200",
                args.toArray());
        Integer totalNational = jdbc.queryForObject(
                "SELECT COUNT(*) FROM awards a " + scope.replace("INNER", "\n                    INNER")
                        + where + " AND a.competition_level = '国赛'",
                Integer.class, args.toArray());
        Integer totalProvincial = jdbc.queryForObject(
                "SELECT COUNT(*) FROM awards a " + scope.replace("INNER", "\n                    INNER")
                        + where + " AND a.competition_level = '省赛'",
                Integer.class, args.toArray());
        return Map.of(
                "rows", rows,
                "totalNational", totalNational == null ? 0 : totalNational,
                "totalProvincial", totalProvincial == null ? 0 : totalProvincial,
                "totalAwards", rows.size());
    }

    /** 教师数据导出 CSV(对照 v1 teacher/data_export):本人关联成果明细。 */
    @GetMapping("/export.csv")
    public ResponseEntity<byte[]> exportCsv(Authentication auth, @RequestParam(required = false) String year) {
        UserEntity me = requireTeacher(auth);
        String where = year != null && !year.isBlank() ? " WHERE a.year = ?" : "";
        Object[] args = year != null && !year.isBlank() ? new Object[] {year} : new Object[0];
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT DISTINCT c.competition_name AS competition, a.award_level AS award_level,
                       a.year, a.winner_name AS winner_name
                FROM award_supervisors s
                INNER JOIN awards a ON s.award_id = a.id
                LEFT JOIN competitions c ON a.competition_id = c.id
                """ + where + " ORDER BY a.year DESC, c.competition_name", args);
        StringBuilder sb = new StringBuilder("\ufeff竞赛,获奖等级,年份,获奖人\r\n");
        for (Map<String, Object> r : rows) {
            sb.append(csvEsc(r.get("competition"))).append(',')
                    .append(csvEsc(r.get("award_level"))).append(',')
                    .append(csvEsc(r.get("year"))).append(',')
                    .append(csvEsc(r.get("winner_name"))).append("\r\n");
        }
        String filename = "teacher-achievements.csv";
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .contentType(MediaType.parseMediaType("text/csv;charset=UTF-8"))
                .body(sb.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }

    private String csvEsc(Object v) {
        String s = v == null ? "" : String.valueOf(v);
        return s.contains(",") || s.contains("\"") ? '"' + s.replace("\"", "\"\"") + '"' : s;
    }

    private UserEntity requireTeacher(Authentication auth) {
        UserEntity me = users.findByLoginCode(auth.getName()).orElseThrow();
        if (!"teacher".equalsIgnoreCase(me.getRole())) {
            throw new org.springframework.security.access.AccessDeniedException("仅教师可访问");
        }
        return me;
    }
}
