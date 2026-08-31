package com.awardie;

import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.context.ApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * 测试/演示环境自举(#16 e2e 前置):--spring.profiles.active=seed 时
 * 注入三角色账号后退出。口令哈希与 v1 兼容(werkzeug scrypt 格式)。
 */
@Component
public class SeedRunner implements CommandLineRunner {

    private final JdbcTemplate jdbc;
    private final PasswordEncoder encoder;
    private final ApplicationContext context;

    public SeedRunner(JdbcTemplate jdbc, PasswordEncoder encoder, ApplicationContext context) {
        this.jdbc = jdbc;
        this.encoder = encoder;
        this.context = context;
    }

    @Override
    public void run(String... args) {
        if (!context.getEnvironment().acceptsProfiles(org.springframework.core.env.Profiles.of("seed"))) {
            return;
        }
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('admin', '测试管理员', 'admin', ?, TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """, encoder.encode("Mayy123"));
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('212306413', '测试学生', 'student', ?, TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """, encoder.encode("P@ss301"));
        jdbc.update("""
                INSERT INTO users (login_code, name, role, password_hash, user_activated, needs_password_change)
                VALUES ('02110606', '测试教师', 'teacher', ?, TRUE, FALSE)
                ON CONFLICT (login_code) DO NOTHING
                """, encoder.encode("P@ss301"));
        System.out.println("[seed] accounts seeded, exiting");
        SpringApplication.exit(context, () -> 0);
    }
}
