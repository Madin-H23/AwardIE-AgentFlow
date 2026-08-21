"""0009 迁移回归：成果删除留痕去重标记 is_redundant（up 标记/down 置 0）。

背景：防重修复前同一成果可被重复删除产生多条 action_type=12；0009 加列
并对同 (kind, achievement_id) 保留最早一条、其余置 1（打标记不物理删）。
断言：up 后重复 action12 仅最早一条 is_redundant=0，其余=1；其他动作不受影响；
down 后全部置 0。
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def _alembic(db, *args):
    env = dict(os.environ)
    env["ALEMBIC_DB"] = str(db)
    r = subprocess.run(
        [sys.executable, "-m", "alembic"] + list(args),
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"alembic 失败: {r.stderr[-2000:]}"


@pytest.fixture()
def audit_db(tmp_path):
    """0008 状态库：audit 表 CHECK 1..12，含重复 action12 数据。"""
    db = tmp_path / "a.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE achievement_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            achievement_id INTEGER NOT NULL,
            achievement_kind TEXT CHECK(achievement_kind IN ('award','patent','software','innovation','other')),
            trace_id TEXT, action_type INTEGER NOT NULL CHECK(action_type BETWEEN 1 AND 12),
            action_result INTEGER NOT NULL DEFAULT 0 CHECK(action_result IN (0,1,2)),
            operator_id INTEGER, operator_code TEXT NOT NULL, operator_name TEXT NOT NULL,
            operator_role INTEGER CHECK(operator_role IN (1,2,3,4)), operator_ip TEXT,
            ai_batch_id TEXT, change_detail TEXT, remark TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    rows = [
        # 同 award#10 的 3 条 action12（最早 id=1 保留，其余标记冗余）
        (1, 10, 'award', 12), (2, 10, 'award', 12), (3, 10, 'award', 12),
        # 另一成果的单条 action12（不冗余）
        (4, 11, 'patent', 12),
        # 非删除动作不受影响
        (5, 10, 'award', 1),
    ]
    for i, aid, kind, at in rows:
        conn.execute(
            "INSERT INTO achievement_audit_log (id, achievement_id, achievement_kind,"
            " action_type, operator_code, operator_name) VALUES (?, ?, ?, ?, 'admin', 'admin')",
            (i, aid, kind, at))
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('0008_audit_action12')")
    conn.commit()
    conn.close()
    return db


def _redundant_map(db):
    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        "SELECT id, is_redundant FROM achievement_audit_log WHERE action_type=12 ORDER BY id"
    ).fetchall()
    conn.close()
    return dict(rows)


class Test0009:
    def test_upgrade_marks_only_redundant(self, audit_db):
        _alembic(audit_db, "upgrade", "0009_audit_redundant_flag")
        m = _redundant_map(audit_db)
        # award#10 三条：最早 id=1 保留，2/3 冗余；patent#11 单条不冗余
        assert m == {1: 0, 2: 1, 3: 1, 4: 0}
        # 非 action12 行也有列且默认 0
        conn = sqlite3.connect(str(audit_db))
        v = conn.execute(
            "SELECT is_redundant FROM achievement_audit_log WHERE id=5").fetchone()[0]
        conn.close()
        assert v == 0

    def test_downgrade_resets_to_zero(self, audit_db):
        _alembic(audit_db, "upgrade", "0009_audit_redundant_flag")
        _alembic(audit_db, "downgrade", "0008_audit_action12")
        m = _redundant_map(audit_db)
        assert m == {1: 0, 2: 0, 3: 0, 4: 0}
        conn = sqlite3.connect(str(audit_db))
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0008_audit_action12"
        conn.close()