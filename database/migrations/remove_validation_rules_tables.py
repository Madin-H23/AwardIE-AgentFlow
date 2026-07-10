#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
删除验证规则相关的数据库表
这些表已废弃，不再使用
"""

import sqlite3
import os
from pathlib import Path

# 获取数据库路径
db_path = Path(__file__).parent.parent / 'competitions.db'

if not db_path.exists():
    print(f"数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# 检查并删除表
tables_to_remove = ['validation_rules', 'rule_sets', 'validation_rule_sets']

for table_name in tables_to_remove:
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if cursor.fetchone():
        print(f"删除表: {table_name}")
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    else:
        print(f"表不存在，跳过: {table_name}")

conn.commit()
conn.close()

print("完成！")
