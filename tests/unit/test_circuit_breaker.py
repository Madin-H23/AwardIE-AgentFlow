"""P1-10 回归测试：熔断器三态转换 + 服务失败计数 + LLM provider 重试/熔断接线。"""
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.circuit_breaker import CircuitBreaker, is_service_failure


@pytest.fixture()
def fresh_breaker():
    """独立实例，避免污染注册表单例。"""
    return CircuitBreaker("test-llm", fail_threshold=3, window=60, cooldown=0.05, success_threshold=2)


class TestBreakerStates:
    def test_closed_to_open_after_threshold(self, fresh_breaker):
        for _ in range(3):
            fresh_breaker.record_failure()
        assert fresh_breaker.state == "open"
        with pytest.raises(Exception) as ei:
            fresh_breaker.guard()
        assert getattr(ei.value, 'code', None) == 4003

    def test_open_to_half_open_after_cooldown(self, fresh_breaker):
        for _ in range(3):
            fresh_breaker.record_failure()
        time.sleep(0.06)                       # 冷却期过
        assert fresh_breaker.state == "half_open"

    def test_half_open_recovers_after_successes(self, fresh_breaker):
        for _ in range(3):
            fresh_breaker.record_failure()
        time.sleep(0.06)
        fresh_breaker.record_success()
        assert fresh_breaker.state == "half_open"      # 1 次不足
        fresh_breaker.record_success()
        assert fresh_breaker.state == "closed"         # 2 次复位

    def test_half_open_failure_reopens(self, fresh_breaker):
        for _ in range(3):
            fresh_breaker.record_failure()
        time.sleep(0.06)
        fresh_breaker.record_failure()                 # 半开探活失败 -> 立即重开
        assert fresh_breaker.state == "open"


class TestFailureClassification:
    def test_service_failures(self):
        import requests
        assert is_service_failure(requests.Timeout())
        assert is_service_failure(requests.ConnectionError())
        resp = requests.Response(); resp.status_code = 503
        assert is_service_failure(requests.HTTPError(response=resp))
        resp4 = requests.Response(); resp4.status_code = 400
        assert not is_service_failure(requests.HTTPError(response=resp4))
        assert not is_service_failure(ValueError("业务错误"))   # 非服务类不计


class TestProviderIntegration:
    def test_provider_uses_breaker_and_retries(self, monkeypatch):
        """LLM provider：连续服务失败达阈值 -> 熔断开启（第 4 次直接 4003 不调用）。"""
        from backend.extract.llm import provider as mod
        import requests

        calls = {"n": 0}

        def fake_post(*a, **k):
            calls["n"] += 1
            resp = requests.Response()
            resp.status_code = 500
            raise requests.HTTPError(response=resp)

        monkeypatch.setattr(mod.requests, "post", fake_post)
        breaker = CircuitBreaker.get("llm")
        # 重置注册表单例（防跨用例污染）
        breaker._state = "closed"; breaker._fails = []; breaker._half_ok = 0

        p = mod.LLMProvider({})
        p._api_config = {"url": "http://x", "timeout": 1, "max_retries": 2, "model": "m"}
        with pytest.raises(requests.HTTPError):
            p._chat_with_api([{"role": "user", "content": "hi"}], 0.1)
        assert calls["n"] == 2                    # max_retries=2 次尝试
        assert breaker.state == "closed"          # 2 次 < 阈值 5

        for _ in range(2):                        # 再失败 3 次到阈值
            try: p._chat_with_api([{"role": "user", "content": "x"}], 0.1)
            except Exception: pass
        try: p._chat_with_api([{"role": "user", "content": "x"}], 0.1)
        except Exception as e:
            assert getattr(e, 'code', None) == 4003   # 熔断开启直接拒
        assert breaker.state == "open"
