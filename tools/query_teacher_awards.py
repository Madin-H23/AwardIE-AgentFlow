# -*- coding: utf-8 -*-
"""临时脚本：查询教师 02114818 的奖状和统计数据"""
import sqlite3
import os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(base, 'database', 'competitions.db')

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. 教师 02114818
cur.execute('SELECT id, teacher_id, name FROM teachers WHERE teacher_id = ?', ('02114818',))
teacher = cur.fetchone()
if not teacher:
    print('Teacher 02114818 not found')
    conn.close()
    exit(1)

tid = teacher['id']
print('=== Teacher ===')
print(dict(teacher))

# 2. 作为获奖者的奖状
cur.execute('SELECT award_id FROM award_teacher_winners WHERE teacher_id = ?', (tid,))
winner_ids = [r[0] for r in cur.fetchall()]
print('\n=== Award IDs (as winner) ===', winner_ids)

# 3. 作为指导教师
cur.execute('SELECT award_id FROM award_supervisors WHERE teacher_id = ?', (tid,))
supervisor_ids = [r[0] for r in cur.fetchall()]
print('=== Award IDs (as supervisor) ===', supervisor_ids)

all_ids = list(set(winner_ids + supervisor_ids))
print('\n=== All award IDs ===', all_ids)

if all_ids:
    ph = ','.join(['?'] * len(all_ids))
    cur.execute(
        'SELECT a.id, a.competition_name_in_file, a.competition_level, a.year, a.granted_role, a.award_level '
        'FROM awards a WHERE a.id IN (' + ph + ')',
        all_ids
    )
    rows = cur.fetchall()
    print('\n=== Award details ===')
    for r in rows:
        d = dict(r)
        aid = d['id']
        cur.execute('SELECT COUNT(*) FROM award_student_winners WHERE award_id = ?', (aid,))
        d['student_count'] = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM award_teacher_winners WHERE award_id = ?', (aid,))
        d['teacher_count'] = cur.fetchone()[0]
        print(d)

# 4. pending_achievements 中 submitter 为该教师的
cur.execute('PRAGMA table_info(pending_achievements)')
cols = [r[1] for r in cur.fetchall()]
print('\n=== pending_achievements columns ===', cols)

cur.execute(
    'SELECT id, achievement_type, status, submitter_type, submitter_id, submit_time FROM pending_achievements'
)
all_pending = cur.fetchall()
print('\n=== All pending (first 15) ===')
for p in all_pending[:15]:
    print(dict(p))

# 按 submitter_id 查教师
cur.execute(
    "SELECT id, achievement_type, status, submitter_id FROM pending_achievements WHERE submitter_type='teacher'"
)
teacher_pending = cur.fetchall()
print('\n=== Pending by teachers ===')
for p in teacher_pending:
    print(dict(p))

conn.close()
print('\nDone')
