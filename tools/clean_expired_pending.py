"""
定时清理超时的 pending 记录（status='pending'）及对应 temp_upload 会话目录与文件。

- 删除条件：status='pending' 且 created_at 早于配置的过期时间（默认 30 分钟）。
- 同时删除 files/temp_upload 下对应会话目录及文件；若会话内无其他 pending 引用则删除整目录。

配置：config/settings.json 中 "pending_cleanup"."expire_minutes"（默认 30）。

用法：
  python tools/clean_expired_pending.py           # 执行清理
  python tools/clean_expired_pending.py --dry-run # 仅打印将删除的条数，不执行

定时任务示例：
  - Linux cron: 每 15 分钟执行一次
     */15 * * * * cd /path/to/project && python tools/clean_expired_pending.py
  - Windows 计划任务：创建每 15 分钟运行一次的任务，程序 python，参数 tools/clean_expired_pending.py，起始于项目根目录
"""
import argparse
import logging
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Optional

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _get_config():
    """从 config/settings.json 读取配置，禁止硬编码路径。"""
    from config.loader import get_config
    loader = get_config()
    config = loader.load_config()
    db_path = loader.get_path("database", "competitions_db")
    expire_minutes = config.get("pending_cleanup", {}).get("expire_minutes", 30)
    if not isinstance(expire_minutes, (int, float)) or expire_minutes <= 0:
        raise ValueError("config pending_cleanup.expire_minutes 必须为正数")
    return db_path, expire_minutes


def _get_file_manager():
    """获取统一文件管理器（用于 resolve_path、files_root）。"""
    from backend.services.unified_file_manager import get_unified_file_manager
    return get_unified_file_manager()


def _session_id_from_file_path(file_path: str) -> Optional[str]:
    """从 file_path 提取会话 ID：temp_upload/session_id/xxx -> session_id。"""
    if not file_path or not file_path.strip():
        return None
    parts = file_path.replace("\\", "/").strip().split("/")
    if len(parts) >= 2 and parts[0].rstrip("/") == "temp_upload":
        return parts[1]
    return None


def select_expired_pending(cursor, expire_minutes: int):
    """查询过期待删的 pending 记录。返回 [(id, file_path, session_id), ...]。"""
    cursor.execute(
        """
        SELECT id, file_path, session_id
        FROM pending_achievements
        WHERE status = 'pending'
          AND datetime(created_at) < datetime('now', 'localtime', '-' || ? || ' minutes')
        """,
        (int(expire_minutes),),
    )
    return cursor.fetchall()


def remaining_refs_to_session(cursor, session_id: str) -> int:
    """统计仍引用该 session 的 pending 条数（session_id 或 file_path 前缀）。"""
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM pending_achievements
        WHERE session_id = ? OR file_path LIKE ?
        """,
        (session_id, f"temp_upload/{session_id}/%"),
    )
    return cursor.fetchone()[0]


def run(dry_run: bool = False) -> dict:
    """
    执行过期 pending 清理。

    Returns:
        dict: deleted_count, files_deleted, sessions_removed, errors
    """
    db_path, expire_minutes = _get_config()
    fm = _get_file_manager()
    temp_upload_dir = fm.files_root / "temp_upload"

    result = {"deleted_count": 0, "files_deleted": 0, "sessions_removed": 0, "errors": []}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 检查表
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pending_achievements'"
    )
    if not cursor.fetchone():
        conn.close()
        logger.info("pending_achievements 表不存在，跳过")
        return result

    rows = select_expired_pending(cursor, expire_minutes)
    if not rows:
        conn.close()
        logger.info("无超过 %s 分钟的 pending 记录，跳过", expire_minutes)
        return result

    ids = [r[0] for r in rows]
    # 收集 session_id：优先列 session_id，否则从 file_path 解析
    session_ids_from_deleted = set()
    file_paths_to_delete = []

    for row in rows:
        _id, file_path, session_id = row
        sid = session_id if session_id else _session_id_from_file_path(file_path or "")
        if sid:
            session_ids_from_deleted.add(sid)
        if file_path and (file_path.startswith("temp_upload/") or file_path.startswith("temp_upload")):
            file_paths_to_delete.append(file_path)

    if dry_run:
        conn.close()
        logger.info("[dry-run] 将删除 pending 记录 %s 条，涉及会话 %s 个", len(ids), len(session_ids_from_deleted))
        result["deleted_count"] = len(ids)
        return result

    # 1. 删除物理文件（在删库记录之前，以便用 count 判断是否可删会话）
    for rel_path in file_paths_to_delete:
        try:
            full = fm.resolve_path(rel_path)
            if full.exists():
                full.unlink()
                result["files_deleted"] += 1
        except Exception as e:
            result["errors"].append(f"删除文件 {rel_path}: {e}")
            logger.warning("删除文件失败: %s", e)

    # 2. 删除数据库记录
    cursor.executemany("DELETE FROM pending_achievements WHERE id = ?", [(i,) for i in ids])
    result["deleted_count"] = cursor.rowcount
    conn.commit()

    # 3. 对每个被删记录涉及的 session_id，若无剩余引用则删除会话目录
    for sid in session_ids_from_deleted:
        if remaining_refs_to_session(cursor, sid) > 0:
            continue
        session_dir = temp_upload_dir / sid
        if not session_dir.exists():
            continue
        try:
            shutil.rmtree(session_dir)
            result["sessions_removed"] += 1
            logger.info("已删除会话目录: %s", session_dir)
        except Exception as e:
            result["errors"].append(f"删除目录 {session_dir}: {e}")
            logger.warning("删除会话目录失败: %s", e)

    conn.close()
    logger.info(
        "清理完成: 删除 pending %s 条, 文件 %s 个, 会话目录 %s 个",
        result["deleted_count"],
        result["files_deleted"],
        result["sessions_removed"],
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="清理超过规定时间的 pending 记录及 temp_upload 会话与文件")
    parser.add_argument("--dry-run", action="store_true", help="仅统计并打印将删除的条数，不执行删除")
    args = parser.parse_args()
    res = run(dry_run=args.dry_run)
    if res["errors"]:
        for err in res["errors"]:
            logger.error("%s", err)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
