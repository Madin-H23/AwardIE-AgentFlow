"""0008 迁移回归：audit 表重建，CHECK 动作枚举 1..11 → 1..12（up），反向（down）。

背景：补"成果删除留痕"需 action_type=12，SQLite CHECK 无法 ALTER → 三步重建表。
断言：up 后 CHECK 含 BETWEEN 1 AND 12 且 action12 可插入、数据保留；
down 后回 1..11 且 action12 插入被拒绝（数据仍保留）。
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
    """0007 状态库：audit 表 CHECK 1..11（0008 前形态）。"""
    db = tmp_path / "a.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE achievement_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            achievement_id INTEGER NOT NULL,
            achievement_kind TEXT CHECK(achievement_kind IN ('award','patent','software','innovation','other')),
            trace_id TEXT, action_type INTEGER NOT NULL CHECK(action_type BETWEEN 1 AND 11),
            action_result INTEGER NOT NULL DEFAULT 0 CHECK(action_result IN (0,1,2)),
            operator_id INTEGER, operator_code TEXT NOT NULL, operator_name TEXT NOT NULL,
            operator_role INTEGER CHECK(operator_role IN (1,2,3,4)), operator_ip TEXT,
            ai_batch_id TEXT, change_detail TEXT, remark TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for i, at in enumerate([1, 6, 8], start=1):
        conn.execute(
            "INSERT INTO achievement_audit_log (achievement_id, achievement_kind, action_type,"
            " operator_code, operator_name) VALUES (?, 'award', ?, 'admin', 'admin')",
            (i, at))
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('0007_audit_localtime')")
    conn.commit()
    conn.close()
    return db


def _check_sql(db):
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='achievement_audit_log'"
    ).fetchone()
    conn.close()
    return row[0] or ''


def _count(db):
    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM achievement_audit_log").fetchone()[0]
    conn.close()
    return n


class Test0008:
    def test_upgrade_check_12_and_data_kept(self, audit_db):
        _alembic(audit_db, "upgrade", "0008_audit_action12")
        sql = _check_sql(audit_db)
        assert "BETWEEN 1 AND 12" in sql
        assert _count(audit_db) == 3  # 重建保留数据
        # 新枚举值可插入
        conn = sqlite3.connect(str(audit_db))
        conn.execute(
            "INSERT INTO achievement_audit_log (achievement_id, achievement_kind,"
            " action_type, operator_code, operator_name) VALUES (9, 'award', 12, 'admin', 'admin')")
        conn.commit()
        conn.close()

    def test_downgrade_back_to_11_rejects_12(self, audit_db):
        _alembic(audit_db, "upgrade", "0008_audit_action12")
        _alembic(audit_db, "downgrade", "0007_audit_localtime")
        sql = _check_sql(audit_db)
        assert "BETWEEN 1 AND 11" in sql
        assert _count(audit_db) == 3  # 数据保留
        # action12 在 1..11 约束下被拒绝
        conn = sqlite3.connect(str(audit_db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO achievement_audit_log (achievement_id, achievement_kind,"
                " action_type, operator_code, operator_name) VALUES (9, 'award', 12, 'admin', 'admin')")
            conn.commit()
        conn.close()