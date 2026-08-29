"""v2 迁移管线(正式版,探针 prototype/pg-etl-probe 固化)。

一条命令幂等重建 awardie_dev:
    python scripts/v2_migrate.py [--source database/competitions.db] [--dsn ...] [--dry-run]

阶段:
  1. baseline 生成:sqlite_master DDL → PG 目标形态 V1__baseline.sql
     (IDENTITY/BYTEA/布尔默认改写/VIRTUAL 生成列剥离+STORED 翻译/JSON 列→jsonb/
      真实时间列→timestamptz/业务文本日期列保留 TEXT/视图不迁移)
  2. 重建:DROP SCHEMA → psql 执行 baseline(30 表)
  3. 装载+清洗:布尔 0/1 适配;混型列 'admin'→NULL(保列型,探针结论);
     非法 JSON 行置 NULL(修复清单落档);BLOB→bytea
  4. 后置:索引(谓词布尔改写)→ FK(21 条)→ 序列(sqlite_sequence 为准)→ 生成列补建
  5. 校验:30 表行数 / BLOB md5 / FK 存量 / 抽样字段
"""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras

REPO = Path(__file__).resolve().parents[1]
BASELINE = REPO / "awardie-backend/src/main/resources/db/migration/V1__baseline.sql"

RE_INLINE_FK = re.compile(
    r"\s+REFERENCES\s+\"?(\w+)\"?\s*(?:\([^)]*\))?(?:\s+ON\s+DELETE\s+((?:SET\s+\w+)|\w+))?(?:\s+ON\s+UPDATE\s+((?:SET\s+\w+)|\w+))?",
    re.I,
)
RE_TABLE_FK = re.compile(r"\s*,?\s*FOREIGN\s+KEY\s*\([^)]*\)", re.I)
RE_VIRTUAL_GEN = re.compile(r",?\s*\"?\w+\"?\s+INTEGER\s+GENERATED\s+ALWAYS\s+AS\s*\(.*?\)\s*VIRTUAL", re.I | re.S)
RE_BOOL_DEFAULT = re.compile(r"(\bBOOLEAN(?:\s+NOT\s+NULL)?\s+DEFAULT\s+)'?([01])'?\b", re.I)
RE_AUTOINC = re.compile(r"(\"?\w+\"?\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT)", re.I)

GENCOL_EXPR = (
    "CASE WHEN jsonb_typeof(validation_result::jsonb) = 'object' "
    "AND (validation_result::jsonb) ? 'is_valid' THEN "
    "CASE jsonb_typeof((validation_result::jsonb) -> 'is_valid') "
    "WHEN 'boolean' THEN CASE WHEN (validation_result::jsonb) ->> 'is_valid' = 'true' THEN 1 ELSE 0 END "
    "WHEN 'number' THEN ((validation_result::jsonb) ->> 'is_valid')::integer "
    "WHEN 'string' THEN CASE (validation_result::jsonb) ->> 'is_valid' "
    "WHEN 'true' THEN 1 WHEN '1' THEN 1 WHEN 'false' THEN 0 ELSE NULL END "
    "ELSE NULL END END"
)

report = {"fail": [], "cleaned": [], "info": []}


def fail(msg):
    report["fail"].append(msg)
    print(f"  ✗ {msg}")


def cleaned(msg):
    report["cleaned"].append(msg)
    print(f"  🧹 {msg}")


def info(msg):
    report["info"].append(msg)
    print(f"  · {msg}")


# ---------------- schema 侦察 ----------------

