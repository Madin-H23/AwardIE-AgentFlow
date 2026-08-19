"""M1 后半③② 补漏：0004 迁移回归（3 张 teacher 关联表 FK 改指 users）。

防回归护栏：视图化后 teacher 关联表 FK 不得再指向 teachers 视图（SQLite 禁止），
foreign_key_check 必须为空。
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


def _alembic(db, *args):
    env = dict(os.environ)
    env["ALEMBIC_DB"] = str(db)
    r = subprocess.run(
        [sys.executable, "-m", "alembic"] + list(args),
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"alembic 失败: {r.stderr[-2000:]}"


@pytest.fixture()
def schema_db(tmp_path):
    """0003 状态库：users + teachers 视图 + 3 张 teacher 关联表（FK→teachers 的遗留形态）。"""
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.execute(USERS_DDL)
    conn.execute("CREATE VIEW teachers AS SELECT id, login_code AS teacher_id, name FROM users WHERE role='teacher'")
    for t in ("laboratory_instructors", "award_teacher_winners", "award_supervisors"):
        conn.execute(f"""CREATE TABLE {t} (
            award_id INTEGER,
            teacher_id INTEGER,
            PRIMARY KEY (award_id, teacher_id),
            FOREIGN KEY (teacher_id) REFERENCES teachers(id))""")
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('0003_typization_rebuild')")
    conn.commit()
    conn.close()
    return db


class TestUpgrade0004:
    def test_teacher_fk_relink_and_check_empty(self, schema_db):
        # 显式升级到 0004（head 已到 0005，本测试聚焦 0004 迁移）
        _alembic(schema_db, "upgrade", "0004_teacher_fk_relink")
        conn = sqlite3.connect(str(schema_db))
        # FK 改指 users
        for t in ("laboratory_instructors", "award_teacher_winners", "award_supervisors"):
            fks = [(f[2], f[4]) for f in conn.execute(f"PRAGMA foreign_key_list({t})")]
            assert ("users", "id") in fks, f"{t} FK 未指向 users: {fks}"
        # foreign_key_check 空（9.5 项 8）
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0004_teacher_fk_relink"
        conn.close()
