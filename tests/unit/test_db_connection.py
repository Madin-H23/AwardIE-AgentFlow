"""P0-4/P0-5/P0-7 回归测试：统一连接工厂的三契约必须生效。"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.db_connection import get_connection


@pytest.fixture()
def tmp_db(tmp_path):
    return tmp_path / "test_contract.db"


def test_pragma_contract(tmp_db):
    """三契约：foreign_keys=ON / journal_mode=WAL / busy_timeout=30000。"""
    conn = get_connection(tmp_db)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    finally:
        conn.close()


def test_foreign_key_actually_enforced(tmp_db):
    """外键不只是开关：插入孤儿行必须被拒（修复前实测已产生 4 条孤儿）。"""
    conn = get_connection(tmp_db)
    try:
        conn.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE child(id INTEGER PRIMARY KEY, pid INTEGER REFERENCES parent(id))")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO child(id, pid) VALUES (1, 999)")
    finally:
        conn.close()


def test_row_factory_named_access(tmp_db):
    """sqlite3.Row 兼容索引访问（不破坏既有元组用法）且支持按列名。"""
    conn = get_connection(tmp_db)
    try:
        conn.execute("CREATE TABLE t(a INTEGER, b TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'x')")
        row = conn.execute("SELECT a, b FROM t").fetchone()
        assert row[0] == 1 and row["b"] == "x"
    finally:
        conn.close()


def test_wal_persists_on_file(tmp_db):
    """WAL 持久化：工厂连接一次后，裸连接也读到 wal（库文件级属性）。"""
    get_connection(tmp_db).close()
    raw = sqlite3.connect(str(tmp_db))
    try:
        assert str(raw.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
    finally:
        raw.close()


def test_managers_use_factory():
    """三个核心 Manager 的 _get_db_connection 必须经工厂（防回退为裸连接）。"""
    import inspect
    from backend.models import student as m_student
    from backend.models import teacher as m_teacher
    from backend.models import pending_achievement as m_pending
    for mod in (m_student, m_teacher, m_pending):
        src = inspect.getsource(mod)
        assert "get_connection" in src, f"{mod.__name__} 未接入连接工厂"
        assert "sqlite3.connect(self.db_path)" not in src, f"{mod.__name__} 仍存在裸连接"
