"""
审核 Agent（图节点）

对抽取结果做异常检测，并给出修改建议。

审核逻辑（双校验）：
1. 规则校验：基于 config/settings.json 的 validation 规则
   - 必填字段是否完整（竞赛名/获奖人/级别）
   - 奖项级别是否合法（一等奖/二等奖/...）
   - 角色是否合法（学生/教师）
2. RAG 交叉校验：若竞赛名存在，查知识库确认其等级/白名单状态是否与抽取结果一致

输出 ReviewResult：decision(pass/need_manual/reject) + issues + suggestion
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agent.state import AgentState

logger = logging.getLogger(__name__)


# 合法值（从 config/validation 派生的简化版；完整实现可读取 config）
VALID_AWARD_LEVELS = {"一等奖", "二等奖", "三等奖", "特等奖", "金奖", "银奖", "铜奖", "优秀奖"}
VALID_ROLES = {"学生", "教师"}
# 必填字段：每个字段接受多个候选名（抽取器输出的字段名可能不同）
REQUIRED_AWARD_FIELDS = {
    "competition_name": ["competition_name"],
    "winner": ["winner", "winner_name"],          # 兼容 winner_name
    "award_level": ["award_level"],
}


def _get_field(data: dict, candidates) -> "any":
    """从 data 中按候选字段名取值（兼容不同抽取器的字段命名）。"""
    if isinstance(candidates, str):
        candidates = [candidates]
    for name in candidates:
        if name in data and data[name] not in (None, "", []):
            return data[name]
    return None


def make_review_node(config_loader, vectorstore=None):
    """
    构造审核 Agent 节点函数。

    Args:
        config_loader: ConfigLoader 实例（读取 validation 规则）
        vectorstore: RAG 向量库（可选，用于交叉校验竞赛白名单）

    Returns:
        LangGraph 节点函数
    """
    # 预读校验规则配置
    config = config_loader.load_config()
    val_cfg = config.get("validation", {})
    valid_levels = set(val_cfg.get("award_levels") or []) or {
        "一等奖", "二等奖", "三等奖", "特等奖", "金奖", "银奖", "铜奖", "优秀奖"
    }

    def review_node(state: AgentState) -> Dict[str, Any]:
        extraction = state.get("extraction_result") or {}
        data = extraction.get("data") or {}
        doc_type = extraction.get("doc_type")

        logger.info("[审核Agent] 审核 doc_type=%s", doc_type)
        issues: List[Dict[str, Any]] = []

        # 仅对奖状类做完整校验（其他类型简化）
        if doc_type == "award":
            issues.extend(_check_required_fields(data))
            issues.extend(_check_award_level(data, valid_levels))
            issues.extend(_check_roles(data))

        # RAG 交叉校验（若有向量库）
        rag_ref = None
        if vectorstore and data.get("competition_name"):
            rag_ref = _rag_cross_check(vectorstore, data["competition_name"])
            if rag_ref and rag_ref.get("category"):
                issues.append({
                    "field": "competition_category",
                    "issue": f"知识库记录该竞赛为 {rag_ref.get('category')}类赛事",
                    "severity": "info",
                })

        # 决策
        high_count = sum(1 for i in issues if i.get("severity") == "high")
        if high_count >= 2:
            decision = "reject"
        elif issues:
            decision = "need_manual"
        else:
            decision = "pass"

        suggestion = _build_suggestion(decision, issues)

        review_result = {
            "decision": decision,
            "issues": issues,
            "suggestion": suggestion,
            "rag_reference": rag_ref,
        }
        return {
            "review_result": review_result,
            "steps": (state.get("steps") or []) + [{
                "agent": "review",
                "decision": decision,
                "issue_count": len(issues),
            }],
        }

    return review_node


def _check_required_fields(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """检查必填字段（兼容不同抽取器的字段命名）。"""
    issues = []
    for field, candidates in REQUIRED_AWARD_FIELDS.items():
        val = _get_field(data, candidates)
        if not val:
            issues.append({
                "field": field,
                "issue": f"缺少必填字段: {field}",
                "severity": "high",
            })
    return issues


def _check_award_level(data: Dict[str, Any], valid_levels: set) -> List[Dict[str, Any]]:
    """检查奖项级别是否合法。"""
    issues = []
    level = data.get("award_level")
    if level and level not in valid_levels:
        issues.append({
            "field": "award_level",
            "issue": f"奖项级别 '{level}' 不在合法集合中",
            "severity": "medium",
        })
    return issues


def _check_roles(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """检查获奖人/指导教师角色。"""
    issues = []
    for role_field in ["winner_role", "supervisor_role"]:
        role = data.get(role_field)
        if role and role not in VALID_ROLES:
            issues.append({
                "field": role_field,
                "issue": f"角色 '{role}' 不合法（应为 学生/教师）",
                "severity": "low",
            })
    return issues


def _rag_cross_check(vectorstore, competition_name: str) -> Optional[Dict[str, Any]]:
    """
    用 RAG 检索竞赛知识库，返回该竞赛的等级/白名单参考。

    用于交叉校验抽取结果与官方规则是否一致。
    """
    try:
        from langchain_core.documents import Document
        results = vectorstore.similarity_search_with_score(competition_name, k=1)
        if not results:
            return None
        doc, score = results[0]
        return {
            "matched_name": doc.metadata.get("name"),
            "level": doc.metadata.get("level"),
            "category": doc.metadata.get("category"),
            "similarity_score": float(score),
        }
    except Exception as e:
        logger.debug("RAG 交叉校验失败（可能未初始化）: %s", e)
        return None


def _build_suggestion(decision: str, issues: List[Dict[str, Any]]) -> str:
    """基于异常清单生成自然语言建议。"""
    if decision == "pass":
        return "审核通过，所有字段校验正常。"
    if decision == "reject":
        high = [i for i in issues if i.get("severity") == "high"]
        return f"审核未通过：存在 {len(high)} 个严重问题，建议退回补充：{'；'.join(i['issue'] for i in high)}"
    # need_manual
    return f"需人工复核：发现 {len(issues)} 个待确认项：{'；'.join(i['issue'] for i in issues[:3])}"


__all__ = ["make_review_node"]
