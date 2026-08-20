"""AlertEngine：阈值规则告警引擎（阶段六 L3，日志系统设计 §4.5）。

六条规则 A001-A006；evaluate() 返回触发列表（含 value/threshold/action）。
数据源：LogAnalyzer 统计 + system_event_log + failed_logins + CircuitBreaker。
"""
from datetime import datetime, timedelta

from backend.utils.db_connection import get_connection

RULES = [
    {"id": "A001", "name": "OCR 失败率突增", "metric": "ocr_error_rate_1h",
     "threshold": 0.3, "severity": "warning",
     "message": "OCR 失败率 {value:.0%}（阈值 {threshold:.0%}），检查 OCR Provider 状态",
     "action": "检查 ocr_runtime.json 禁用记录 / 切换备用 Provider"},
    {"id": "A002", "name": "审核积压超限", "metric": "pending_over_48h",
     "threshold": 20, "severity": "warning",
     "message": "待审核积压 {value} 条（超 48h），建议增加审核人手",
     "action": "检查教师审核排班 / 评估 AI 自动审核覆盖率"},
    {"id": "A003", "name": "熔断器 Open", "metric": "breaker_open",
     "threshold": 1, "severity": "critical",
     "message": "熔断器 {extra[name]} 处于 Open 状态，AI 服务不可用",
     "action": "检查 LLM/OCR Provider 可用性 / 等待 cooldown 恢复"},
    {"id": "A004", "name": "留痕写入失败率", "metric": "audit_write_failure_rate",
     "threshold": 0.01, "severity": "critical",
     "message": "审核留痕写入失败率 {value:.2%}（阈值 {threshold:.2%}）",
     "action": "检查 SQLite 锁竞争 / 审计日志表完整性"},
    {"id": "A005", "name": "认证失败激增", "metric": "auth_failure_count_5m",
     "threshold": 10, "severity": "warning",
     "message": "认证失败 {value} 次/5min，可能暴力破解",
     "action": "检查 limiter 是否生效 / 封禁高频 IP"},
    {"id": "A006", "name": "DB 锁等待", "metric": "db_error_recent",
     "threshold": 0, "severity": "warning",
     "message": "数据库错误 {value} 次（system_event_log db 类 error）",
     "action": "检查 busy_timeout / 评估是否需迁 Redis 队列"},
]


def _ocr_error_rate_1h(db_path) -> float | None:
    """近 1h system_event_log ocr 类 error 占比（无数据/无表返回 None 不评估）。

    窗口基准用 UTC——created_at 为 SQLite CURRENT_TIMESTAMP（UTC）。
    """
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT SUM(event_level='error'), COUNT(*) FROM system_event_log "
            "WHERE event_category='ocr' AND created_at >= ?",
            ((datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),)).fetchone()
        if not row[1]:
            return None
        return row[0] / row[1]
    except Exception:   # 缺表（老库）——不评估
        return None
    finally:
        conn.close()


def _auth_failures_5m(db_path) -> int:
    """近 5min failed_logins 窗口内失败次数（按 first_fail_at 计的行）。"""
    conn = get_connection(db_path)
    try:
        return conn.execute(
            "SELECT COALESCE(SUM(fail_count),0) FROM failed_logins "
            "WHERE updated_at >= ?", ((datetime.now() - timedelta(minutes=5)).strftime(
                "%Y-%m-%d %H:%M:%S"),)).fetchone()[0]
    except Exception:   # 缺表（老库）——0 次不告警
        return 0
    finally:
        conn.close()


def _db_errors_recent(db_path) -> int:
    conn = get_connection(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM system_event_log "
            "WHERE event_category='db' AND event_level='error'").fetchone()[0]
    except Exception:   # 缺表（老库）——0 次不告警
        return 0
    finally:
        conn.close()


def evaluate(db_path=None) -> list[dict]:
    """评估全部规则，返回触发告警列表 [{id,name,severity,value,threshold,message,action,extra}]。"""
    from backend.services.log_analyzer import LogAnalyzer
    if db_path is None:
        from config.loader import ConfigLoader
        db_path = str(ConfigLoader().get_path('database', 'competitions_db'))

    fired = []
    for rule in RULES:
        mid = rule["metric"]
        extra = {}
        if mid == "ocr_error_rate_1h":
            value = _ocr_error_rate_1h(db_path)
            if value is None:
                continue   # 无 OCR 事件数据，不评估
        elif mid == "pending_over_48h":
            value = LogAnalyzer.review_bottleneck(db_path=db_path)["over_48h"]
        elif mid == "breaker_open":
            value = 0
            from backend.utils.circuit_breaker import CircuitBreaker
            for name in ("llm", "ocr"):
                if CircuitBreaker.get(name).state == "open":
                    value = 1
                    extra = {"name": name}
        elif mid == "audit_write_failure_rate":
            value = LogAnalyzer.audit_write_health()["failure_rate"]
            if value == 0.0 and LogAnalyzer.audit_write_health()["total"] == 0:
                continue   # 无留痕数据，不评估
        elif mid == "auth_failure_count_5m":
            value = _auth_failures_5m(db_path)
        elif mid == "db_error_recent":
            value = _db_errors_recent(db_path)
        else:
            continue

        hit = value > rule["threshold"] if mid not in ("breaker_open",) else value >= rule["threshold"]
        if hit:
            fired.append({
                "id": rule["id"], "name": rule["name"], "severity": rule["severity"],
                "metric": mid, "value": value, "threshold": rule["threshold"],
                "message": rule["message"].format(value=value, threshold=rule["threshold"], extra=extra),
                "action": rule["action"], "extra": extra,
            })
    return fired


def get_recent_alerts(days: int = 7, db_path=None) -> list[dict]:
    """历史告警：system_event_log 中告警归档（detail 含 alert_id 的 security/system 事件）。"""
    import json
    from datetime import timedelta
    if db_path is None:
        from config.loader import ConfigLoader
        db_path = str(ConfigLoader().get_path('database', 'competitions_db'))
    conn = get_connection(db_path)
    try:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute(
            "SELECT created_at, event_message, detail FROM system_event_log "
            "WHERE event_message LIKE '[alert]%' AND created_at >= ? ORDER BY id DESC",
            (since,)).fetchall()
        out = []
        for r in rows:
            d = {}
            try:
                d = json.loads(r[2]) if r[2] else {}
            except Exception:
                pass
            out.append({"created_at": r[0], "message": r[1], **d})
        return out
    finally:
        conn.close()


def archive_alerts(alerts: list[dict], db_path=None) -> int:
    """告警归档入 system_event_log（message 前缀 [alert]，detail 含规则上下文）。"""
    from backend.utils.system_event_logger import SystemEventLogger
    n = 0
    for a in alerts:
        if SystemEventLogger.log(
                "security" if a["severity"] == "critical" else "system",
                a["severity"],
                f"[alert] {a['id']} {a['message']}",
                detail={"alert_id": a["id"], "value": a["value"], "threshold": a["threshold"],
                        "action": a["action"]},
                source_module="backend.services.alert_engine"):
            n += 1
    return n
