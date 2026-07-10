#!/usr/bin/env python3
"""查询教师数据库记录 - 诊断登录问题"""
import sqlite3
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
db_path = root / 'database' / 'competitions.db'

teacher_id = sys.argv[1] if len(sys.argv) > 1 else '02110606'

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 精确匹配
cur.execute('SELECT teacher_id, name, password_hash, user_activated, role FROM teachers WHERE teacher_id = ?', (teacher_id,))
row = cur.fetchone()

if row:
    d = dict(row)
    ph = d.get('password_hash')
    ph_display = 'None' if ph is None else ('empty' if ph == '' else f'{ph[:40]}...')
    d['password_hash'] = ph_display
    print('Teacher record:', d)
    print('user_activated:', row['user_activated'], '(1=active, 0=disabled)')
    if ph:
        from werkzeug.security import check_password_hash
        ok = check_password_hash(ph, 'P@ss301')
        print('P@ss301 verify:', ok)
    else:
        print('P@ss301 verify: N/A (no password_hash)')
else:
    print(f'Teacher {teacher_id}: NOT FOUND')
    # 模糊搜索
    cur.execute("SELECT teacher_id, name, user_activated FROM teachers WHERE teacher_id LIKE ?", ('%' + teacher_id + '%',))
    rows = cur.fetchall()
    if rows:
        print('Similar teachers:', [dict(r) for r in rows])

conn.close()
