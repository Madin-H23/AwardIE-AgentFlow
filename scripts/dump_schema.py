"""导出真实库 schema 快照到 tests/fixtures/full_schema.sql（T64 CI 种子库基建）。

用法：python scripts/dump_schema.py
迁移（migrations/versions/*）变更表结构后必须重新执行，保持测试 schema 与生产一致。
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB = PROJECT_ROOT / "database" / "competitions.db"
OUT = PROJECT_ROOT / "tests" / "fixtures" / "full_schema.sql"

conn = sqlite3.connect(str(DB))
rows = conn.execute("""
    SELECT name, sql FROM sqlite_master
    WHERE type IN ('table','view','index') AND sql IS NOT NULL
      AND name NOT LIKE 'sqlite_%'
    ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'view' THEN 1 ELSE 2 END, name
""").fetchall()
conn.close()

out = ['-- 全库 schema 快照（自 database/competitions.db 反射导出）。',
       '',
       '-- 用途：CI 种子库建库（无 *.db 环境）；迁移变更后需重新导出。',
       '-- 由 scripts/dump_schema.py 生成，勿手工编辑。', '']
for name, sql in rows:
    out.append(sql.rstrip(';') + ';')
    out.append('')
OUT.write_text("\n".join(out), encoding='utf-8')
print(f"dumped {len(rows)} objects -> {OUT}")
