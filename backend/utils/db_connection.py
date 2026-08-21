"""统一数据库连接工厂（P0-4 / P0-5 / P0-7 修复）。

设计依据：《数据库设计》第二章 G1 连接契约——所有 SQLite 连接必须经本工厂，
禁止裸 sqlite3.connect（CI 静态门禁 grep）。

强制契约（每次连接生效）：
- PRAGMA foreign_keys = ON      外键约束启用（P0-4：修复前实测已产生 4 条孤儿数据）
- PRAGMA journal_mode = WAL     写前日志（P0-5：修复并发写锁竞争；幂等，首次后持久化于库文件）
- PRAGMA busy_timeout = 30000   锁等待 30s（P0-7：修复多 worker 下立即抛 database is locked）
"""
import sqlite3
from pathlib import Path

_BUSY_TIMEOUT_MS = 30000


def get_connection(db_path, *, row_factory: bool = True, timeout: float = 30.0) -> sqlite3.Connection:
    """获取带强制契约的 SQLite 连接。

    Args:
        db_path: 库文件路径（str/Path）
        row_factory: True 时行对象为 sqlite3.Row（兼容索引访问，另支持按列名访问）
        timeout: sqlite3 层连接超时（秒），与 busy_timeout 语义配合
    """
    try:
        conn = sqlite3.connect(str(db_path), timeout=timeout)
        if row_factory:
            conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA journal_mode = WAL")
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        return conn
    except sqlite3.Error as e:
        # T56 接入点：DB 连接失败落系统事件（db 类；写入失败已吞，异常照常上抛）
        try:
            from backend.utils.system_event_logger import SystemEventLogger
            SystemEventLogger.log(
                "db", "error",
                f"数据库连接失败: {type(e).__name__}: {e}",
                detail={"db_path": str(db_path)},
                source_module="backend.utils.db_connection")
        except Exception:  # noqa: BLE001
            pass
        raise
