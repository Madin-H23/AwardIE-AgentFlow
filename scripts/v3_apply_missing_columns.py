#!/usr/bin/env python
"""v3 切流前置:给**已建好**的库补齐批11 的列/表(幂等)。

为什么需要:`awardie-business.sql` 里的 ALTER 不带幂等守卫(与既有 11 处同惯例),
它只给全新库跑——CI 每次重建库所以没问题,但 dev 库已经跑过一次,再跑会在
第 283 行就报 1060 重复列而中断。本脚本先查 information_schema 判存在性,
只在缺的时候补,可在任意已迁库上重复执行。

**刻意零 Python 依赖**(只用标准库 + mysql 命令行):首版用 pymysql,挂在 ci-v3 上
直接 ModuleNotFoundError —— CI runner 上没有装。门禁脚本引入第三方依赖,就多一处
"装不上就变成门禁自己挂了"的失败点。与 scripts/v3_sanitize_sql_secrets.py 同一先例。

用法:
    python scripts/v3_apply_missing_columns.py [--check]
    # 口令取自 AWARDIE_MYSQL_PASSWORD;目标库取自 AWARDIE_TARGET_DB(默认 awardie_v3)
    # 本地若 mysql 不在 PATH,可设 AWARDIE_MYSQL_CLI 指向可执行文件

--check 只检查不落盘,退出码 1 = 仍有缺失(挂 CI 做「全新库是否建全」的复检)。
"""
import io
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_FILE = os.path.join(ROOT, 'awardie-v3', 'sql', 'awardie-business.sql')
TARGET_DB = os.environ.get('AWARDIE_TARGET_DB', 'awardie_v3')
WIN_CLI = r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe'

# (表, 列, 列定义) —— 必须与 awardie-business.sql 批11 段的定义逐字一致
MISSING_COLUMNS = [
    ('awardie_awards', 'granted_role',
     "VARCHAR(20) DEFAULT NULL COMMENT '授予角色(学生/教师,v2 存量,切流时补)'"),
    ('awardie_awards', 'llm_prompt', "TEXT DEFAULT NULL COMMENT 'LLM 提示词(v2 存量)'"),
    ('awardie_awards', 'llm_response',
     "TEXT DEFAULT NULL COMMENT 'LLM 响应(v2 存量,PG jsonb 序列化为字符串)'"),
    ('awardie_awards', 'validation_result',
     "TEXT DEFAULT NULL COMMENT '校验结果(v2 存量,PG jsonb 序列化为字符串)'"),
]
NEW_TABLES = ['awardie_award_teacher_winners', 'awardie_award_related_students', 'awardie_review_logs']


def find_cli():
    cli = os.environ.get('AWARDIE_MYSQL_CLI')
    if cli:
        return cli
    if os.path.isfile(WIN_CLI):
        return WIN_CLI
    return shutil.which('mysql') or 'mysql'


def run_sql(statements):
    """把 SQL 文本喂给 mysql CLI。返回 (rc, 合并输出)。"""
    cli = find_cli()
    password = os.environ.get('AWARDIE_MYSQL_PASSWORD', '')
    cmd = [cli, '--default-character-set=utf8mb4', '-h', '127.0.0.1', '-P', '3307',
           '-uroot', f'-p{password}', TARGET_DB, '-N', '-B']
    p = subprocess.run(cmd, input=statements, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return p.returncode, ((p.stdout or '') + (p.stderr or '')).strip()


def load_new_table_ddl():
    """从 awardie-business.sql 里切出批11 新建的三张表语句(避免两处定义漂移)。"""
    with io.open(SQL_FILE, encoding='utf-8') as f:
        text = f.read()
    idx = text.find('批11 切流前置')
    if idx < 0:
        raise SystemExit('awardie-business.sql 里找不到批11 段,DDL 与本脚本已漂移')
    stmts, buf, in_stmt = [], [], False
    for line in text[idx:].splitlines():
        s = line.strip()
        if s.startswith('CREATE TABLE IF NOT EXISTS'):
            in_stmt = True
        if in_stmt:
            buf.append(line)
            if s.endswith(';'):
                stmts.append('\n'.join(buf))
                buf, in_stmt = [], False
    return stmts


def main() -> int:
    check_only = '--check' in sys.argv
    if not os.environ.get('AWARDIE_MYSQL_PASSWORD'):
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2

    # 一次查出「本批关心的表/列」里哪些不存在
    probes = ''.join(
        f"SELECT '{t}.{c}', COUNT(*) FROM information_schema.columns "
        f"WHERE table_schema='{TARGET_DB}' AND table_name='{t}' AND column_name='{c}';\n"
        for t, c, _ in MISSING_COLUMNS)
    probes += ''.join(
        f"SELECT '{t}', COUNT(*) FROM information_schema.tables "
        f"WHERE table_schema='{TARGET_DB}' AND table_name='{t}';\n"
        for t in NEW_TABLES)
    rc, out = run_sql(probes)
    if rc != 0:
        print(f'[error] 探测失败: {out[:300]}', file=sys.stderr)
        return 2

    present = {}
    for line in out.splitlines():
        if '\t' in line:
            k, v = line.split('\t', 1)
            present[k.strip()] = v.strip()

    todo_cols = [(t, c, d) for t, c, d in MISSING_COLUMNS if present.get(f'{t}.{c}') == '0']
    todo_tables = [t for t in NEW_TABLES if present.get(t) == '0']

    print(f'[scan] 目标库 {TARGET_DB}:待补列 {len(todo_cols)} 个,待建表 {len(todo_tables)} 张')
    for t, c, _ in todo_cols:
        print(f'  col   {t}.{c}')
    for t in todo_tables:
        print(f'  table {t}')

    if not todo_cols and not todo_tables:
        print('[ok] 批11 的列与表都已就位')
        return 0
    if check_only:
        print('[check] 存在缺失(未落盘)')
        return 1

    stmts = [f"ALTER TABLE `{t}` ADD COLUMN `{c}` {d};" for t, c, d in todo_cols]
    stmts += load_new_table_ddl()
    rc, out = run_sql('\n'.join(stmts))
    if rc != 0:
        print(f'[error] 落盘失败: {out[:500]}', file=sys.stderr)
        return 1
    for t, c, _ in todo_cols:
        print(f'[exec] +{t}.{c}')
    print('[done] 批11 schema 已补齐')
    return 0


if __name__ == '__main__':
    sys.exit(main())
