package com.awardie.profile;

import java.time.Instant;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.auth.UserEntity;
import com.awardie.auth.UserRepository;
import com.awardie.common.ApiResponse;

/** 个人资料(#17,高频扩展队列第一项):查看/修改,字段与 v1 FR-PROFILE 等价。 */
@RestController
@RequestMapping("/api/v2/profile")
public class ProfileController {

    /** 学生/教师字段超集:v1 按 role 区分展示,存储列同表。 */
    public record ProfileView(String loginCode, String name, String role, String phone, String qq,
            String skills, String major, String grade, String title, String department, boolean profileIsPublic) {}

    public record ProfileUpdate(String name, String phone, String qq, String skills, String major,
            String grade, String title, String department, Boolean profileIsPublic) {}

    private final UserRepository users;
    private final JdbcTemplate jdbc;

    public ProfileController(UserRepository users, JdbcTemplate jdbc) {
        this.users = users;
        this.jdbc = jdbc;
    }

    private UserEntity requireUser(Authentication auth) {
        return users.findByLoginCode(auth.getName()).orElseThrow();
    }

    @GetMapping
    public ApiResponse<ProfileView> me(Authentication auth) {
        UserEntity u = requireUser(auth);
        return ApiResponse.ok(new ProfileView(u.getLoginCode(), u.getName(), u.getRole(),
                u.getPhone(), u.getQq(), u.getSkills(), u.getMajor(), u.getGrade(),
                u.getTitle(), u.getDepartment(), Boolean.TRUE.equals(u.getProfileIsPublic())));
    }

    @PutMapping
    public ApiResponse<ProfileView> update(@RequestBody ProfileUpdate req, Authentication auth) {
        UserEntity u = requireUser(auth);
        jdbc.update("""
                UPDATE users SET name=?, phone=?, qq=?, skills=?, major=?, grade=?, title=?,
                    department=?, profile_is_public=?, updated_at=?
                WHERE id=?
                """,
                req.name(), req.phone(), req.qq(), req.skills(), req.major(), req.grade(),
                req.title(), req.department(), req.profileIsPublic(), java.sql.Timestamp.from(Instant.now()), u.getId());
        return me(auth);
    }

    /** 前端字典:按角色展示哪些字段(v1 语义)。 */
    @GetMapping("/fields")
    public ApiResponse<Map<String, Object>> fields(Authentication auth) {
        UserEntity u = requireUser(auth);
        boolean student = "student".equalsIgnoreCase(u.getRole());
        return ApiResponse.ok(Map.of(
                "role", u.getRole(),
                "fields", student
                        ? java.util.List.of("name", "phone", "qq", "skills", "major", "grade")
                        : java.util.List.of("name", "phone", "qq", "title", "department")));
    }
}
