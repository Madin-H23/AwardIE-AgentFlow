"""历史 awards 数据恢复（T62）：从 pre-0010 备份去重合并 197 行历史成果进主库。

背景：R-031（_save_award 缺 commit）修复前，awards 写入从未落库——主库只剩
少量测试残留；最后一份含完整业务成果的快照是 database/bak.2026-08-21-pre-0010.db
（0009 态，awards=197，id∈[860,1193]，197 个独立 image_hash）。本脚本把该快照的
awards 与 4 张关联表**去重合并**进主库（0011 态，列集已核对一致）。

安全设计：
- 默认 --dry-run 只出报告不动数据；--apply 才写入
- 仅插入主库不存在的 id；image_hash 已存在的行跳过并计数（防重复成果）
- 单事务 + 完成后 PRAGMA integrity_check / foreign_key_check 自检
- sqlite_sequence.awards 提升到 max(id)（防自增复用，R-032 教训）
- 幂等：重复运行自动跳过已并入行

用法：
    python scripts/restore_awards_history.py            # dry-run 报告
    python scripts/restore_awards_history.py --apply    # 实际恢复
"""
import argparse
import shutil
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_DB = PROJECT_ROOT / "database" / "competitions.db"
DEFAULT_BACKUP = PROJECT_ROOT / "database" / "bak.2026-08-21-pre-0010.db"

RELATED_TABLES = (
    "award_student_winners",
    "award_teacher_winners",
    "award_supervisors",
    "award_related_students",
)


def table_columns(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def precheck(main, bak):
    """列集一致性预检（0009 态 vs 0011 态应同名同序）。"""
    for t in ("awards",) + RELATED_TABLES:
        ca, cb = table_columns(bak, t), table_columns(main, t)
        if ca != cb:
            raise SystemExit(f"[FAIL] 列集不一致 {t}: 备份={ca} 主库={cb}")


def snapshot_counts(conn):
    c = conn.cursor()
    out = {"awards": c.execute("SELECT COUNT(*) FROM awards").fetchone()[0]}
    for t in RELATED_TABLES:
        out[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return out


def run(backup_path: Path, apply: bool):
    if not MAIN_DB.exists() or not backup_path.exists():
        raise SystemExit(f"[FAIL] 库文件缺失: main={MAIN_DB.exists()} backup={backup_path.exists()}")

    main = sqlite3.connect(str(MAIN_DB))
    main.row_factory = sqlite3.Row
    bak = sqlite3.connect(str(backup_path))
    bak.row_factory = sqlite3.Row
    precheck(main, bak)

    before = snapshot_counts(main)
    existing_ids = {r[0] for r in main.execute("SELECT id FROM awards")}
    existing_hashes = {r[0] for r in main.execute("SELECT image_hash FROM awards")}

    bak_rows = bak.execute("SELECT * FROM awards ORDER BY id").fetchall()
    to_insert, skipped_id, skipped_hash = [], [], []
    for row in bak_rows:
        if row["id"] in existing_ids:
            skipped_id.append(row["id"])
        elif row["image_hash"] and row["image_hash"] in existing_hashes:
            skipped_hash.append(row["id"])
        else:
            to_insert.append(row)

    print(f"[plan] 备份行={len(bak_rows)} 将并入={len(to_insert)} "
          f"id已存在跳过={len(skipped_id)} hash冲突跳过={len(skipped_hash)}")
    print(f"[plan] 恢复前 awards={before['awards']} 预期恢复后="
          f"{before['awards'] + len(to_insert)}")

    if not apply:
        print("[dry-run] 未修改任何数据。加 --apply 执行恢复。")
        return 0

    # 安全网：恢复前再留一份带时间戳的主库备份
    stamp = time.strftime("%Y%m%d_%H%M%S")
    guard = PROJECT_ROOT / "database" / f"bak.pre-restore-{stamp}.db"
    shutil.copy2(MAIN_DB, guard)
    print(f"[guard] 恢复前备份 -> {guard.name}")

    cols = table_columns(main, "awards")
    placeholders = ",".join("?" for _ in cols)
    col_list = ",".join(cols)
    inserted_ids = []
    try:
        main.execute("BEGIN")
        for row in to_insert:
            main.execute(
                f"INSERT INTO awards ({col_list}) VALUES ({placeholders})",
                tuple(row[c] for c in cols))
            inserted_ids.append(row["id"])

        # 关联表：只搬已并入 award 的关联行，且 (award_id, 对方id) 不存在才插
        related_stats = {}
        for t in RELATED_TABLES:
            rcols = table_columns(main, t)
            other_col = "student_id" if "student_id" in rcols else "teacher_id"
            rcols_b = table_columns(bak, t)
            n = 0
            for rrow in bak.execute(
                    f"SELECT * FROM {t} WHERE award_id IN ({','.join('?' for _ in inserted_ids)})",
                    inserted_ids):
                exists = main.execute(
                    f"SELECT 1 FROM {t} WHERE award_id=? AND {other_col}=?",
                    (rrow["award_id"], rrow[other_col])).fetchone()
                if exists:
                    continue
                main.execute(
                    f"INSERT INTO {t} ({','.join(rcols_b)}) VALUES ({','.join('?' for _ in rcols_b)})",
                    tuple(rrow[c] for c in rcols_b))
                n += 1
            related_stats[t] = n

        # 自增计数提升到 max(id)（防自增复用，R-032）
        max_id = main.execute("SELECT MAX(id) FROM awards").fetchone()[0]
        cur_seq = main.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='awards'").fetchone()
        if cur_seq is None:
            main.execute("INSERT INTO sqlite_sequence(name, seq) VALUES ('awards', ?)", (max_id,))
        elif cur_seq[0] < max_id:
            main.execute(
                "UPDATE sqlite_sequence SET seq=? WHERE name='awards'", (max_id,))

        main.commit()
    except Exception as e:
        main.rollback()
        raise SystemExit(f"[FAIL] 恢复失败已回滚: {e}")

    after = snapshot_counts(main)
    integrity = main.execute("PRAGMA integrity_check").fetchone()[0]
    fk = main.execute("PRAGMA foreign_key_check").fetchall()
    seq_row = main.execute(
        "SELECT seq FROM sqlite_sequence WHERE name='awards'").fetchone()
    main.close()
    bak.close()

    print("=" * 60)
    print(f"[done] awards {before['awards']} -> {after['awards']}（并入 {len(inserted_ids)}）")
    for t in RELATED_TABLES:
        print(f"       {t}: {before[t]} -> {after[t]}（并入 {related_stats[t]}）")
    print(f"[verify] integrity={integrity} fk_check={fk[:3]}{'...' if len(fk) > 3 else ''}"
          f"({'空' if not fk else len(fk)}条)")
    print(f"[verify] sqlite_sequence.awards={seq_row[0]} >= max(id)={max_id}: "
          f"{seq_row[0] >= max_id}")
    ok = (integrity == "ok" and not fk and after["awards"] == before["awards"] + len(inserted_ids)
          and seq_row[0] >= max_id)
    print(f"[result] {'全部校验通过' if ok else '存在校验失败项，见上'}")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", default=str(DEFAULT_BACKUP),
                    help="历史快照库路径（默认 pre-0010）")
    ap.add_argument("--apply", action="store_true", help="实际执行恢复（默认 dry-run）")
    args = ap.parse_args()
    sys.exit(run(Path(args.backup), args.apply))