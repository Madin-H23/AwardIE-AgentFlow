"""旧三表视图化 + 关联表 student_id 重写为 users.id（M1 后半③②，手写迁移）。

背景：
- 5 张关联表（laboratory_students / laboratory_assistants / innovation_project_students /
  award_student_winners / award_related_students）的 student_id 仍存旧 students.id
  （M1 前半只重写了 submitter_id 系业务表）——视图化前必须重写为 users.id，否则数据错位
- 视图不可写，写路径已迁 users（见阶段五实施文档 §2.6）；本迁移仅做数据层收口

步骤：
1. 关联表 student_id：旧 students.id → users.id（经 login_code 映射），零悬空断言
2. 重建 5 张关联表：FK 从 REFERENCES students(id) 改为 REFERENCES users(id)（列名保留）
3. DROP students/teachers/admins → 建视图指向 users（列序与旧表完全一致，读路径零改动）
"""
from typing import Sequence, Union

from alembic import op

revision: str = '0002_legacy_tables_to_views'
down_revision: Union[str, Sequence[str], None] = '0001_orm_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (表名, 除 student_id 外的关联列名) —— created_at 等其余列原样保留
_RELINK_TABLES = (
    ('laboratory_students', 'laboratory_id'),
    ('laboratory_assistants', 'laboratory_id'),
    ('innovation_project_students', 'project_id'),
    ('award_student_winners', 'award_id'),
    ('award_related_students', 'award_id'),
)

_STUDENTS_VIEW = """
CREATE VIEW students AS
SELECT u.id, u.login_code AS student_id, u.name, u.major, u.grade, u.phone,
       u.user_activated, u.created_at, u.updated_at, u.password_hash, u.role,
       u.qq, u.skills, u.profile_is_public, u.needs_password_change
FROM users u WHERE u.role = 'student'
"""

_TEACHERS_VIEW = """
CREATE VIEW teachers AS
SELECT u.id, u.login_code AS teacher_id, u.name, u.title, u.department, u.phone,
       u.id_number, u.user_activated, u.created_at, u.updated_at, u.password_hash,
       u.role, u.qq, u.skills, u.profile_is_public, u.needs_password_change
FROM users u WHERE u.role = 'teacher'
"""

_ADMINS_VIEW = """
CREATE VIEW admins AS
SELECT u.id, u.login_code AS username, u.password_hash, u.name, u.user_activated,
       u.created_at, u.needs_password_change
FROM users u WHERE u.role = 'admin'
"""


_OLD_TABLE_DDL = {
    "students": """
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    major TEXT NOT NULL,
    grade TEXT NOT NULL,
    phone TEXT,
    user_activated INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    password_hash TEXT, role TEXT DEFAULT "student", qq TEXT, skills TEXT,
    profile_is_public BOOLEAN DEFAULT 1, needs_password_change INTEGER NOT NULL DEFAULT 0)""",
    "teachers": """
CREATE TABLE teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    title TEXT,
    department TEXT NOT NULL,
    phone TEXT,
    id_number TEXT,
    user_activated INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    password_hash TEXT, role TEXT DEFAULT "teacher", qq TEXT, skills TEXT,
    profile_is_public BOOLEAN DEFAULT 1, needs_password_change INTEGER NOT NULL DEFAULT 0)""",
    "admins": """
CREATE TABLE admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT,
    user_activated INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    needs_password_change INTEGER NOT NULL DEFAULT 0)""",
}


def _rewrite_student_ids(conn) -> None:
    """关联表 student_id：旧 students.id → users.id（login_code 映射）。"""
    from sqlalchemy import text
    for table, other_col in _RELINK_TABLES:
        conn.execute(text(f"""
            UPDATE {table}
            SET student_id = (
                SELECT u.id FROM users u
                JOIN students s ON u.login_code = s.student_id
                WHERE s.id = {table}.student_id
            )
            WHERE student_id IN (SELECT id FROM students)
        """))
        # 零悬空断言：重写后所有 student_id 必须能在 users 中命中
        orphans = conn.execute(text(
            f"SELECT COUNT(*) FROM {table} WHERE student_id NOT IN (SELECT id FROM users)"
        )).fetchone()[0]
        if orphans:
            raise RuntimeError(f"{table}: {orphans} 行 student_id 无法映射到 users.id")


