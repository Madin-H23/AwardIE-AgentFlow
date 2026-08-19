"""0002 补漏：3 张 teacher 关联表 FK 改指 users（M1 后半③② 覆盖缺口）。

背景：0002 视图化只处理了 student 关联表（laboratory_students 等 5 张 FK→users），
遗漏 3 张 teacher 关联表——laboratory_instructors / award_teacher_winners /
award_supervisors 的 FK 仍 REFERENCES teachers(id)，而 teachers 已变视图，
SQLite 不允许 FK 引用视图 → PRAGMA foreign_key_check 报 mismatch（9.5 项 8 拦截）。

本迁移：3 表 0 行，仅重建表把 FK 目标 teachers→users（保留其余 FK/约束/PK）。
"""
import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '0004_teacher_fk_relink'
down_revision: Union[str, Sequence[str], None] = '0003_typization_rebuild'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("laboratory_instructors", "award_teacher_winners", "award_supervisors")


def _rebuild(conn, table: str) -> None:
    row = conn.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}).fetchone()
    if row is None or not row[0]:
        raise RuntimeError(f"找不到表 {table} 的 CREATE 语句")
    ddl = row[0]
    # 仅替换 FK 目标：REFERENCES teachers(id) → REFERENCES users(id)，其余约束原样保留
    new_ddl = re.sub(r"REFERENCES\s+teachers\s*\(id\)", "REFERENCES users(id)", ddl)
    if "REFERENCES users(id)" not in new_ddl:
        raise RuntimeError(f"{table}: 未发现 teachers FK 可替换")
    new_name = f"{table}_new"
    conn.execute(text(f"DROP TABLE IF EXISTS {new_name}"))
    conn.execute(text(re.sub(
        rf'CREATE TABLE\s*"?{re.escape(table)}"?\s*\(',
        f"CREATE TABLE {new_name} (", new_ddl, count=1)))
    conn.execute(text(f"INSERT INTO {new_name} SELECT * FROM {table}"))
    old_n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
    new_n = conn.execute(text(f"SELECT COUNT(*) FROM {new_name}")).fetchone()[0]
    if old_n != new_n:
        raise RuntimeError(f"{table}: 重建行数不一致 {old_n} != {new_n}")
    conn.execute(text(f"DROP TABLE {table}"))
    conn.execute(text(f"ALTER TABLE {new_name} RENAME TO {table}"))


def upgrade() -> None:
    conn = op.get_bind()
    for t in _TABLES:
        _rebuild(conn, t)
    # 校验：全库无 FK mismatch（9.5 项 8 要求 foreign_key_check 为空）
    mismatches = conn.execute(text("PRAGMA foreign_key_check")).fetchall()
    if mismatches:
        raise RuntimeError(f"foreign_key_check 仍有 mismatch: {mismatches}")


def downgrade() -> None:
    """回退：FK 还原指向 teachers（视图）——仅用于异常回滚，数据不受影响。"""
    conn = op.get_bind()
    for table in _TABLES:
        row = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}).fetchone()
        if row is None or not row[0]:
            continue
        ddl = re.sub(r"REFERENCES\s+users\s*\(id\)", "REFERENCES teachers(id)", row[0])
        new_name = f"{table}_new"
        conn.execute(text(f"DROP TABLE IF EXISTS {new_name}"))
        conn.execute(text(re.sub(
            rf'CREATE TABLE\s*"?{re.escape(table)}"?\s*\(',
            f"CREATE TABLE {new_name} (", ddl, count=1)))
        conn.execute(text(f"INSERT INTO {new_name} SELECT * FROM {table}"))
        conn.execute(text(f"DROP TABLE {table}"))
        conn.execute(text(f"ALTER TABLE {new_name} RENAME TO {table}"))
