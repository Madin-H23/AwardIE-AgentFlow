"""LLM 成功率打点回归：build_chat_model 统一挂 metrics 回调（llm_call_total ok/fail），
修复"日志看板 LLM 成功率恒 0"（inc_llm 此前从未被调用）。"""
import pytest

from backend.agent import llm_adapter
from backend.agent.llm_adapter import _LlmMetricHandler


def test_metric_handler_ok_and_fail(monkeypatch):
    calls = []
    monkeypatch.setattr("backend.utils.metrics.inc_llm", lambda p, o: calls.append((p, o)))
    h = _LlmMetricHandler("deepseek")
    h.on_llm_end(None)
    h.on_llm_error(Exception("boom"))
    assert calls == [("deepseek", "ok"), ("deepseek", "fail")]


def test_build_chat_model_attaches_metric_callbacks(monkeypatch):
    """build_chat_model 构造的实例必须带 _LlmMetricHandler 回调（统一打点入口）。"""
    from backend.agent.llm_adapter import build_chat_model
    if not llm_adapter._LANGCHAIN_AVAILABLE:
        pytest.skip("langchain 未安装，跳过真实构造")
    try:
        from config.loader import get_config
        llm = build_chat_model(get_config())
    except Exception:
        pytest.skip("无法构造（依赖缺失），跳过")
    handlers = getattr(llm, "callbacks", None) or []
    assert any(isinstance(h, _LlmMetricHandler) for h in handlers)


def test_ai_health_aggregates_by_outcome(monkeypatch):
    from backend.services.log_analyzer import LogAnalyzer
    # collect 键含 provider 维度 → 按 outcome 跨 provider 聚合
    monkeypatch.setattr(
        "backend.services.metrics_snapshot.collect",
        lambda: {
            "llm_call_total_total{outcome=fail,provider=deepseek}": 1.0,
            "llm_call_total_total{outcome=ok,provider=deepseek}": 3.0,
            "llm_call_total_total{outcome=ok,provider=zhipu}": 1.0,
        })
    h = LogAnalyzer.ai_health()
    assert h["llm_success_rate"] == round(4 / 5, 4)   # 4 ok / (4+1)


def test_ai_health_empty_is_none(monkeypatch):
    from backend.services.log_analyzer import LogAnalyzer
    monkeypatch.setattr("backend.services.metrics_snapshot.collect", lambda: {})
    assert LogAnalyzer.ai_health()["llm_success_rate"] is None


def test_collect_reads_new_version_metric_types(monkeypatch):
    """prometheus_client 0.26 REGISTRY.collect() 非 Gauge/CounterMetricFamily 实例——
    collect() 须直接读 samples，否则业务 Counter 被过滤致快照恒空（LLM 成功率 0 根因）。"""
    from prometheus_client import CollectorRegistry, Counter
    import prometheus_client
    reg = CollectorRegistry()
    c = Counter("llm_call_total", "llm 调用计数", ["provider", "outcome"], registry=reg)
    c.labels(provider="deepseek", outcome="ok").inc(2)
    monkeypatch.setattr(prometheus_client, "REGISTRY", reg)
    from backend.services.metrics_snapshot import collect
    snap = collect()
    # prometheus 0.26：名字已含 _total 的 Counter 不再追加 _total → 键为 llm_call_total{...}
    hit = [v for k, v in snap.items()
           if k.startswith("llm_call_total") and not k.startswith("llm_call_created")
           and "outcome=ok" in k]
    assert hit and hit[0] == 2.0
