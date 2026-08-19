"""users 业务号 → users.id 桥接（M1 后半③③ 双写收尾后仅存函数）。

历史：8.5 渐进原为旧表真源 + users 双写（sync_user_row/insert_user_row 已随视图化退役）；
现 users 为唯一真源、旧三表为视图，仅保留业务号→users.id 映射桥接（session 业务号写入时用）。
"""
import logging

logger = logging.getLogger(__name__)


def to_users_id(db_path, business_code: str, user_type: str):
    """业务号(学号/工号/用户名)→users.id（session 业务号写入时映射）。

    user_type: 'student'|'teacher'|'admin'。查不到返回 None（调用方降级）。
    """
    if not business_code:
        return None
    try:
        from backend.utils.db_connection import get_connection
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT id FROM users WHERE login_code=? AND role=?",
                (business_code, user_type)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception as e:
        logger.warning("[users_sync] to_users_id 失败(已吞): code=%s err=%s", business_code, e)
        return None
