"""
Supervisor 主管 Agent

多智能体协作的"指挥中心"：根据用户意图和当前状态，决定下一个该路由到哪个 Agent。

路由策略（两种实现）：
1. 规则路由（默认，可靠）：基于 state.task_type 和消息内容做关键词路由
2. LLM 路由（进阶，智能）：用 LLM 理解意图后输出 next_agent

本实现采用【规则优先 + LLM 兜底】的混合策略：
- task_type 明确时直接路由（extract_and_review / qa / stats / export）
- task_type 缺失时用 LLM 理解消息意图
- 兜底走 FINISH

路由目标：extraction / review / qa / tools / FINISH
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from backend.agent.state import AgentState

logger = logging.getLogger(__name__)

# 路由目标常量
ROUTE_EXTRACTION = "extraction"
ROUTE_REVIEW = "review"
ROUTE_QA = "qa"
ROUTE_TOOLS = "tools"
ROUTE_FINISH = "FINISH"


def make_supervisor_node(config_loader, llm=None):
    """
    构造 Supervisor 节点。

    Args:
        config_loader: ConfigLoader 实例
        llm: LangChain ChatModel（可选，用于 LLM 意图理解兜底）

    Returns:
        (supervisor_node, route_function)
        - supervisor_node: 写 state.next_agent
        - route_function: 供 StateGraph 条件边调用，返回 state.next_agent
    """
    def supervisor_node(state: AgentState) -> Dict[str, Any]:
        task_type = state.get("task_type")
        next_agent = _decide_next(state, task_type, llm)

        logger.info("[Supervisor] 路由 -> %s (task_type=%s)", next_agent, task_type)
        return {
            "next_agent": next_agent,
            "steps": (state.get("steps") or []) + [{
                "agent": "supervisor",
                "decision": next_agent,
            }],
        }

    def route_function(state: AgentState) -> str:
        return state.get("next_agent", ROUTE_FINISH)

    return supervisor_node, route_function


def _decide_next(state: AgentState, task_type, llm) -> str:
    """决策下一个 Agent。"""
    # 已执行过的节点（从 steps 轨迹提取，避免无限循环）
    executed = {
        s.get("agent") for s in (state.get("steps") or [])
        if s.get("agent") not in (None, "supervisor")
    }

    # 已完成审核流程，结束
    if state.get("review_result") and task_type == "extract_and_review":
        return ROUTE_FINISH

    # 明确的任务类型路由
    if task_type == "extract_and_review":
        # 先抽取再审核
        if ROUTE_EXTRACTION not in executed and not state.get("extraction_result"):
            return ROUTE_EXTRACTION
        if ROUTE_REVIEW not in executed and not state.get("review_result"):
            return ROUTE_REVIEW
        return ROUTE_FINISH

    if task_type == "qa":
        # qa 执行过就结束（单轮问答）
        return ROUTE_QA if ROUTE_QA not in executed else ROUTE_FINISH

    # 数据操作类任务统一走 tools 节点（单 Agent 工具调用）
    if task_type in ("stats", "export", "query", "tools"):
        # tools 执行过就结束（单轮数据操作）
        return ROUTE_TOOLS if ROUTE_TOOLS not in executed else ROUTE_FINISH

    # auto 模式：用 LLM 理解用户意图后路由
    if task_type in ("auto", None) and llm is not None:
        try:
            target = _llm_route(state, llm)
            # auto 模式下，目标节点已执行过则结束
            if target in executed and target != ROUTE_FINISH:
                return ROUTE_FINISH
            return target
        except Exception as e:
            logger.warning("LLM 路由失败，兜底 FINISH: %s", e)

    # 最终兜底
    return ROUTE_FINISH


def _llm_route(state: AgentState, llm) -> str:
    """用 LLM 理解用户意图，输出路由目标。"""
    messages = state.get("messages") or []
    user_text = ""
    for msg in reversed(messages):
        role = getattr(msg, "type", None) or (msg.get("role") if isinstance(msg, dict) else None)
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
        # 兼容两种消息形态：dict 的 role="user"，LangChain BaseMessage 的 type="human"
        if role in ("user", "human") and content:
            user_text = content
            break

    if not user_text:
        return ROUTE_FINISH

    prompt = f"""判断用户意图属于以下哪个类别，只返回类别名（不要其他内容）：

类别：
- extraction：用户上传了证书文件，需要提取信息
- qa：用户询问竞赛规则、等级、白名单等知识性问题
- tools：用户要求查询奖状、统计、导出报表等数据操作
- FINISH：无法判断或闲聊

用户消息：{user_text}

类别："""
    response = llm.invoke([{"role": "user", "content": prompt}])
    text = response.content if hasattr(response, "content") else str(response)
    text = text.strip().strip("`").strip()
    # 归一化到合法路由
    mapping = {
        "extraction": ROUTE_EXTRACTION,
        "qa": ROUTE_QA,
        "tools": ROUTE_TOOLS,
        "finish": ROUTE_FINISH,
    }
    return mapping.get(text.lower(), ROUTE_FINISH)


__all__ = [
    "make_supervisor_node",
    "ROUTE_EXTRACTION",
    "ROUTE_REVIEW",
    "ROUTE_QA",
    "ROUTE_TOOLS",
    "ROUTE_FINISH",
]
