"""登录失败锁定（P2-25 落库版，不依赖 Redis）。

安全设计 §2.4：flask-limiter + Redis 为完整方案；本模块实现设计明确的
`failed_logins` 落库兜底（账号级锁定）——SQLite 表多 worker 天然共享计数，
单机/多 worker 均有效，无需 Redis。锁定统一提示（不区分账号是否存在，防枚举）。

阈值（可调）：账号连续失败 5 次锁 15 分钟；IP 窗口 1 分钟失败 10 次锁 5 分钟。
"""
import sqlite3
from datetime import datetime, timedelta

from backend.utils.db_connection import get_connection

# 账号维度
ACCOUNT_MAX_FAIL = 5
ACCOUNT_LOCK_MINUTES = 15
# IP 维度
IP_WINDOW_MINUTES = 1
IP_MAX_FAIL = 10
IP_LOCK_MINUTES = 5

_DDL = """CREATE TABLE IF NOT EXISTS failed_logins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login_code TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    fail_count INTEGER NOT NULL DEFAULT 0,
    first_fail_at TEXT NOT NULL,
    lock_until TEXT,
    updated_at TEXT NOT NULL
)"""
# 复合索引：账号/IP 查询路径
_DDL_IDX = "CREATE INDEX IF NOT EXISTS idx_failed_logins_code ON failed_logins(login_code)"


def _now() -> datetime:
    return datetime.now()


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def _ensure_table(conn) -> None:
    conn.execute(_DDL)
    conn.execute(_DDL_IDX)
    conn.commit()


def check_login_allowed(db_path: str, login_code: str, ip: str):
    """检查是否允许登录尝试。

    Returns:
        (allowed: bool, retry_after_seconds: int|None)
        allowed=False 时 retry_after 为剩余锁定秒数（0=即刻已到）。
    """
    conn = get_connection(db_path)
    try:
        _ensure_table(conn)
        # 账号锁定优先（存在且未过期）
        for key, col in ((login_code, "login_code"), (ip, "ip")):
            if not key:
                continue
            row = conn.execute(
                f"SELECT lock_until FROM failed_logins WHERE {col}=? "
                "ORDER BY id DESC LIMIT 1", (key,)).fetchone()
            if row and row[0]:
                lock_until = _parse(row[0])
                if lock_until > _now():
                    return False, max(1, int((lock_until - _now()).total_seconds()))
        return True, None
    finally:
        conn.close()


def record_login_failure(db_path: str, login_code: str, ip: str) -> None:
    """记录一次失败（账号 + IP 双维度计数，跨窗口自动重置）。"""
    now = _now()
    conn = get_connection(db_path)
    try:
        _ensure_table(conn)
        # 账号/IP 维度各用独立行（账号行 ip=''、IP 行 login_code=''），
        # 否则两维度 WHERE 命中同一行致计数叠加（5 次变 10 次误触 IP 锁）
        for key, col, other, window_min, max_fail, lock_min in (
            (login_code, "login_code", "ip", ACCOUNT_LOCK_MINUTES, ACCOUNT_MAX_FAIL, ACCOUNT_LOCK_MINUTES),
            (ip, "ip", "login_code", IP_WINDOW_MINUTES, IP_MAX_FAIL, IP_LOCK_MINUTES),
        ):
            if not key:
                continue
            row = conn.execute(
                f"SELECT id, fail_count, first_fail_at FROM failed_logins "
                f"WHERE {col}=? AND {other}='' ORDER BY id DESC LIMIT 1", (key,)).fetchone()
            if row and (now - _parse(row[2])).total_seconds() <= window_min * 60:
                fail_count = row[1] + 1
                first = row[2]
            else:
                fail_count = 1
                first = _fmt(now)
            lock_until = _fmt(now + timedelta(minutes=lock_min)) if fail_count >= max_fail else None
            # 阶段六 L1：锁定触发落系统事件（security 关注项；写入失败已吞）
            if lock_until:
                from backend.utils.system_event_logger import SystemEventLogger
                SystemEventLogger.log(
                    "auth", "warning",
                    f"登录锁定触发（{col}={key}，连续失败 {fail_count} 次，锁定 {lock_min} 分钟）",
                    detail={"fail_count": fail_count, "lock_until": lock_until},
                    source_module="backend.utils.login_guard")
            if row:
                conn.execute(
                    f"UPDATE failed_logins SET fail_count=?, first_fail_at=?, "
                    f"lock_until=?, updated_at=? WHERE id=?", (fail_count, first, lock_until, _fmt(now), row[0]))
            else:
                # 独立行：本维度填 key，另一维度置空（隔离计数）
                code_val, ip_val = (login_code, "") if col == "login_code" else ("", ip)
                conn.execute(
                    f"INSERT INTO failed_logins (login_code, ip, fail_count, first_fail_at, "
                    f"lock_until, updated_at) VALUES (?,?,?,?,?,?)",
                    (code_val, ip_val, fail_count, first, lock_until, _fmt(now)))
        conn.commit()
    finally:
        conn.close()


def record_login_success(db_path: str, login_code: str, ip: str) -> None:
    """登录成功：清空该账号与 IP 的失败计数（解锁）。"""
    conn = get_connection(db_path)
    try:
        _ensure_table(conn)
        conn.execute("DELETE FROM failed_logins WHERE login_code=?", (login_code,))
        conn.execute("DELETE FROM failed_logins WHERE ip=?", (ip,))
        conn.commit()
    finally:
        conn.close()
