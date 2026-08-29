"""影子比对(ADR-0002/T15):v1 SQLite 与 v2 PG 的数据一致性核验。

用途:窗口制切换前的 assurance——确认纵切面域数据在双库间一致(或如实暴露共存期分叉)。

比对维度:
  1. 30 表行数对比
  2. 每表内容指纹:按主键排序整行 md5(规范化后逐行累积)——行级差异可定位
  3. 差异表清单输出(共存期分叉是预期发现:长尾域 v1 继续写入,PG 副本停止演进)

用法:
    python scripts/shadow_compare.py \
        --sqlite database/competitions.db \
        --pg "host=127.0.0.1 port=5433 dbname=awardie_dev user=postgres"
"""
import argparse
import hashlib
import json
import sqlite3
import sys

import psycopg2

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from v2_migrate import probe_sqlite  # 复用侦察(表清单)  # noqa: E402


def fingerprint(rows):
    """规范化行集指纹:按全行 JSON 排序后累积 md5(与行序无关)。"""
    norm = sorted(json.dumps(list(r), ensure_ascii=False, default=str) for r in rows)
    return hashlib.md5("\n".join(norm).encode("utf-8")).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", default="database/competitions.db")
    ap.add_argument("--dsn", default="host=127.0.0.1 port=5433 dbname=awardie_dev user=postgres")
    args = ap.parse_args()

    sq, sqcur, tables, ddl, cols, fks, indexes, seq, views = probe_sqlite(args.sqlite)
    pg = psycopg2.connect(args.dsn)
    pgcur = pg.cursor()

    diffs, same = [], 0
    print(f"== 影子比对:{len(tables)} 表 ==")
    for t in tables:
        s_count = sqcur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        pgcur.execute(f'SELECT COUNT(*) FROM "{t}"')
        p_count = pgcur.fetchone()[0]
        # 内容指纹(列序按 sqlite 侧;pg 侧 SELECT 同名列序一致——baseline 由同一 DDL 生成)
        try:
            s_fp = fingerprint(sqcur.execute(f'SELECT * FROM "{t}" ORDER BY 1'))
            pgcur.execute(f'SELECT * FROM "{t}" ORDER BY 1')
            p_fp = fingerprint(pgcur.fetchall())
        except Exception as e:  # noqa: BLE001
            diffs.append(f"{t}: 指纹异常 {str(e)[:60]}")
            continue
        if s_count != p_count:
            diffs.append(f"{t}: 行数 sqlite={s_count} pg={p_count}(共存期分叉或清洗差异)")
        elif s_fp != p_fp:
            diffs.append(f"{t}: 行数同({s_count})但内容指纹不同(逐字段有差异)")
        else:
            same += 1
    print(f"\n一致 {same}/{len(tables)} 表")
    if diffs:
        print("差异表(共存期分叉定位):")
        for d in diffs:
            print("  -", d)
    print("""
口径说明:
  - 纵切面域(pending_achievements/awards/achievement_audit_log):v1 冻结后应零分叉;
    冻结前的新提交分叉为预期(增量补迁覆盖,见窗口切换 runbook)
  - 长尾域(v1 继续写入):分叉为预期,不属于缺陷
""")


if __name__ == "__main__":
    main()
