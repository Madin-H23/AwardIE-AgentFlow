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

        logger.info("[问答Agent] 回答: %r", question)
        result = answer_question(config_loader, vectorstore, llm, question)
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


def _extract_user_question(messages) -> str:
    """从消息列表提取最后一条 user 消息的文本。"""
    for msg in reversed(messages):
        # LangChain BaseMessage 或 dict 两种形态
        role = getattr(msg, "type", None) or (msg.get("role") if isinstance(msg, dict) else None)
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
        if role == "user" and content:
            return content
    return ""


__all__ = ["make_qa_node"]
