package com.awardie;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * 集成测试基座:集成测试共享的自举约定。
 *
 * seedAccounts 让测试对数据库状态自洽(空库/任意库均可跑)——
 * 这是 CI(GitHub Actions postgres service + Flyway V1 空库建表)的前提,
 * 也是"测试不依赖本地库存量数据"的边界。密码哈希用 v2 的 werkzeug scrypt
 * 兼容编码器生成,与存量 1834 条同构。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
public abstract class BaseIntegrationTest {

    @Autowired
    protected JdbcTemplate jdbc;

    @Autowired
    protected PasswordEncoder passwordEncoder;

    /** 三角色测试账号:不存在则建(口令与本地约定一致)。 */
    protected void seedAccounts() {
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('admin', '系统管理员', 'admin', ?, TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """, passwordEncoder.encode("Mayy123"));
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('212306413', '测试学生', 'student', ?, TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """, passwordEncoder.encode("P@ss301"));
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('02110606', '测试教师', 'teacher', ?, TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """, passwordEncoder.encode("P@ss301"));
    }
}
