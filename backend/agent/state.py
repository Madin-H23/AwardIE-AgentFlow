"""
多智能体协作共享状态定义

LangGraph 的 StateGraph 通过共享 State 在多个 Agent 节点之间传递信息。
所有 Agent 节点读取并更新这个 State，由框架负责合并。

设计要点：
- 使用 TypedDict 声明字段，LangGraph 据此做状态合并
- messages 字段使用 Annotated + add_messages，支持消息追加而非覆盖
- 业务数据（抽取结果、审核结果）使用默认覆盖语义
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, TypedDict

# LangGraph 的消息追加 reducer（惰性导入，避免未安装时整个模块不可用）
try:
    from langgraph.graph.message import add_messages
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False
    # 降级：未安装 langgraph 时提供占位符，使模块可被导入（仅做配置校验/类型检查）
    def add_messages(left: List, right: List) -> List:  # type: ignore[no-redef]
        return (left or []) + (right or [])


class ReviewResult(TypedDict, total=False):
    """审核 Agent 的输出。"""

    # 总体结论：pass / reject / need_manual
    decision: str
    # 异常项清单，每项 {"field": "字段", "issue": "问题描述", "severity": "high|medium|low"}
    issues: List[Dict[str, Any]]
    # 给用户的修改建议（自然语言）
    suggestion: str


class ExtractionResult(TypedDict, total=False):
    """抽取 Agent 的输出。"""

    # 文档类型：award / patent / software / innovation / other
    doc_type: str
    # 结构化数据（字段随文档类型变化）
    data: Dict[str, Any]
    # 抽取置信度 0~1
    confidence: float
    # 原始 OCR 文本（供审核 Agent 复用，避免二次识别）
    ocr_text: str


class QAContext(TypedDict, total=False):
    """问答 Agent（RAG）的输出上下文。"""

    # 检索到的知识片段
    sources: List[Dict[str, Any]]
    # 基于知识生成的回答
    answer: str


class AgentState(TypedDict, total=False):
    """
    多智能体协作的共享状态。

    该 State 在 Supervisor -> {抽取/审核/问答} Agent 之间流转。
    每个字段都是可选的（total=False），由各 Agent 按需读写。

    生命周期示例（上传一份奖状的场景）：
        1. 初始化：messages=[用户上传请求], task_type="extract_and_review"
        2. 抽取 Agent：填充 extraction_result
        3. 审核 Agent：读取 extraction_result，填充 review_result（并可能查询 RAG 校验白名单）
        4. Supervisor 汇总：基于 review_result.decision 决定通过/退回
    """

    # ===== 消息流（LangGraph 标准字段）=====
    # 会话消息列表，使用 add_messages reducer 自动追加
    messages: Annotated[List[Any], add_messages]

    # ===== 任务元信息 =====
    # 当前任务类型：extract_and_review / qa / stats / export / chat
    task_type: str
    # 发起任务的文件路径（抽取任务用）
    file_path: str
    # 当前用户上下文（角色、id、姓名），用于工具鉴权
    user_context: Dict[str, Any]

    # ===== 各 Agent 的输出 =====
    extraction_result: ExtractionResult
    review_result: ReviewResult
    qa_context: QAContext

    # ===== Supervisor 决策与流程控制 =====
    # 下一个要路由到的 Agent 名称（Supervisor 输出，LangGraph 条件边读取）
    next_agent: str
    # 累计的步骤记录，便于前端展示 Agent 思考过程
    steps: List[Dict[str, Any]]
    # 是否已完成（Supervisor 判定流程结束）
    done: bool
