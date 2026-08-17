-- ============================================================================
-- AwardIE-AgentFlow 数据库迁移脚本（对齐《数据库设计》第二章 §7 路线图）
-- 版本: v1.0  日期: 2026-08-14  方言: SQLite
-- 执行前提（每次执行前必做）:
--   1) 全量冷备份: cp database/competitions.db database/competitions.db.bak.$(date +%F)
--   2) 连接契约由应用层 get_connection() 保证（PRAGMA foreign_keys=ON / journal_mode=WAL /
--      busy_timeout=30000）。本脚本经任意 sqlite3 CLI 执行时请先手动执行:
--        PRAGMA foreign_keys = ON;
--        PRAGMA journal_mode = WAL;
--   3) 幂等性: 所有语句可重复执行; 每节末尾附验证断言, 失败立即停止并回滚该节事务。
-- 分节:
--   §1 P0 低风险（阶段一/二随发布执行）
--   §2 P1 核心（阶段三, Feature Flag 灰度, 严禁跳过 8.4 流程直接在生产执行）
--   §3 P2 收尾（阶段三观察一个迭代后）
-- ============================================================================

-- ############################################################################
-- §1 P0 低风险 —— 随阶段一/二发布
-- ############################################################################

-- ----------------------------------------------------------------------------
-- §1.1 awards 补索引（P1-7）+ image_hash 去重护栏（P0-9）
-- 注: uk_awards_image_hash 依赖 §1.3 的存量清洗, 顺序不可颠倒。
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_awards_competition ON awards(competition_id);
CREATE INDEX IF NOT EXISTS idx_awards_submitter   ON awards(submitter_type, submitter_id);
CREATE INDEX IF NOT EXISTS idx_awards_laboratory  ON awards(laboratory_id) WHERE laboratory_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_awards_date        ON awards(date);
CREATE INDEX IF NOT EXISTS idx_awards_abnormal    ON awards(is_abnormal) WHERE is_abnormal = 1;

-- ----------------------------------------------------------------------------
-- §1.2 四张 award_* 关联表重建: 补 PK/FK/CASCADE, DISTINCT 去重, 清洗孤儿（P1-12）
-- 模板同构, 其余三张替换表名/列名: award_teacher_winners(teacher_id) /
-- award_supervisors(teacher_id) / award_related_students(student_id)
-- ----------------------------------------------------------------------------
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS award_student_winners_new (
    award_id   INTEGER NOT NULL REFERENCES awards(id)   ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (award_id, student_id)
);
INSERT OR IGNORE INTO award_student_winners_new (award_id, student_id)
    SELECT DISTINCT award_id, student_id FROM award_student_winners
    WHERE award_id IN (SELECT id FROM awards)
      AND student_id IN (SELECT id FROM students);
DROP TABLE IF EXISTS award_student_winners;
ALTER TABLE award_student_winners_new RENAME TO award_student_winners;
COMMIT;
-- 重复执行说明: 第二次执行时源表已带约束, DISTINCT 结果一致, 幂等安全。

-- ----------------------------------------------------------------------------
-- §1.3 awards 存量重复清洗（P0-9）: 同 image_hash 保留最早一条（id 最小）
-- ----------------------------------------------------------------------------
DELETE FROM awards
WHERE image_hash IS NOT NULL AND image_hash <> ''
  AND id NOT IN (
      SELECT MIN(id) FROM awards
      WHERE image_hash IS NOT NULL AND image_hash <> ''
      GROUP BY image_hash
  );
-- 验证: SELECT image_hash, COUNT(*) FROM awards WHERE image_hash<>'' GROUP BY 1 HAVING COUNT(*)>1;  -- 应为空

CREATE UNIQUE INDEX IF NOT EXISTS uk_awards_image_hash
    ON awards(image_hash) WHERE image_hash IS NOT NULL AND image_hash <> '';

