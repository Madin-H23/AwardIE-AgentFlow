"""测试共享 Schema 常量（2026-08-18：修复 CI 反射依赖——仓库不跟踪 *.db，测试不得依赖真实库文件）。

DDL 与 database/competitions.db 反射一致；表结构变更时须同步本文件（加对应测试）。
"""
PENDING_ACHIEVEMENTS_DDL = """CREATE TABLE pending_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_type TEXT,
    achievement_data TEXT NOT NULL,
    validation_result TEXT,
    submitter_type TEXT,
    submitter_id INTEGER,
    submit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    reviewer_id INTEGER,
    review_time TIMESTAMP,
    review_comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT,
    assigned_reviewer_type TEXT CHECK(assigned_reviewer_type IN ('teacher', 'admin')),
    reviewer_type TEXT CHECK(reviewer_type IN ('teacher', 'admin')),
    file_hash TEXT NOT NULL DEFAULT '',
    ocr_text TEXT, llm_prompt TEXT, llm_response TEXT, ext_info TEXT,
    session_id TEXT, laboratory_id INTEGER,
    version INTEGER NOT NULL DEFAULT 1,
    is_valid INTEGER GENERATED ALWAYS AS (
        CASE WHEN json_extract(validation_result, '$.is_valid') IS NULL THEN NULL
             ELSE CAST(json_extract(validation_result, '$.is_valid') AS INTEGER) END
    ) VIRTUAL)"""

# 旧三表视图（M1 后半②：与 migrations/versions/0002_legacy_tables_to_views.py 定义同步，
# 测试 fixture 用视图模拟视图化后的库——视图是唯一读路径数据源）
STUDENTS_VIEW_DDL = """CREATE VIEW students AS
SELECT u.id, u.login_code AS student_id, u.name, u.major, u.grade, u.phone,
       u.user_activated, u.created_at, u.updated_at, u.password_hash, u.role,
       u.qq, u.skills, u.profile_is_public, u.needs_password_change
FROM users u WHERE u.role = 'student'"""

TEACHERS_VIEW_DDL = """CREATE VIEW teachers AS
SELECT u.id, u.login_code AS teacher_id, u.name, u.title, u.department, u.phone,
       u.id_number, u.user_activated, u.created_at, u.updated_at, u.password_hash,
       u.role, u.qq, u.skills, u.profile_is_public, u.needs_password_change
FROM users u WHERE u.role = 'teacher'"""

ADMINS_VIEW_DDL = """CREATE VIEW admins AS
SELECT u.id, u.login_code AS username, u.password_hash, u.name, u.user_activated,
       u.created_at, u.needs_password_change
FROM users u WHERE u.role = 'admin'"""

USERS_DDL = """CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login_code TEXT UNIQUE, name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
    password_hash TEXT,
    user_activated INTEGER NOT NULL DEFAULT 1 CHECK(user_activated IN (0,1)),
    phone TEXT, qq TEXT, skills TEXT, profile_is_public INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    major TEXT, grade TEXT, title TEXT, department TEXT, id_number TEXT,
    needs_password_change INTEGER NOT NULL DEFAULT 0)"""

AUDIT_LOG_DDL = """CREATE TABLE achievement_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id INTEGER NOT NULL,
    achievement_kind TEXT CHECK(achievement_kind IN ('award','patent','software','innovation','other')),
    trace_id TEXT, action_type INTEGER NOT NULL CHECK(action_type BETWEEN 1 AND 11),
    action_result INTEGER NOT NULL DEFAULT 0 CHECK(action_result IN (0,1,2)),
    operator_id INTEGER, operator_code TEXT NOT NULL, operator_name TEXT NOT NULL,
    operator_role INTEGER CHECK(operator_role IN (1,2,3,4)), operator_ip TEXT,
    ai_batch_id TEXT, change_detail TEXT, remark TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP)"""


def require_real_db():
    """真实库守卫（R-028 兜底升级）：文件存在 **且** users 表存在，否则 skip。

    原版只查文件存在——CI 曾被启动事件建出空 competitions.db（无表），
    守卫放行致 3 个真实库用例由 skip 变挂。空/半初始化库一律按"无库"跳过。
    """
    import sqlite3
    from pathlib import Path
    import pytest
    db = Path(__file__).resolve().parents[2] / "database" / "competitions.db"
    if not db.exists():
        pytest.skip("CI 环境无真实库文件")
    conn = sqlite3.connect(str(db))
    try:
        has_users = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    finally:
        conn.close()
    if not has_users:
        pytest.skip("库文件存在但无业务表（空库）")
