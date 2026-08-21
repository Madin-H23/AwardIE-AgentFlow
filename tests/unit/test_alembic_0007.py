"""0007 迁移回归：audit 时间基准 UTC→本地 +8h（up），-8h 回滚（down）。

背景：achievement_audit_log.created_at 原为 SQLite CURRENT_TIMESTAMP(UTC)，
0007 把存量行一次性 +8h 对齐写入层本地时间策略。
断言：up 后每行 +8h；down 后回滚 -8h；版本号双向正确。
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.schemas import AUDIT_LOG_DDL  # noqa: E402


def _alembic(db, *args):
    env = dict(os.environ)
    env["ALEMBIC_DB"] = str(db)
    r = subprocess.run(
        [sys.executable, "-m", "alembic"] + list(args),
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"alembic 失败: {r.stderr[-2000:]}"


@pytest.fixture()
def audit_db(tmp_path):
    """0006 状态库：audit 表（UTC 形态）+ 两行时间数据。"""
    db = tmp_path / "a.db"
    conn = sqlite3.connect(str(db))
    conn.execute(AUDIT_LOG_DDL)
    # 0006 形态（0008 尚未重建）：action_type 1..11 即可——AUDIT_LOG_DDL 已是 1..12，
    # 0007 只动时间与结构无关，直接复用
    conn.executemany(
        "INSERT INTO achievement_audit_log (achievement_id, achievement_kind, action_type,"
        " operator_code, operator_name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        [(100, 'award', 1, '212306413', '陈品天', '2026-08-21 03:00:00'),
         (101, 'patent', 8, 'admin', 'admin', '2026-08-20 14:30:00')])
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('0006_system_event_log')")
    conn.commit()
    conn.close()
    return db


def _created_ats(db):
    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        "SELECT created_at FROM achievement_audit_log ORDER BY id").fetchall()
    conn.close()
    return [r[0] for r in rows]


class Test0007:
    def test_upgrade_adds_8h(self, audit_db):
        _alembic(audit_db, "upgrade", "0007_audit_localtime")
        assert _created_ats(audit_db) == ['2026-08-21 11:00:00', '2026-08-20 22:30:00']
        conn = sqlite3.connect(str(audit_db))
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0007_audit_localtime"
        conn.close()

    def test_roundtrip_downgrade_upgrade(self, audit_db):
        _alembic(audit_db, "upgrade", "0007_audit_localtime")
        _alembic(audit_db, "downgrade", "0006_system_event_log")
        # down 回滚 -8h 回到 UTC 基准
        assert _created_ats(audit_db) == ['2026-08-21 03:00:00', '2026-08-20 14:30:00']
        _alembic(audit_db, "upgrade", "0007_audit_localtime")
        assert _created_ats(audit_db) == ['2026-08-21 11:00:00', '2026-08-20 22:30:00']