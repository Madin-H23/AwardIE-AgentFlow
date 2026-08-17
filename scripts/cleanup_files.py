"""成果文件定期清理（P1-9）。

清理范围（设计 SRS 5.4）：
1. 关联记录已删除（pending 物理删除但文件残留）——按 files 目录与库内 file_path 对账
2. 长期未提交的 pending（created_at < 180 天且 status='pending'）关联文件
3. 临时上传目录中孤儿文件（temp_upload 下无对应 pending 记录）

用法（cron 每日）：
    python scripts/cleanup_files.py [--dry-run]
    # crontab: 30 3 * * * cd /path && venv/bin/python scripts/cleanup_files.py >> logs/cleanup.log 2>&1
"""
import argparse
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cleanup")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PENDING_DAYS = 180


def main(dry_run: bool = True):
    sys.path.insert(0, str(PROJECT_ROOT))
    from config.loader import get_config
    from backend.utils.db_connection import get_connection

    cl = get_config()
    files_root = Path(str(cl.get_path("files")))
    db = str(cl.get_path("database", "competitions_db"))
    conn = get_connection(db)
    removed_bytes = 0
    removed_files = 0

    try:
        # 1) DB 中仍引用的文件路径集合（pending 未删除 + archived 保留）
        referenced = set()
        for (fp,) in conn.execute("SELECT file_path FROM pending_achievements WHERE file_path IS NOT NULL").fetchall():
            referenced.add(str(fp))

        # 2) 扫描 files 下所有文件
        for f in files_root.rglob("*"):
            if not f.is_file():
                continue
            rel = str(f.relative_to(files_root))
            if rel in referenced:
                continue
            # 孤儿（无任何 pending 引用）→ 清理
            logger.info("%s 清理孤儿文件: %s", "DRY" if dry_run else "删除", rel)
            if not dry_run:
                removed_bytes += f.stat().st_size
                removed_files += 1
                f.unlink()

        # 3) 长期未提交 pending（180 天）——仅清理其文件，不删记录（保守）
        rows = conn.execute(
            "SELECT id, file_path FROM pending_achievements "
            "WHERE status='pending' AND created_at < datetime('now', ?)",
            (f"-{PENDING_DAYS} days",),
        ).fetchall()
        for pid, fp in rows:
            if not fp:
                continue
            p = files_root / fp if not Path(fp).is_absolute() else Path(fp)
            if p.exists():
                logger.info("%s 清理长期未提交(pending %s)文件: %s", "DRY" if dry_run else "删除", pid, fp)
                if not dry_run:
                    removed_bytes += p.stat().st_size
                    removed_files += 1
                    p.unlink()
    finally:
        conn.close()

    logger.info("完成：%s %d 个文件，%.1f MB", "将清理" if dry_run else "已清理", removed_files, removed_bytes / 1024 / 1024)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="成果文件定期清理（P1-9）")
    ap.add_argument("--dry-run", action="store_true", default=True, help="演练模式（默认）")
    ap.add_argument("--apply", action="store_true", help="实际删除")
    args = ap.parse_args()
    main(dry_run=not args.apply)
