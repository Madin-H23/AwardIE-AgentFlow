package com.awardie.student;

import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.auth.UserEntity;
import com.awardie.auth.UserRepository;
import com.awardie.common.ApiResponse;

/** 学生门户聚合(#35,对照 v1 student/dashboard_ref):信息卡/统计/成果四表数据——只读。 */
@RestController
@RequestMapping("/api/v2/student/portal")
public class StudentPortalController {

    private final JdbcTemplate jdbc;
    private final UserRepository users;

    public StudentPortalController(JdbcTemplate jdbc, UserRepository users) {
        this.jdbc = jdbc;
        this.users = users;
    }

    /** 信息卡+统计:姓名/年级/专业/学号/实验室/技能标签 + 获奖/大创/标签计数。 */
    @GetMapping("/summary")
    public ApiResponse<Map<String, Object>> summary(Authentication auth) {
        UserEntity me = requireStudent(auth);
        Map<String, Object> profile = jdbc.queryForMap("""
                SELECT name, COALESCE(grade, '') AS grade, COALESCE(major, '') AS major,
                       login_code AS student_id, COALESCE(skills, '') AS skills,
                       profile_is_public AS public_profile
                FROM users WHERE id = ?
                """, me.getId());
        Integer awardCount = jdbc.queryForObject(
                "SELECT COUNT(*) FROM award_student_winners WHERE student_id = ?", Integer.class, me.getId());
        Integer innovationCount = jdbc.queryForObject("""
                SELECT COUNT(*) FROM innovation_project_students s
                INNER JOIN innovation_projects p ON s.project_id = p.id
                WHERE s.student_id = ?
                """, Integer.class, me.getId());
        List<String> skills = jdbc.queryForList(
                "SELECT name FROM unnest(string_to_array(?, ',')) AS t(name) WHERE name <> ''", String.class,
                (String) profile.get("skills"));
        List<Map<String, Object>> labs = jdbc.queryForList("""
                SELECT l.name FROM laboratory_students ls
                INNER JOIN laboratories l ON ls.laboratory_id = l.id
                WHERE ls.student_id = ?
                """, me.getId());
        return ApiResponse.ok(Map.of(
                "name", profile.get("name"),
                "grade", profile.get("grade"),
                "major", profile.get("major"),
                "studentId", profile.get("student_id"),
                "publicProfile", Boolean.TRUE.equals(profile.get("public_profile")),
                "laboratories", labs.stream().map(m -> m.get("name")).toList(),
                "skills", skills,
                "skillsCount", skills.size(),
                "awardCount", awardCount == null ? 0 : awardCount,
                "innovationCount", innovationCount == null ? 0 : innovationCount));
    }

    /** 成果四表:获奖/大创/专利/软著(对照 v1 我的成果区)。 */
    @GetMapping("/achievements")
    public ApiResponse<Map<String, Object>> achievements(Authentication auth) {
        UserEntity me = requireStudent(auth);
        List<Map<String, Object>> awards = jdbc.queryForList("""
                SELECT c.competition_name AS competition, a.competition_level AS level,
                       a.award_level AS awardLevel, a.year
                FROM award_student_winners w
                INNER JOIN awards a ON w.award_id = a.id
                LEFT JOIN competitions c ON a.competition_id = c.id
                WHERE w.student_id = ?
                ORDER BY a.year DESC NULLS LAST
                """, me.getId());
        List<Map<String, Object>> innovations = jdbc.queryForList("""
                SELECT p.project_no AS projectNo, p.project_name AS projectName,
                       p.project_type AS projectType, p.student_leader_name AS leader,
                       p.supervisors, p.status
                FROM innovation_project_students s
                INNER JOIN innovation_projects p ON s.project_id = p.id
                WHERE s.student_id = ?
                ORDER BY p.id DESC
                """, me.getId());
        List<Map<String, Object>> patents = jdbc.queryForList("""
                SELECT id, patent_name AS patentName, patent_type AS patentType
                FROM patents WHERE submitter_type = 'student' AND submitter_id = ?
                ORDER BY id DESC
                """, me.getId());
        List<Map<String, Object>> software = jdbc.queryForList("""
                SELECT id, software_name AS softwareName, registration_number AS registrationNumber
                FROM software_copyrights WHERE submitter_type = 'student' AND submitter_id = ?
                ORDER BY id DESC
                """, me.getId());
        return ApiResponse.ok(Map.of(
                "awards", awards,
                "innovations", innovations,
                "patents", patents,
                "software", software));
    }

    private UserEntity requireStudent(Authentication auth) {
        UserEntity me = users.findByLoginCode(auth.getName()).orElseThrow();
        if (!"student".equalsIgnoreCase(me.getRole())) {
            throw new org.springframework.security.access.AccessDeniedException("仅学生可访问");
        }
        return me;
    }
}
