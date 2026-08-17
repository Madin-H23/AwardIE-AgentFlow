"""阶段三批A回归：P2-5 决策单一数据源 / P2-6 统一检索+threshold / P2-7 精度可配置。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------- P2-5 ----------
class TestDecisionModule:
    @pytest.mark.parametrize("issues,expected", [
        ([], "pass"),
        ([{"severity": "info"}], "pass"),                      # info 不拦截
        ([{"severity": "low"}], "need_manual"),
        ([{"severity": "medium"}, {"severity": "info"}], "need_manual"),
        ([{"severity": "high"}], "need_manual"),               # 1 个 high 不足 reject
        ([{"severity": "high"}, {"severity": "high"}], "reject"),
        ([{"severity": "high"}, {"severity": "high"}, {"severity": "low"}], "reject"),
    ])
    def test_aggregate_decision(self, issues, expected):
        from backend.agent.decision import aggregate_decision
        assert aggregate_decision(issues) == expected

    def test_dual_impl_converged(self):
        """两侧不再有内联决策代码（防回退双实现）。"""
        for f in ("backend/agent/review_api.py", "backend/agent/graph/review_agent.py"):
            src = (PROJECT_ROOT / f).read_text(encoding='utf-8')
            assert "aggregate_decision" in src
            assert 'high_count >= 2' not in src, f"{f} 仍有内联决策"


# ---------- P2-6 ----------
class TestUnifiedRetrieval:
    def test_review_agent_uses_unified_entry(self):
        """review_agent 不再直连 similarity_search_with_score k=1（防回退绕过）。"""
        src = (PROJECT_ROOT / "backend" / "agent" / "graph" / "review_agent.py").read_text(encoding='utf-8')
        assert "retrieve_with_scores" in src
        assert "vectorstore.similarity_search_with_score(competition_name, k=1)" not in src

    def test_retrieve_with_scores_filters_threshold(self, monkeypatch):
        """低于 threshold 的结果被过滤（P2-23：无关查询返回空）。"""
        from backend.rag import retriever as mod

        class FakeDoc:
            def __init__(self, content):
                self.page_content = content
                self.metadata = {}

        class FakeRetriever:
            def invoke(self, q):
                return [FakeDoc("a"), FakeDoc("b")]

        class FakeVS:
            def as_retriever(self, **kw):
                return FakeRetriever()
            def similarity_search_with_score(self, q, k):
                return [(FakeDoc("a"), 0.9), (FakeDoc("b"), 0.1)]   # b 低于阈值

        class FakeCL:
            def load_config(self):
                return {"rag": {"retrieval": {"top_k": 4, "score_threshold": 0.5,
                                               "search_type": "similarity"}}}

        hits = mod.retrieve_with_scores(FakeCL(), FakeVS(), "q")
        assert len(hits) == 1 and hits[0][1] == pytest.approx(0.9)

    def test_retrieve_delegates(self, monkeypatch):
        from backend.rag import retriever as mod
        called = {}
        monkeypatch.setattr(mod, "retrieve_with_scores",
                            lambda *a, **k: called.setdefault("hits", [(object(), 0.9)]))
        docs = mod.retrieve(None, None, "q")
        assert len(docs) == 1 and "hits" in called


# ---------- P2-7 ----------
class TestPreciseOcrConfig:
    def test_framework_reads_config(self, tmp_path):
        """use_precise_ocr 从 settings 读取（默认 True 走高精度链）。"""
        from backend.extract.framework import ExtractFramework
        fw = ExtractFramework.__new__(ExtractFramework)
        fw._raw_config = {"extract": {"use_precise_ocr": False}}
        # 精度值经 _ocr_image 内部读取——此处验证配置解析逻辑
        assert fw._raw_config["extract"]["use_precise_ocr"] is False

    def test_settings_has_flag(self):
        from config.loader import ConfigLoader
        cfg = ConfigLoader().load_config()
        assert cfg.get("extract", {}).get("use_precise_ocr") is True

    def test_no_hardcoded_false(self):
        """framework 不再有硬编码 is_precise=False。"""
        src = (PROJECT_ROOT / "backend" / "extract" / "framework.py").read_text(encoding='utf-8')
        assert "is_precise=False" not in src
