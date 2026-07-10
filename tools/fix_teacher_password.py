#!/usr/bin/env python3
"""为 password_hash 为空的教师设置默认密码 P@ss301

用法:
  python fix_teacher_password.py              # 修复所有 password_hash 为空的教师
  python fix_teacher_password.py 02110606     # 强制重置指定教师的密码为默认
"""
import sqlite3
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from werkzeug.security import generate_password_hash

db_path = root / 'database' / 'competitions.db'
default_password = 'P@ss301'
password_hash = generate_password_hash(default_password)

# 可选：指定单个教师工号强制重置
specific_teacher_id = sys.argv[1].strip() if len(sys.argv) > 1 else None

conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

if specific_teacher_id:
    cur.execute('SELECT teacher_id, name FROM teachers WHERE teacher_id = ?', (specific_teacher_id,))
    row = cur.fetchone()
    if not row:
        print(f'教师 {specific_teacher_id} 不存在')
        conn.close()
        sys.exit(1)
    cur.execute('UPDATE teachers SET password_hash = ? WHERE teacher_id = ?', (password_hash, specific_teacher_id))
    conn.commit()
    print(f'已重置教师 {row[0]} ({row[1]}) 的密码，可使用工号 + {default_password} 登录')
else:
    cur.execute(
        'SELECT teacher_id, name FROM teachers WHERE password_hash IS NULL OR password_hash = ""'
    )
    rows = cur.fetchall()
    if not rows:
        print('没有需要修复的教师（所有教师均已设置密码）')
        conn.close()
        sys.exit(0)
    print(f'发现 {len(rows)} 名教师未设置密码，将设置为默认密码 {default_password}:')
    for teacher_id, name in rows:
        print(f'  - {teacher_id} ({name})')
    cur.execute(
        'UPDATE teachers SET password_hash = ? WHERE password_hash IS NULL OR password_hash = ""',
        (password_hash,)
    )
    conn.commit()
    updated = cur.rowcount
    print(f'\n已更新 {updated} 名教师的密码，可使用工号 + {default_password} 登录')

conn.close()
