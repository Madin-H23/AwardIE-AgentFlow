"""0011 迁移回归：sqlite_sequence 重复行去重（A3 迁移 up/down 断言）。

背景：0010 的 _restore_seqs 用 INSERT OR REPLACE 但 sqlite_sequence 无唯一
索引 → 同一表出现重复行 → AUTOINCREMENT 读第一行产生 id 复用（awards 新行
恒 1194，二次插入 PK 冲突被吞，表行数不增长）。
断言：up 后每表名仅一行且保留最大 seq；down no-op 不报错、版本回退。
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
def seq_db(tmp_path):
    """0010 状态库：含重复 sqlite_sequence 条目（复现 0010 缺陷后形态）。"""
    db = tmp_path / "seq.db"
    conn = sqlite3.connect(str(db))
    # 一个 AUTOINCREMENT 表（awards）+ 两张普通业务表（无 seq 条目也应保留）
    conn.execute("CREATE TABLE awards (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    # 0010 缺陷形态：同表两行 seq（先小后大，模拟 INSERT OR REPLACE 无冲突插入）
    conn.execute("INSERT INTO sqlite_sequence VALUES ('awards', 1193)")
    conn.execute("INSERT INTO sqlite_sequence VALUES ('awards', 1195)")
    conn.execute("INSERT INTO sqlite_sequence VALUES ('users', 1834)")
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('0010_typization_finish')")
    conn.commit()
    conn.close()
    return db


class TestUpgrade0011:
    def test_dedup_keeps_max_seq(self, seq_db):
        _alembic(seq_db, "upgrade", "0011_sqlite_seq_dedup")
        conn = sqlite3.connect(str(seq_db))
        rows = conn.execute("SELECT name, seq FROM sqlite_sequence ORDER BY name").fetchall()
        # awards 仅一行且保留最大值 1195
        awards = [r[1] for r in rows if r[0] == "awards"]
        assert awards == [1195], f"awards seq 应去重为 [1195]: {rows}"
        # 无重复的表不受影响
        users = [r[1] for r in rows if r[0] == "users"]
        assert users == [1834], f"users seq 不应被误删: {rows}"
        assert conn.execute(
            "SELECT version_num FROM alembic_version").fetchone()[0] == "0011_sqlite_seq_dedup"
        conn.close()

    def test_new_insert_uses_next_seq_after_dedup(self, seq_db):
        # 去重后自增恢复正常：新行 id = 1196（而不是恒 1194）
        _alembic(seq_db, "upgrade", "0011_sqlite_seq_dedup")
        conn = sqlite3.connect(str(seq_db))
        cur = conn.execute("INSERT INTO awards (name) VALUES ('x')")
        conn.commit()
        assert cur.lastrowid == 1196, f"去重后首次插入应取 1196，实际 {cur.lastrowid}"
        conn.close()

    def test_downgrade_noop_and_version_rollback(self, seq_db):
        _alembic(seq_db, "upgrade", "0011_sqlite_seq_dedup")
        _alembic(seq_db, "downgrade", "0010_typization_finish")
        conn = sqlite3.connect(str(seq_db))
        rows = conn.execute("SELECT name, seq FROM sqlite_sequence ORDER BY name").fetchall()
        awards = [r[1] for r in rows if r[0] == "awards"]
        # down 为 no-op（去重不可还原），版本回退 0010，数据保持去重后形态
        assert awards == [1195]
        assert conn.execute(
            "SELECT version_num FROM alembic_version").fetchone()[0] == "0010_typization_finish"
        conn.close()