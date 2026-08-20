"""SystemEventLogger：系统事件结构化落库（阶段六 L1，日志系统设计 §3.3）。

复用 AuditLogger 设计模式：进程级类方法 / 独立连接 / append-only /
不阻塞主业务（任何失败仅 warning，绝不抛异常）。
PII 脱敏（安全设计 §4）：身份证/手机号/完整学号写入前掩码。
"""
import json
import logging
import re
import traceback

logger = logging.getLogger(__name__)

EVENT_CATEGORIES = frozenset(
    {"ocr", "llm", "breaker", "auth", "upload", "db", "security", "system"})
EVENT_LEVELS = frozenset({"debug", "info", "warning", "error", "critical"})

# PII 掩码（写入前；匹配→保留首尾片段）
_PII_RULES = (
    (re.compile(r"\d{17}[\dXx]"), lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:]),   # 身份证 18 位
    (re.compile(r"\d{15}[\dXx]"), lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:]),   # 身份证 15 位
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:]),  # 手机号
    (re.compile(r"(?<!\d)(2\d{7})\d(?!\d)"), lambda m: m.group(1) + "****"),              # 学号 9 位（21/20 开头）
)


def _sanitize(text: str) -> str:
    """PII 掩码：身份证/手机号保留首尾，学号保留前 8 位。"""
    if not text:
        return text
    for pattern, repl in _PII_RULES:
        text = pattern.sub(repl, text)
    return text


class SystemEventLogger:
    """系统事件写入器（进程级单例用法：直接调用类方法）。"""

    _db_path = None

    @classmethod
    def _get_db_path(cls):
        if cls._db_path is None:
            from config.loader import ConfigLoader
            cls._db_path = str(ConfigLoader().get_path('database', 'competitions_db'))
        return cls._db_path

    @classmethod
    def _ensure_table(cls, conn) -> None:
        """兜底建表（老库首次调用自动建；正常由迁移 0006 建立）。"""
        conn.execute("""CREATE TABLE IF NOT EXISTS system_event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_category VARCHAR(20) NOT NULL CHECK(event_category IN (
                'ocr','llm','breaker','auth','upload','db','security','system')),
            event_level VARCHAR(10) NOT NULL CHECK(event_level IN (
                'debug','info','warning','error','critical')),
            event_message TEXT NOT NULL,
            trace_id VARCHAR(64),
            operator_id INTEGER REFERENCES users(id),
            operator_code VARCHAR(50),
            detail TEXT,
            source_module VARCHAR(100),
            source_file VARCHAR(200),
            source_line INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    @classmethod
    def log(cls, category: str, level: str, message: str, *,
            trace_id=None, operator=None, detail=None,
            source_module=None, source_file=None, source_line=None) -> bool:
        """写入一条系统事件。任何失败只 warning，绝不向调用方抛异常。

        Args:
            category: 事件类别（EVENT_CATEGORIES 之一；非法值拒绝写入返回 False）
            level: 级别（EVENT_LEVELS 之一）
            message: 消息（经 PII 脱敏）
            operator: 可选 dict{id, code} 或 Flask session 自动解析
            detail: 可选 dict/list（JSON 序列化后脱敏）
        Returns:
            是否写入成功（False=已吞掉的失败，调用方无需处理）。
        """
        try:
            if category not in EVENT_CATEGORIES:
                logger.warning("[system_event] 非法事件类别: %s", category)
                return False
            if level not in EVENT_LEVELS:
                logger.warning("[system_event] 非法事件级别: %s", level)
                return False

            # R-028 治本：库文件不存在直接跳过——sqlite3.connect 对不存在路径会静默建空文件
            # （CI 曾因此被 create_app 启动事件建出空 competitions.db，3 个真实库用例由
            # skip 变挂）。无库环境（CI/新环境）不落事件属预期，debug 级不刷 warning 噪声。
            from pathlib import Path as _P
            db_file = _P(cls._get_db_path())
            if not db_file.exists():
                logger.debug("[system_event] 库不存在，跳过事件写入: %s", db_file)
                return False

            # operator 解析（复用 AuditLogger 语义：显式 dict > Flask session）
            op_id, op_code = None, None
            if isinstance(operator, dict) and operator.get("code"):
                op_id, op_code = operator.get("id"), str(operator["code"])
            else:
                try:
                    from flask import session
                    uid = session.get("user_id")
                    if uid:
                        op_id, op_code = uid, str(uid)
                except Exception:
                    pass

            msg = _sanitize(str(message))
            detail_json = None
            if detail is not None:
                try:
                    detail_json = _sanitize(json.dumps(detail, ensure_ascii=False, default=str))
                except Exception:
                    detail_json = _sanitize(str(detail))

            from backend.utils.db_connection import get_connection
            conn = get_connection(cls._get_db_path())
            try:
                cls._ensure_table(conn)
                conn.execute(
                    """INSERT INTO system_event_log
                       (event_category, event_level, event_message, trace_id,
                        operator_id, operator_code, detail,
                        source_module, source_file, source_line)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (category, level, msg, trace_id, op_id, op_code, detail_json,
                     source_module, source_file, source_line))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001 —— 契约：事件写入失败不阻塞主业务
            logger.warning("[system_event] 写入失败（已吞掉）: category=%s err=%s", category, e)
            return False

    @classmethod
    def from_exception(cls, exc: BaseException, category: str = "system", level: str = "error", *,
                       message=None, **kwargs) -> bool:
        """从异常对象自动填充 message/traceback/source 写入事件。"""
        msg = message or f"{type(exc).__name__}: {exc}"
        tb = traceback.extract_tb(exc.__traceback__)
        source_file, source_line = None, None
        if tb:
            source_file, source_line = tb[-1].filename, tb[-1].lineno
        detail = {"error_type": type(exc).__name__,
                  "stack_trace": "".join(traceback.format_exception(exc))[:4000]}
        return cls.log(category, level, msg, source_file=source_file,
                       source_line=source_line, detail=detail, **kwargs)
