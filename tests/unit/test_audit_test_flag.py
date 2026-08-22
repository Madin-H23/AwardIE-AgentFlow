"""0012 迁移与审计防复发回归：is_test 打标 / pytest 运行态自动标记 / 查询默认过滤。

背景：本地跑批在真实库产生 ~1290 条测试留痕污染 admin/logs 取证价值。
0012 加列 is_test 并按保守特征打标（深夜时段/合成操作者/分钟突发/冒烟教师孤儿实体）；
AuditLogger 在 pytest 运行态写入自动 is_test=1（conftest 注入 AWARDIE_AUDIT_TEST_MODE）；
查询层默认过滤 is_test=1，include_tests=True 查全量。downgrade 置 0 可回退。
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


AUDIT_DDL_0011 = """CREATE TABLE achievement_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id INTEGER NOT NULL, achievement_kind TEXT, trace_id TEXT,
    action_type INTEGER NOT NULL, action_result INTEGER NOT NULL DEFAULT 0,
    operator_id INTEGER, operator_code TEXT NOT NULL, operator_name TEXT NOT NULL,
    operator_role INTEGER, operator_ip TEXT, ai_batch_id TEXT,
    change_detail TEXT, remark TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, is_redundant INTEGER NOT NULL DEFAULT 0)"""


@pytest.fixture()
def flag_db(tmp_path):
    """0011 状态库：audit 表无 is_test 列 + 最小 awards 表（孤儿判定依赖）。"""
    db = tmp_path / "flag.db"
    conn = sqlite3.connect(str(db))
    conn.execute(AUDIT_DDL_0011)
    conn.execute("CREATE TABLE awards (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO awards (id, title) VALUES (1, '存活成果')")
    rows = [
        # (id, created_at, action, op_code, entity)  期望 up 后 is_test
        (1, "2026-08-23 03:30:00", 6, "0", 100),          # 1=深夜+合成 → 标
        (2, "2026-08-23 14:00:00", 1, "212306413", 101),   # 1=冒烟学生账号 → 标
        (3, "2026-08-21 15:39:21", 12, "admin", 1195),     # 0=真实删除史，保留
        (4, "2026-08-23 14:00:00", 8, "02110606", 9999),   # 1=冒烟教师指向孤儿实体 → 标
        (5, "2026-08-23 14:00:00", 8, "02110606", 1),      # 0=教师指向存活实体，保留
        (6, "2026-08-23 10:00:01", 6, "admin", 200),       # 1=同分钟同操作者同动作×5 突发 → 标
        (7, "2026-08-23 10:00:02", 6, "admin", 201),       # 1
        (8, "2026-08-23 10:00:03", 6, "admin", 202),       # 1
        (9, "2026-08-23 10:00:04", 6, "admin", 203),       # 1
        (10, "2026-08-23 10:00:05", 6, "admin", 204),      # 1（第5条触发突发阈值）
        (11, "2026-08-23 15:00:00", 1, "admin", 300),      # 0=白天单条人工形态，保留
    ]
    for i, ts, at, op, aid in rows:
        conn.execute(
            "INSERT INTO achievement_audit_log (id, created_at, action_type,"
            " operator_code, operator_name, achievement_kind, achievement_id)"
            " VALUES (?,?,?,?,?,?,?)", (i, ts, at, op, op, "award", aid))
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('0011_sqlite_seq_dedup')")
    conn.commit()
    conn.close()
    return db


def _flags(db):
    conn = sqlite3.connect(str(db))
    m = dict(conn.execute("SELECT id, is_test FROM achievement_audit_log ORDER BY id"))
    conn.close()
    return m


class Test0012Migration:
    def test_upgrade_marks_conservatively(self, flag_db):
        _alembic(flag_db, "upgrade", "0012_audit_test_flag")
        m = _flags(flag_db)
        assert m == {1: 1, 2: 1, 3: 0, 4: 1, 5: 0, 6: 1, 7: 1, 8: 1, 9: 1, 10: 1, 11: 0}
        conn = sqlite3.connect(str(flag_db))
        v = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        conn.close()
        assert v == "0012_audit_test_flag"

    def test_downgrade_resets_to_zero(self, flag_db):
        _alembic(flag_db, "upgrade", "0012_audit_test_flag")
        _alembic(flag_db, "downgrade", "0011_sqlite_seq_dedup")
        m = _flags(flag_db)
        assert set(m.values()) == {0}
        conn = sqlite3.connect(str(flag_db))
        v = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        conn.close()
        assert v == "0011_sqlite_seq_dedup"


@pytest.fixture()
def logger_db(tmp_path, monkeypatch):
    """含 is_test 列的临时库，AuditLogger._db_path 指向它。"""
    db = tmp_path / "logger.db"
    conn = sqlite3.connect(str(db))
    conn.execute(AUDIT_DDL_0011.replace(
        "is_redundant INTEGER NOT NULL DEFAULT 0)",
        "is_redundant INTEGER NOT NULL DEFAULT 0, is_test INTEGER NOT NULL DEFAULT 0)"))
    conn.commit(); conn.close()
    from backend.utils.audit_logger import AuditLogger
    monkeypatch.setattr(AuditLogger, "_db_path", str(db))
    return str(db)


class TestAuditLoggerTestMode:
    def test_pytest_mode_writes_is_test_1(self, logger_db):
        """pytest 进程内（conftest 已注入旗标）：写入自动 is_test=1。"""
        from backend.utils.audit_logger import audit_log
        assert audit_log(1, 42, "award",
                         operator={"id": 7, "code": "20230001", "user_type": "student"}) is True
        row = _flags(logger_db)
        assert list(row.values()) == [1]

    def test_production_mode_writes_is_test_0(self, logger_db, monkeypatch):
        """模拟生产进程：剥离双信号后 is_test=0。"""
        monkeypatch.delenv("AWARDIE_AUDIT_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        from backend.utils.audit_logger import audit_log
        assert audit_log(1, 43, "award",
                         operator={"id": 7, "code": "20230001", "user_type": "student"}) is True
        assert list(_flags(logger_db).values()) == [0]


class TestQueryFilters:
    @pytest.fixture()
    def mixed_db(self, tmp_path):
        db = tmp_path / "mixed.db"
        conn = sqlite3.connect(str(db))
        conn.execute(AUDIT_DDL_0011.replace(
            "is_redundant INTEGER NOT NULL DEFAULT 0)",
            "is_redundant INTEGER NOT NULL DEFAULT 0, is_test INTEGER NOT NULL DEFAULT 0)"))
        conn.execute("""INSERT INTO achievement_audit_log
            (achievement_id, achievement_kind, action_type, operator_code, operator_name, is_test)
            VALUES (1,'award',1,'admin','admin',0), (2,'award',8,'0','0',1)""")
        conn.commit(); conn.close()
        return str(db)

    def test_default_excludes_test_rows(self, mixed_db):
        from backend.services.log_query_service import LogQueryService
        r = LogQueryService.query_audit_logs(db_path=mixed_db, per_page=10)
        assert [it["achievement_id"] for it in r["items"]] == [1]

    def test_include_tests_returns_all(self, mixed_db):
        from backend.services.log_query_service import LogQueryService
        r = LogQueryService.query_audit_logs(db_path=mixed_db, per_page=10, include_tests=True)
        assert sorted(it["achievement_id"] for it in r["items"]) == [1, 2]

    def test_action_distribution_excludes_test_rows(self, mixed_db):
        from backend.services.log_analyzer import LogAnalyzer
        d = LogAnalyzer.action_distribution(db_path=mixed_db)
        assert d == {1: 1}
