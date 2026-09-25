#!/usr/bin/env python
"""v3 切流前置:给**已建好**的库补齐批11 的列/表(幂等)。

为什么需要:`awardie-business.sql` 里的 ALTER 不带幂等守卫(与既有 11 处同惯例),
它只给全新库跑——CI 每次重建库所以没问题,但 dev 库已经跑过一次,再跑会在
第 283 行就报 1060 重复列而中断。本脚本用 information_schema 判存在性,
可以在任意已迁库上重复执行。

用法(venv python):
    AWARDIE_MYSQL_PASSWORD=<口令> python scripts/v3_apply_missing_columns.py [--check]

--check 只检查不落盘,退出码 1 = 仍有缺失(可挂 CI 做「全新库是否建全」的复检)。
"""
import os
import sys

import pymysql

# (表, 列, 列定义) —— 必须与 awardie-business.sql 批11 段的定义逐字一致
MISSING_COLUMNS = [
    ('awardie_awards', 'granted_role', "VARCHAR(20) DEFAULT NULL COMMENT '授予角色(学生/教师,v2 存量,切流时补)'"),
    ('awardie_awards', 'llm_prompt', "TEXT DEFAULT NULL COMMENT 'LLM 提示词(v2 存量)'"),
    ('awardie_awards', 'llm_response', "TEXT DEFAULT NULL COMMENT 'LLM 响应(v2 存量,PG jsonb 序列化为字符串)'"),
    ('awardie_awards', 'validation_result', "TEXT DEFAULT NULL COMMENT '校验结果(v2 存量,PG jsonb 序列化为字符串)'"),
]

# 与 awardie-business.sql 批11 段同源的建表语句(直接复用,避免两处定义漂移)
SQL_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'awardie-v3', 'sql', 'awardie-business.sql')
NEW_TABLES = ['awardie_award_teacher_winners', 'awardie_award_related_students', 'awardie_review_logs']


def load_new_table_ddl():
    """从 awardie-business.sql 里切出批11 新建的三张表语句。"""
    with open(SQL_FILE, encoding='utf-8') as f:
        text = f.read()
    marker = '批11 切流前置'
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit('awardie-business.sql 里找不到批11 段,DDL 与本脚本已漂移')
    section = text[idx:]
    stmts, buf, in_stmt = [], [], False
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith('CREATE TABLE IF NOT EXISTS'):
            in_stmt = True
        if in_stmt:
            buf.append(line)
            if stripped.endswith(';'):
                stmts.append('\n'.join(buf))
                buf, in_stmt = [], False
    return stmts


def main() -> int:
    check_only = '--check' in sys.argv
    password = os.environ.get('AWARDIE_MYSQL_PASSWORD', '')
    if not password:
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2
    conn = pymysql.connect(host='127.0.0.1', port=3307, user='root',
                           password=password, database=os.environ.get("AWARDIE_TARGET_DB", "awardie_v3"), charset='utf8mb4')
    cur = conn.cursor()

    todo_cols = []
    for table, col, ddl in MISSING_COLUMNS:
        cur.execute("""SELECT COUNT(*) FROM information_schema.columns
                       WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s""",
                    (table, col))
        if cur.fetchone()[0] == 0:
            todo_cols.append((table, col, ddl))

    todo_tables = []
    for t in NEW_TABLES:
        cur.execute("""SELECT COUNT(*) FROM information_schema.tables
                       WHERE table_schema=DATABASE() AND table_name=%s""", (t,))
        if cur.fetchone()[0] == 0:
            todo_tables.append(t)

    print(f'[scan] 待补列 {len(todo_cols)} 个,待建表 {len(todo_tables)} 张')
    for table, col, _ in todo_cols:
        print(f'  col   {table}.{col}')
    for t in todo_tables:
        print(f'  table {t}')

    if not todo_cols and not todo_tables:
        print('[ok] 批11 的列与表都已就位')
        return 0
    if check_only:
        print('[check] 存在缺失(未落盘)')
        return 1

    for table, col, ddl in todo_cols:
        cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {ddl}")
        print(f'[exec] +{table}.{col}')
    for stmt in load_new_table_ddl():
        cur.execute(stmt)
        print(f"[exec] +{stmt.split()[5]}")
    conn.commit()
    conn.close()
    print('[done] 批11 schema 已补齐')
    return 0


if __name__ == '__main__':
    sys.exit(main())
