"""P1-13 回归测试：AuditLogger 骨架（落行/不阻塞/operator 解析）。"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_DDL = """CREATE TABLE achievement_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id INTEGER NOT NULL, achievement_kind TEXT, trace_id TEXT,
    action_type INTEGER NOT NULL, action_result INTEGER NOT NULL DEFAULT 0,
    operator_id INTEGER, operator_code TEXT NOT NULL, operator_name TEXT NOT NULL,
    operator_role INTEGER, operator_ip TEXT, ai_batch_id TEXT,
    change_detail TEXT, remark TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, is_redundant INTEGER NOT NULL DEFAULT 0, is_test INTEGER NOT NULL DEFAULT 0)"""


@pytest.fixture()
def audit_db(tmp_path, monkeypatch):
    db = tmp_path / "audit.db"
    conn = sqlite3.connect(str(db))
    conn.execute(AUDIT_DDL)
    conn.commit()
    conn.close()
    from backend.utils.audit_logger import AuditLogger
    monkeypatch.setattr(AuditLogger, "_db_path", str(db))   # 指向临时库
    return str(db)


def _rows(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    r = [dict(x) for x in c.execute("SELECT * FROM achievement_audit_log ORDER BY id")]
    c.close()
    return r


def test_submit_audit_written(audit_db):
    from backend.utils.audit_logger import audit_log
    assert audit_log(1, 42, "award", operator={"id": 7, "code": "20230001", "user_type": "student"}) is True
    row = _rows(audit_db)[0]
    assert row["action_type"] == 1 and row["achievement_id"] == 42
    assert row["operator_code"] == "20230001" and row["operator_role"] == 1   # student→1
    assert row["action_result"] == 1


def test_ai_audit_with_snapshot(audit_db):
    from backend.utils.audit_logger import audit_log
    review = {"decision": "reject", "issues": [{"field": "level", "severity": "high"}]}
    audit_log(2, 99, "patent", operator="AI", action_result=2, change_detail=review)
    row = _rows(audit_db)[0]
    assert row["operator_code"] == "AI" and row["operator_role"] == 3
    assert json.loads(row["change_detail"])["decision"] == "reject"          # 决策快照落库


def test_missing_operator_skips_silently(audit_db):
    """无 operator（无 session 显式传）→ 跳过并返回 False，不抛异常。"""
    from backend.utils.audit_logger import audit_log
    assert audit_log(6, 1, "award") is False
    assert _rows(audit_db) == []


def test_db_failure_never_raises(tmp_path, monkeypatch):
    """8.6.3 契约：库损坏/路径错误也绝不阻塞主业务。"""
    from backend.utils.audit_logger import AuditLogger
    monkeypatch.setattr(AuditLogger, "_db_path", str(tmp_path / "not_exist_dir" / "x.db"))
    assert AuditLogger.log(6, 1, "award", operator="AI") is False           # 吞掉返回 False


def test_session_operator_resolution(audit_db):
    """请求上下文内自动取 session 登录人。"""
    from backend.utils.audit_logger import audit_log
    from flask import Flask
    app = Flask(__name__)
    app.secret_key = "test-only-key"
    with app.test_request_context():
        from flask import session
        session["user_id"] = "T001"
        session["user_type"] = "teacher"
        session["name"] = "张老师"
        assert audit_log(5, 7, "award") is True
    row = _rows(audit_db)[0]
    assert row["operator_code"] == "T001" and row["operator_role"] == 2 and row["operator_name"] == "张老师"
