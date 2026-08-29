"""探针 P2 前置侦察:盘点 competitions.db 的迁移坑位分布。

只读,不写库。产出:表/行数/生成列/BLOB/JSON 嫌疑列/序列/时间格式。
"""
import json
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "database/competitions.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

tables = [
    r[0]
    for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
]

gen_cols, blob_cols, json_suspect, empty_tables = [], [], [], []
total_rows = 0
row_counts = {}

for t in tables:
    n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    row_counts[t] = n
    total_rows += n
    if n == 0:
        empty_tables.append(t)
    for c in cur.execute(f'PRAGMA table_xinfo("{t}")'):
        r = dict(c)
        if r["hidden"] in (2, 3):
            gen_cols.append((t, r["name"], "VIRTUAL" if r["hidden"] == 2 else "STORED", r["type"]))
        if "BLOB" in (r["type"] or "").upper():
            blob_cols.append((t, r["name"]))

# JSON 嫌疑列:列名含 json / metadata / config / extra,抽样值以 { 或 [ 开头
for t in tables:
    if row_counts[t] == 0:
        continue
    for c in cur.execute(f'PRAGMA table_info("{t}")'):
        name = c["name"]
        if not any(k in name.lower() for k in ("json", "meta", "config", "extra", "payload")):
            continue
        sample = cur.execute(f'SELECT "{name}" FROM "{t}" WHERE "{name}" IS NOT NULL LIMIT 1').fetchone()
        if sample and isinstance(sample[0], str) and sample[0].lstrip()[:1] in ("{", "["):
            json_suspect.append((t, name, sample[0][:60]))

seq = [(r["name"], r["seq"]) for r in cur.execute("SELECT name, seq FROM sqlite_sequence")]

print(f"业务表数量: {len(tables)}  总行数: {total_rows}")
print(f"空表({len(empty_tables)}): {', '.join(empty_tables)}")
print(f"\n生成列({len(gen_cols)}):")
for g in gen_cols:
    print(f"  {g[0]}.{g[1]} [{g[2]}] declared={g[3]}")
print(f"\n声明 BLOB 列({len(blob_cols)}): {blob_cols if blob_cols else '无'}")
print(f"\nJSON 嫌疑列({len(json_suspect)}):")
for j in json_suspect:
    print(f"  {j[0]}.{j[1]} -> {j[2]!r}")
print(f"\nsqlite_sequence({len(seq)}): {seq[:10]}{' ...' if len(seq) > 10 else ''}")

# 时间列格式抽样:全库 typeof 分布
print("\n时间列 typeof 抽样:")
for t in tables:
    if row_counts[t] == 0:
        continue
    for c in cur.execute(f'PRAGMA table_info("{t}")'):
        if "time" in c["name"].lower() or "date" in c["name"].lower() or "_at" in c["name"].lower():
            types = [
                r[0]
                for r in cur.execute(
                    f'SELECT DISTINCT typeof("{c["name"]}") FROM "{t}" LIMIT 3'
                )
            ]
            sample = cur.execute(f'SELECT "{c["name"]}" FROM "{t}" WHERE "{c["name"]}" IS NOT NULL LIMIT 1').fetchone()
            print(f"  {t}.{c['name']}: types={types} sample={sample[0] if sample else None!r}")

# 外键依赖图(建表顺序需要)
print("\n外键依赖:")
for t in tables:
    fks = list(cur.execute(f'PRAGMA foreign_key_list("{t}")'))
    if fks:
        print(f"  {t} -> {[(f['table'], f['from']) for f in fks]}")

# DDL 原文(生成列表达式翻译要用)
print("\n含生成列/JSON/复杂默认值的 CREATE TABLE 原文:")
for t in tables:
    ddl = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)
    ).fetchone()[0]
    if any(t == g[0] for g in gen_cols) or any(t == j[0] for j in json_suspect):
        print(f"--- {t} ---\n{ddl}\n")