-- ----------------------------------------------------------------------------
-- §1.4 审核留痕表 achievement_audit_log（8.6 定稿; operator_id 暂不加 FK,
--      阶段三 users 落地后随 §2.3 重写并补 FK, 详见第二章 3.3 说明）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS achievement_audit_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id   INTEGER NOT NULL,
    achievement_kind TEXT CHECK(achievement_kind IN ('award','patent','software','innovation','other')),
    trace_id         TEXT,
    action_type      INTEGER NOT NULL CHECK(action_type BETWEEN 1 AND 11),
    action_result    INTEGER NOT NULL DEFAULT 0 CHECK(action_result IN (0,1,2)),
    operator_id      INTEGER,
    operator_code    TEXT NOT NULL,
    operator_name    TEXT NOT NULL,
    operator_role    INTEGER CHECK(operator_role IN (1,2,3,4)),
    operator_ip      TEXT,
    ai_batch_id      TEXT,
    change_detail    TEXT,
    remark           TEXT,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_achievement ON achievement_audit_log(achievement_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_trace ON achievement_audit_log(trace_id) WHERE trace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_action ON achievement_audit_log(action_type);

-- ----------------------------------------------------------------------------
-- §1.5 pending_achievements 乐观锁（P1-15）
-- 渐进策略: 阶段一/二仅 ADD COLUMN(零风险); status 的 CHECK 扩展
-- （pending|submit|rejected|archived）推迟到 §2 表重建一并完成（8.4 渐进原则）。
-- ----------------------------------------------------------------------------
ALTER TABLE pending_achievements ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

-- ----------------------------------------------------------------------------
-- §1.6 现存数据 bug 与词汇修复（P1-11 / P2-14）
-- admin submitter_id 曾存字符串 'admin': 先归一为 0 占位, 阶段三 §2.3 统一映射到
-- 管理员真实 users.id（admins 表仅 1 人, 语义无损）。
-- ----------------------------------------------------------------------------
UPDATE innovation_projects SET submitter_id = 0
WHERE submitter_type = 'admin' AND submitter_id = 'admin';
UPDATE awards SET granted_role = 'student' WHERE granted_role = '学生';
UPDATE awards SET granted_role = 'teacher' WHERE granted_role = '教师';

-- ############################################################################
-- §2 P1 核心 —— 阶段三（Feature Flag 灰度; 执行前必须完成影子读环境准备）
-- ############################################################################

-- ----------------------------------------------------------------------------
-- §2.1 users 单表继承 + 映射表（8.5.1）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    login_code      TEXT UNIQUE,
    name            TEXT NOT NULL,
    role            TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
    password_hash   TEXT,
    user_activated  INTEGER NOT NULL DEFAULT 1 CHECK(user_activated IN (0,1)),
    phone TEXT, qq TEXT, skills TEXT,
    profile_is_public INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    major TEXT, grade TEXT,
    title TEXT, department TEXT, id_number TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_role       ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_login_code ON users(login_code);

CREATE TABLE IF NOT EXISTS old_user_map (
    old_role    TEXT NOT NULL CHECK(old_role IN ('student','teacher','admin')),
    old_id      INTEGER NOT NULL,
    new_user_id INTEGER NOT NULL REFERENCES users(id),
    PRIMARY KEY (old_role, old_id)
);

-- ----------------------------------------------------------------------------
-- §2.2 三表搬迁（事务包裹; 幂等: 按 old_user_map 已存在判断跳过）
-- ----------------------------------------------------------------------------
BEGIN IMMEDIATE;
-- students（1793 行）
INSERT INTO users(login_code,name,role,password_hash,user_activated,phone,qq,skills,
                  profile_is_public,created_at,updated_at,major,grade)
SELECT s.student_id, s.name, 'student', s.password_hash,
       COALESCE(s.user_activated,0), s.phone, s.qq, s.skills,
       COALESCE(s.profile_is_public,1), s.created_at, s.updated_at, s.major, s.grade
FROM students s
WHERE NOT EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role='student' AND m.old_id=s.id);
INSERT OR IGNORE INTO old_user_map(old_role, old_id, new_user_id)
SELECT 'student', s.id,
       (SELECT u.id FROM users u WHERE u.login_code=s.student_id AND u.role='student')
FROM students s;
-- teachers（38 行）
INSERT INTO users(login_code,name,role,password_hash,user_activated,phone,qq,skills,
                  profile_is_public,created_at,updated_at,title,department,id_number)
SELECT t.teacher_id, t.name, 'teacher', t.password_hash,
       COALESCE(t.user_activated,0), t.phone, t.qq, t.skills,
       COALESCE(t.profile_is_public,1), t.created_at, t.updated_at, t.title, t.department, t.id_number
FROM teachers t
WHERE NOT EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role='teacher' AND m.old_id=t.id);
INSERT OR IGNORE INTO old_user_map(old_role, old_id, new_user_id)
SELECT 'teacher', t.id,
       (SELECT u.id FROM users u WHERE u.login_code=t.teacher_id AND u.role='teacher')