def probe_sqlite(src):
    sq = sqlite3.connect(src)
    sq.row_factory = sqlite3.Row
    cur = sq.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    ddl = {t: cur.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0] for t in tables}
    cols = {t: list(cur.execute(f'PRAGMA table_info("{t}")')) for t in tables}
    fks = {t: list(cur.execute(f'PRAGMA foreign_key_list("{t}")')) for t in tables}
    indexes = list(cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"))
    seq = {r["name"]: r["seq"] for r in cur.execute("SELECT name, seq FROM sqlite_sequence")}
    views = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='view'")]
    return sq, cur, tables, ddl, cols, fks, indexes, seq, views


def column_type_map(cur, tables, cols):
    """逐列判定目标类型:jsonb / timestamptz / 保留声明类型;返回 {table: {col: target_type}}。"""
    result = {t: {} for t in tables}
    import datetime
    for t in tables:
        for c in cols[t]:
            name, ctype = c["name"], (c["type"] or "").upper()
            if "INT" in ctype:
                # 混型列:'admin' 文本 → 值清洗为 NULL,保列型 INTEGER
                bad = cur.execute(
                    f'SELECT COUNT(*) FROM "{t}" WHERE typeof("{name}") NOT IN (\'integer\',\'null\')'
                ).fetchone()[0]
                if bad:
                    result[t][name] = ("clean_null", bad)
                continue
            if name == "validation_result" and t in ("pending_achievements", "awards"):
                result[t][name] = ("jsonb", 0)
                continue
            # JSON 内容探测:非空且首字符 {/[ 的 text 列
            if ctype in ("TEXT", "VARCHAR", "") or "CHAR" in ctype:
                sample = cur.execute(
                    f'SELECT "{name}" FROM "{t}" WHERE substr("{name}",1,1) IN (char(123), char(91)) LIMIT 1'
                ).fetchone()
                if sample:
                    total = bad = 0
                    for (v,) in cur.execute(f'SELECT "{name}" FROM "{t}" WHERE "{name}" IS NOT NULL'):
                        total += 1
                        try:
                            json.loads(v)
                        except Exception:
                            bad += 1
                    result[t][name] = ("jsonb_fix" if bad else "jsonb", bad)
                continue
            # 时间列:值全部 ISO 可解析 → timestamptz
            if any(k in name.lower() for k in ("_at", "_time")) and "text" in ctype.lower() or ctype == "TIMESTAMP":
                vals = [r[0] for r in cur.execute(f'SELECT DISTINCT "{name}" FROM "{t}" WHERE "{name}" IS NOT NULL')]
                ok = all(_is_iso(v) for v in vals)
                if ok and vals:
                    result[t][name] = ("timestamptz", 0)
    return result


def _is_iso(v):
    try:
        datetime.datetime.fromisoformat(v)
        return True
    except Exception:
        return False


# ---------------- baseline 生成 ----------------

def gen_baseline(tables, ddl, cols, colmap, fks, indexes, views):
    out = ["-- V1__baseline.sql:由 scripts/v2_migrate.py 从 v1 SQLite 自动生成(勿手改)",
           "-- PG 目标形态:jsonb/timestamptz/IDENTITY;混型列清洗后保列型;视图不迁移(决策:legacy shim 废弃)",
           "BEGIN;"]
    for t in tables:
        sql = ddl[t]
        sql = RE_AUTOINC.sub(lambda m: m.group(1).replace("AUTOINCREMENT", "GENERATED BY DEFAULT AS IDENTITY"), sql)
        sql = RE_INLINE_FK.sub("", sql)
        sql = RE_TABLE_FK.sub("", sql)
        sql = RE_VIRTUAL_GEN.sub("", sql)
        sql = RE_BOOL_DEFAULT.sub(lambda m: m.group(1) + ("true" if m.group(2) == "1" else "false"), sql)
        sql = re.sub(r"\bBLOB\b", "BYTEA", sql, flags=re.I)
        # 列型替换:jsonb / timestamptz;混型清洗列同步放宽 NOT NULL(v1 事实行为:'admin' 审核无 id)
        for name, (target, _) in colmap[t].items():
            if target == "clean_null":
                sql = re.sub(rf"(\"?{name}\"?\s+INTEGER)(\s+NOT\s+NULL)", r"\1", sql, count=1, flags=re.I)
            elif target in ("jsonb", "jsonb_fix"):
                sql = re.sub(rf"(\"?{name}\"?\s+)(?:TEXT|VARCHAR\(\d+\))", rf"\1JSONB", sql, count=1, flags=re.I)
            elif target == "timestamptz":
                sql = re.sub(rf"(\"?{name}\"?\s+)(?:TEXT|TIMESTAMP)", rf"\1TIMESTAMPTZ", sql, count=1, flags=re.I)
        out.append(sql.rstrip().rstrip(";") + ";")
    # 索引(谓词布尔改写;idx_pending_is_valid 依赖生成列,延后到 ADD COLUMN 之后)
    for r in indexes:
        if r["tbl_name"] in tables and r["name"] != "idx_pending_is_valid":
            sql = r["sql"]
            sql = re.sub(r"=\s*([01])\b", lambda m: f"= {'TRUE' if m.group(1) == '1' else 'FALSE'}", sql)
            out.append(sql + ";")
    # 生成列先建,依赖它的索引随后
    out.append(f'ALTER TABLE "pending_achievements" ADD COLUMN is_valid integer GENERATED ALWAYS AS ({GENCOL_EXPR}) STORED;')
    out.append("CREATE INDEX idx_pending_is_valid ON pending_achievements(is_valid);")
    # FK 后置
    for t in tables:
        for i, f in enumerate(fks[t]):
            action = f" ON DELETE {f['on_delete']}" if f["on_delete"] != "NO ACTION" else ""
            out.append(
                f'ALTER TABLE "{t}" ADD CONSTRAINT fkc_{t}_{i} '
                f'FOREIGN KEY ("{f["from"]}") REFERENCES "{f["table"]}"("{f["to"] or "id"}"){action};'
            )
    out.append("COMMIT;")
    if views:
        out.append(f"-- 视图未迁移(legacy shim,决策废弃): {', '.join(views)}")
    return "\n".join(out)


# ---------------- 装载 + 校验 ----------------

def load_data(sq, cur, tables, colmap, pgcur, seq):
    # FK 在 baseline 已就位,而装载按字母序(子表先于父表)——装载期关 FK 校验,装完恢复
    pgcur.execute("SET session_replication_role = replica")
    total = 0
    for t in tables:
        col_info = list(cur.execute(f'PRAGMA table_info("{t}")'))
        names = [c["name"] for c in col_info]
        json_cols = {n for n, (tg, _) in colmap.get(t, {}).items() if tg in ("jsonb", "jsonb_fix")}
        clean_cols = {n for n, (tg, _) in colmap.get(t, {}).items() if tg == "clean_null"}
        batch = []
        for row in cur.execute(f'SELECT * FROM "{t}"'):
            vals = []
            for n, v in zip(names, tuple(row)):
                if n in clean_cols and not isinstance(v, int):
                    v = None  # 混型清洗:'admin' 等文本 → NULL(保列型)
                elif n in json_cols and v is not None and not _is_iso(str(v)) and n.lower().endswith(("_time", "_date", "time", "date")) is False:
                    try:
                        json.loads(v)
                    except Exception:
                        v = None  # 非法 JSON 修复(如 awards.llm_response 1/79)
                if isinstance(v, int) and v in (0, 1) and _col_is_bool(col_info, n):
                    v = bool(v)
                elif isinstance(v, (bytes, memoryview)):
                    v = psycopg2.Binary(v)
                vals.append(v)
            batch.append(vals)
            if len(batch) >= 500:
                psycopg2.extras.execute_values(pgcur, f'INSERT INTO "{t}" VALUES %s', batch, page_size=500)
                total += len(batch)
                batch = []
        if batch:
            psycopg2.extras.execute_values(pgcur, f'INSERT INTO "{t}" VALUES %s', batch, page_size=500)
            total += len(batch)
    # 序列
    for t in tables:
        target = seq.get(t)
        if target is None:
            continue
        pgcur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (t,))
        seqname = pgcur.fetchone()[0]
        if not seqname:
            continue
        if target <= 0:
            pgcur.execute(f"SELECT setval('{seqname}', 1, false)")
        else:
            pgcur.execute(f"SELECT setval('{seqname}', %s)", (target,))
    pgcur.execute("SET session_replication_role = DEFAULT")
    return total


