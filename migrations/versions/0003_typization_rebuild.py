"""类型规范全表重建（M1 后半③③，手写迁移）。

依据：docs/重构/设计/2026-08-19_字段类型规范映射表.md
- 短字段 TEXT → VARCHAR(N)（18 张表，映射表 §2 清单）
- 长文本保留 TEXT（§3 保留列表）；存量数据最大长度已实测 < VARCHAR 目标，无截断风险
- 保留：PK/AUTOINCREMENT/CHECK/NOT NULL/DEFAULT（从原 CREATE 语句抓取语义，仅替换类型）、
  pending_achievements.is_valid 生成列（VIRTUAL）、全部索引/唯一约束

策略（G6 建新替旧 + 映射表 §4）：备份 → 建 t_new（改类型）→ INSERT SELECT → 校验行数 →
DROP t → RENAME → 重建索引。视图（students/teachers/admins）惰性绑定 users，重建后自动恢复。
迁移期 PRAGMA foreign_keys=OFF（重建 users 不被关联表 FK 阻断），结束恢复。

downgrade：类型规范为单向改进（回退靠备份），降级仅 no-op 保留数据。
"""
import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '0003_typization_rebuild'
down_revision: Union[str, Sequence[str], None] = '0002_legacy_tables_to_views'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 映射表 §2：表 → {字段: 目标类型}
_TYPE_OVERRIDES = {
    "users": {"login_code": "VARCHAR(50)", "name": "VARCHAR(50)", "role": "VARCHAR(20)",
              "password_hash": "VARCHAR(255)", "phone": "VARCHAR(20)", "qq": "VARCHAR(50)",
              "major": "VARCHAR(50)", "grade": "VARCHAR(50)", "title": "VARCHAR(50)",
              "department": "VARCHAR(50)", "id_number": "VARCHAR(50)"},
    "pending_achievements": {"achievement_type": "VARCHAR(20)", "status": "VARCHAR(20)",
              "submitter_type": "VARCHAR(20)", "assigned_reviewer_type": "VARCHAR(20)",
              "reviewer_type": "VARCHAR(20)", "file_path": "VARCHAR(500)",
              "session_id": "VARCHAR(50)", "file_hash": "VARCHAR(64)"},
    "awards": {"image_hash": "VARCHAR(64)", "certificate_id": "VARCHAR(50)",
              "competition_name_in_file": "VARCHAR(200)", "track": "VARCHAR(100)",
              "issuer": "VARCHAR(100)", "province": "VARCHAR(100)", "group_name": "VARCHAR(100)",
              "winner_name": "VARCHAR(100)", "supervisor_name": "VARCHAR(100)",
              "award_level": "VARCHAR(20)", "competition_level": "VARCHAR(20)",
              "date": "VARCHAR(10)", "project_title": "VARCHAR(200)",
              "granted_role": "VARCHAR(20)", "related_student_name": "VARCHAR(100)",
              "submitter_type": "VARCHAR(20)"},
    "review_logs": {"achievement_type": "VARCHAR(20)", "file_hash": "VARCHAR(64)",
              "file_path": "VARCHAR(500)", "submitter_type": "VARCHAR(20)",
              "reviewer_type": "VARCHAR(20)", "action_type": "VARCHAR(20)",
              "result_type": "VARCHAR(20)", "result_file_path": "VARCHAR(500)"},
    "achievement_audit_log": {"trace_id": "VARCHAR(64)", "operator_code": "VARCHAR(50)",
              "operator_name": "VARCHAR(50)", "ai_batch_id": "VARCHAR(50)"},
    "patents": {"patent_name": "VARCHAR(200)", "patent_type": "VARCHAR(20)",
              "certificate_file": "VARCHAR(500)", "submitter_type": "VARCHAR(20)"},
    "software_copyrights": {"software_name": "VARCHAR(200)", "software_version": "VARCHAR(20)",
              "certificate_file": "VARCHAR(500)", "submitter_type": "VARCHAR(20)"},
    "innovation_projects": {"project_name": "VARCHAR(200)", "project_type": "VARCHAR(20)",
              "status": "VARCHAR(20)", "submitter_type": "VARCHAR(20)",
              "student_leader_name": "VARCHAR(50)", "student_leader_id": "VARCHAR(50)"},
    "other_files": {"file_name": "VARCHAR(100)", "file_type": "VARCHAR(20)",
              "file_path": "VARCHAR(500)", "file_hash": "VARCHAR(64)", "submitter_type": "VARCHAR(20)"},
    "competitions": {"competition_name": "VARCHAR(200)", "grade_category": "VARCHAR(20)"},
    "laboratories": {"name": "VARCHAR(100)"},
    "templates": {"template_type": "VARCHAR(20)"},
    "auto_archive_config": {"achievement_type": "VARCHAR(20)", "validation_status": "VARCHAR(20)"},
    "innovation_project_students": {"role": "VARCHAR(20)", "student_name": "VARCHAR(50)", "match_type": "VARCHAR(20)"},
    "laboratory_downloads": {"file_title": "VARCHAR(200)", "file_name": "VARCHAR(200)",
              "file_path": "VARCHAR(500)", "submitter_type": "VARCHAR(20)"},
    "laboratory_images": {"file_name": "VARCHAR(100)", "image_path": "VARCHAR(500)",
              "file_hash": "VARCHAR(64)", "submitter_type": "VARCHAR(20)"},
    "user_photos": {"file_name": "VARCHAR(100)", "file_path": "VARCHAR(500)",
              "thumbnail_path": "VARCHAR(500)", "file_hash": "VARCHAR(64)",
              "photo_type": "VARCHAR(20)", "submitter_type": "VARCHAR(20)"},
    "old_user_map": {"old_role": "VARCHAR(20)"},
}

