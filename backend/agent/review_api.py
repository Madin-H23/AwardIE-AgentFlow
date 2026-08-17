"""
独立审核 API：脱离 LangGraph 多智能体工作流，直接对一份抽取结果做审核。

设计动机
========
业务流程（导入校对页、审核决策）需要复用 review_agent 的校验能力，但不必启动
整个 Supervisor 多智能体工作流。本模块把 review_node 里的校验 + 决策聚合逻辑
抽成纯函数，供业务代码直接 import 调用。

校验能力（与 review_agent 节点一致）：
1. 规则校验：必填字段 / 奖项级别合法 / 角色合法（仅 award 类型）
2. RAG 交叉校验：查竞赛知识库，附等级/类别参考（需传入 vectorstore）

输出：{decision: pass|need_manual|reject, issues, suggestion, rag_reference}
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.agent.graph.review_agent import (
    _resolve_valid_levels,
    _check_required_fields,
    _check_award_level,
    _check_roles,
    _rag_cross_check,
    _build_suggestion,
)

logger = logging.getLogger(__name__)


def review_extraction(
    config_loader,
    extraction_result: Dict[str, Any],
    vectorstore=None,
) -> Dict[str, Any]:
    """
    对一份抽取结果做独立审核。

    Args:
        config_loader: ConfigLoader 实例（读取 award_levels 合法集合）
        extraction_result: {"data": dict, "doc_type": "award"|"patent"|...}
        vectorstore: 可选 RAG 向量库；为 None 时跳过知识库交叉校验

    Returns:
        {
            "decision": "pass" | "need_manual" | "reject",
            "issues": [{"field", "issue", "severity"}, ...],
            "suggestion": str,
            "rag_reference": dict | None,
        }

    说明：
        - 仅 doc_type=="award" 做完整规则校验（与 review_agent 节点保持一致）
        - 内部异常向上抛出，由调用方决定降级策略（业务可用性优先）
    """
    extraction = extraction_result or {}
    data = extraction.get("data") or {}
    doc_type = extraction.get("doc_type")

    issues = []
    if doc_type == "award":
        valid_levels = _resolve_valid_levels(config_loader)
        issues.extend(_check_required_fields(data))
        issues.extend(_check_award_level(data, valid_levels))
        issues.extend(_check_roles(data))

    # RAG 交叉校验（可选）
    rag_ref = None
    if vectorstore and data.get("competition_name"):
        rag_ref = _rag_cross_check(vectorstore, data["competition_name"])
        if rag_ref and rag_ref.get("category"):
            issues.append({
                "field": "competition_category",
                "issue": f"知识库记录该竞赛为 {str(rag_ref.get('category', '')).rstrip('类')}类赛事",
                "severity": "info",
            })

    # 决策聚合（与 review_agent.review_node 一致）
    # 仅 high/medium/low 影响决策；info 只是知识库附加提示，不触发拦截
    real_issues = [i for i in issues if i.get("severity") in ("high", "medium", "low")]
    high_count = sum(1 for i in real_issues if i.get("severity") == "high")
    if high_count >= 2:
        decision = "reject"
    elif real_issues:
        decision = "need_manual"
    else:
        decision = "pass"

    return {
        "decision": decision,
        "issues": issues,
        "suggestion": _build_suggestion(decision, issues),
        "rag_reference": rag_ref,
    }


__all__ = ["review_extraction"]
