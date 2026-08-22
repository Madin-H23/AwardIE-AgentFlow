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

def test_run_daily_triggers_backup(monkeypatch):
    """T63：run_daily 每日窗口应触发每日全量备份（subprocess 调 scripts/backup.py）。"""
    import sys
    from pathlib import Path
    from backend.utils import log_scheduler

    called = {}

    def fake_run(cmd, **kwargs):
        called["cmd"] = cmd
        return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    import subprocess as _sub
    monkeypatch.setattr(_sub, "run", fake_run)
    # 备份脚本必须存在（仓库内真实路径）
    assert Path(log_scheduler.__file__).resolve().parents[2].joinpath("scripts", "backup.py").exists()
    monkeypatch.setattr(log_scheduler, "_cleanup_capacity", lambda p: None)
    monkeypatch.setattr(log_scheduler, "_reopen_ignored", lambda p: None)
    monkeypatch.setattr(log_scheduler, "_log_daily_report", lambda p: None)
    log_scheduler.run_daily(db_path=":memory:")
    assert any(str(p).endswith("backup.py") for p in called["cmd"]), called
