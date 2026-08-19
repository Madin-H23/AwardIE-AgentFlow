"""users 表双写同步（8.5 渐进第一批：旧三表仍是写路径真源，users 需保持同步）。

下批引用重写后写路径切 users 为真源、旧表转视图，本模块退役。
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)


def sync_user_row(db_path, login_code: str, **fields) -> bool:
    """把旧表写操作镜像到 users 行（按 login_code 定位）。best-effort：失败仅告警。

    支持：password_hash / needs_password_change / name / phone / qq / skills /
          user_activated / major / grade / title / department
    """
    if not fields:
        return False
    allowed = {"password_hash", "needs_password_change", "name", "phone", "qq", "skills",
               "user_activated", "major", "grade", "title", "department"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    try:
        from backend.utils.db_connection import get_connection
        conn = get_connection(db_path)
        try:
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE users SET {sets}, updated_at=CURRENT_TIMESTAMP "
                         "WHERE login_code=?", (*updates.values(), login_code))
            conn.commit()
            return True
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("[users_sync] 同步失败(已吞): login_code=%s err=%s", login_code, e)
        return False


def insert_user_row(db_path, login_code: str, name: str, role: str,
                    password_hash: str = None, needs_password_change: int = 0, **extra) -> bool:
    """旧表新增用户时镜像插入 users 行（INSERT OR IGNORE 幂等）。best-effort。"""
    try:
        from backend.utils.db_connection import get_connection
        conn = get_connection(db_path)
        try:
            conn.execute(
                """INSERT OR IGNORE INTO users
                   (login_code, name, role, password_hash, needs_password_change,
                    major, grade, title, department, phone, qq, skills, user_activated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (login_code, name, role, password_hash, needs_password_change,
                 extra.get("major"), extra.get("grade"), extra.get("title"),
                 extra.get("department"), extra.get("phone"), extra.get("qq"),
                 extra.get("skills")))
            conn.commit()
            return True
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("[users_sync] 插入失败(已吞): login_code=%s err=%s", login_code, e)
        return False


def to_users_id(db_path, business_code: str, user_type: str):
    """业务号(学号/工号/用户名)→users.id（路径 A 桥接：session 业务号写入时映射）。

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
