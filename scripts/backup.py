"""全量备份（部署设计 §5：SQLite 三库 + chroma + files + .env，30 天滚动）。

用法（cron 每日 02:00）：
    python scripts/backup.py
    # crontab: 0 2 * * * cd /path && venv/bin/python scripts/backup.py >> logs/backup.log 2>&1
"""
import logging
import shutil
import sqlite3
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backup")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = PROJECT_ROOT / "database" / "backups"
RETAIN_DAYS = 30

TARGETS = {
    "competitions.db": "database/competitions.db",
    "ocr_cache.db": "database/ocr_cache.db",
    "extract_cache.db": "database/extract_cache.db",
    "chroma/": "database/chroma",
    "files/": "files",
}


def integrity_check(db: Path) -> bool:
    try:
        conn = sqlite3.connect(str(db))
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        conn.close()
        return ok
    except Exception as e:
        logger.error("integrity_check 失败 %s: %s", db, e)
        return False


def checkpoint(db_path: Path) -> None:
    """WAL checkpoint（A5/A6 发现）：copy2 只备份主文件、不带 -wal/-shm，
    未 checkpoint 的写入/删除会丢失或残留（表现为备份计数与主库不一致）。
    备份前 TRUNCATE checkpoint 把 WAL 全部合并进主文件。"""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception as e:
        logger.warning("WAL checkpoint 失败 %s: %s", db_path, e)


def main():
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest_dir = BACKUP_ROOT / stamp
    dest_dir.mkdir(parents=True, exist_ok=True)

    ok_all = True
    for name, rel in TARGETS.items():
        src = PROJECT_ROOT / rel
        if not src.exists():
            logger.info("跳过（不存在）: %s", rel)
            continue
        try:
            d = dest_dir / name
            d.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, d)
            else:
                if name.endswith(".db"):
                    checkpoint(src)  # WAL 合并进主文件再拷贝，保证副本与主库一致
                shutil.copy2(src, d)
                if name.endswith(".db") and not integrity_check(d):
                    logger.error("备份库完整性校验失败: %s", name)
                    ok_all = False
            logger.info("✓ %s", rel)
        except Exception as e:
            logger.error("备份失败 %s: %s", rel, e)
            ok_all = False

    # .env 单独（含密钥，权限收紧）
    env = PROJECT_ROOT / ".env"
    if env.exists():
        try:
            shutil.copy2(env, dest_dir / "env.bak")
            logger.info("✓ .env")
        except Exception as e:
            logger.error("备份 .env 失败: %s", e)
            ok_all = False

    # 抽样对账（随机 3 表 COUNT）
    try:
        src_db = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
        bak_db = sqlite3.connect(str(dest_dir / "competitions.db"))
        for t in ("students", "awards", "pending_achievements"):
            a = src_db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            b = bak_db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            assert a == b, f"{t} 计数不一致 {a}!={b}"
        src_db.close(); bak_db.close()
        logger.info("✓ 对账 3 表计数一致")
    except Exception as e:
        logger.error("对账失败: %s", e)
        ok_all = False

    # 滚动清理 30 天前
    cutoff = time.time() - RETAIN_DAYS * 86400
    removed = 0
    for d in BACKUP_ROOT.iterdir():
        if d.is_dir() and d.stat().st_mtime < cutoff:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    if removed:
        logger.info("清理 %d 个过期备份（>%d天）", removed, RETAIN_DAYS)

    logger.info("备份%s: %s", "成功" if ok_all else "完成但存在问题", dest_dir)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
