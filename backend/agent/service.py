"""
AgentService —— 对外统一入口

组装 LLM + 工具 + Agent Executor，提供单 Agent 的 Function Calling 能力。

职责：
1. 构造 LangChain ChatModel（复用 config 多 Provider）
2. 收集所有工具（查询/统计/抽取/导出）
3. 用 create_tool_calling_agent 组装可对话的 Agent
4. 注册 ExtractFramework 的业务抽取器（award/patent/software/innovation）
5. 对外暴露 .chat(query) 方法

这是岗位 JD 第 2 条（AI Agent + Function Calling）的完整落地。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agent.llm_adapter import build_chat_model
from backend.agent.tools.context import ToolContext

logger = logging.getLogger(__name__)


# Agent 的系统提示词：定义角色、能力边界、回答规范
AGENT_SYSTEM_PROMPT = """你是"竞赛与奖状管理智能助手"，服务于福州大学至诚学院的师生成果管理系统。

你可以通过调用工具来帮助用户完成以下任务：
1. 查询奖状记录（按教师/学生/年份/级别筛选）
2. 匹配和查询竞赛信息（等级、白名单状态）
3. 统计分析（竞赛贡献度排名、获奖趋势、热力图）
4. 智能抽取（从上传的证书文件中提取结构化信息）
5. 导出年度成果汇总报表

工作原则：
- 优先调用工具获取真实数据，不要凭空编造
- 对于查询，明确说明筛选条件和结果数量
- 如果用户意图不明确，先询问澄清
- 涉及具体数据时，引用工具返回的真实数字

