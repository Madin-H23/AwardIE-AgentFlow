"""阶段三批E回归：前端流式接入（源码断言）+ timeline 端点。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

def _require_real_db():
    """共享守卫（schemas.require_real_db）：文件存在且 users 表存在，否则 skip（R-028 升级）。"""
    from tests.fixtures.schemas import require_real_db
    require_real_db()



class TestFrontendStream:
    def test_eventsource_wired(self):
        """chat.html 必须：EventSource 消费 + 逐 delta 追加 + 失败回退同步。"""
        src = (PROJECT_ROOT / "app" / "templates" / "assistant" / "partials" / "_chat_scripts.html").read_text(encoding='utf-8')
        assert "new EventSource(" in src, "未接 EventSource"
        assert "sendStreamed" in src and "event: delta" not in src   # addEventListener('delta'...)
        assert "addEventListener('delta'" in src
        assert "resolve(false)" in src, "无失败回退同步路径"
        assert "▍" in src, "无打字机光标"

    def test_fallback_fetch_kept(self):
        """同步 fetch 路径保留（回退目标）。"""
        src = (PROJECT_ROOT / "app" / "templates" / "assistant" / "partials" / "_chat_scripts.html").read_text(encoding='utf-8')
        assert "fetch('/assistant/chat'" in src


class TestTimelineEndpoint:
    def test_requires_login(self):
        from config.flask import TestingConfig
        from app import create_app
        app = create_app(TestingConfig)
        app.config.update(SECRET_KEY="tl-key-0123456789abcdef0123456789a")
        c = app.test_client()
        r = c.get("/api/audit/timeline/award/1")
        assert r.status_code in (302, 401, 403)      # 未登录被拦

    def test_invalid_kind_rejected(self):
        from config.flask import TestingConfig
        from app import create_app
        app = create_app(TestingConfig)
        app.config.update(SECRET_KEY="tl-key-0123456789abcdef0123456789a")
        c = app.test_client()
        with c.session_transaction() as s:
            s.update(user_type='admin', user_id='admin', logged_in=True, role='admin')
        assert c.get("/api/audit/timeline/hack/1").status_code == 400

    def test_valid_kind_returns_timeline(self):
        _require_real_db()
        from config.flask import TestingConfig
        from app import create_app
        app = create_app(TestingConfig)
        app.config.update(SECRET_KEY="tl-key-0123456789abcdef0123456789a")
        c = app.test_client()
        with c.session_transaction() as s:
            s.update(user_type='admin', user_id='admin', logged_in=True, role='admin')
        r = c.get("/api/audit/timeline/award/1")
        assert r.status_code == 200
        data = r.get_json()
        assert data['success'] is True and isinstance(data['timeline'], list)
        if data['timeline']:
            item = data['timeline'][0]
            assert {'action', 'operator', 'operator_role', 'is_ai', 'created_at'} <= set(item)
