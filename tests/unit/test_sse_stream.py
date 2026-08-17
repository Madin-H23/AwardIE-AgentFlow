"""P2-4 回归测试：SSE 流式端点（事件协议/连接限流/错误事件）。"""
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def client(monkeypatch):
    from config.flask import TestingConfig
    from app import create_app
    app = create_app(TestingConfig)
    app.config.update(SECRET_KEY="sse-test-key-0123456789abcdef")

    # 短路 _dispatch：返回固定结果（不触真实 Agent/LLM）
    from app.routes import chat as chat_mod
    def fake_dispatch(message, mode, user_context):
        return {"answer": "测试回答", "sources": [{"name": "挑战杯", "score": 0.9}],
                "steps": ["step1"], "mode_used": mode}
    monkeypatch.setattr(chat_mod, "_dispatch", fake_dispatch)
    monkeypatch.setattr(chat_mod, "_ACTIVE_SSE", {})   # 每用例干净计数
    return app.test_client()


def _events(resp_text: str):
    """解析 SSE 文本 -> [(event, data_dict)]。"""
    out = []
    for block in resp_text.split("\n\n"):
        ev = re.search(r"event: (\w+)", block)
        da = re.search(r"data: (\{.*\})", block, re.S)
        if ev and da:
            import json
            out.append((ev.group(1), json.loads(da.group(1))))
    return out


def _login(client):
    with client.session_transaction() as s:
        s.update(user_type='student', user_id='7', role='student', logged_in=True)


def test_sse_event_sequence(client):
    _login(client)
    r = client.get("/assistant/chat/stream?message=hi&mode=tools")   # tools 仍走 _dispatch 路径（qa 已切真流式，见 test_true_stream）
    assert r.status_code == 200
    assert r.mimetype == "text/event-stream"
    assert r.headers.get("Cache-Control") == "no-cache"
    events = _events(r.get_data(as_text=True))
    names = [e[0] for e in events]
    assert names[0] == "open" and names[-1] == "done"         # 协议首尾
    assert "source" in names and "delta" in names
    done = [e for e in events if e[0] == "done"][0][1]
    assert done["answer"] == "测试回答" and done["mode_used"] == "tools"


def test_empty_message_400(client):
    _login(client)
    assert client.get("/assistant/chat/stream?message=").status_code == 400


def test_concurrent_limit_429(client):
    """每用户同时 ≤2 连接：第 3 个返回 429。"""
    _login(client)
    from app.routes.chat import _ACTIVE_SSE
    _ACTIVE_SSE["student:7"] = 2
    assert client.get("/assistant/chat/stream?message=x").status_code == 429


def test_breaker_open_emits_error_event(client, monkeypatch):
    """LLM 熔断中：SSE 发 error 4003 事件而非调用。"""
    from backend.utils.circuit_breaker import CircuitBreaker
    b = CircuitBreaker.get("llm")
    b._state = "open"; b._opened_at = __import__("time").time()   # 强制 open
    try:
        _login(client)
        r = client.get("/assistant/chat/stream?message=x")
        events = _events(r.get_data(as_text=True))
        err = [e for e in events if e[0] == "error"][0][1]
        assert err["code"] == 4003
    finally:
        b._state = "closed"; b._fails = []


def test_stream_endpoint_registered():
    from app import create_app
    from config.flask import TestingConfig
    app = create_app(TestingConfig)
    rules = [str(r) for r in app.url_map.iter_rules()]
    assert any("/assistant/chat/stream" in r for r in rules)
