"""M1 后半②：旧三表视图化迁移 0002 往返回归（防迁移回归护栏）。

在临时模拟库上执行 alembic upgrade/downgrade（ALEMBIC_DB 环境变量指向测试库——
env.py 在线模式经 _resolve_db_path 解析，不再误跑生产库）。
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.schemas import USERS_DDL

_RELINK_TABLES = (
    "laboratory_students", "laboratory_assistants", "innovation_project_students",
    "award_student_winners", "award_related_students",
)


def _alembic(db, *args):
    """子进程执行 alembic（env.py 经 ALEMBIC_DB 定位测试库）。"""
    env = dict(os.environ)
    env["ALEMBIC_DB"] = str(db)
    r = subprocess.run(
        [sys.executable, "-m", "alembic"] + list(args),
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"alembic 失败: {r.stderr[-2000:]}"


@pytest.fixture()
def legacy_db(tmp_path):
    """0001 前置库：旧三表 + users + 5 关联表（带旧表 id 数据 + FK→students）。"""
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, student_id TEXT, name TEXT)")
    conn.execute("CREATE TABLE teachers (id INTEGER PRIMARY KEY, teacher_id TEXT, name TEXT)")
    conn.execute("CREATE TABLE admins (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, name TEXT, user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
    conn.execute(USERS_DDL)
    conn.execute("INSERT INTO users (login_code, name, role) VALUES ('s1', '张三', 'student')")
    conn.execute("INSERT INTO students (id, student_id, name) VALUES (1, 's1', '张三')")
    for t in _RELINK_TABLES:
        conn.execute(f"CREATE TABLE {t} (award_id INTEGER, student_id INTEGER, "
                     "FOREIGN KEY(student_id) REFERENCES students(id))")
    conn.execute("INSERT INTO award_student_winners VALUES (10, 1)")   # 旧 students.id=1
    conn.commit()
    conn.close()
    return db


class TestUpgrade0002:
    def test_upgrade_views_and_relinks(self, legacy_db):
        _alembic(legacy_db, "upgrade", "head")
        conn = sqlite3.connect(str(legacy_db))
        # 视图化
        for t in ("students", "teachers", "admins"):
            assert conn.execute(
                "SELECT type FROM sqlite_master WHERE name=?", (t,)).fetchone()[0] == "view"
        # 关联表数据重写为 users.id + FK 指向 users
        uid = conn.execute("SELECT id FROM users WHERE login_code='s1'").fetchone()[0]
        assert conn.execute(
            "SELECT student_id FROM award_student_winners").fetchone()[0] == uid
        fk = conn.execute("PRAGMA foreign_key_list(award_student_winners)").fetchall()
        assert fk and fk[0][2] == "users" and fk[0][4] == "id"
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002_legacy_tables_to_views"
        conn.close()

    def test_roundtrip_downgrade_upgrade(self, legacy_db):
        """往返：0002 → 0001（视图还原实体表+数据回拷）→ 0002（幂等重做）。"""
        _alembic(legacy_db, "upgrade", "head")
        _alembic(legacy_db, "downgrade", "0001_orm_baseline")
        conn = sqlite3.connect(str(legacy_db))
        assert conn.execute("SELECT type FROM sqlite_master WHERE name='students'").fetchone()[0] == "table"
        assert conn.execute("SELECT student_id FROM students").fetchone()[0] == "s1"
        conn.close()
        _alembic(legacy_db, "upgrade", "head")
        conn = sqlite3.connect(str(legacy_db))
        assert conn.execute("SELECT type FROM sqlite_master WHERE name='students'").fetchone()[0] == "view"
        conn.close()
