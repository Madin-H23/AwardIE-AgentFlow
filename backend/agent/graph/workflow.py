"""
多智能体工作流（LangGraph StateGraph 编排）

把 Supervisor + 抽取/审核/问答 Agent + 单 Agent 工具 装配为一张可执行的图。

图结构：
                         ┌──→ extraction ──→ review ──┐
    START → supervisor ──┼──→ qa ──────────────────────┼──→ supervisor → END
                         └──→ tools (单Agent) ─────────┘

特点：
1. Supervisor 模式：统一入口路由
2. 共享 State：Agent 间通过 AgentState 传递抽取/审核结果
3. 条件边：Supervisor 根据状态动态决定下一个节点
4. Checkpoint：支持断点续跑（长任务友好）

这是岗位 JD 第 2 条（多智能体框架设计与开发）的核心落地。
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from backend.agent.state import AgentState
from backend.agent.llm_adapter import build_chat_model
from backend.agent.tools.context import ToolContext
from backend.agent.graph.supervisor import (
    make_supervisor_node,
    ROUTE_EXTRACTION,
    ROUTE_REVIEW,
    ROUTE_QA,
    ROUTE_TOOLS,
    ROUTE_FINISH,
)
from backend.agent.graph.extraction_agent import make_extraction_node
from backend.agent.graph.review_agent import make_review_node
from backend.agent.graph.qa_agent_node import make_qa_node

logger = logging.getLogger(__name__)


class MultiAgentWorkflow:
    """
    多智能体工作流。

    用法：
        wf = MultiAgentWorkflow.from_config(get_config())
        result = wf.run(task_type="extract_and_review", file_path="/path/to/award.jpg")
        result = wf.run(task_type="qa", message="挑战杯是几类竞赛？")
    """

    def __init__(self, graph, config_loader, tool_context, compiled=True):
        self.graph = graph
        self.config_loader = config_loader
        self.tool_context = tool_context

    @classmethod
    def from_config(
        cls,
        config_loader,
        *,
        vectorstore=None,
        llm_provider: Optional[str] = None,
        enable_checkpoint: bool = False,
    ) -> "MultiAgentWorkflow":
        """
        从配置装配完整工作流。

        Args:
            config_loader: ConfigLoader 实例
            vectorstore: RAG 向量库（None 时审核 Agent 跳过交叉校验）
            llm_provider: LLM Provider
            enable_checkpoint: 是否启用 checkpoint（断点续跑）

        Returns:
            MultiAgentWorkflow 实例
        """
        from langgraph.graph import StateGraph, START, END

        config = config_loader.load_config()
        agent_cfg = config.get("agent", {})
        if llm_provider is None:
            llm_provider = agent_cfg.get("default_llm_provider", "deepseek")

        # 构造共享 LLM
        llm = build_chat_model(config_loader, llm_provider)

        # 构造 ToolContext（惰性：framework 只在真正抽取时才初始化 OCR）
        tool_context = ToolContext(config_loader)

        # 构造各节点
        supervisor_node, route_fn = make_supervisor_node(config_loader, llm)
        # 传 ToolContext 而非已构造的 framework，避免工作流构造时初始化 OCR 引擎
        extraction_node = make_extraction_node(tool_context)
        review_node = make_review_node(config_loader, vectorstore)
        qa_node = make_qa_node(config_loader, vectorstore, llm)
        tools_node = _make_tools_node(config_loader, llm)

        # 装配图
        builder = StateGraph(AgentState)
        builder.add_node("supervisor", supervisor_node)
        builder.add_node(ROUTE_EXTRACTION, extraction_node)
        builder.add_node(ROUTE_REVIEW, review_node)
        builder.add_node(ROUTE_QA, qa_node)
        builder.add_node(ROUTE_TOOLS, tools_node)

        builder.add_edge(START, "supervisor")

        # Supervisor 条件路由
        builder.add_conditional_edges(
            "supervisor",
            route_fn,
            {
                ROUTE_EXTRACTION: ROUTE_EXTRACTION,
                ROUTE_REVIEW: ROUTE_REVIEW,
                ROUTE_QA: ROUTE_QA,
                ROUTE_TOOLS: ROUTE_TOOLS,
                ROUTE_FINISH: END,
            },
        )

        # 各执行节点执行完后回到 Supervisor（循环直到 FINISH）
        for node in [ROUTE_EXTRACTION, ROUTE_REVIEW, ROUTE_QA, ROUTE_TOOLS]:
            builder.add_edge(node, "supervisor")

        # 编译（可选 checkpoint）
        checkpointer = None
        if enable_checkpoint:
            try:
                from langgraph.checkpoint.memory import MemorySaver
                checkpointer = MemorySaver()
                logger.info("已启用 LangGraph checkpoint（断点续跑）")
            except ImportError:
                logger.warning("langgraph-checkpoint 未安装，跳过 checkpoint")

        compiled_graph = builder.compile(checkpointer=checkpointer)
        logger.info("多智能体工作流编译完成")
        return cls(compiled_graph, config_loader, tool_context)

    def run(
        self,
        *,
        task_type: str = "qa",
        message: Optional[str] = None,
        file_path: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行工作流。

        Args:
            task_type: 任务类型（extract_and_review / qa / stats / export / query）
            message: 用户消息（qa/tools 类任务）
            file_path: 文件路径（extract_and_review 类任务）
            user_context: 用户上下文
            thread_id: 会话 ID（启用 checkpoint 时用于多轮记忆）

        Returns:
            最终 state，含 extraction_result / review_result / qa_context / steps
        """
        from langchain_core.messages import HumanMessage

        initial_state: Dict[str, Any] = {
            "task_type": task_type,
            "file_path": file_path or "",
            "user_context": user_context or {},
            "steps": [],
        }
        if message:
            initial_state["messages"] = [HumanMessage(content=message)]

        run_config = {"recursion_limit": 50}  # 安全上限，防止路由异常导致死循环
        if thread_id:
            run_config["configurable"] = {"thread_id": thread_id}

        logger.info("工作流启动: task_type=%s", task_type)
        final_state = self.graph.invoke(initial_state, config=run_config)
        return final_state

    def run_stream(self, *, task_type: str = "qa", message: Optional[str] = None,
                   file_path: Optional[str] = None,
                   user_context: Optional[Dict[str, Any]] = None,
                   thread_id: Optional[str] = None):
        """流式执行（T23 auto 模式）：逐节点 yield 进度，最终 yield 完整 state。

        yield：{"node": "supervisor"} / {"node": "extraction"} / ... / {"__final__": state}
        节点级进度——多智能体场景用户要看"AI 正在抽取/审核"的过程；
        诚实标注：LangGraph updates 模式不回传最终态，末尾补一次 invoke 取全量结果
        （单机课程项目双跑成本可接受；生产可改 values 模式或状态累积）。
        """
        from langchain_core.messages import HumanMessage

        initial_state: Dict[str, Any] = {
            "task_type": task_type,
            "file_path": file_path or "",
            "user_context": user_context or {},
            "steps": [],
        }
        if message:
            initial_state["messages"] = [HumanMessage(content=message)]

        run_config = {"recursion_limit": 50}
        if thread_id:
            run_config["configurable"] = {"thread_id": thread_id}

        try:
            for chunk in self.graph.stream(initial_state, config=run_config,
                                           stream_mode="updates"):
                for node_name in chunk:
                    yield {"node": node_name}
        except Exception as e:
            logger.warning("stream 执行异常（进度事件中断，结果走 invoke 兜底）: %s", e)

        final_state = self.graph.invoke(initial_state, config=run_config)
        yield {"__final__": final_state}


    @classmethod
    def get_default(cls, config_loader) -> "MultiAgentWorkflow":
        """进程级单例（P1-5/设计 AI 层 §3 WorkflowRegistry）。

        编译 StateGraph + 装配工具代价高（~300ms+），每次请求重建是性能痛点；
        双检锁保证并发下只编译一次。仅缓存默认参数（无自定义 vectorstore/llm_provider/
        checkpoint）的实例；自定义参数路径仍走 from_config 新建（罕见调用）。
        配置热更新：管理端改配置后调用 cls.reset_default() 失效重建。
        """
        if cls._default is None:
            with cls._default_lock:
                if cls._default is None:
                    cls._default = cls.from_config(config_loader)
        return cls._default

    @classmethod
    def reset_default(cls) -> None:
        """配置变更后失效单例（管理页改 LLM/RAG 配置时调用）。"""
        cls._default = None