# pending 生成列（映射表 §4.1：VIRTUAL 保留）
_PENDING_GENERATED = """, is_valid INTEGER GENERATED ALWAYS AS (
    CASE WHEN json_extract(validation_result, '$.is_valid') IS NULL THEN NULL
         ELSE CAST(json_extract(validation_result, '$.is_valid') AS INTEGER) END
) VIRTUAL"""

# 重建顺序：users 先行（视图/关联表 FK 目标），其余无依赖
_REBUILD_ORDER = [
    "users", "pending_achievements", "awards", "review_logs", "achievement_audit_log",
    "patents", "software_copyrights", "innovation_projects", "other_files",
    "competitions", "laboratories", "templates", "auto_archive_config",
    "innovation_project_students", "laboratory_downloads", "laboratory_images",
    "user_photos", "old_user_map",
]


def _target_ddl(conn, table: str) -> str:
    """从原 CREATE 语句派生目标 DDL：仅替换覆盖列的类型，保留其余全部语义。"""
    row = conn.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}).fetchone()
    if row is None or not row[0]:
        raise RuntimeError(f"找不到表 {table} 的 CREATE 语句")
    ddl = row[0]
    for col, new_type in _TYPE_OVERRIDES.get(table, {}).items():
        # 列名须独立成词（避免误替换含相同前缀的列）；类型用 \w+（不含逗号——\S+ 会贪婪吞掉
        # 行内逗号致语法错，如 `col TEXT, next` 被替换成 `col VARCHAR(n) next`）
        pat = re.compile(rf"(?P<pre>[,\s(\[]){re.escape(col)}(?P<post>\s+)\w+")
        m = pat.search(ddl)
        if not m:
            # 覆盖字段在真实库不存在时跳过（列缺失属 schema 演进差异，不强求）
            continue
        ddl = pat.sub(f"\g<pre>{col}\g<post>{new_type}", ddl, count=1)
    if table == "pending_achievements":
        # 真实库已含 is_valid 生成列（M3 已建）——已有则不重复追加，否则 duplicate column
        inner = re.search(r"\((.*)\)", ddl, re.S).group(1)
        if "is_valid" not in inner:
            ddl = ddl.rstrip().rstrip(")") + _PENDING_GENERATED + ")"
    return ddl


def _rebuild_indexes(conn, table: str) -> None:
    """（索引重建已并入 _rebuild_table 的 DROP 前抓取——此函数保留为兼容桩）"""


def _rebuild_table(conn, table: str) -> None:
    # 表不存在则跳过（迁移作用于真实库；缺失表不阻塞——测试模拟库可只建部分表）
    exists = conn.execute(text(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}).fetchone()
    if not exists:
        return
    new_name = f"{table}_new"
    conn.execute(text(f"DROP TABLE IF EXISTS {new_name}"))
    # DROP 前抓取索引 SQL（DROP TABLE 会连带删除 sqlite_master 里的索引记录）
    idx_sqls = [r[0] for r in conn.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=:t AND sql IS NOT NULL"),
        {"t": table}).fetchall() if r[0] and "sqlite_autoindex" not in r[0]]
    # 兼容引号表名（如 CREATE TABLE "pending_achievements"）
    ddl = re.sub(
        rf'CREATE TABLE\s*"?{re.escape(table)}"?\s*\(',
        f"CREATE TABLE {new_name} (", _target_ddl(conn, table), count=1)
    conn.execute(text(ddl))
    conn.execute(text(f"INSERT INTO {new_name} SELECT * FROM {table}"))
    # 校验：行数一致
    old_n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
    new_n = conn.execute(text(f"SELECT COUNT(*) FROM {new_name}")).fetchone()[0]
    if old_n != new_n:
        raise RuntimeError(f"{table}: 重建行数不一致 {old_n} != {new_n}")
    conn.execute(text(f"DROP TABLE {table}"))
    conn.execute(text(f"ALTER TABLE {new_name} RENAME TO {table}"))
    # 重建索引（表名已恢复原名，原 SQL 可直接执行）
    for sql in idx_sqls:
        conn.execute(text(sql))


def _views_sql(conn) -> dict:
    """抓取三视图 DDL（0002 建立）——DROP 被引用表会让 SQLite 视图永久失效，须先删后建。"""
    views = {}
    for v in ("students", "teachers", "admins"):
        row = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='view' AND name=:n"), {"n": v}).fetchone()
        if row and row[0]:
            views[v] = row[0]
    return views


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    views = _views_sql(conn)
    for v in views:
        conn.execute(text(f"DROP VIEW {v}"))
    try:
        for t in _REBUILD_ORDER:
            _rebuild_table(conn, t)
        # 重建视图（惰性绑定 users，表已重建完成）
        for sql in views.values():
            conn.execute(text(sql))
        # 校验视图（仅校验实际存在/重建的视图）
        for v in views:
            conn.execute(text(f"SELECT COUNT(*) FROM {v}"))
    finally:
        conn.execute(text("PRAGMA foreign_keys=ON"))


def downgrade() -> None:
    """类型规范为单向改进；回退依赖迁移前备份（0003 不还原类型）。"""