当前用户上下文：{user_context}
"""


class AgentService:
    """
    单 Agent 服务（Function Calling）。

    用法：
        service = AgentService.from_config(get_config())
        result = service.chat("张老师2024年指导了多少奖状？")
    """

    def __init__(
        self,
        llm,
        tools: List,
        tool_context: ToolContext,
        agent_executor=None,
        max_iterations: int = 10,
        verbose: bool = False,
    ):
        self.llm = llm
        self.tools = tools
        self.tool_context = tool_context
        self._agent_executor = agent_executor
        self.max_iterations = max_iterations
        self.verbose = verbose

    @classmethod
    def from_config(cls, config_loader, *, llm_provider: Optional[str] = None) -> "AgentService":
        """
        从配置构造完整的 AgentService。

        Args:
            config_loader: ConfigLoader 实例
            llm_provider: 指定 LLM Provider；None 用 agent.default_llm_provider

        Returns:
            AgentService 实例
        """
        # 1. 解析 Agent 配置
        config = config_loader.load_config()
        agent_cfg = config.get("agent", {})
        if llm_provider is None:
            llm_provider = agent_cfg.get("default_llm_provider", "deepseek")
        max_iterations = agent_cfg.get("max_iterations", 10)
        verbose = agent_cfg.get("verbose", False)

        # 2. 构造 LLM
        llm = build_chat_model(config_loader, llm_provider)

        # 3. 构造工具上下文 + 收集工具
        tool_context = ToolContext(config_loader)
        tools = _collect_all_tools(tool_context)

        # 4. 组装 Agent（langchain 1.x 的 create_agent 统一 API）
        #    create_agent 基于 langgraph，自带状态管理、工具调用循环、消息历史，
        #    替代了 0.x 的 create_tool_calling_agent + AgentExecutor。
        from langchain.agents import create_agent

        system_prompt = AGENT_SYSTEM_PROMPT.format(user_context="（由调用方注入）")
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            # max_iterations 通过 recursion_limit 在调用时控制
        )

        logger.info("AgentService 初始化完成：provider=%s, tools=%d", llm_provider, len(tools))
        return cls(llm, tools, tool_context, agent_executor=agent, max_iterations=max_iterations, verbose=verbose)

    def chat(
        self,
        query: str,
        *,
        user_context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List] = None,
    ) -> Dict[str, Any]:
        """
        与 Agent 对话。

        Args:
            query: 用户输入
            user_context: 用户上下文（角色/姓名/id），注入到 system prompt
            chat_history: 历史对话（LangChain Message 列表），可选

        Returns:
            {"output": str, "intermediate_steps": [...]}
        """
        from langchain_core.messages import HumanMessage

        # langchain 1.x create_agent 返回 CompiledStateGraph，
        # 输入为 {"messages": [...]}，输出含完整消息轨迹。
        # recursion_limit 控制最大工具调用轮次（每轮约 2 步：决策+执行）。
        messages = list(chat_history or [])
        messages.append(HumanMessage(content=query))

        try:
            result = self._agent_executor.invoke(
                {"messages": messages},
                config={"recursion_limit": self.max_iterations * 4 + 2},
            )
        except Exception as e:
            # 工具调用失败时给出可读错误，不阻断
            logger.exception("Agent 执行失败: %s", e)
            return {"output": f"Agent 执行失败: {e}", "intermediate_steps": []}

        # 从最终 messages 提取答案与工具调用轨迹
        final_messages = result.get("messages", [])
        output = _extract_final_answer(final_messages)
        steps = _extract_tool_steps(final_messages)
        return {"output": output, "intermediate_steps": steps}

    @property
    def tool_names(self) -> List[str]:
        """返回所有已注册工具名（供前端展示）。"""
        return [getattr(t, "name", str(t)) for t in self.tools]


# ==================== 辅助函数 ====================

def _collect_all_tools(ctx: ToolContext) -> List:
    """收集所有工具（查询/统计/抽取/导出）。"""
    from backend.agent.tools.query_tools import (
        make_query_awards_tool,
        make_match_competition_tool,
        make_get_competition_tool,
        make_check_whitelist_tool,
        make_list_whitelist_tool,
    )
    from backend.agent.tools.stats_tools import (
        make_list_competitions_tool,
        make_contribution_ranking_tool,
        make_competition_trend_tool,
        make_heatmap_tool,
    )
    from backend.agent.tools.extract_tools import make_extract_tool
    from backend.agent.tools.export_tools import make_export_report_tool

    return [
        # 查询类
        make_query_awards_tool(ctx),
        make_match_competition_tool(ctx),
        make_get_competition_tool(ctx),
        make_check_whitelist_tool(ctx),
        make_list_whitelist_tool(ctx),
        # 统计类
        make_list_competitions_tool(ctx),
        make_contribution_ranking_tool(ctx),
        make_competition_trend_tool(ctx),
        make_heatmap_tool(ctx),
        # 抽取类
        make_extract_tool(ctx),
        # 导出类
        make_export_report_tool(ctx),
    ]


def _format_user_context(ctx: Dict[str, Any]) -> str:
    """格式化用户上下文为字符串。"""
    if not ctx:
        return "（未提供）"
    role = ctx.get("role", "未知")
    name = ctx.get("name", "")
    return f"角色={role}, 姓名={name}"


def _extract_final_answer(messages: List) -> str:
    """
    从 langchain 1.x 的消息轨迹中提取最终答案。

    create_agent 的输出 messages 末尾是 AIMessage（最终回答）。
    """
    for msg in reversed(messages):
        # AIMessage 且无 tool_calls（纯文本回答）
        msg_type = getattr(msg, "type", "")
        content = getattr(msg, "content", "")
        tool_calls = getattr(msg, "tool_calls", None)
        if msg_type == "ai" and content and not tool_calls:
            return content
        # 兼容AIMessage)
        if msg_type == "ai" and content:
            return content
    # 兜底：取最后一条消息的 content
    if messages:
        return getattr(messages[-1], "content", str(messages[-1]))
    return "(Agent 未产生回答)"


def _extract_tool_steps(messages: List) -> List[Dict[str, Any]]:
    """
    从消息轨迹中提取工具调用步骤（供前端展示思考过程）。

    langchain 1.x 的轨迹：AIMessage(tool_calls=[...]) -> ToolMessage(result) -> ...
    """
    steps = []
    pending_tool_calls = {}  # tool_call_id -> {name, args}

    for msg in messages:
        msg_type = getattr(msg, "type", "")
        # AIMessage 带 tool_calls：记录待执行的工具
        if msg_type == "ai":
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                tc_id = tc.get("id") or tc.get("name", "")
                pending_tool_calls[tc_id] = {
                    "name": tc.get("name", ""),
                    "args": tc.get("args", {}),
                }
        # ToolMessage：工具执行结果，匹配对应的 tool_call
        elif msg_type == "tool":
            tc_id = getattr(msg, "tool_call_id", "")
            content = getattr(msg, "content", "")
            info = pending_tool_calls.get(tc_id, {})
            steps.append({
                "tool": info.get("name", "unknown"),
                "input": info.get("args"),
                "output": str(content)[:500],
            })
    return steps


__all__ = ["AgentService", "AGENT_SYSTEM_PROMPT"]
