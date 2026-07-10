"""
Stage 1 单元测试：RAG 模块纯逻辑

覆盖不依赖 chroma/langchain 真实安装的部分：
- indexer._parse_competition_docx: docx 表格解析（用真实数据文件）
- indexer._entries_to_documents: 条目转 Document（需 langchain_core，用 stub）
- retriever.format_context: 上下文格式化
- retriever.resolve_retrieval_config / embeddings.resolve_embedding_config: 配置解析
"""
import pytest
from pathlib import Path

from config.loader import ConfigLoader


# ==================== docx 解析 ====================

@pytest.fixture
def config_loader():
    return ConfigLoader()


@pytest.fixture
def competition_docx_path(config_loader):
    """从配置读取真实的竞赛等级分类表路径。"""
    config = config_loader.load_config()
    rel = config["rag"]["knowledge_sources"]["competition_levels_doc"]
    p = (config_loader.project_root / rel).resolve()
    if not p.exists():
        pytest.skip(f"竞赛等级分类表不存在: {p}")
    return str(p)


class TestParseCompetitionDocx:
    """解析竞赛等级分类表 docx"""

    def test_parse_returns_entries(self, competition_docx_path):
        from backend.rag.indexer import _parse_competition_docx
        entries = _parse_competition_docx(competition_docx_path)
        # 真实文件应有 100+ 条竞赛
        assert len(entries) > 50, f"竞赛条目过少: {len(entries)}"

    def test_entry_has_required_fields(self, competition_docx_path):
        from backend.rag.indexer import _parse_competition_docx
        entries = _parse_competition_docx(competition_docx_path)
        e = entries[0]
        assert "name" in e
        assert "level" in e
        assert "category" in e
        assert e["name"], "竞赛名称不应为空"

    def test_known_competition_present(self, competition_docx_path):
        """应包含'挑战杯'等知名赛事"""
        from backend.rag.indexer import _parse_competition_docx
        entries = _parse_competition_docx(competition_docx_path)
        names = [e["name"] for e in entries]
        joined = "".join(names)
        # 至少应包含挑战杯或创新大赛之一
        assert "挑战杯" in joined or "创新大赛" in joined, "未找到知名赛事"

    def test_categories_are_valid(self, competition_docx_path):
        """类别应是 A/B/C 之一"""
        from backend.rag.indexer import _parse_competition_docx
        entries = _parse_competition_docx(competition_docx_path)
        valid_cats = {"A", "B", "C", "A类", "B类", "C类", ""}
        for e in entries:
            # 类别字段可能含"类"字，做宽松校验
            cat = e["category"].replace("类", "").strip()
            assert cat in {"A", "B", "C", ""}, f"异常类别: {e['category']} (竞赛: {e['name']})"


# ==================== 配置解析 ====================

class TestRAGConfig:
    """RAG 配置节点解析"""

    def test_embedding_config_zhipu(self, config_loader):
        from backend.rag.embeddings import resolve_embedding_config
        import os
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("ZHIPUAI_API_KEY", "fake-key")
            name, cfg = resolve_embedding_config(config_loader, "zhipu")
            assert name == "zhipu"
            # /embeddings 后缀应被剥离
            assert cfg["base_url"] == "https://open.bigmodel.cn/api/paas/v4"
            assert cfg["model"] == "embedding-3"
            assert cfg["dimensions"] == 1024

    def test_vectorstore_config(self, config_loader):
        from backend.rag.vectorstore import resolve_vectorstore_config
        vs = resolve_vectorstore_config(config_loader)
        assert Path(vs["persist_path"]).is_absolute()
        assert vs["default_collection"] == "competition_rules"
        assert "competition_rules" in vs["collections"]

    def test_retrieval_config_defaults(self, config_loader):
        from backend.rag.retriever import resolve_retrieval_config
        rc = resolve_retrieval_config(config_loader)
        assert rc["search_type"] == "mmr"
        assert rc["top_k"] == 4
        assert 0 < rc["mmr_lambda"] <= 1


# ==================== format_context ====================

class TestFormatContext:
    """上下文格式化"""

    def test_empty_docs(self):
        from backend.rag.retriever import format_context
        assert "未检索到" in format_context([])

    def test_format_with_docs(self):
        from backend.rag.retriever import format_context

        class FakeDoc:
            def __init__(self, content, name):
                self.page_content = content
                self.metadata = {"name": name}

        docs = [
            FakeDoc("竞赛名称：挑战杯。级别：国家级。", "挑战杯"),
            FakeDoc("竞赛名称：数模。级别：省级。", "数模"),
        ]
        result = format_context(docs)
        assert "[1]" in result
        assert "[2]" in result
        assert "挑战杯" in result
        assert "数模" in result
