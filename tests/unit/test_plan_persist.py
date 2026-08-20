"""L6 收尾测试：行动计划持久化（action_plans 落库）+ 日志定时任务容错。"""
import pytest

from backend.services import plan_generator as pg
from backend.utils import log_scheduler
from backend.utils.db_connection import get_connection

_DDL = """
CREATE TABLE IF NOT EXISTS action_plans (
    id TEXT PRIMARY KEY, alert_id TEXT NOT NULL, priority TEXT NOT NULL,
    category TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
    evidence TEXT, suggested_actions TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL, updated_at TEXT, resolved_at TEXT)
"""


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "log_plans.db")


def _insert_plan(db, pid="P-A001", status="open"):
    conn = get_connection(db)
    try:
        conn.execute(_DDL)
        conn.execute(
            "INSERT INTO action_plans (id, alert_id, priority, category, title, description, "
            "evidence, suggested_actions, status, created_at, updated_at, resolved_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, "A001", "高", "运维", "A001: t", "d", '[{}]', '["a"]',
             status, "2026-08-20 10:00:00", None, None))
        conn.commit()
    finally:
        conn.close()


def test_load_returns_persisted(tmp_db):
    _insert_plan(tmp_db)
    plans = pg.load(db_path=tmp_db)
    assert any(p["id"] == "P-A001" for p in plans)


def test_transition_writes_db_and_survives_reload(tmp_db):
    _insert_plan(tmp_db)
    p = next(x for x in pg.load(db_path=tmp_db) if x["id"] == "P-A001")
    pg.transition(p, "acknowledged", db_path=tmp_db)
    reloaded = next(x for x in pg.load(db_path=tmp_db) if x["id"] == "P-A001")
    assert reloaded["status"] == "acknowledged"
    assert reloaded["updated_at"]


def test_transition_invalid_raises_valueerror(tmp_db):
    _insert_plan(tmp_db)
    p = next(x for x in pg.load(db_path=tmp_db) if x["id"] == "P-A001")
    # open 不允许直接 resolved（open → acknowledged → resolved 才合法）
    with pytest.raises(ValueError):
        pg.transition(p, "resolved", db_path=tmp_db)


def test_resolve_chain_legal(tmp_db):
    _insert_plan(tmp_db)
    p = next(x for x in pg.load(db_path=tmp_db) if x["id"] == "P-A001")
    pg.transition(p, "acknowledged", db_path=tmp_db)
    pg.transition(p, "resolved", db_path=tmp_db)
    q = next(x for x in pg.load(db_path=tmp_db) if x["id"] == "P-A001")
    assert q["status"] == "resolved"
    assert q["resolved_at"]


def test_scheduler_daily_no_crash_on_minimal_db(tmp_db):
    # 空/最小库上每日任务不抛（容量清理/ignored 重评估对缺表容错）
    log_scheduler.run_daily(db_path=tmp_db)
    # 无异常即通过


def test_reopen_ignored_updates_status(tmp_db):
    conn = get_connection(tmp_db)
    try:
        conn.execute(_DDL)
        conn.execute(
            "INSERT INTO action_plans (id, alert_id, priority, category, title, status, created_at) "
            "VALUES ('P-IGN','A004','高','安全','old','ignored', datetime('now','-10 days'))")
        conn.commit()
    finally:
        conn.close()
    log_scheduler.run_daily(db_path=tmp_db)
    rows = pg.load(db_path=tmp_db)
    p = next(x for x in rows if x["id"] == "P-IGN")
    assert p["status"] == "open"