def _relink_tables(conn) -> None:
    """重建关联表：FK 改指 users(id)，列结构/索引保留。"""
    from sqlalchemy import text
    for table, other_col in _RELINK_TABLES:
        cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        col_defs = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        # 只把 REFERENCES students(id) 换成 REFERENCES users(id)，其余约束不动
        new_name = f"{table}_new"
        conn.execute(text(f"CREATE TABLE {new_name} ({col_defs}, "
                          "FOREIGN KEY(student_id) REFERENCES users(id))"))
        conn.execute(text(f"INSERT INTO {new_name} SELECT * FROM {table}"))
        conn.execute(text(f"DROP TABLE {table}"))
        conn.execute(text(f"ALTER TABLE {new_name} RENAME TO {table}"))
        # 重建原索引（除 sqlite_autoindex）
        for idx in conn.execute(text(f"PRAGMA index_list({table})")):
            if idx[1].startswith("sqlite_autoindex"):
                continue
            sql = conn.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='index' AND name=:n"
            ), {"n": idx[1]}).fetchone()[0]
            if sql:
                conn.execute(text(sql))


def upgrade() -> None:
    from sqlalchemy import text
    conn = op.get_bind()
    _rewrite_student_ids(conn)
    _relink_tables(conn)
    for table, view in (("students", _STUDENTS_VIEW),
                        ("teachers", _TEACHERS_VIEW),
                        ("admins", _ADMINS_VIEW)):
        conn.execute(text(f"DROP TABLE {table}"))
        conn.execute(text(view))


_DOWNGRADE_COLS = {
    "students": ("id, student_id, name, major, grade, phone, user_activated, "
                 "created_at, updated_at, password_hash, role, qq, skills, "
                 "profile_is_public, needs_password_change",
                 "id, login_code, name, COALESCE(major,''), COALESCE(grade,''), "
                 "phone, user_activated, created_at, updated_at, password_hash, "
                 "role, qq, skills, profile_is_public, needs_password_change"),
    "teachers": ("id, teacher_id, name, title, department, phone, id_number, "
                 "user_activated, created_at, updated_at, password_hash, role, "
                 "qq, skills, profile_is_public, needs_password_change",
                 "id, login_code, name, title, COALESCE(department,''), phone, "
                 "id_number, user_activated, created_at, updated_at, "
                 "password_hash, role, qq, skills, profile_is_public, "
                 "needs_password_change"),
    "admins": ("id, username, password_hash, name, user_activated, created_at, "
               "needs_password_change",
               "id, login_code, COALESCE(password_hash,''), name, "
               "user_activated, created_at, needs_password_change"),
}


def downgrade() -> None:
    """反向：视图还原为实体表（数据从 users 回拷），关联表 FK 还原指向 students。"""
    from sqlalchemy import text
    conn = op.get_bind()
    for table in ("students", "teachers", "admins"):
        conn.execute(text(f"DROP VIEW {table}"))
        conn.execute(text(_OLD_TABLE_DDL[table]))
        cols, src_cols = _DOWNGRADE_COLS[table]
        role = {"students": "student", "teachers": "teacher", "admins": "admin"}[table]
        conn.execute(text(f"""
            INSERT INTO {table} ({cols})
            SELECT {src_cols} FROM users WHERE role = '{role}'
        """))
    for table, other_col in _RELINK_TABLES:
        cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        col_defs = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        new_name = f"{table}_new"
        conn.execute(text(
            f"CREATE TABLE {new_name} ({col_defs}, "
            "FOREIGN KEY(student_id) REFERENCES students(id))"))
        conn.execute(text(f"INSERT INTO {new_name} SELECT * FROM {table}"))
        conn.execute(text(f"DROP TABLE {table}"))
        conn.execute(text(f"ALTER TABLE {new_name} RENAME TO {table}"))
