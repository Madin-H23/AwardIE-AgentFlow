"""MetricsSnapshot：Prometheus 指标快照采集与归档（阶段六 L2，日志系统设计 §4.3）。

collect() 读取当前值；archive() 将快照写入 system_event_log（category='system'，
detail=JSON 指标值）——以 DB 归档替代时序存储，供后续趋势图表（L3）。
"""
import json


def collect() -> dict:
    """读取全部 prometheus 指标当前值（未安装 prometheus_client 返回空）。

    注：prometheus_client 0.26+ 的 REGISTRY.collect() 返回 Metric 包装对象，
    不再是 GaugeMetricFamily/CounterMetricFamily 实例——直接遍历 metric.samples
    （各版本返回对象均带 samples），否则业务 Counter 被过滤致快照恒空。
    """
    try:
        from prometheus_client import REGISTRY
    except ImportError:
        return {}
    out = {}
    try:
        for metric in REGISTRY.collect():
            for sample in metric.samples:
                labels = sample.labels or {}
                key = sample.name
                if labels:
                    key = f"{sample.name}{{{','.join(f'{k}={v}' for k, v in sorted(labels.items()))}}}"
                out[key] = sample.value
    except Exception:
        return {}
    return out


def archive() -> bool:
    """快照归档入 system_event_log（category='system', level='info'）。

    写入失败已吞（SystemEventLogger 契约）；供定时任务（L6）周期调用。
    """
    from backend.utils.system_event_logger import SystemEventLogger
    snap = collect()
    if not snap:
        return False
    return SystemEventLogger.log(
        "system", "info", "metrics_snapshot",
        detail={"type": "metrics_snapshot", "values": snap},
        source_module="backend.services.metrics_snapshot")
