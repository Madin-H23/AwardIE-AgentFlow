"""阶段四批B回归：metrics 暴露/埋点 + 备份脚本。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestMetrics:
    def test_exporter_endpoint(self):
        from config.flask import TestingConfig
        from app import create_app
        app = create_app(TestingConfig)
        app.config.update(SECRET_KEY="mx-key-0123456789abcdef0123456789a")
        c = app.test_client()
        r = c.get("/api/metrics")
        assert r.status_code == 200
        assert "audit_write_total" in r.get_data(as_text=True)   # audit 埋点已暴露

    def test_audit_metric_counts(self):
        from backend.utils.metrics import inc_audit, exporter_response
        inc_audit(True); inc_audit(True); inc_audit(False)
        body, _, _ = exporter_response()
        assert 'audit_write_total_total{result="fail"} 1.0' in body or 'result="fail"} 1' in body

    def test_breaker_gauge(self):
        from backend.utils.metrics import set_breaker, exporter_response
        from backend.utils.circuit_breaker import CircuitBreaker
        b = CircuitBreaker.get("llm")
        b.record_failure()
        body, _, _ = exporter_response()
        assert "breaker_state" in body

    def test_degraded_without_lib(self, monkeypatch):
        """prometheus_client 缺失时静默降级（_AVAILABLE False 分支）。"""
        from backend.utils import metrics as mod
        monkeypatch.setattr(mod, "_AVAILABLE", False)
        mod.inc_upload(True)   # 不抛即过
        body, code, _ = mod.exporter_response()
        assert "未安装" in body


class TestBackup:
    def test_script_exists(self):
        assert (PROJECT_ROOT / "scripts" / "backup.py").exists()

    def test_script_dry_logic(self, tmp_path, monkeypatch):
        """核心逻辑（拷贝+integrity+对账）在临时目录跑通。"""
        import sqlite3, importlib.util
        # 构造最小项目结构
        fake_root = tmp_path / "proj"
        (fake_root / "database").mkdir(parents=True)
        (fake_root / "files").mkdir()
        conn = sqlite3.connect(str(fake_root / "database" / "competitions.db"))
        conn.execute("CREATE TABLE students(id INTEGER)")
        conn.execute("INSERT INTO students VALUES (1)")
        conn.execute("CREATE TABLE awards(id INTEGER)")
        conn.execute("CREATE TABLE pending_achievements(id INTEGER)")
        conn.commit(); conn.close()

        spec = importlib.util.spec_from_file_location("bk", PROJECT_ROOT / "scripts" / "backup.py")
        bk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bk)
        monkeypatch.setattr(bk, "PROJECT_ROOT", fake_root)
        monkeypatch.setattr(bk, "BACKUP_ROOT", fake_root / "database" / "backups")
        rc = bk.main()
        assert rc == 0
        bak = fake_root / "database" / "backups"
        assert any(d.is_dir() for d in bak.iterdir())
        assert (list(bak.iterdir())[0] / "files").is_dir()      # files 目录已备份
