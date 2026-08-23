#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断 pending_achievements 表

打印按类型、状态、验证结果（valid/invalid）的统计，便于排查成果审核页面
「统计与查询不一致」「第 1/ 0 项」等问题。

使用: python tools/diagnose_pending_achievements.py
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.loader import get_config_loader


def _is_valid(validation_result: str) -> bool:
    try:
        d = json.loads(validation_result) if validation_result else {}
        return bool(d.get("is_valid", False))
    except Exception:
        return False


def main():
    config = get_config_loader()
    db_path = config.get_path("database", "competitions_db")
    path = Path(db_path)
    if not path.exists():
        print(f"数据库不存在: {db_path}")
        return 1

    import sqlite3
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_achievements'")
    if not cur.fetchone():
        print("表 pending_achievements 不存在")
        conn.close()
        return 1

    cur.execute("SELECT COUNT(*) FROM pending_achievements")
    total = cur.fetchone()[0]
    print(f"pending_achievements 总条数: {total}")
    if total == 0:
        conn.close()
        return 0

    cur.execute(
        "SELECT id, achievement_type, status, validation_result FROM pending_achievements ORDER BY achievement_type, id"
    )
    rows = cur.fetchall()

    by_type_status = {}
    by_type_valid = {}
    for r in rows:
        t = r["achievement_type"]
        s = r["status"]
        v = _is_valid(r["validation_result"])
        by_type_status[(t, s)] = by_type_status.get((t, s), 0) + 1
        key = (t, "valid" if v else "invalid")
        by_type_valid[key] = by_type_valid.get(key, 0) + 1

    print("\n按 achievement_type + status:")
    for (t, s), c in sorted(by_type_status.items()):
        print(f"  {t} / {s}: {c}")

    print("\n按 achievement_type + 验证结果 (valid/invalid，用于成果审核子TAB):")
    for (t, v), c in sorted(by_type_valid.items()):
        print(f"  {t} / {v}: {c}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
