"""阶段六 L3 分析层测试：LogAnalyzer / AlertEngine / PlanGenerator。"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.schemas import USERS_DDL


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """分析库：users + audit_log + system_event_log + pending + failed_logins。"""
    from backend.utils.system_event_logger import SystemEventLogger
    from backend.services.log_analyzer import LogAnalyzer
    d = tmp_path / "a.db"
    conn = sqlite3.connect(str(d))
    conn.execute(USERS_DDL)
    conn.execute("""CREATE TABLE achievement_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, achievement_id INTEGER, achievement_kind TEXT,
        trace_id VARCHAR(64), action_type INTEGER, action_result INTEGER,
        operator_id INTEGER, operator_code VARCHAR(50), operator_name VARCHAR(50),
        operator_role INTEGER, ai_batch_id VARCHAR(50), change_detail TEXT, remark TEXT,
        created_at TEXT, is_redundant INTEGER NOT NULL DEFAULT 0, is_test INTEGER NOT NULL DEFAULT 0)""")
    conn.execute("""CREATE TABLE pending_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, achievement_type TEXT, achievement_data TEXT,
        status TEXT, submit_time TEXT, submitter_type TEXT, submitter_id INTEGER)""")
    conn.execute("""CREATE TABLE failed_logins (
        id INTEGER PRIMARY KEY AUTOINCREMENT, login_code TEXT, ip TEXT,
        fail_count INTEGER, first_fail_at TEXT, lock_until TEXT, updated_at TEXT)""")
    conn.commit()
    conn.close()
    db = str(d)
    monkeypatch.setattr(SystemEventLogger, "_db_path", db)
    monkeypatch.setattr(LogAnalyzer, "_db_path", db)
    return db


def _ins_audit(db, action, code, name, ts):
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO achievement_audit_log (action_type, operator_code, operator_name, created_at) "
                 "VALUES (?,?,?,?)", (action, code, name, ts))
    conn.commit(); conn.close()


class TestLogAnalyzer:
    def test_action_distribution(self, db):
        from backend.services.log_analyzer import LogAnalyzer
        _ins_audit(db, 6, "t1", "张", "2026-01-01 10:00:00")
        _ins_audit(db, 6, "t1", "张", "2026-01-01 11:00:00")
        _ins_audit(db, 7, "s1", "李", "2026-01-01 12:00:00")
        dist = LogAnalyzer.action_distribution(db_path=db)
        assert dist == {6: 2, 7: 1}

    def test_action_distribution_date_filter(self, db):
        from backend.services.log_analyzer import LogAnalyzer
        _ins_audit(db, 6, "t1", "张", "2026-01-01 10:00:00")
        _ins_audit(db, 6, "t1", "张", "2026-02-01 10:00:00")
        # start_date=01-15：01-01 被滤除，02-01 保留
        assert LogAnalyzer.action_distribution(start_date="2026-01-15", db_path=db) == {6: 1}
        assert LogAnalyzer.action_distribution(start_date="2026-03-01", db_path=db) == {}

    def test_error_trend_groups_by_day(self, db):
        from backend.utils.system_event_logger import SystemEventLogger
        from backend.services.log_analyzer import LogAnalyzer
        SystemEventLogger.log("ocr", "error", "e1")
        SystemEventLogger.log("ocr", "warning", "w1")
        trend = LogAnalyzer.error_trend(days=1, db_path=db)
        assert len(trend) == 1
        assert trend[0]["error"] == 1 and trend[0]["warning"] == 1

    def test_review_bottleneck(self, db):
        from backend.services.log_analyzer import LogAnalyzer
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO pending_achievements (status, submit_time) VALUES "
                     "('submit', datetime('now','-3 days')),('submit', datetime('now','-1 hour')),"
                     "('pending', datetime('now','-5 days'))")   # pending 态不计入
        conn.commit(); conn.close()
        b = LogAnalyzer.review_bottleneck(db_path=db)
        assert b["pending_total"] == 2 and b["over_48h"] == 1

    def test_user_activity_top_n(self, db):
        from backend.services.log_analyzer import LogAnalyzer
        for i in range(5):
            _ins_audit(db, 6, "t1", "张", "2026-01-01 10:00:00")
        _ins_audit(db, 6, "s1", "李", "2026-01-01 11:00:00")
        top = LogAnalyzer.user_activity(top_n=1, db_path=db)
        assert top[0]["operator_code"] == "t1" and top[0]["count"] == 5

    def test_daily_summary(self, db):
        from backend.services.log_analyzer import LogAnalyzer
        from backend.utils.system_event_logger import SystemEventLogger
        _ins_audit(db, 6, "t1", "张", "2026-08-20 10:00:00")
        SystemEventLogger.log("db", "error", "锁")
        s = LogAnalyzer.daily_summary(day="2026-08-20", db_path=db)
        # SystemEventLogger 的 created_at 是 UTC——本地 08-20 可能落 UTC 08-20，断言审计行确定
        assert s["audit_actions"] == 1 and s["date"] == "2026-08-20"


class TestAlertEngine:
    def test_a001_ocr_error_rate_fires(self, db):
        from backend.utils.system_event_logger import SystemEventLogger
        from backend.services.alert_engine import evaluate
        SystemEventLogger.log("ocr", "error", "失败1")
        SystemEventLogger.log("ocr", "error", "失败2")
        SystemEventLogger.log("ocr", "info", "成功")
        fired = evaluate(db_path=db)
        a1 = [a for a in fired if a["id"] == "A001"]
        assert a1 and a1[0]["value"] == pytest.approx(2 / 3, abs=0.01)
        assert "OCR" in a1[0]["message"]

    def test_a001_no_data_not_fired(self, db):
        from backend.services.alert_engine import evaluate
        assert not [a for a in evaluate(db_path=db) if a["id"] == "A001"]

    def test_a002_backlog_fires(self, db):
        from backend.services.alert_engine import evaluate
        conn = sqlite3.connect(db)
        for _ in range(25):
            conn.execute("INSERT INTO pending_achievements (status, submit_time) "
                         "VALUES ('submit', datetime('now','-3 days'))")
        conn.commit(); conn.close()
        a2 = [a for a in evaluate(db_path=db) if a["id"] == "A002"]
        assert a2 and a2[0]["value"] == 25

    def test_a005_auth_failures_fires(self, db):
        from backend.services.alert_engine import evaluate
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO failed_logins (login_code, ip, fail_count, first_fail_at, updated_at) "
                     "VALUES ('admin','1.1.1.1',12,datetime('now','localtime'),datetime('now','localtime'))")
        conn.commit(); conn.close()
        a5 = [a for a in evaluate(db_path=db) if a["id"] == "A005"]
        assert a5 and a5[0]["value"] == 12

    def test_a006_db_errors_fires(self, db):
        from backend.utils.system_event_logger import SystemEventLogger
        from backend.services.alert_engine import evaluate
        SystemEventLogger.log("db", "error", "锁等待")
        a6 = [a for a in evaluate(db_path=db) if a["id"] == "A006"]
        assert a6 and a6[0]["severity"] == "warning"

    def test_archive_and_recent_alerts(self, db):
        from backend.services.alert_engine import evaluate, archive_alerts, get_recent_alerts
        from backend.utils.system_event_logger import SystemEventLogger
        SystemEventLogger.log("db", "error", "锁")
        fired = evaluate(db_path=db)
        assert archive_alerts(fired, ) >= 1
        recent = get_recent_alerts(db_path=db)
        assert any("[alert] A006" in r["message"] for r in recent)


class TestPlanGenerator:
    def test_generate_from_alerts_sorted(self, db):
        from backend.utils.system_event_logger import SystemEventLogger
        from backend.services.plan_generator import generate
        SystemEventLogger.log("db", "error", "锁")                       # A006 中
        conn = sqlite3.connect(db)
        for _ in range(25):
            conn.execute("INSERT INTO pending_achievements (status, submit_time) "
                         "VALUES ('submit', datetime('now','-3 days'))")
        conn.commit(); conn.close()                                       # A002 中
        plans = generate(db_path=db)
        assert all(p["status"] == "open" for p in plans)
        assert {p["priority"] for p in plans} <= {"高", "中"}

    def test_from_alert_fields(self):
        from backend.services.plan_generator import from_alert
        alert = {"id": "A004", "name": "留痕写入失败率", "severity": "critical",
                 "metric": "audit_write_failure_rate", "value": 0.023, "threshold": 0.01,
                 "message": "留痕写入失败率 2.30%", "action": "检查锁竞争", "extra": {}}
        p = from_alert(alert)
        assert p["priority"] == "高" and p["category"] == "安全"
        assert p["suggested_actions"] == ["检查锁竞争"] and p["status"] == "open"

    def test_transition_state_machine(self):
        from backend.services.plan_generator import from_alert, transition
        alert = {"id": "A001", "name": "x", "severity": "warning", "metric": "m",
                 "value": 1, "threshold": 0, "message": "m", "action": "a", "extra": {}}
        plan = from_alert(alert)
        transition(plan, "acknowledged")
        transition(plan, "resolved")
        with pytest.raises(ValueError):
            transition(plan, "open")          # resolved 不可逆
        plan2 = from_alert(alert)
        transition(plan2, "ignored")
        with pytest.raises(ValueError):
            transition(plan2, "acknowledged")  # ignored 只能重评估复活

    def test_daily_report_shape(self, db):
        from backend.services.plan_generator import daily_report
        r = daily_report(db_path=db)
        assert {"date", "audit_actions", "system_events", "system_errors", "alerts", "ai_health"} <= set(r)
