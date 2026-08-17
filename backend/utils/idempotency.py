"""幂等键存储（T3 / 设计 API §1.3 / CR-4）。

多 worker 共享（SQLite 表，非内存——CR-4 教训）；阶段四迁 Redis 时仅换本模块实现。
用法：批量审核/导入路由加 @idempotent(ttl) 装饰器，客户端传 X-Idempotency-Key 头
（或 body.idempotency_key），10 分钟窗口内同 key 直接返回上次响应——防双击重复提交（P0-9 前端侧）。
"""
import functools
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

TTL_SECONDS = 600
_DB_PATH = None   # 惰性定位主库


def _db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        from config.loader import ConfigLoader
        _DB_PATH = Path(str(ConfigLoader().get_path('database', 'competitions_db')))
    return _DB_PATH


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS idempotency_keys (
        key TEXT PRIMARY KEY,
        response_json TEXT NOT NULL,
        status_code INTEGER NOT NULL DEFAULT 200,
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL)""")


def _gc(conn):
    """惰性清理过期键（写路径顺带，无需调度）。"""
    conn.execute("DELETE FROM idempotency_keys WHERE expires_at < ?", (time.time(),))


def get_stored_response(key: str):
    """命中返回 (response_dict, status_code)；未命中/过期返回 None。"""
    if not key:
        return None
    from backend.utils.db_connection import get_connection
    conn = get_connection(_db_path())
    try:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT response_json, status_code FROM idempotency_keys "
            "WHERE key=? AND expires_at > ?", (key, time.time())).fetchone()
        if row:
            return json.loads(row[0]), row[1]
        return None
    finally:
        conn.close()


def store_response(key: str, response: dict, status_code: int = 200, ttl: int = TTL_SECONDS) -> bool:
    """存储响应（best-effort：失败仅告警，不阻塞主响应返回）。"""
    if not key:
        return False
    try:
        from backend.utils.db_connection import get_connection
        conn = get_connection(_db_path())
        try:
            _ensure_table(conn)
            _gc(conn)
            conn.execute(
                "INSERT OR REPLACE INTO idempotency_keys (key, response_json, status_code, created_at, expires_at) "
                "VALUES (?,?,?,?,?)",
                (key, json.dumps(response, ensure_ascii=False), status_code, time.time(), time.time() + ttl))
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001 —— 幂等存储失败不影响主流程（下次重试仍会执行）
        logger.warning("[idempotency] 存储失败(已吞): key=%s err=%s", key, e)
        return False


def idempotent(ttl: int = TTL_SECONDS):
    """路由装饰器：同 key 在窗口内直接返回上次响应。

    key 优先取 X-Idempotency-Key 头，其次 body.idempotency_key；无 key 则透传（向后兼容）。
    仅对 JSON 响应生效；2xx/4xx/5xx 一并存储（重试语义：确定性结果都该复用）。
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import request
            key = request.headers.get('X-Idempotency-Key') or ''
            if not key:
                body = request.get_json(silent=True) or {}
                key = str(body.get('idempotency_key') or '')
            if key:
                hit = get_stored_response(key)
                if hit is not None:
                    from flask import jsonify
                    logger.info("[idempotency] 命中复用: key=%s", key[:12])
                    return jsonify(hit[0]), hit[1]
            result = fn(*args, **kwargs)
            # 解析 (body, status) 形态
            status = 200
            body = result
            if isinstance(result, tuple) and len(result) == 2:
                body, status = result
            if key:
                try:
                    payload = body.get_json() if hasattr(body, 'get_json') else body
                    if payload is not None:
                        store_response(key, payload, status, ttl)
                except Exception:
                    pass
            return result
        return wrapper
    return decorator
