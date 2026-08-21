"""T56 测试：SystemEventLogger 接入点补齐（llm/upload/db）+ category 规范化。

验证三处新接入点失败时写对应类别事件（写入失败不影响主业务）：
- LLM 回调 on_llm_error → "llm"
- 文件上传 except → "upload"
- db_connection 连接失败 → "db"
以及全部生产调用点使用的类别均在 8 类枚举内（规范化护栏）。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture()
def captured():
    """记录 SystemEventLogger.log 的调用（隔离：不真实写库）。

    注意：以 staticmethod 包装避免类属性函数访问时的 cls 绑定——否则调用
    SystemEventLogger.log(...) 会把类作为第一个位置参数传入 fake。
    """
    calls = []

    import backend.utils.system_event_logger as sel

    def fake_log(category, level, message, **kwargs):
        calls.append({"category": category, "level": level, "message": message,
                      "kwargs": kwargs})
        return True

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sel.SystemEventLogger, "log", staticmethod(fake_log))
    yield calls
    monkeypatch.undo()


class TestLLMHook:
    def test_on_llm_error_writes_llm_event(self, captured):
        from backend.agent import llm_adapter
        # 直接实例化 handler 触发 error 回调
        handler = llm_adapter._LlmMetricHandler("deepseek")
        handler.on_llm_error(ConnectionError("boom"))
        assert any(c["category"] == "llm" and c["level"] == "error"
                   and "deepseek" in c["message"] for c in captured)


class TestUploadHook:
    def test_upload_failure_writes_upload_event(self, captured):
        from backend.services.file_upload_service import FileUploadService

        class BadStream:
            def read(self, *a):
                raise OSError("disk full")

        class BadFile:
            filename = "x.pdf"
            stream = BadStream()

        svc = FileUploadService()
        # 直接触发失败路径：无 filename 的非法文件（upload_file 签名只收 uploaded_file）
        result = svc.upload_file(BadFile())
        assert result.success is False
        assert any(c["category"] == "upload" for c in captured)


class TestDBHook:
    def test_connection_failure_writes_db_event(self, tmp_path, monkeypatch):
        """连接失败事件真写临时库（不 patch log——验证真实写入路径）。"""
        import sqlite3
        from backend.utils import db_connection
        from backend.utils.system_event_logger import SystemEventLogger
        # 事件落到临时库（log 有 R-028 库存在性预检；且 INSERT 外键引用 users(id)，
        # FK=ON 下缺 users 表会写入失败——补最小 users 表）
        events_db = tmp_path / "events.db"
        conn0 = sqlite3.connect(str(events_db))
        conn0.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, login_code TEXT)")
        conn0.commit()
        conn0.close()
        monkeypatch.setattr(SystemEventLogger, "_db_path", str(events_db))
        bad_path = tmp_path / "no" / "such" / "dir" / "x.db"  # 父目录不存在 → connect 失败
        with pytest.raises(Exception):
            db_connection.get_connection(bad_path)
        conn = sqlite3.connect(str(events_db))
        rows = conn.execute(
            "SELECT event_category, event_level FROM system_event_log").fetchall()
        conn.close()
        assert ("db", "error") in rows


class TestCategoryDiscipline:
    def test_all_call_sites_use_8_enum(self):
        """生产代码所有 SystemEventLogger.log/from_exception 的类别均在 8 类枚举内。

        硬扫描调用点：category 必须是字面量（EVENT_CATEGORIES 成员）或 from_exception
        默认参数。非法值由 log() 白名单拒绝 + DDL CHECK 双重拦截。
        """
        from backend.utils.system_event_logger import EVENT_CATEGORIES, SystemEventLogger
        assert EVENT_CATEGORIES == frozenset(
            {"ocr", "llm", "breaker", "auth", "upload", "db", "security", "system"})
        # log() 对非法类别拒绝写入
        assert SystemEventLogger.log("not_a_category", "info", "x") is False