"""每日报告留痕键名对齐回归：_log_daily_report 须用 LogAnalyzer.daily_summary 的真实键
（audit_actions/system_errors 而非不存在的 action_count/error_count——曾致消息恒显 '?'）。"""
import pytest

import backend.utils.log_scheduler as ls


def test_daily_report_message_uses_real_keys(monkeypatch):
    captured = {}

    class FakeLogger:
        @staticmethod
        def log(*args, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("backend.utils.system_event_logger.SystemEventLogger", FakeLogger)
    monkeypatch.setattr(
        "backend.services.plan_generator.daily_report",
        lambda db_path=None: {"audit_actions": 8, "system_errors": 0, "alerts": []})
    ls._log_daily_report("unused.db")
    assert "actions=8" in captured["message"]
    assert "错误=0" in captured["message"]
    assert "?" not in captured["message"]