"""阶段六 L4：admin_log 蓝图路由测试（权限 + 各 API 形状 + SSE）。"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.schemas import USERS_DDL


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """应用 + 临时库（users/admin 种子 + 三源日志表）+ engine 注入。"""
    db = tmp_path / "l4.db"
    conn = sqlite3.connect(str(db))
    conn.execute(USERS_DDL)
    conn.execute("INSERT INTO users (id, login_code, name, role, user_activated) "
                 "VALUES (5, 'admin', '管理员', 'admin', 1)")
    conn.execute("""CREATE TABLE achievement_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, achievement_id INTEGER, achievement_kind TEXT,
        trace_id VARCHAR(64), action_type INTEGER, action_result INTEGER,
        operator_id INTEGER, operator_code VARCHAR(50), operator_name VARCHAR(50),
        operator_role INTEGER, ai_batch_id VARCHAR(50), change_detail TEXT, remark TEXT,
        created_at TEXT, is_redundant INTEGER NOT NULL DEFAULT 0, is_test INTEGER NOT NULL DEFAULT 0)""")
    conn.execute("""CREATE TABLE review_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, pending_id INTEGER, achievement_type TEXT,
        file_hash TEXT, file_path TEXT, submitter_type TEXT, submitter_id INTEGER,
        reviewer_type TEXT, reviewer_id INTEGER, action_type TEXT, result_type TEXT,
        result_id INTEGER, result_file_path TEXT, review_comment TEXT, operation_note TEXT,
        created_at TEXT)""")
    conn.execute("""CREATE TABLE pending_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, achievement_type TEXT, achievement_data TEXT,
        status TEXT, submit_time TEXT, submitter_type TEXT, submitter_id INTEGER)""")
    conn.execute("INSERT INTO achievement_audit_log (achievement_id, action_type, operator_code, created_at) "
                 "VALUES (1, 6, 'admin', '2026-01-01 10:00:00')")
    conn.commit()
    conn.close()

    from backend.utils.system_event_logger import SystemEventLogger
    from backend.services.log_analyzer import LogAnalyzer
    from backend.services.log_query_service import LogQueryService
    monkeypatch.setattr(SystemEventLogger, "_db_path", str(db))
    monkeypatch.setattr(LogAnalyzer, "_db_path", str(db))
    monkeypatch.setattr(LogQueryService, "_db_path", str(db))

    import backend.orm.base as b
    b.reset_engine()
    b._engine = b.build_engine(str(db))
    b._SessionLocal = None

    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    yield app
    if b._engine is not None:
        b._engine.dispose()
    b.reset_engine()


def _admin_client(app):
    client = app.test_client()
    with client.session_transaction() as s:
        s['user_id'] = 'admin'
        s['role'] = 'admin'
        s['user_type'] = 'admin'
    return client


def _student_client(app):
    client = app.test_client()
    with client.session_transaction() as s:
        s['user_id'] = '212306413'
        s['role'] = 'student'
        s['user_type'] = 'student'
    return client


class TestAuth:
    def test_anonymous_rejected(self, app):
        r = app.test_client().get('/admin/api/logs/audit')
        assert r.status_code == 401

    def test_student_forbidden(self, app):
        r = _student_client(app).get('/admin/api/logs/audit')
        assert r.status_code == 403

    def test_admin_ok(self, app):
        r = _admin_client(app).get('/admin/api/logs/audit')
        assert r.status_code == 200
        body = r.get_json()
        assert body["code"] == 0 and body["data"]["total"] == 1


class TestQueryAPIs:
    def test_audit_shape(self, app):
        r = _admin_client(app).get('/admin/api/logs/audit?action_type=6')
        d = r.get_json()["data"]
        assert d["total"] == 1 and d["items"][0]["operator_code"] == "admin"

    def test_system_contains_startup_event(self, app):
        """create_app 启动事件（system info）应已在测试库。"""
        r = _admin_client(app).get('/admin/api/logs/system')
        d = r.get_json()["data"]
        assert d["total"] >= 1
        assert any("应用启动" in (it.get("event_message") or "") for it in d["items"])

    def test_review_ok(self, app):
        r = _admin_client(app).get('/admin/api/logs/review')
        assert r.get_json()["data"]["total"] == 0

    def test_app_tail_ok(self, app):
        r = _admin_client(app).get('/admin/api/logs/app/tail?lines=10')
        assert r.status_code == 200   # 真实 app.log 可能无——形状不断言内容


class TestAnalysisAPIs:
    def test_actions_and_bottleneck(self, app):
        c = _admin_client(app)
        # JSON 序列化后 action_type 键为字符串
        assert c.get('/admin/api/logs/analysis/actions').get_json()["data"] == {"6": 1}
        b = c.get('/admin/api/logs/analysis/bottleneck').get_json()["data"]
        assert {"pending_total", "over_48h", "avg_wait_hours", "max_wait_hours"} <= set(b)

    def test_errors_activity_ai_health(self, app):
        c = _admin_client(app)
        for url in ('/admin/api/logs/analysis/errors', '/admin/api/logs/analysis/activity',
                    '/admin/api/logs/analysis/ai-health', '/admin/api/logs/metrics',
                    '/admin/api/logs/daily-report'):
            assert c.get(url).status_code == 200, url


class TestAlertsAndPlan:
    def test_alerts_ok(self, app):
        r = _admin_client(app).get('/admin/api/logs/alerts')
        assert r.get_json()["data"]["total"] >= 0   # 无触发时 0

    def test_plan_endpoints_ok(self, app):
        c = _admin_client(app)
        assert c.get('/admin/api/logs/plan').get_json()["data"]["total"] >= 0
        # 不存在的计划项：友好 message 而非 500
        r = c.post('/admin/api/logs/plan/P-XXX-0/acknowledge')
        assert r.status_code == 200 and "不存在" in r.get_json()["message"]


class TestSSE:
    def test_stream_mimetype_and_open_event(self, app):
        r = _admin_client(app).get('/admin/api/logs/stream?source=system')
        assert r.status_code == 200
        assert r.mimetype == "text/event-stream"

    def test_stream_concurrency_limit(self, app):
        """同一管理员并发 >2 返回 429。"""
        from app.routes.admin_log import _SSE_CONN
        c = _admin_client(app)
        _SSE_CONN["admin"] = 2
        try:
            r = c.get('/admin/api/logs/stream')
            assert r.status_code == 429
        finally:
            _SSE_CONN.pop("admin", None)