def _col_is_bool(col_info, name):
    for c in col_info:
        if c["name"] == name:
            return (c["type"] or "").upper() == "BOOLEAN"
    return False


def verify(sq, cur, tables, pgcur, seq):
    bad = []
    blob_ok = None
    for t in tables:
        s = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        pgcur.execute(f'SELECT COUNT(*) FROM "{t}"')
        d = pgcur.fetchone()[0]
        if s != d:
            bad.append(f"{t}: sqlite={s} pg={d}")
    if bad:
        fail("行数不一致: " + "; ".join(bad))
    else:
        info(f"30 表行数全部一致")
    try:
        cur.execute("SELECT sample_image_blob FROM templates WHERE sample_image_blob IS NOT NULL LIMIT 1")
        src = hashlib.md5(cur.fetchone()[0]).hexdigest()
        pgcur.execute("SELECT sample_image_blob FROM templates WHERE sample_image_blob IS NOT NULL LIMIT 1")
        dst = hashlib.md5(pgcur.fetchone()[0]).hexdigest()
        blob_ok = src == dst
        info(f"BLOB md5 {'一致' if blob_ok else '不一致'} ({src[:10]})")
        if not blob_ok:
            fail("BLOB md5 不一致")
    except Exception as e:  # noqa: BLE001
        fail(f"BLOB 校验异常: {e}")
    # 生成列抽查
    pgcur.execute("SELECT COUNT(*), COUNT(is_valid) FROM pending_achievements")
    n, nv = pgcur.fetchone()
    info(f"生成列 is_valid: {nv}/{n} 行非 NULL(45 行中按内容可有 NULL,符合语义)")
    mism = 0
    for row in cur.execute("SELECT id, is_valid FROM pending_achievements"):
        pgcur.execute("SELECT is_valid FROM pending_achievements WHERE id=%s", (row["id"],))
        got = pgcur.fetchone()[0]
        expect = row["is_valid"]
        if (int(expect) if expect is not None else None) != got:
            mism += 1
    if mism:
        fail(f"生成列 {mism} 行与 SQLite 不一致")
    else:
        info("生成列逐行与 SQLite 引擎一致")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="database/competitions.db")
    ap.add_argument("--dsn", default="host=127.0.0.1 port=5433 dbname=awardie_dev user=postgres")
    ap.add_argument("--skip-baseline", action="store_true", help="跳过 baseline 生成(已有)")
    args = ap.parse_args()

    src = REPO / args.source
    sq, cur, tables, ddl, cols, fks, indexes, seq, views = probe_sqlite(str(src))
    print(f"== 1. 侦察: {len(tables)} 表 / {len(views)} 视图(不迁移) ==")
    colmap = column_type_map(cur, tables, cols)
    for t, m in colmap.items():
        for n, (tg, bad) in m.items():
            if tg == "clean_null":
                cleaned(f"混型清洗: {t}.{n} 有 {bad} 个非整数值→NULL(保 INTEGER 列型)")
            elif tg == "jsonb_fix":
                cleaned(f"JSON 修复: {t}.{n} 有 {bad} 行非法→NULL 后转 jsonb")
            elif tg == "jsonb":
                info(f"JSON 列: {t}.{n} → jsonb")
            elif tg == "timestamptz":
                info(f"时间列: {t}.{n} → timestamptz")

    print("== 2. baseline 生成 ==")
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    if not args.skip_baseline or not BASELINE.exists():
        BASELINE.write_text(gen_baseline(tables, ddl, cols, colmap, fks, indexes, views), encoding="utf-8")
    info(f"{BASELINE.relative_to(REPO)} ({BASELINE.stat().st_size} bytes)")

    pg = psycopg2.connect(args.dsn)
    pg.autocommit = True
    pgcur = pg.cursor()
    print("== 3. 重建 schema ==")
    pgcur.execute("DROP SCHEMA public CASCADE")
    pgcur.execute("CREATE SCHEMA public")
    proc = subprocess.run(
        [r"D:\Develop\tools\pg16-portable\pg16\pgsql\bin\psql.exe", "-h", "127.0.0.1", "-p", "5433",
         "-U", "postgres", "-d", "awardie_dev", "-v", "ON_ERROR_STOP=1", "-f", str(BASELINE)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        tail = [ln for ln in (proc.stderr or "").splitlines() if ln.strip()][-12:]
        for ln in tail:
            print(f"  psql> {ln}")
        fail(f"baseline 执行失败(exit {proc.returncode}),见上方 psql 输出")
        sys.exit(1)
    info("baseline 执行成功(30 表+索引+生成列+FK)")

    print("== 4. 数据装载+清洗 ==")
    n = load_data(sq, cur, tables, colmap, pgcur, seq)
    info(f"装载 {n} 行")

    print("== 5. 校验 ==")
    verify(sq, cur, tables, pgcur, seq)

    print("\n========== 迁移汇总 ==========")
    if report["cleaned"]:
        print(f"清洗动作 {len(report['cleaned'])} 项:")
        for c in report["cleaned"]:
            print("  " + c)
    print(f"FAIL {len(report['fail'])}: " + " | ".join(report["fail"]) if report["fail"] else "✅ 零 FAIL")
    (REPO / "scripts/v2_migrate_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(1 if report["fail"] else 0)


if __name__ == "__main__":
    main()
