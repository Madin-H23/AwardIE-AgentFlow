"""PlanGenerator：告警→行动计划生成（阶段六 L3，日志系统设计 §4.6）。

基于 AlertEngine.evaluate() 输出生成可执行计划项；状态机
open → acknowledged → resolved（忽略 ignored 7 天后重评估）。
本批状态不持久化（设计开放问题 Q1 选 B 纯内存——L6 收尾时重估）。
"""
from datetime import datetime

# 规则→计划类别与优先级映射（设计 §4.6 生成逻辑表）
_PLAN_META = {
    "A001": ("高", "运维"), "A002": ("中", "业务"), "A003": ("高", "性能"),
    "A004": ("高", "安全"), "A005": ("高", "安全"), "A006": ("中", "性能"),
}


def from_alert(alert: dict, seq: int = 0) -> dict:
    """单条告警 → 计划项。"""
    priority, category = _PLAN_META.get(alert["id"], ("中", "运维"))
    return {
        "id": f"P-{alert['id']}-{seq}",
        "alert_id": alert["id"],
        "priority": priority,
        "category": category,
        "title": f"{alert['id']}: {alert['name']}",
        "description": alert["message"],
        "evidence": {"metric": alert["metric"], "value": alert["value"],
                     "threshold": alert["threshold"], "severity": alert["severity"]},
        "suggested_actions": [alert["action"]],
        "status": "open",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def generate(db_path=None) -> list[dict]:
    """当前告警全量转计划（按优先级排序：高→中→低）。"""
    from backend.services.alert_engine import evaluate
    alerts = evaluate(db_path=db_path)
    plans = [from_alert(a, i) for i, a in enumerate(alerts)]
    order = {"高": 0, "中": 1, "低": 2}
    return sorted(plans, key=lambda p: order.get(p["priority"], 3))


def transition(plan: dict, to_status: str) -> dict:
    """状态机：open → acknowledged → resolved；open → ignored（7 天后重评估）。

    非法跳转抛 ValueError（不静默）。
    """
    allowed = {"open": ("acknowledged", "ignored"),
               "acknowledged": ("resolved",),
               "ignored": (),          # ignored 由重评估复活，不接受人工跳转
               "resolved": ()}
    if to_status not in allowed.get(plan["status"], ()):
        raise ValueError(f"非法状态跳转: {plan['status']} → {to_status}")
    plan["status"] = to_status
    plan["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return plan


def daily_report(db_path=None) -> dict:
    """每日报告摘要（供 L6 定时推送）。"""
    from backend.services.log_analyzer import LogAnalyzer
    from backend.services.alert_engine import evaluate
    summary = LogAnalyzer.daily_summary(db_path=db_path)
    summary["alerts"] = evaluate(db_path=db_path)
    summary["ai_health"] = LogAnalyzer.ai_health()
    return summary
