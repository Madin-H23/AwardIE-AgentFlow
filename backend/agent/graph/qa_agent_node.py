"""
问答 Agent（图节点）

把 RAG 问答能力封装为 LangGraph 节点。
当用户任务是 qa（咨询竞赛规则）时，Supervisor 路由到此节点。

复用 backend/agent/qa_agent.py 的 answer_question 逻辑。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agent.state import AgentState

logger = logging.getLogger(__name__)


def make_qa_node(config_loader, vectorstore, llm):
    """
    构造问答 Agent 节点。

    Args:
        config_loader: ConfigLoader 实例
        vectorstore: RAG 向量库
        llm: LangChain ChatModel

    Returns:
        LangGraph 节点函数
    """
    from backend.agent.qa_agent import answer_question

    def qa_node(state: AgentState) -> Dict[str, Any]:
        # 从 messages 提取用户问题（最后一条 user 消息）
        messages = state.get("messages") or []
        question = _extract_user_question(messages)
        if not question:
            return {
                "steps": (state.get("steps") or []) + [{
                    "agent": "qa", "status": "skipped", "reason": "无问题",
                }],
            }

        # 未显式传入 vectorstore 时惰性构建（auto 模式等场景兜底）
        vs = vectorstore or _ensure_vectorstore(config_loader)
        if vs is None:
            logger.warning("[问答Agent] 向量库不可用，无法回答: %r", question)
            return {
                "qa_context": {"answer": "知识库暂不可用，请稍后再试。", "sources": []},
                "steps": (state.get("steps") or []) + [{
                    "agent": "qa", "status": "error", "error": "向量库不可用",
                }],
            }

        logger.info("[问答Agent] 回答: %r", question)
        result = answer_question(config_loader, vs, llm, question)
        return {
            "qa_context": {
                "answer": result["answer"],
                "sources": result["sources"],
            },
            "steps": (state.get("steps") or []) + [{
                "agent": "qa",
                "status": "done",
                "sources_count": len(result["sources"]),
            }],
        }

    return qa_node


def _ensure_vectorstore(config_loader):
    """惰性构建 RAG 向量库；失败返回 None，由调用方降级。"""
    from backend.rag.vectorstore import build_default_vectorstore
    return build_default_vectorstore(config_loader)


def _extract_user_question(messages) -> str:
    """从消息列表提取最后一条 user 消息的文本。"""
    for msg in reversed(messages):
        # LangChain BaseMessage 或 dict 两种形态
        role = getattr(msg, "type", None) or (msg.get("role") if isinstance(msg, dict) else None)
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
        # 兼容两种消息形态：dict 的 role="user"，LangChain BaseMessage 的 type="human"
        if role in ("user", "human") and content:
            return content
    return ""


__all__ = ["make_qa_node"]