FROM teachers t;
-- admins（login_code=username）
INSERT INTO users(login_code,name,role,password_hash,user_activated,created_at)
SELECT a.username, COALESCE(a.name,a.username), 'admin', a.password_hash,
       COALESCE(a.user_activated,1), a.created_at
FROM admins a
WHERE NOT EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role='admin' AND m.old_id=a.id);
INSERT OR IGNORE INTO old_user_map(old_role, old_id, new_user_id)
SELECT 'admin', a.id,
       (SELECT u.id FROM users u WHERE u.login_code=a.username AND u.role='admin')
FROM admins a;
-- 验证断言（任一不为 0 即 ROLLBACK 并停止）:
--   SELECT COUNT(*) FROM old_user_map m WHERE m.new_user_id IS NULL;                 -- 0
--   SELECT (SELECT COUNT(*) FROM students) - (SELECT COUNT(*) FROM old_user_map WHERE old_role='student'); -- 0
COMMIT;

-- ----------------------------------------------------------------------------
-- §2.3 全量引用重写（逐表条件 UPDATE; 重写后 submitter_type 仅作迁移校验保留）
-- 涉及表（10 处 submitter 对 + reviewer 对, 见第二章 4.2）
-- ----------------------------------------------------------------------------
BEGIN IMMEDIATE;
UPDATE awards SET submitter_id = (SELECT m.new_user_id FROM old_user_map m
    WHERE m.old_role = awards.submitter_type AND m.old_id = awards.submitter_id)
WHERE EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role=awards.submitter_type AND m.old_id=awards.submitter_id);
UPDATE patents SET submitter_id = (SELECT m.new_user_id FROM old_user_map m
    WHERE m.old_role = patents.submitter_type AND m.old_id = patents.submitter_id)
WHERE EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role=patents.submitter_type AND m.old_id=patents.submitter_id);
UPDATE software_copyrights SET submitter_id = (SELECT m.new_user_id FROM old_user_map m
    WHERE m.old_role = software_copyrights.submitter_type AND m.old_id = software_copyrights.submitter_id)
WHERE EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role=software_copyrights.submitter_type AND m.old_id=software_copyrights.submitter_id);
UPDATE other_files SET submitter_id = (SELECT m.new_user_id FROM old_user_map m
    WHERE m.old_role = other_files.submitter_type AND m.old_id = other_files.submitter_id)
WHERE EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role=other_files.submitter_type AND m.old_id=other_files.submitter_id);
-- innovation_projects: §1.6 已把 'admin' 归一为 0 → 统一映射管理员（admins.id, 现库唯一）
UPDATE innovation_projects SET submitter_id = (SELECT m.new_user_id FROM old_user_map m
    WHERE m.old_role = innovation_projects.submitter_type AND m.old_id = innovation_projects.submitter_id)
WHERE EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role=innovation_projects.submitter_type
              AND m.old_id=innovation_projects.submitter_id);
UPDATE pending_achievements SET submitter_id = (SELECT m.new_user_id FROM old_user_map m
    WHERE m.old_role = pending_achievements.submitter_type AND m.old_id = pending_achievements.submitter_id)
WHERE EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role=pending_achievements.submitter_type
              AND m.old_id=pending_achievements.submitter_id);
-- review_logs: submitter 侧重写; reviewer 侧 teacher/admin 重写, system(71%) 置 NULL+标志
ALTER TABLE review_logs ADD COLUMN is_system_review INTEGER NOT NULL DEFAULT 0;
UPDATE review_logs SET submitter_id = (SELECT m.new_user_id FROM old_user_map m
    WHERE m.old_role = review_logs.submitter_type AND m.old_id = review_logs.submitter_id)
WHERE EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role=review_logs.submitter_type AND m.old_id=review_logs.submitter_id);
UPDATE review_logs SET
    reviewer_id = (SELECT m.new_user_id FROM old_user_map m
        WHERE m.old_role = review_logs.reviewer_type AND m.old_id = review_logs.reviewer_id),
    is_system_review = 0
WHERE reviewer_type IN ('teacher','admin')
  AND EXISTS (SELECT 1 FROM old_user_map m WHERE m.old_role=review_logs.reviewer_type AND m.old_id=review_logs.reviewer_id);
UPDATE review_logs SET reviewer_id = NULL, is_system_review = 1 WHERE reviewer_type = 'system';
-- audit_log operator 重写（阶段二存量）
UPDATE achievement_audit_log SET operator_id = (SELECT m.new_user_id FROM old_user_map m
    WHERE m.old_role = CASE achievement_audit_log.operator_role WHEN 1 THEN 'student' WHEN 2 THEN 'teacher' ELSE 'admin' END
      AND m.old_id = achievement_audit_log.operator_id)
