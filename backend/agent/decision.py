"""审核决策聚合（P2-5：消除 review_api / review_agent 双实现）。

单一数据源：决策规则改动只改这里，两侧自动生效。
规则（SRS 附录 D + 记忆条目 ③）：仅 high/medium/low 影响决策；info 只是知识库附加提示不拦截；
high_count >= 2 → reject；有任何 real issue → need_manual；否则 pass。
"""
from typing import Dict, List


def aggregate_decision(issues: List[Dict]) -> str:
    """根据 issue 列表聚合审核决策。"""
    real_issues = [i for i in issues if i.get("severity") in ("high", "medium", "low")]
    high_count = sum(1 for i in real_issues if i.get("severity") == "high")
    if high_count >= 2:
        return "reject"
    if real_issues:
        return "need_manual"
    return "pass"
