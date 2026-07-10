#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查询指定学号学生在 pending_achievements 中的记录。用法: python tools/query_student_pending.py 212306413"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.loader import get_config
import sqlite3

def main():
    student_no = sys.argv[1] if len(sys.argv) > 1 else "212306413"
    cfg = get_config()
    db = cfg.get_path("database", "competitions_db")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, student_id, name FROM students WHERE student_id = ?", (student_no,))
    row = cur.fetchone()
    if not row:
        print(f"未找到学号 {student_no} 的学生")
        conn.close()
        return 1

    sid = row["id"]
    print(f"学生: id={sid}, student_id(学号)={row['student_id']}, name={row['name']}")

    cur.execute("""
        SELECT id, achievement_type, status, submitter_type, submitter_id, submit_time, assigned_reviewer_type
        FROM pending_achievements
        WHERE submitter_type = ? AND submitter_id = ?
        ORDER BY submit_time DESC
    """, ("student", sid))
    rows = cur.fetchall()
    print(f"\npending_achievements 中该学生记录数: {len(rows)}")
    for r in rows:
        print(dict(r))

    cur.execute("""
        SELECT id, achievement_type, status FROM pending_achievements
        WHERE submitter_type = ? AND status = ?
    """, ("student", "submit"))
    all_submit = cur.fetchall()
    print(f"\n全库 submitter_type=student 且 status=submit 的记录数: {len(all_submit)}")
    for r in all_submit:
        print(dict(r))

    conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
