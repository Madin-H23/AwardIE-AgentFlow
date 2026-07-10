"""
抽取 Agent（图节点）

把现有的 ExtractFramework（OCR + LLM 抽取流水线）封装为 LangGraph 的一个节点。

作为节点，它：
- 读取 state.file_path
- 调用 ExtractFramework.extract() 抽取结构化数据
- 写回 state.extraction_result + state.messages（记录步骤）

这个节点体现了一个重要设计：现有 AI 抽取能力被"原汁原味"地接入多智能体图，
没有重写——抽取 Agent 内部本身就是 OCR + LLM 的组合，符合 Agent 的定义。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agent.state import AgentState

logger = logging.getLogger(__name__)


def make_extraction_node(extract_framework_or_ctx):
    """
    构造抽取 Agent 节点函数。

    Args:
        extract_framework_or_ctx: ExtractFramework 实例，或 ToolContext（惰性获取 framework）。
            传 ToolContext 可避免工作流构造时就初始化 OCR 引擎（只有真正抽取时才构造）。

    Returns:
        LangGraph 节点函数 (state) -> state_update
    """
    def extraction_node(state: AgentState) -> Dict[str, Any]:
        file_path = state.get("file_path", "")
        if not file_path:
            return {
                "steps": (state.get("steps") or []) + [{
                    "agent": "extraction",
                    "status": "skipped",
                    "reason": "无 file_path",
                }],
            }

        # 惰性获取 framework（支持直接传 framework 或传 ToolContext）
        if hasattr(extract_framework_or_ctx, "extract"):
            framework = extract_framework_or_ctx
        else:
            framework = extract_framework_or_ctx.extract_framework  # ToolContext

        logger.info("[抽取Agent] 处理文件: %s", file_path)
        try:
            result = framework.extract(file_path, use_ocr_cache=True, use_llm_cache=True)
            extraction_result = {
                "doc_type": result.template_type.value if hasattr(result.template_type, 'value') else result.template_type,
                "data": result.data,
                "confidence": _estimate_confidence(result),
                "ocr_text": (result.ocr_text or "")[:500],  # 截断避免 state 过大
            }
            return {
                "extraction_result": extraction_result,
                "steps": (state.get("steps") or []) + [{
                    "agent": "extraction",
                    "status": result.status.value if hasattr(result.status, "value") else str(result.status),
                    "doc_type": extraction_result["doc_type"],
                    "error": result.error_message,
                }],
            }
        except Exception as e:
            logger.exception("[抽取Agent] 失败: %s", e)
            return {
                "steps": (state.get("steps") or []) + [{
                    "agent": "extraction",
                    "status": "error",
                    "error": str(e),
                }],
                "extraction_result": {"doc_type": None, "data": {}, "confidence": 0.0},
            }

    return extraction_node


def _estimate_confidence(result) -> float:
    """
    粗略估计抽取置信度。

    真实项目可基于 LLM 返回的 logprobs 或字段完整度计算；
    这里用启发式：数据字段数 / 预期字段数。
    """
    data = getattr(result, "data", None) or {}
    if not data:
        return 0.0
    # 有效字段数（非空）
    valid = sum(1 for v in data.values() if v not in (None, "", []))
    return min(valid / 8.0, 1.0)  # 假设奖状约 8 个关键字段


__all__ = ["make_extraction_node"]