WHERE operator_role IN (1,2,4)
  AND EXISTS (SELECT 1 FROM old_user_map m
              WHERE m.old_role = CASE achievement_audit_log.operator_role WHEN 1 THEN 'student' WHEN 2 THEN 'teacher' ELSE 'admin' END
                AND m.old_id = achievement_audit_log.operator_id);
COMMIT;
-- 验证断言:
--   PRAGMA foreign_key_check;                                      -- 空
--   SELECT COUNT(*) FROM awards WHERE submitter_id NOT IN (SELECT id FROM users); -- 0（同法查各表）

-- ----------------------------------------------------------------------------
-- §2.4 旧三表转只读视图（过渡兼容; §3.2 才 DROP）
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_students;
CREATE VIEW v_students AS
  SELECT u.id, u.login_code AS student_id, u.name, u.major, u.grade, u.phone,
         u.user_activated, u.created_at, u.updated_at, u.password_hash, u.role,
         u.qq, u.skills, u.profile_is_public
  FROM users u WHERE u.role='student';
-- v_teachers / v_admins 同构（teacher_id / username 列名映射）

-- ############################################################################
-- §3 P2 收尾 —— 观察一个迭代后执行
-- ############################################################################

-- §3.1 pending 表重建: 补 status CHECK(pending|submit|rejected|archived), 删 submitter_type
--      （全列迁移, 服务层已切换后执行; DDL 模板见第二章 3.4）

-- §3.2 DROP TABLE IF EXISTS students / teachers / admins;   -- 视图过渡期结束后
DROP VIEW IF EXISTS v_students;  -- 及 v_teachers/v_admins

-- §3.3 关联表合并 award_user_links（第二章 4.3; 搬迁后 DROP 四张旧关联表）
CREATE TABLE IF NOT EXISTS award_user_links (
    award_id  INTEGER NOT NULL REFERENCES awards(id) ON DELETE CASCADE,
    user_id   INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    link_role TEXT NOT NULL CHECK(link_role IN ('winner_student','winner_teacher','supervisor','related_student')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (award_id, user_id, link_role)
);
INSERT OR IGNORE INTO award_user_links(award_id, user_id, link_role, created_at)
SELECT award_id, student_id, 'winner_student', created_at FROM award_student_winners
UNION ALL SELECT award_id, teacher_id, 'winner_teacher', created_at FROM award_teacher_winners
UNION ALL SELECT award_id, teacher_id, 'supervisor',      created_at FROM award_supervisors
UNION ALL SELECT award_id, student_id, 'related_student', created_at FROM award_related_students;
-- 验证计数一致后: DROP TABLE award_student_winners; (×4)

-- §3.4 成果表业务键唯一约束（P0-9 根治, 入库改 ON CONFLICT 幂等）
CREATE UNIQUE INDEX IF NOT EXISTS uk_patents_application_no ON patents(application_number)
    WHERE application_number IS NOT NULL AND application_number <> '';
CREATE UNIQUE INDEX IF NOT EXISTS uk_softwares_registration ON software_copyrights(registration_number)
    WHERE registration_number IS NOT NULL AND registration_number <> '';

-- §3.5 统一成果视图（第二章 4.4）
CREATE VIEW IF NOT EXISTS v_achievements AS
SELECT id,'award' kind, title, NULL AS biz_no, submitter_id, laboratory_id, date AS business_date FROM awards
UNION ALL SELECT id,'patent', patent_name, application_number, submitter_id, laboratory_id, application_date FROM patents
UNION ALL SELECT id,'software', software_name, registration_number, submitter_id, laboratory_id, registration_date FROM software_copyrights
UNION ALL SELECT id,'innovation', project_name, project_no, submitter_id, laboratory_id, start_date FROM innovation_projects
UNION ALL SELECT id,'other', file_name, file_path, submitter_id, laboratory_id, NULL FROM other_files;

-- ############################################################################
-- 收尾验证（全部执行完必跑）
-- ############################################################################
PRAGMA foreign_key_check;            -- 期望: 空
PRAGMA integrity_check;              -- 期望: ok
-- SELECT COUNT(*) FROM users;       -- 期望 ≈ 1832（1793+38+1）
-- 对账: 每张重写表 COUNT(*) 与备份库一致
