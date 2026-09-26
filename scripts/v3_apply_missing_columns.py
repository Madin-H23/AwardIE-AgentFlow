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
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_FILE = os.path.join(ROOT, 'awardie-v3', 'sql', 'awardie-business.sql')
TARGET_DB = os.environ.get('AWARDIE_TARGET_DB', 'awardie_v3')
WIN_CLI = r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe'

# (表, 列) —— **列定义不在这里写**,由 load_new_column_ddl() 从 awardie-business.sql
# 的批11 段切出来。两处各存一份必然漂移,而 --check 只验「列是否存在」不验定义,
# 漂移的表现是两套 schema 分叉且两边都报绿(C-3)。
MISSING_COLUMNS = [
    ('awardie_awards', 'granted_role'),
    ('awardie_awards', 'llm_prompt'),
    ('awardie_awards', 'llm_response'),
    ('awardie_awards', 'validation_result'),
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
    """把 SQL 文本喂给 mysql CLI。返回 (rc, 合并输出)。

    用哪个账号由 AWARDIE_MYSQL_USER 决定,默认 awardie_v3(应用账号,与其它 v3
    脚本一致,适用于本地 dev 库与演练库)。

    CI 必须显式设成 root:该 job 的 AWARDIE_MYSQL_PASSWORD 装的是**应用用户**口令,
    与 root 口令不是同一个值。这里连栽两次(先用 root + 应用口令,再用应用账号 +
    应用口令,CI 都不认),根因是**没先看清 CI 这个 job 的凭据到底怎么发的**——
    相邻步骤 `-uroot -proot` 天天过,那才是这个 job 的既有口径。
    """
    cli = find_cli()
    password = os.environ.get('AWARDIE_MYSQL_PASSWORD', '')
    user = os.environ.get('AWARDIE_MYSQL_USER', 'awardie_v3')
    cmd = [cli, '--default-character-set=utf8mb4', '-h', '127.0.0.1', '-P', '3307',
           f'-u{user}', f'-p{password}', TARGET_DB, '-N', '-B']
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
        # C-2:必须有结束标记。原来是「从标记扫到文件末尾」,批12 往尾部追加自己的
        # DDL 之后,这个"补批11 的列"的脚本会顺手把批12 的表也建了,而输出只说
        # 「批11 schema 已补齐」——一个改 schema 的工具,作用域是文件剩余全部。
        if s.startswith('-- END 批11'):
            break
        if s.startswith('CREATE TABLE IF NOT EXISTS'):
            in_stmt = True
        if in_stmt:
            buf.append(line)
            if s.endswith(';'):
                stmts.append('\n'.join(buf))
                buf, in_stmt = [], False
    # 解析结果必须与 NEW_TABLES 严格对应,否则说明作用域或解析出了偏差
    got = []
    for st in stmts:
        m = re.search(r'CREATE TABLE IF NOT EXISTS\s+`?(\w+)`?', st)
        if m:
            got.append(m.group(1))
    if sorted(got) != sorted(NEW_TABLES):
        raise SystemExit(
            f'[FATAL] 从 awardie-business.sql 解析到的建表语句是 {got},'
            f'与本脚本预期的 {sorted(NEW_TABLES)} 不符 —— 作用域或解析已漂移,拒绝执行。'
            f'若批11 段新增了表,请同步更新 NEW_TABLES 并加 -- END 批11 标记。')
    return stmts


def load_new_column_ddl():
    """C-3:从 awardie-business.sql 里切出批11 的 ADD COLUMN 定义,不在 Python 里另存一份。

    原先 4 个 ALTER 的列定义在 .py 与 .sql 各存一份,注释写着「必须逐字一致」却
    没有任何机制保证。SQL 侧把 VARCHAR(20) 放宽成 50 → 全新库建出来是 50、
    已迁过的 dev 库因为 --check 只验「列是否存在」永远停在 20 → 两套 schema
    静默分叉,而 --check 在两边都报绿。CREATE TABLE 早就从文件切了,这里补齐 ALTER。
    """
    with io.open(SQL_FILE, encoding='utf-8') as f:
        text = f.read()
    idx = text.find('批11 切流前置')
    if idx < 0:
        raise SystemExit('awardie-business.sql 里找不到批11 段,DDL 与本脚本已漂移')
    section = text[idx:]
    end = section.find('-- END 批11')
    if end >= 0:
        section = section[:end]
    # 形如: ADD COLUMN [反引号]col[反引号] <定义>,  —— 一条 ALTER 里可能有多列,
    # 以「, ADD COLUMN」或语句末尾的 ';' 为界。列名**不一定带反引号**(本仓的
    # awardie-business.sql 就不带),所以两种都要认。
    out = {}
    for stmt in re.findall(r'ALTER TABLE[^;]*;', section, re.S):
        # 去掉表名部分,只留 ADD COLUMN 列表
        body = stmt.split('ADD COLUMN', 1)
        if len(body) < 2:
            continue
        table = re.search(r'ALTER TABLE\s+`?(\w+)`?', stmt)
        if not table:
            continue
        parts = re.split(r',\s*(?=ADD COLUMN)', 'ADD COLUMN' + body[1])
        for part in parts:
            m = re.match(r'\s*ADD COLUMN\s+`?(\w+)`?\s+(.+)', part, re.S)
            if not m:
                continue
            out[m.group(1)] = ' '.join(m.group(2).split()).rstrip(',;').strip()
    return out


def main() -> int:
    check_only = '--check' in sys.argv
    if not os.environ.get('AWARDIE_MYSQL_PASSWORD'):
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2

    # 一次查出「本批关心的表/列」里哪些不存在
    probes = ''.join(
        f"SELECT '{t}.{c}', COUNT(*) FROM information_schema.columns "
        f"WHERE table_schema='{TARGET_DB}' AND table_name='{t}' AND column_name='{c}';\n"
        for t, c in MISSING_COLUMNS)
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

    todo_cols = [(t, c) for t, c in MISSING_COLUMNS if present.get(f'{t}.{c}') == '0']
    todo_tables = [t for t in NEW_TABLES if present.get(t) == '0']

    print(f'[scan] 目标库 {TARGET_DB}:待补列 {len(todo_cols)} 个,待建表 {len(todo_tables)} 张')
    for t, c in todo_cols:
        print(f'  col   {t}.{c}')
    for t in todo_tables:
        print(f'  table {t}')

    if not todo_cols and not todo_tables:
        print('[ok] 批11 的列与表都已就位')
        return 0
    if check_only:
        print('[check] 存在缺失(未落盘)')
        return 1

    col_ddl = load_new_column_ddl()
    stmts = []
    for t, c in todo_cols:
        if c not in col_ddl:
            raise SystemExit(
                f'[FATAL] awardie-business.sql 的批11 段里找不到 {t}.{c} 的 ADD COLUMN 定义,'
                f'拒绝用本地副本落盘(两处定义会漂移)。')
        stmts.append(f"ALTER TABLE `{t}` ADD COLUMN `{c}` {col_ddl[c]};")
    stmts += load_new_table_ddl()
    rc, out = run_sql('\n'.join(stmts))
    if rc != 0:
        print(f'[error] 落盘失败: {out[:500]}', file=sys.stderr)
        return 1
    for t, c in todo_cols:
        print(f'[exec] +{t}.{c}')
    print('[done] 批11 schema 已补齐')
    return 0


if __name__ == '__main__':
    sys.exit(main())
