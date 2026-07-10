"""
RAG integration 测试

验证 RAG 知识库的端到端检索与问答（需真实 API + 已入库向量库）。
固化了联调中验证的成果：检索质量、问答准确性。

运行：RUN_AGENT_INTEGRATION=1 python -m pytest tests/integration/agent/test_rag_integration.py -v
"""
import pytest
from tests.integration.agent.conftest import skip_if_no_integration

pytestmark = [skip_if_no_integration]


class TestRAGRetrieval:
    """RAG 检索质量"""

    def test_retrieve_lanqiao_cup(self, config_loader, vectorstore):
        """检索'蓝桥杯'应命中蓝桥杯相关竞赛"""
        from backend.rag.retriever import retrieve
        docs = retrieve(config_loader, vectorstore, "蓝桥杯是什么级别")
        assert len(docs) > 0
        # 至少有一条含"蓝桥杯"
        names = [d.metadata.get("name", "") for d in docs]
        assert any("蓝桥杯" in n for n in names), f"未命中蓝桥杯: {names}"

    def test_retrieve_challenge_cup(self, config_loader, vectorstore):
        """检索'挑战杯'应命中挑战杯（验证 bge-m3 检索正确性）"""
        from backend.rag.retriever import retrieve
        docs = retrieve(config_loader, vectorstore, "挑战杯竞赛")
        names = [d.metadata.get("name", "") for d in docs]
        assert any("挑战杯" in n for n in names), f"未命中挑战杯: {names}"


class TestRAGQA:
    """RAG 端到端问答"""

    def test_qa_lanqiao_category(self, config_loader, vectorstore):
        """问蓝桥杯级别，应回答 A 类"""
        from backend.agent.llm_adapter import build_chat_model
        from backend.agent.qa_agent import answer_question
        llm = build_chat_model(config_loader, "deepseek")
        result = answer_question(config_loader, vectorstore, llm, "蓝桥杯是什么级别的竞赛？")
        answer = result["answer"]
        # 回答应包含 A 类相关信息
        assert "A" in answer or "a类" in answer.lower(), f"回答未提及A类: {answer[:100]}"
        assert len(result["sources"]) > 0

    def test_qa_math_modeling(self, config_loader, vectorstore):
        """问数学建模，应列出多个数模竞赛"""
        from backend.agent.llm_adapter import build_chat_model
        from backend.agent.qa_agent import answer_question
        llm = build_chat_model(config_loader, "deepseek")
        result = answer_question(config_loader, vectorstore, llm, "有哪些数学建模竞赛？")
        answer = result["answer"]
        assert "建模" in answer or "数模" in answer
