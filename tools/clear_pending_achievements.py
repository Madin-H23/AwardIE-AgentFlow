#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清空 pending_achievements 表

用于从头测试成果审核流程：删除表中所有记录。
数据库路径来自 config/settings.json 的 database.competitions_db。

使用: python tools/clear_pending_achievements.py
      python tools/clear_pending_achievements.py --dry-run   # 仅打印将删除条数，不执行
"""
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.loader import get_config_loader


def main():
    parser = argparse.ArgumentParser(description="清空 pending_achievements 表")
    parser.add_argument("--dry-run", action="store_true", help="仅统计条数，不执行删除")
    args = parser.parse_args()

    config = get_config_loader()
    db_path = config.get_path("database", "competitions_db")
    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        return 1

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_achievements'")
    if not cur.fetchone():
        print("表 pending_achievements 不存在")
        conn.close()
        return 1

    cur.execute("SELECT COUNT(*) FROM pending_achievements")
    count = cur.fetchone()[0]
    print(f"pending_achievements 当前条数: {count}")

    if count == 0:
        print("无需清空")
        conn.close()
        return 0

    if args.dry_run:
        print("--dry-run: 未执行删除")
        conn.close()
        return 0

    cur.execute("DELETE FROM pending_achievements")
    conn.commit()
    print(f"已删除 {count} 条记录")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
