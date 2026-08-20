"""阶段六 L1：SystemEventLogger 单元测试 + 接入点验证。

覆盖：写入/类别级别校验/PII 脱敏/detail JSON/不阻塞契约/from_exception/
operator 解析/建表兜底；接入点（breaker 翻转、auth 锁定）。
"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.system_event_logger import SystemEventLogger, _sanitize


@pytest.fixture()
def evt_db(tmp_path, monkeypatch):
    """隔离库 + users 表（system_event_log.operator_id 有 FK→users——R8 完整 DDL 纪律）。"""
    from tests.fixtures.schemas import USERS_DDL
    db = tmp_path / "evt.db"
    conn = sqlite3.connect(str(db))
    conn.execute(USERS_DDL)
    conn.execute("INSERT INTO users (id, login_code, name, role) VALUES (5, 'admin', '管理员', 'admin')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(SystemEventLogger, "_db_path", str(db))
    return str(db)


def _rows(db, sql="SELECT event_category, event_level, event_message, detail, source_module FROM system_event_log"):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql)]
    except sqlite3.OperationalError:
        return []   # 表未建（写入被拒绝时）视为空
    finally:
        conn.close()


class TestWrite:
    def test_write_basic_fields(self, evt_db):
        assert SystemEventLogger.log("ocr", "error", "百度 OCR 超时",
                                     trace_id="abc123", operator={"id": 5, "code": "admin"},
                                     detail={"provider": "baidu"},
                                     source_module="backend.ocr") is True
        rows = _rows(evt_db)
        assert len(rows) == 1
        r = rows[0]
        assert r["event_category"] == "ocr" and r["event_level"] == "error"
        assert r["event_message"] == "百度 OCR 超时"
        assert r["source_module"] == "backend.ocr"
        assert '"provider": "baidu"' in r["detail"]

    def test_invalid_category_rejected(self, evt_db):
        assert SystemEventLogger.log("not_a_cat", "error", "x") is False
        assert _rows(evt_db) == []

    def test_invalid_level_rejected(self, evt_db):
        assert SystemEventLogger.log("ocr", "fatal", "x") is False
        assert _rows(evt_db) == []

    def test_all_valid_categories_accepted(self, evt_db):
        for cat in ("ocr", "llm", "breaker", "auth", "upload", "db", "security", "system"):
            assert SystemEventLogger.log(cat, "info", f"事件-{cat}") is True
        assert len(_rows(evt_db)) == 8

    def test_ensure_table_bootstraps_empty_db(self, evt_db):
        """老库无表：首写自动建表（迁移 0006 之外的兜底路径）。"""
        assert SystemEventLogger.log("system", "info", "bootstrap") is True
        assert len(_rows(evt_db)) == 1


class TestSanitize:
    def test_phone_masked(self):
        assert _sanitize("联系 13812345678 处理") == "联系 138****5678 处理"

    def test_id_card_masked(self):
        raw = "110101199001011234"
        out = _sanitize(f"证件 {raw} 已核")
        assert raw not in out and "110****1234" in out

    def test_student_code_masked(self):
        assert _sanitize("学号 212306413 注册") == "学号 21230641**** 注册"

    def test_log_sanitize_applied(self, evt_db):
        SystemEventLogger.log("auth", "warning", "手机 13812345678 登录失败")
        assert "13812345678" not in _rows(evt_db)[0]["event_message"]

    def test_no_false_positive_on_short_numbers(self):
        assert _sanitize("订单号 12345") == "订单号 12345"   # 不满足手机/学号模式


class TestNeverBlocks:
    def test_missing_db_file_not_created(self, tmp_path, monkeypatch):
        """R-028 治本：库文件不存在时 log 直接跳过——绝不因写入静默建空库（CI 事故根因）。"""
        from pathlib import Path
        no_db = tmp_path / "not_exist.db"
        monkeypatch.setattr(SystemEventLogger, "_db_path", str(no_db))
        assert SystemEventLogger.log("system", "info", "不应落盘") is False
        assert not no_db.exists()   # 关键：不创建文件

    def test_db_failure_returns_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr(SystemEventLogger, "_db_path",
                            str(tmp_path / "no_dir" / "x.db"))
        assert SystemEventLogger.log("system", "error", "写不进") is False  # 不抛异常

    def test_bad_detail_still_writes(self, evt_db):
        """detail 不可序列化对象降级 str 而非失败。"""
        class Weird:
            def __repr__(self):
                return "<Weird obj>"
        assert SystemEventLogger.log("db", "warning", "x", detail=Weird()) is True


class TestFromException:
    def test_auto_fill_source_and_stack(self, evt_db):
        try:
            raise ValueError("演示异常")
        except ValueError as e:
            assert SystemEventLogger.from_exception(e, category="upload") is True
        rows = _rows(evt_db, "SELECT event_category, event_level, event_message, "
                             "source_file, detail FROM system_event_log")
        r = rows[0]
        assert r["event_category"] == "upload" and r["event_level"] == "error"
        assert "演示异常" in r["event_message"]
        assert r["source_file"] and r["source_file"].endswith("test_system_event_logger.py")
        assert "ValueError" in r["detail"] and "stack_trace" in r["detail"]


class TestIntegrationPoints:
    def test_breaker_open_logs_event(self, evt_db):
        """熔断翻转接入：open 触发 breaker 事件落库。"""
        from backend.utils.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker.get("test_evt_open", fail_threshold=1, window=60)
        cb.reset_for_tests() if hasattr(cb, "reset_for_tests") else None
        cb.record_failure()
        assert cb.state == "open"
        rows = _rows(evt_db, "SELECT event_category, event_level, event_message "
                             "FROM system_event_log WHERE event_category='breaker'")
        assert any("test_evt_open" in r["event_message"] for r in rows)

    def test_auth_lock_logs_event(self, evt_db):
        """登录锁定接入：连续失败达阈值触发 auth 事件。"""
        from backend.utils.login_guard import ACCOUNT_MAX_FAIL, record_login_failure
        for _ in range(ACCOUNT_MAX_FAIL):
            record_login_failure(evt_db, "admin", "10.1.1.1")
        rows = _rows(evt_db, "SELECT event_category, event_message, detail "
                             "FROM system_event_log WHERE event_category='auth'")
        assert len(rows) == 1
        assert "admin" in rows[0]["event_message"] and "锁定" in rows[0]["event_message"]
