"""T23 + M1 回归测试：QA 真流式逐 token / max_tokens / 输入截断。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class FakeChunk:
    def __init__(self, text):
        self.content = text


class FakeLLM:
    """模拟 ChatOpenAI：stream 逐块吐 3 段。"""
    def __init__(self):
        self.streamed_with = None

    def stream(self, messages):
        self.streamed_with = messages
        for t in ("你好", "，这里是", "流式回答"):
            yield FakeChunk(t)

    def invoke(self, messages):
        return FakeChunk("降级完整")


class TestStreamAnswer:
    def _run(self, monkeypatch):
        from backend.agent import qa_agent as mod
        monkeypatch.setattr(mod, "retrieve",
                            lambda *a, **k: [type("D", (), {"metadata": {"name": "挑战杯", "level": "A", "category": "A"}})()])
        monkeypatch.setattr(mod, "format_context", lambda docs: "ctx")

        class FakeCL:
            def load_config(self):
                return {"rag": {}}
        chunks = list(mod.stream_answer(FakeCL(), None, FakeLLM(), "什么是挑战杯"))
        return chunks

    def test_yields_incremental_tokens_then_sources(self, monkeypatch):
        chunks = self._run(monkeypatch)
        texts = [c for c in chunks if isinstance(c, str)]
        tail = chunks[-1]
        assert texts == ["你好", "，这里是", "流式回答"]    # 真增量（3 段独立 yield）
        assert "__sources__" in tail and tail["__sources__"][0]["name"] == "挑战杯"

    def test_input_truncated(self, monkeypatch):
        from backend.agent import qa_agent as mod
        monkeypatch.setattr(mod, "retrieve", lambda *a, **k: [])
        monkeypatch.setattr(mod, "format_context", lambda d: "")
        llm = FakeLLM()

        class FakeCL:
            def load_config(self):
                return {"rag": {}}
        list(mod.stream_answer(FakeCL(), None, llm, "x" * 9000))
        user_msg = llm.streamed_with[1]["content"]
        assert len(user_msg) == 4000                        # M1 输入截断

    def test_stream_failure_falls_back_to_invoke(self, monkeypatch):
        from backend.agent import qa_agent as mod
        monkeypatch.setattr(mod, "retrieve", lambda *a, **k: [])
        monkeypatch.setattr(mod, "format_context", lambda d: "")

        class FailLLM:
            def stream(self, m):
                raise RuntimeError("stream not supported")
                yield  # pragma: no cover

            def invoke(self, m):
                return FakeChunk("降级完整")

        class FakeCL:
            def load_config(self):
                return {"rag": {}}
        chunks = list(mod.stream_answer(FakeCL(), None, FailLLM(), "q"))
        assert "降级完整" in chunks


class TestMaxTokens:
    def test_build_model_includes_max_tokens(self):
        from backend.agent.llm_adapter import build_chat_model
        import inspect
        src = inspect.getsource(build_chat_model)
        assert "max_tokens" in src
        assert "max_retries" in src and "timeout" in src     # 既有项不回退

    def test_chat_stream_qa_mode_multiple_deltas(self, monkeypatch):
        """chat_stream qa 模式：多个 delta 事件（真流式行为）。"""
        from config.flask import TestingConfig
        from app import create_app
        from app.routes import chat as chat_mod
        app = create_app(TestingConfig)
        app.config.update(SECRET_KEY="t23-key-0123456789abcdef012345678")

        # 打桩整个 qa 依赖链
        from backend.agent import qa_agent as qa_mod
        monkeypatch.setattr(chat_mod, "_ACTIVE_SSE", {})
        monkeypatch.setattr("backend.agent.llm_adapter.build_chat_model", lambda *a, **k: FakeLLM())
        monkeypatch.setattr("backend.rag.embeddings.build_embeddings", lambda cl: object())
        monkeypatch.setattr("backend.rag.vectorstore.build_vectorstore", lambda cl, e: object())

        def fake_stream(cl, vs, llm, q, **kw):
            for t in ("逐", "token", "输出"):
                yield t
            yield {"__sources__": []}
        monkeypatch.setattr(qa_mod, "stream_answer", fake_stream)

        c = app.test_client()
        with c.session_transaction() as s:
            s.update(user_type='student', user_id='7', logged_in=True)
        r = c.get("/assistant/chat/stream?message=hi&mode=qa")
        body = r.get_data(as_text=True)
        assert r.status_code == 200
        assert body.count("event: delta") >= 3              # 多个增量事件而非 1 个
        assert "event: done" in body
