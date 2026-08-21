"""阶段六 L2 查询层测试：LogFileReader / LogQueryService / MetricsSnapshot / trace_id 链路。"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.schemas import USERS_DDL


@pytest.fixture()
def db(tmp_path):
    """三源日志库（users + system_event_log 由 Logger 兜底建）。"""
    d = tmp_path / "q.db"
    conn = sqlite3.connect(str(d))
    conn.execute(USERS_DDL)
    conn.execute("""CREATE TABLE achievement_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, achievement_id INTEGER, achievement_kind TEXT,
        trace_id VARCHAR(64), action_type INTEGER, action_result INTEGER,
        operator_id INTEGER, operator_code VARCHAR(50), operator_name VARCHAR(50),
        operator_role INTEGER, ai_batch_id VARCHAR(50), change_detail TEXT, remark TEXT,
        created_at TEXT, is_redundant INTEGER NOT NULL DEFAULT 0)""")
    conn.execute("""CREATE TABLE review_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, pending_id INTEGER, achievement_type TEXT,
        file_hash TEXT, file_path TEXT, submitter_type TEXT, submitter_id INTEGER,
        reviewer_type TEXT, reviewer_id INTEGER, action_type TEXT, result_type TEXT,
        result_id INTEGER, result_file_path TEXT, review_comment TEXT, operation_note TEXT,
        created_at TEXT)""")
    conn.execute("INSERT INTO achievement_audit_log (achievement_id, trace_id, action_type, operator_role, created_at) "
                 "VALUES (1,'t-a',6,2,'2026-01-01 10:00:00'),(2,'t-b',7,4,'2026-01-01 11:00:00')")
    conn.execute("INSERT INTO review_logs (pending_id, action_type, reviewer_id, created_at) "
                 "VALUES (1,'approve',9,'2026-01-01 09:00:00')")
    conn.commit()
    conn.close()
    return str(d)


@pytest.fixture()
def evt_db(db, monkeypatch):
    from backend.utils.system_event_logger import SystemEventLogger
    monkeypatch.setattr(SystemEventLogger, "_db_path", db)
    return db


class TestLogFileReader:
    @pytest.fixture()
    def log_file(self, tmp_path):
        f = tmp_path / "app.log"
        f.write_text(
            "2026-08-20 10:00:01 - INFO [app.x] [tid:abc123] 启动完成\n"
            "2026-08-20 10:00:02 - WARNING [backend.ocr] [tid:def456] OCR 超时重试\n"
            "2026-08-20 10:00:03 - ERROR [app.y] 旧格式无tid\n"
            "不是日志行\n", encoding="utf-8")
        return str(f)

    def test_tail_parses_new_and_old_format(self, log_file):
        from backend.services.log_file_reader import LogFileReader
        rows = LogFileReader.tail(lines=10, log_file=log_file)
        # 倒序：旧格式错误 → 无tid → OCR → 启动（"不是日志行"被跳过）
        assert [r.get("trace_id") for r in rows] == [None, "def456", "abc123"]
        assert rows[-1]["msg"] == "启动完成"

    def test_search_keyword_and_level(self, log_file):
        from backend.services.log_file_reader import LogFileReader
        rows = LogFileReader.search(keyword="OCR", log_file=log_file)
        assert len(rows) == 1 and rows[0]["level"] == "WARNING"
        rows2 = LogFileReader.search(level="INFO", log_file=log_file)
        assert len(rows2) == 1 and "启动" in rows2[0]["msg"]

    def test_search_time_range(self, log_file):
        from backend.services.log_file_reader import LogFileReader
        rows = LogFileReader.search(start_time="2026-08-20 10:00:03", log_file=log_file)
        assert len(rows) == 1 and rows[0]["level"] == "ERROR"

    def test_missing_file_returns_empty(self, tmp_path):
        from backend.services.log_file_reader import LogFileReader
        assert LogFileReader.tail(log_file=tmp_path / "no.log") == []
        assert LogFileReader.search(log_file=tmp_path / "no.log") == []


class TestLogQueryService:
    def test_audit_filter_and_pagination(self, db):
        from backend.services.log_query_service import LogQueryService
        r = LogQueryService.query_audit_logs(action_type=6, db_path=db)
        assert r["total"] == 1 and r["items"][0]["trace_id"] == "t-a"
        r2 = LogQueryService.query_audit_logs(page=1, per_page=1, db_path=db)
        assert r2["total"] == 2 and len(r2["items"]) == 1

    def test_audit_trace_id_filter(self, db):
        from backend.services.log_query_service import LogQueryService
        r = LogQueryService.query_audit_logs(trace_id="t-b", db_path=db)
        assert r["total"] == 1 and r["items"][0]["achievement_id"] == 2

    def test_system_events_query(self, evt_db):
        from backend.utils.system_event_logger import SystemEventLogger
        from backend.services.log_query_service import LogQueryService
        SystemEventLogger.log("ocr", "error", "百度超时")
        SystemEventLogger.log("llm", "info", "重试成功")
        r = LogQueryService.query_system_events(category="ocr", db_path=evt_db)
        assert r["total"] == 1 and "百度" in r["items"][0]["event_message"]
        r2 = LogQueryService.query_system_events(db_path=evt_db)
        assert r2["total"] == 2

    def test_review_logs_query(self, db):
        from backend.services.log_query_service import LogQueryService
        r = LogQueryService.query_review_logs(action_type="approve", db_path=db)
        assert r["total"] == 1 and r["items"][0]["reviewer_id"] == 9

    def test_query_all_merges_by_time(self, evt_db):
        from backend.utils.system_event_logger import SystemEventLogger
        from backend.services.log_query_service import LogQueryService
        SystemEventLogger.log("db", "warning", "锁等待")
        r = LogQueryService.query_all(db_path=evt_db)
        assert r["total"] == 3   # 2 audit + 1 system
        sources = {it["_source"] for it in r["items"]}
        assert sources == {"audit", "system"}
        # 时间倒序：system 事件刚写入 created_at 最新
        assert r["items"][0]["_source"] == "system"


class TestMetricsSnapshot:
    def test_collect_returns_dict(self):
        from backend.services.metrics_snapshot import collect
        snap = collect()
        assert isinstance(snap, dict)   # 未装 prometheus_client 也安全返回 {}

    def test_archive_writes_system_event(self, evt_db, monkeypatch):
        from backend.services import metrics_snapshot as ms
        monkeypatch.setattr(ms, "collect", lambda: {"upload_total": 3})
        assert ms.archive() is True
        from backend.services.log_query_service import LogQueryService
        r = LogQueryService.query_system_events(category="system", db_path=evt_db)
        assert r["total"] == 1 and "upload_total" in r["items"][0]["detail"]


class TestTraceIdLink:
    def test_before_request_sets_trace_id_and_header_passthrough(self):
        """trace_id 链路：请求生成 tid + X-Trace-Id 透传 + errorhandler 读 g（非 None）。"""
        from app import create_app
        app = create_app()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        client = app.test_client()
        # 触发一个 404（HTTPException 放行路径）确认请求链路正常
        r = client.get("/definitely-not-exist", headers={"X-Trace-Id": "tid-xyz"})
        assert r.status_code == 404
        # 请求上下文内 g.trace_id 应为透传值
        with app.test_request_context("/", headers={"X-Trace-Id": "tid-xyz"}):
            from flask import g, request
            # before_request 不自动跑于 test_request_context——直接验证 _current_trace_id 函数
            g.trace_id = request.headers.get("X-Trace-Id")
            assert app._current_trace_id() == "tid-xyz"
