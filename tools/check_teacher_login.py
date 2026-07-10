#!/usr/bin/env python3
"""临时脚本：检查教师 02104019 登录失败原因"""
import sqlite3
import sys
from pathlib import Path

# 项目根目录
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

db_path = root / 'database' / 'competitions.db'
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

teacher_id = sys.argv[1] if len(sys.argv) > 1 else '02104019'
password = sys.argv[2] if len(sys.argv) > 2 else 'P@ss301'

# 检查教师记录
cur.execute(
    'SELECT teacher_id, name, password_hash, user_activated, role FROM teachers WHERE teacher_id = ?',
    (teacher_id,)
)
row = cur.fetchone()

if not row:
    print(f'❌ 教师 {teacher_id} 不存在于 teachers 表')
    cur.execute('SELECT teacher_id, name, user_activated FROM teachers LIMIT 5')
    print('\n部分教师列表:', [dict(r) for r in cur.fetchall()])
    conn.close()
    sys.exit(1)

print('教师记录存在:')
print(dict(row))
print()

# 检查 user_activated
user_activated = row['user_activated']
print(f'user_activated: {user_activated} (1=已激活可登录, 0=未激活不可登录)')
if not user_activated:
    print('❌ 原因: 账号未激活，无法登录')
    conn.close()
    sys.exit(1)

# 检查 password_hash
ph = row['password_hash']
if not ph:
    print('❌ 原因: password_hash 为空，未设置密码，无法登录')
    conn.close()
    sys.exit(1)

# 验证密码
from werkzeug.security import check_password_hash

if check_password_hash(ph, password):
    print(f'✓ 密码 {password} 验证通过')
else:
    print(f'❌ 原因: 密码验证失败，输入的密码与数据库中存储的哈希不匹配')
    print('  可能原因: 1) 密码已修改 2) 数据库中存储的是其他密码的哈希')
    # 生成 P@ss301 的哈希用于参考
    from werkzeug.security import generate_password_hash
    correct_hash = generate_password_hash(password)
    print(f'  P@ss301 正确哈希示例: {correct_hash[:50]}...')

conn.close()
