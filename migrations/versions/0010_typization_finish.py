"""0010: 类型规范收尾（短字段 TEXT → VARCHAR/TIMESTAMP，手写迁移）。

背景：0003 类型规范只覆盖高活跃表；低活跃/边缘表仍残留 TEXT 短字段
（patents/action_plans 几乎全 TEXT；users 时间戳 TEXT 与多数表 TIMESTAMP 不一致；
award 关联表 created_at 为 TEXT 等）。SQLite 动态类型下无行为差异，本迁移是
**声明一致性收尾**（文档整洁 + 未来换库友好）。

改动清单（14 张表）：
- 时间戳统一：users.created_at/updated_at、awards.submit_time、failed_logins 三个时间列、
  action_plans 三个时间列、award_student_winners/award_teacher_winners/award_related_students/
  award_supervisors.created_at → TIMESTAMP（0006/0008 的 system_event_log/audit created_at 保留
  TEXT——时间基准待办未了，避免搅动）
- 短字段 VARCHAR：patents 5 列、software_copyrights 4 列、failed_logins login_code/ip、
  action_plans 6 列、innovation_projects.project_no、innovation_project_students.student_id_str、
  templates.language、achievement_audit_log.operator_ip
- 长文本（JSON/OCR/LLM/描述/备注）保持 TEXT 不动

保留：PK/AUTOINCREMENT/CHECK/NOT NULL/DEFAULT/全部索引与唯一约束
（从原 CREATE 语句派生，仅替换类型）。与 0003 差异：重建前抓 sqlite_sequence 计数、
重建后恢复（防自增 id 复用——0003 时库无删除历史故未处理，现 awards seq=1195 ≫ 行数 197）。

策略同 0003（G6 建新替旧 + 行数校验 + 视图先删后建 + PRAGMA foreign_keys=OFF）。
存量数据长度已实测 < VARCHAR 目标；迁移内置长度越界校验兜底（超限即中止）。

downgrade：单向改进，回退靠迁移前备份（bak.2026-08-21-pre-0010.db），降级 no-op。
"""
import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '0010_typization_finish'
down_revision: Union[str, Sequence[str], None] = '0009_audit_redundant_flag'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 表 → {字段: 目标类型}（仅短字段；长文本不在此列）
_TYPE_OVERRIDES = {
    "users": {"created_at": "TIMESTAMP", "updated_at": "TIMESTAMP"},
    "awards": {"submit_time": "TIMESTAMP"},
    "patents": {"application_number": "VARCHAR(50)", "publication_number": "VARCHAR(50)",
                "application_date": "VARCHAR(10)", "inventor": "VARCHAR(200)", "patentee": "VARCHAR(200)"},
    "software_copyrights": {"registration_number": "VARCHAR(50)", "certificate_no": "VARCHAR(50)",
                "registration_date": "VARCHAR(10)", "copyright_owner": "VARCHAR(200)"},
    "failed_logins": {"login_code": "VARCHAR(50)", "ip": "VARCHAR(45)",
                "first_fail_at": "TIMESTAMP", "lock_until": "TIMESTAMP", "updated_at": "TIMESTAMP"},
    "action_plans": {"id": "VARCHAR(64)", "alert_id": "VARCHAR(64)", "priority": "VARCHAR(20)",
                "category": "VARCHAR(50)", "title": "VARCHAR(200)", "status": "VARCHAR(20)",
                "created_at": "TIMESTAMP", "updated_at": "TIMESTAMP", "resolved_at": "TIMESTAMP"},
    "innovation_projects": {"project_no": "VARCHAR(50)"},
    "innovation_project_students": {"student_id_str": "VARCHAR(50)"},
    "templates": {"language": "VARCHAR(10)"},
    "achievement_audit_log": {"operator_ip": "VARCHAR(45)"},
    "award_student_winners": {"created_at": "TIMESTAMP"},
    "award_teacher_winners": {"created_at": "TIMESTAMP"},
    "award_related_students": {"created_at": "TIMESTAMP"},
    "award_supervisors": {"created_at": "TIMESTAMP"},
}

# 重建顺序：users 先行（视图/关联 FK 目标），其余无依赖
_REBUILD_ORDER = [
    "users", "awards", "patents", "software_copyrights", "failed_logins",
    "action_plans", "innovation_projects", "innovation_project_students",
    "templates", "achievement_audit_log",
    "award_student_winners", "award_teacher_winners",
    "award_related_students", "award_supervisors",
]

_SEQ_LOCK_TABLES = ["users", "awards", "patents", "software_copyrights",
                    "failed_logins", "innovation_projects", "templates",
                    "achievement_audit_log"]


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
    return ddl


def _check_lengths(conn, table: str) -> None:
    """VARCHAR(n) 目标越界兜底：存量数据超长立即中止（防静默截断/写入失败）。

    注意：SQLite 双引号在列不存在时退化为字符串字面量，LENGTH("缺列") 会返回
    字符串长度（如 'application_date'=16）误报越界——故先按 table_info 过滤
    实际存在的列，缺失列跳过（与 _target_ddl 的缺失列跳过语义一致）。
    """
    existing = {r[1] for r in conn.execute(text(f'PRAGMA table_info("{table}")'))}
    for col, new_type in _TYPE_OVERRIDES.get(table, {}).items():
        if col not in existing:
            continue
        m = re.fullmatch(r"VARCHAR\((\d+)\)", new_type)
        if not m:
            continue
        limit = int(m.group(1))
        row = conn.execute(text(
            f'SELECT MAX(LENGTH("{col}")) FROM "{table}"')).fetchone()
        mx = row[0] or 0
        if mx > limit:
            raise RuntimeError(f"{table}.{col}: 存量最大长度 {mx} > VARCHAR({limit})，迁移中止")


def _rebuild_table(conn, table: str) -> None:
    # 表不存在则跳过（迁移作用于真实库；缺失表不阻塞——测试模拟库可只建部分表）
    exists = conn.execute(text(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}).fetchone()
    if not exists:
        return
    _check_lengths(conn, table)
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


def _seq_locks(conn) -> dict:
    """抓取待重建 AUTOINCREMENT 表的自增计数——重建后恢复，防自增 id 复用。"""
    locks = {}
    for t in _SEQ_LOCK_TABLES:
        row = conn.execute(text(
            "SELECT seq FROM sqlite_sequence WHERE name=:n"), {"n": t}).fetchone()
        if row is not None:
            locks[t] = row[0]
    return locks


def _restore_seqs(conn, locks: dict) -> None:
    for t, seq in locks.items():
        conn.execute(text(
            "INSERT OR REPLACE INTO sqlite_sequence(name, seq) VALUES(:n, :s)"),
            {"n": t, "s": seq})


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    views = _views_sql(conn)
    for v in views:
        conn.execute(text(f"DROP VIEW {v}"))
    seqs = _seq_locks(conn)
    try:
        for t in _REBUILD_ORDER:
            _rebuild_table(conn, t)
        _restore_seqs(conn, seqs)
        # 重建视图（惰性绑定 users，表已重建完成）
        for sql in views.values():
            conn.execute(text(sql))
        # 校验视图（仅校验实际存在/重建的视图）
        for v in views:
            conn.execute(text(f"SELECT COUNT(*) FROM {v}"))
    finally:
        conn.execute(text("PRAGMA foreign_keys=ON"))


def downgrade() -> None:
    """类型规范为单向改进；回退依赖迁移前备份（0010 不还原类型）。"""