"""PlanGenerator：告警→行动计划生成（阶段六 L3→L6，日志系统设计 §4.6）。

基于 AlertEngine.evaluate() 输出生成可执行计划项；状态机
open → acknowledged → resolved；open → ignored（7 天后重评估复活）。

L6 变更：状态持久化（取消 L3 纯内存 Q1 选 B）——新增 action_plans 表，
generate() 合并已持久化计划（状态/时间保留），transition() 写库；幂等建表
（老库演进期容错，与 0006 system_event_log 同样以 IF NOT EXISTS 演进）。
"""
from datetime import datetime
import json

# 规则→计划类别与优先级映射（设计 §4.6 生成逻辑表）
_PLAN_META = {
    "A001": ("高", "运维"), "A002": ("中", "业务"), "A003": ("高", "性能"),
    "A004": ("高", "安全"), "A005": ("高", "安全"), "A006": ("中", "性能"),
}

_DDL = """
CREATE TABLE IF NOT EXISTS action_plans (
    id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL,
    priority TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    evidence TEXT,
    suggested_actions TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT,
    resolved_at TEXT
)
"""
_ORDER = {"高": 0, "中": 1, "低": 2}


def _default_db():
    try:
        from config.loader import get_config_loader
        return get_config_loader()["database"]["competitions_db"]
    except Exception:
        return "database/competitions.db"


def _connect(db_path=None):
    """打开连接并幂等建表（不存在则建，老库演进不破坏）。"""
    from backend.utils.db_connection import get_connection
    conn = get_connection(db_path or _default_db())
    conn.execute(_DDL)
    conn.commit()
    return conn


def _row_to_plan(r) -> dict:
    p = dict(r)
    for k in ("evidence", "suggested_actions"):
        if p.get(k):
            try:
                p[k] = json.loads(p[k])
            except (TypeError, ValueError):
                pass
    return p


def from_alert(alert: dict, seq: int = 0) -> dict:
    """单条告警 → 计划项。"""
    priority, category = _PLAN_META.get(alert["id"], ("中", "运维"))
    return {
        "id": f"P-{alert['id']}",
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
        "updated_at": None,
        "resolved_at": None,
    }


def load(db_path=None) -> list[dict]:
    """读取全部已持久化计划（按优先级排序）。"""
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM action_plans").fetchall()
        plans = [_row_to_plan(r) for r in rows]
    finally:
        conn.close()
    return sorted(plans, key=lambda p: _ORDER.get(p["priority"], 3))


def generate(db_path=None) -> list[dict]:
    """当前告警全量转计划（持久化合并）：已有计划保留状态，新告警插入 open。"""
    from backend.services.alert_engine import evaluate
    conn = _connect(db_path)
    try:
        existing = {}
        for r in conn.execute("SELECT * FROM action_plans").fetchall():
            p = _row_to_plan(r)
            existing[p["id"]] = p
        alerts = evaluate(db_path=db_path)
        for a in alerts:
            pid = f"P-{a['id']}"
            if pid not in existing:
                p = from_alert(a)
                conn.execute(
                    "INSERT INTO action_plans (id, alert_id, priority, category, title, description, "
                    "evidence, suggested_actions, status, created_at, updated_at, resolved_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (p["id"], p["alert_id"], p["priority"], p["category"], p["title"], p["description"],
                     json.dumps(p["evidence"], ensure_ascii=False),
                     json.dumps(p["suggested_actions"], ensure_ascii=False),
                     p["status"], p["created_at"], p["updated_at"], p["resolved_at"]))
                existing[pid] = p
        conn.commit()
        plans = list(existing.values())
    finally:
        conn.close()
    return sorted(plans, key=lambda p: _ORDER.get(p["priority"], 3))


def transition(plan: dict, to_status: str, db_path=None) -> dict:
    """状态机：open → acknowledged → resolved；open → ignored（7 天后重评估）。

    非法跳转抛 ValueError（不静默）。校验通过后**写库**（L6 持久化）。
    """
    allowed = {"open": ("acknowledged", "ignored"),
               "acknowledged": ("resolved",),
               "ignored": (),          # ignored 由重评估复活，不接受人工跳转
               "resolved": ()}
    if to_status not in allowed.get(plan["status"], ()):
        raise ValueError(f"非法状态跳转: {plan['status']} → {to_status}")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE action_plans SET status=?, updated_at=?, resolved_at=? WHERE id=?",
            (to_status, now, now if to_status == "resolved" else None, plan["id"]))
        conn.commit()
    finally:
        conn.close()
    plan["status"] = to_status
    plan["updated_at"] = now
    plan["resolved_at"] = now if to_status == "resolved" else None
    return plan


def daily_report(db_path=None) -> dict:
    """每日报告摘要（供 L6 定时推送）。"""
    from backend.services.log_analyzer import LogAnalyzer
    from backend.services.alert_engine import evaluate
    summary = LogAnalyzer.daily_summary(db_path=db_path)
    summary["alerts"] = evaluate(db_path=db_path)
    summary["ai_health"] = LogAnalyzer.ai_health()
    return summary