def _make_tools_node(config_loader, llm):
    """
    构造"工具"节点：复用单 Agent 的 Function Calling 能力。

    在多智能体图中，tools 节点封装 AgentService 的工具调用逻辑，
    实现"查询/统计/导出"等数据操作。
    """
    def tools_node(state: AgentState) -> Dict[str, Any]:
        from backend.agent.service import AgentService

        # 提取用户消息
        messages = state.get("messages") or []
        user_text = _extract_last_user_message(messages)

        if not user_text:
            return {"steps": (state.get("steps") or []) + [{"agent": "tools", "status": "skipped"}]}

        try:
            service = AgentService.from_config(config_loader)
            result = service.chat(user_text, user_context=state.get("user_context"))
            return {
                "qa_context": {"answer": result["output"], "sources": []},
                "steps": (state.get("steps") or []) + [{
                    "agent": "tools",
                    "status": "done",
                    "tool_steps": result["intermediate_steps"],
                }],
            }
        except Exception as e:
            logger.exception("tools 节点失败: %s", e)
            return {
                "steps": (state.get("steps") or []) + [{"agent": "tools", "status": "error", "error": str(e)}],
            }

    return tools_node


def _extract_last_user_message(messages) -> str:
    """
    从消息列表提取最后一条用户消息的文本。

    兼容三种形态：
    - LangChain HumanMessage（type="human"）
    - dict {"role": "user", "content": ...}
    - 旧式 role="user" 的 BaseMessage
    """
    for msg in reversed(messages or []):
        role = getattr(msg, "type", None) or getattr(msg, "role", None)
        if isinstance(msg, dict):
            role = msg.get("role")
        content = getattr(msg, "content", None)
        if isinstance(msg, dict):
            content = msg.get("content")
        # human (LangChain) 或 user (OpenAI 格式) 都算用户消息
        if role in ("human", "user") and content:
            return content
    return ""




__all__ = ["MultiAgentWorkflow"]
MultiAgentWorkflow._default = None
MultiAgentWorkflow._default_lock = threading.Lock()
