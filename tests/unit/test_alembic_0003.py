"""M1 后半③③：类型规范全表重建 0003 往返回归（防类型/索引/视图回归护栏）。

在临时模拟库上执行 alembic upgrade（ALEMBIC_DB 环境变量指向测试库），断言：
- 短字段 TEXT → VARCHAR(N)，长文本保留 TEXT
- 索引/唯一约束保留、视图重建可用、数据行数一致
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
def schema_db(tmp_path):
    """0002 状态库：users(TEXT)+视图+索引+数据（0003 重建的输入形态）。"""
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login_code TEXT UNIQUE, name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
        password_hash TEXT, skills TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("CREATE INDEX idx_users_code ON users(login_code)")
    conn.execute("CREATE UNIQUE INDEX uk_users_name ON users(name)")
    conn.execute("CREATE VIEW students AS SELECT id, login_code AS student_id, name FROM users WHERE role='student'")
    conn.execute("INSERT INTO users (login_code, name, role, password_hash) VALUES ('s1','张三','student','hash')")
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('0002_legacy_tables_to_views')")
    conn.commit()
    conn.close()
    return db


class TestUpgrade0003:
    def test_types_indexes_views_preserved(self, schema_db):
        # 显式升级到 0003（head 已到 0004，本测试聚焦 0003 迁移）
        _alembic(schema_db, "upgrade", "0003_typization_rebuild")
        conn = sqlite3.connect(str(schema_db))
        cols = {r[1]: r[2] for r in conn.execute("PRAGMA table_info(users)")}
        assert cols["login_code"] == "VARCHAR(50)"
        assert cols["name"] == "VARCHAR(50)"
        assert cols["password_hash"] == "VARCHAR(255)"
        assert cols["skills"] == "TEXT"            # 长文本保留
        # 索引/唯一约束保留
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='idx_users_code'").fetchone()
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='uk_users_name'").fetchone()
        # 视图重建可用 + 数据保留
        assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 1
        assert conn.execute("SELECT student_id, name FROM students").fetchone() == ("s1", "张三")
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0003_typization_rebuild"
        conn.close()

    def test_views_dropped_and_recreated_on_users_rebuild(self, schema_db):
        """重建 users（被视图引用）不破坏视图：DROP 前删视图、完成后重建。"""
        _alembic(schema_db, "upgrade", "0003_typization_rebuild")
        conn = sqlite3.connect(str(schema_db))
        assert conn.execute("SELECT type FROM sqlite_master WHERE name='students'").fetchone()[0] == "view"
        conn.close()
