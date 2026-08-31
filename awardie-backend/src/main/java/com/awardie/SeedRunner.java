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

        // 业务种子(CI E2E 列表页断言依赖;幂等):2 竞赛 + admin 1 条 pending 提交
        jdbc.update("""
                INSERT INTO competitions (competition_name, white_list, watch_list, is_auto_added)
                VALUES ('种子竞赛-白名单', TRUE, FALSE, FALSE)
                ON CONFLICT (competition_name) DO NOTHING
                """);
        jdbc.update("""
                INSERT INTO competitions (competition_name, white_list, watch_list, is_auto_added)
                VALUES ('种子竞赛-观察', FALSE, TRUE, FALSE)
                ON CONFLICT (competition_name) DO NOTHING
                """);
        Integer seeded = jdbc.queryForObject(
                "SELECT COUNT(*) FROM pending_achievements WHERE file_hash='seed-e2e-admin-0001'", Integer.class);
        if (seeded != null && seeded == 0) {
            Integer adminId = jdbc.queryForObject(
                    "SELECT id FROM users WHERE login_code='admin'", Integer.class);
            jdbc.update("""
                    INSERT INTO pending_achievements
                        (achievement_type, achievement_data, submitter_type, submitter_id,
                         submit_time, status, file_path, file_hash, version, created_at)
                    VALUES ('award', ?::jsonb, 'admin', ?,
                            NOW(), 'pending', 'seed/e2e-admin.png', 'seed-e2e-admin-0001', 1, NOW())
                    """, "{\"competition_name\":\"种子竞赛-白名单\",\"award_level\":\"一等奖\","
                    + "\"winner_name\":\"种子获奖人\",\"date\":\"2026-08\"}", adminId);
        }
        // 自动归档默认配置行(#32):五类型矩阵,默认全关(v1 同构;幂等)
        jdbc.update("""
                INSERT INTO auto_archive_config (achievement_type, validation_status, auto_archive_enabled) VALUES
                ('award', 'valid', FALSE), ('award', 'invalid', FALSE),
                ('patent', 'valid', FALSE), ('patent', 'invalid', FALSE),
                ('software', 'valid', FALSE), ('software', 'invalid', FALSE),
                ('innovation', NULL, FALSE), ('other', NULL, FALSE)
                ON CONFLICT (achievement_type, validation_status) DO NOTHING
                """);
        System.out.println("[seed] accounts + business data seeded, exiting");
        SpringApplication.exit(context, () -> 0);
    }
}
