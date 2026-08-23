"""阶段三批H回归：auto 模式 progress 流（run_stream + 端点 + 前端消费）。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestRunStream:
    def test_run_stream_exists(self):
        from backend.agent.graph.workflow import MultiAgentWorkflow
        assert hasattr(MultiAgentWorkflow, "run_stream")

    def test_stream_yields_nodes_then_final(self):
        """节点事件序列 + __final__ 兜底（FakeGraph）。"""
        from backend.agent.graph.workflow import MultiAgentWorkflow

        class FakeGraph:
            invoked = False
            def stream(self, state, config=None, stream_mode=None):
                # T49 新契约：三通道 (mode, payload)
                assert set(stream_mode) == {"updates", "messages", "values"}
                yield ("updates", {"supervisor": {}})
                yield ("updates", {"qa": {}})
                yield ("values", {"qa_context": {"answer": "最终回答", "sources": []},
                                  "steps": []})
            def invoke(self, state, config=None):
                FakeGraph.invoked = True
                return {}

        wf = MultiAgentWorkflow.__new__(MultiAgentWorkflow)
        wf.graph = FakeGraph()
        events = list(wf.run_stream(task_type="auto", message="hi"))
        assert not FakeGraph.invoked, "T49 双跑应消灭：values 终态足够，无需 invoke"
        assert {"node": "supervisor"} in events and {"node": "qa"} in events
        assert "__final__" in events[-1]
        assert events[-1]["__final__"]["qa_context"]["answer"] == "最终回答"

    def test_stream_failure_still_yields_final(self):
        """stream 抛异常时 invoke 兜底仍出结果。"""
        from backend.agent.graph.workflow import MultiAgentWorkflow

        class BadGraph:
            def stream(self, *a, **k):
                raise RuntimeError("stream unsupported")
                yield {}
            def invoke(self, state, config=None):
                return {"qa_context": {"answer": "兜底回答"}}

        wf = MultiAgentWorkflow.__new__(MultiAgentWorkflow)
        wf.graph = BadGraph()
        events = list(wf.run_stream(task_type="auto", message="hi"))
        assert events and "__final__" in events[-1]
        assert events[-1]["__final__"]["qa_context"]["answer"] == "兜底回答"


class TestEndpointAndFrontend:
    def test_chat_stream_has_progress_branch(self):
        src = (PROJECT_ROOT / "app" / "routes" / "chat.py").read_text(encoding='utf-8')
        assert "run_stream" in src and "progress" in src
        assert "NODE_LABELS" in src                       # 节点中文化
        assert "回退 _dispatch" in src                    # 失败回退

    def test_frontend_consumes_progress(self):
        src = (PROJECT_ROOT / "app" / "templates" / "assistant" / "partials" / "_chat_scripts.html").read_text(encoding='utf-8')
        assert "addEventListener('progress'" in src
        assert "spinner-border" in src                    # 阶段提示 spinner

    def test_progress_event_via_test_client(self, monkeypatch):
        """端到端：auto 模式 SSE 流含 progress 事件（打桩 run_stream）。"""
        from config.flask import TestingConfig
        from app import create_app
        from app.routes import chat as chat_mod
        from backend.agent.graph import workflow as wf_mod
        app = create_app(TestingConfig)
        app.config.update(SECRET_KEY="pr-key-0123456789abcdef0123456789")

        class FakeWF:
            def run_stream(self, **kw):
                yield {"node": "extraction"}
                yield {"node": "review"}
                yield {"__final__": {"qa_context": {"answer": "A", "sources": []},
                                     "steps": [], "review_result": None, "extraction_result": None}}

        monkeypatch.setattr(wf_mod.MultiAgentWorkflow, "get_default",
                            staticmethod(lambda cl: FakeWF()))
        monkeypatch.setattr(chat_mod, "_ACTIVE_SSE", {})
        c = app.test_client()
        with c.session_transaction() as s:
            s.update(user_type='student', user_id='7', logged_in=True)
        body = c.get("/assistant/chat/stream?message=hi&mode=auto").get_data(as_text=True)
        assert "event: progress" in body
        assert "AI 抽取中" in body and "AI 审核中" in body
        assert "event: done" in body
