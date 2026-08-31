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


def pg_column_kinds(pgcur, table):
    """列名→规范化类别映射(#22):ts=timestamptz / json=jsonb / bool=boolean / raw=其余。"""
    pgcur.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s", (table,))
    kinds = {}
    for name, dtype in pgcur.fetchall():
        if dtype == "timestamp with time zone":
            kinds[name] = "ts"
        elif dtype == "jsonb":
            kinds[name] = "json"
        elif dtype == "boolean":
            kinds[name] = "bool"
        else:
            kinds[name] = "raw"
    return kinds


def normalize_row(row):
    """按值形态归一一行(#22):datetime 统一本地墙上时间;jsonb 文本/对象键序排序;bool→0/1。"""
    import datetime
    out = []
    for v in row:
        if isinstance(v, datetime.datetime):
            # timestamptz(aware)转本地墙上时间,与 sqlite 文本同构;naive 保持
            if v.tzinfo is not None:
                v = v.astimezone().replace(tzinfo=None)
            out.append(v.isoformat(sep=" "))
        elif isinstance(v, bool):
            out.append(int(v))
        elif isinstance(v, (bytes, memoryview)):
            out.append(hashlib.md5(bytes(v)).hexdigest())  # BLOB/bytea 按内容 md5 归一
        elif isinstance(v, (dict, list)):
            out.append(json.dumps(v, ensure_ascii=False, sort_keys=True))
        elif isinstance(v, str) and v[:1] in ("{", "["):
            try:
                out.append(json.dumps(json.loads(v), ensure_ascii=False, sort_keys=True))
            except Exception:
                out.append(v)
        elif isinstance(v, str):
            # sqlite 时间文本 → naive datetime 归一(与 PG 侧同构);非时间文本原样
            try:
                out.append(datetime.datetime.fromisoformat(v).isoformat(sep=" "))
            except Exception:
                out.append(v)
        else:
            out.append(v)
    return out


def fingerprint_normalized(rows):
    """规范化指纹:值归一后排序累积 md5。"""
    norm = sorted(json.dumps(normalize_row(list(r)), ensure_ascii=False, default=str) for r in rows)
    return hashlib.md5("\n".join(norm).encode("utf-8")).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", default="database/competitions.db")
    ap.add_argument("--dsn", default="host=127.0.0.1 port=5433 dbname=awardie_dev user=postgres")
    args = ap.parse_args()

    sq, sqcur, tables, ddl, cols, fks, indexes, seq, views = probe_sqlite(args.sqlite)

    # 已知清洗列(迁移设计内差异,#5/#15 记录):比对时双侧剔除,信号只留真实分叉
    KNOWN_CLEANED = {
        "review_logs": ["reviewer_id"],            # 435 行 'admin'→NULL
        "achievement_audit_log": ["operator_id"],  # 3 行 'admin'→NULL
        "awards": ["llm_response"],                # 1 行非法 JSON→NULL
    }
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
            cleaned = KNOWN_CLEANED.get(t, [])
            sel_cols = "*" if not cleaned else ", ".join(
                c for c in (x["name"] for x in cols[t]) if c not in cleaned)
            s_rows = [tuple(r) for r in sqcur.execute(f'SELECT {sel_cols} FROM "{t}" ORDER BY 1')]
            pgcur.execute(f'SELECT {sel_cols} FROM "{t}" ORDER BY 1')
            p_rows = [tuple(r) for r in pgcur.fetchall()]
            # 值形态归一后指纹(#22):datetime ISO 化/bool→0-1/jsonb 键序排序,双侧同构可比
            s_fp = fingerprint_normalized(s_rows)
            p_fp = fingerprint_normalized(p_rows)
        except Exception as e:  # noqa: BLE001
            diffs.append(f"{t}: 指纹异常 {str(e)[:60]}")
            continue
        if s_count != p_count:
            diffs.append(f"{t}: 行数 sqlite={s_count} pg={p_count}(共存期分叉或清洗差异)")
        elif s_fp != p_fp:
            diffs.append(f"{t}: 行数同({s_count})但规范化指纹不同(存在真实字段差异)")
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
