"""业务黄金指标（4.7 / 部署设计 §3.1——prometheus_client 实现）。

指标清单：
- upload_total{result}         上传成功/失败（黄金指标）
- review_action_total{action}  审核动作计数（approve/reject/withdraw/discard）
- llm_call_total{provider,outcome}  LLM 调用成功/失败/熔断拒绝
- breaker_state{name}          熔断器状态 gauge（0=closed 1=half_open 2=open）
- review_cycle_hours           提交→入库时长（价值验证指标，audit_log 时间差）
- audit_write_total{result}    留痕写入成功/失败（best-effort 可观测化）
用法：业务代码 `from backend.utils.metrics import inc_upload, inc_review...` 一行埋点；
/metrics 由 app/__init__.py 暴露（内网）。
"""
import logging
import time

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, values
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    logger.info("prometheus_client 未安装——metrics 静默降级（计数丢失不影响业务）")

if _AVAILABLE:
    UPLOAD_TOTAL = Counter("upload_total", "文件上传计数", ["result"])
    REVIEW_ACTION_TOTAL = Counter("review_action_total", "审核动作计数", ["action"])
    LLM_CALL_TOTAL = Counter("llm_call_total", "LLM 调用计数", ["provider", "outcome"])
    BREAKER_STATE = Gauge("breaker_state", "熔断状态(0=closed,1=half_open,2=open)", ["name"])
    REVIEW_CYCLE_HOURS = Gauge("review_cycle_hours", "提交→入库时长(小时,最近一次)", ["kind"])
    AUDIT_WRITE_TOTAL = Counter("audit_write_total", "留痕写入计数", ["result"])
    _BUFFER = None   # 进程内也可用 values.ValueClass；直接 Counter 即可

    def inc_upload(ok: bool):
        try: UPLOAD_TOTAL.labels(result="ok" if ok else "fail").inc()
        except Exception: pass

    def inc_review(action: str):
        try: REVIEW_ACTION_TOTAL.labels(action=action).inc()
        except Exception: pass

    def inc_llm(provider: str, outcome: str):
        try: LLM_CALL_TOTAL.labels(provider=provider, outcome=outcome).inc()
        except Exception: pass

    def set_breaker(name: str, state: str):
        try: BREAKER_STATE.labels(name=name).set({"closed": 0, "half_open": 1, "open": 2}[state])
        except Exception: pass

    def set_review_cycle(kind: str, submit_ts, approve_ts):
        """提交→入库时长（audit_log created_at 差；价值验证月报数据源）。"""
        try:
            from datetime import datetime
            fmt_list = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]
            def _p(t):
                for f in fmt_list:
                    try: return datetime.strptime(str(t)[:26], f)
                    except ValueError: continue
                return None
            a, b = _p(submit_ts), _p(approve_ts)
            if a and b and b >= a:
                REVIEW_CYCLE_HOURS.labels(kind=kind).set(round((b - a).total_seconds() / 3600, 2))
        except Exception: pass

    def inc_audit(ok: bool):
        try: AUDIT_WRITE_TOTAL.labels(result="ok" if ok else "fail").inc()
        except Exception: pass
else:
    def _noop(*a, **k): pass
    inc_upload = inc_review = inc_llm = inc_audit = _noop
    set_breaker = set_review_cycle = _noop


def exporter_response():
    """/metrics 端点内容（Flask 路由包装用）。"""
    if not _AVAILABLE:
        return "# prometheus_client 未安装\n", 200, {"Content-Type": "text/plain"}
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return generate_latest().decode("utf-8"), 200, {"Content-Type": CONTENT_TYPE_LATEST}
