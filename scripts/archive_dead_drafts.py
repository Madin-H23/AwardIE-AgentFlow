"""T70：失效导入草稿归档订正（决策分析 P2 批2）。

背景：库中残留 2026-02 月批量的 status='pending' 导入草稿（约 39 条，含当时
OCR/LLM 结论），长期滞留 dashboard「待提交」计数。用户拍板归档处理。

判据（超期口径）：status='pending' 且 created_at 早于 --days 天（默认 30）。
不依赖会话表（schema 无导入会话持久化表）；近期草稿不受影响。

安全设计（沿用 restore_awards_history 模式）：
- 默认 dry-run 仅预览；--apply 才执行
- apply 前强制守卫备份（wal_checkpoint 后整库拷贝）
- 只改 status → 'archived'（软归档，保留 OCR/LLM 结论），零物理删除
- 执行后 integrity_check 自检

用法：
    python scripts/archive_dead_drafts.py            # 预览
    python scripts/archive_dead_drafts.py --apply    # 执行（自动备份）
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _real_db_path() -> Path:
    from config.loader import ConfigLoader
    return Path(ConfigLoader().get_path("database", "competitions_db"))


def _checkpoint_copy(src: Path, dst: Path):
    conn = sqlite3.connect(str(src))
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    shutil.copy2(src, dst)


def main():
    ap = argparse.ArgumentParser(description="归档超期导入草稿")
    ap.add_argument("--days", type=int, default=30,
                    help="超期天数阈值（默认 30）")
    ap.add_argument("--apply", action="store_true",
                    help="实际执行（默认 dry-run 仅预览）")
    args = ap.parse_args()

    db = _real_db_path()
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cutoff = f"-{args.days} days"
    match = conn.execute(
        """SELECT id, achievement_type, submitter_type, submitter_id, created_at
           FROM pending_achievements
           WHERE status='pending' AND created_at < datetime('now','localtime', ?)
           ORDER BY id""", (cutoff,)).fetchall()
    total_pending = conn.execute(
        "SELECT COUNT(*) FROM pending_achievements WHERE status='pending'").fetchone()[0]

    print(f"[scope] status='pending' 且 created_at < {args.days} 天前：{len(match)} 条"
          f"（当前 pending 总数 {total_pending}）")
    for r in match[:10]:
        print(f"  #{r['id']} {r['achievement_type']} submitter={r['submitter_type']}/{r['submitter_id']}"
              f" created={r['created_at']}")
    if len(match) > 10:
        print(f"  ... 其余 {len(match)-10} 条略")

    if not args.apply:
        print("[dry-run] 未做任何修改。确认无误后加 --apply 执行。")
        conn.close()
        return

    stamp = date.today().isoformat()
    snap = db.parent / "snapshots"
    snap.mkdir(exist_ok=True)
    bak = snap / f"bak.{stamp}-pre-archive-drafts.db"
    _checkpoint_copy(db, bak)
    print(f"[guard] 备份完成: {bak.name}")

    cur = conn.execute(
        """UPDATE pending_achievements SET status='archived'
           WHERE status='pending' AND created_at < datetime('now','localtime', ?)""",
        (cutoff,))
    conn.commit()
    after = conn.execute(
        "SELECT COUNT(*) FROM pending_achievements WHERE status='pending'").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    print(f"[apply] 已归档 {cur.rowcount} 条 → status='archived'；剩余 pending={after}")
    print(f"[verify] integrity_check={integrity}")
    if integrity != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
