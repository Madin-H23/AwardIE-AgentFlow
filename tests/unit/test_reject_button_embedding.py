"""T1 UI + P2-21 回归测试：驳回按钮渲染 / Embedding 超时重试。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestRejectButton:
    def test_button_and_js_present(self):
        """审核页模板：驳回按钮 + rejectAward JS（含 teacher/admin 双 API 路由）。"""
        src = (PROJECT_ROOT / "app" / "templates" / "admin" / "file_import" / "results.html").read_text(encoding='utf-8')
        assert "驳回" in src and "rejectAward(" in src
        assert "api_achievement_review_reject" in src      # teacher API
        assert "admin_review.api_reject" in src            # admin API
        assert "请输入驳回原因" in src                     # 原因必填交互

    def test_reject_only_in_review_routes(self):
        """驳回按钮仅审核场景渲染（teacher_review/admin_review + submit 态）。"""
        src = (PROJECT_ROOT / "app" / "templates" / "admin" / "file_import" / "results.html").read_text(encoding='utf-8')
        assert "route_prefix in ('teacher_review', 'admin_review')" in src
        assert "current_item.status == 'submit'" in src


class TestEmbeddingRetry:
    def test_client_has_timeout(self):
        """P2-21：OpenAI 客户端必须带 timeout。"""
        src = (PROJECT_ROOT / "backend" / "rag" / "embeddings.py").read_text(encoding='utf-8')
        assert "timeout=30" in src

    def test_retry_decorator_present(self):
        src = (PROJECT_ROOT / "backend" / "rag" / "embeddings.py").read_text(encoding='utf-8')
        assert "@retry(" in src and "stop_after_attempt(3)" in src

    def test_embed_retries_then_raises(self, monkeypatch):
        """连续网络失败重试 3 次后抛错（不无限挂起）。"""
        from backend.rag.embeddings import SimpleOpenAIEmbeddings
        import requests

        calls = {"n": 0}

        def fake_create(*a, **kw):
            calls["n"] += 1
            raise requests.Timeout()

        emb = SimpleOpenAIEmbeddings(api_key="k", base_url="http://x", model="m")
        emb._client = type("C", (), {"embeddings": type("E", (), {"create": fake_create})()})()
        with pytest.raises(requests.Timeout):
            emb._embed(["hi"])
        assert calls["n"] == 3                        # 重试 3 次（1 初始 + 2 重试）

    def test_embed_success_on_retry(self, monkeypatch):
        """第 2 次成功则正常返回（重试自愈）。"""
        from backend.rag.embeddings import SimpleOpenAIEmbeddings
        import requests

        calls = {"n": 0}

        def fake_create(*a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise requests.ConnectionError()
            return type("R", (), {"data": [type("D", (), {"index": 0, "embedding": [0.1, 0.2]})()]})()

        emb = SimpleOpenAIEmbeddings(api_key="k", base_url="http://x", model="m")
        emb._client = type("C", (), {"embeddings": type("E", (), {"create": fake_create})()})()
        result = emb._embed(["hi"])
        assert result == [[0.1, 0.2]] and calls["n"] == 2
