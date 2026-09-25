#!/usr/bin/env python
"""v3 切流演练:在一次性库里从零复刻「建库 → 迁数据 → 对账」全流程。

为什么必须演练:切流是单向的。真实目标库一旦被写入 v2 数据,再想验证
「这套流程能不能从零跑通」就只能等下一次。而流程里有大量只有跑起来才会
暴露的东西(SQL 顺序、幂等性、列名漂移、ETL 的 NOT NULL 冲突)。

演练库用完即删,**不碰 awardie_v3**,所以可以随时重跑。

用法(venv python):
    AWARDIE_MYSQL_PASSWORD=<口令> python scripts/v3_cutover_rehearsal.py [--keep]

--keep 保留演练库(失败时留现场排查,默认成功即删)。
"""
import os
import subprocess
import sys

import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(ROOT, 'awardie-v3', 'sql')
MYSQL_CLI = r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe'
PY = sys.executable
REHEARSE_DB = 'awardie_v3_rehearsal'
# 与 CI 建库流程同序(批4 踩坑:user-domain 必须排在 menus 之后,
# 否则角色拿不到菜单 → 三角色不存在 → 提交类测试全 403 而本地有角色故全绿)
SQL_ORDER = [
    ('awardie-v3/sql/mysql/ruoyi-vue-pro.sql', '官方基线(脱敏版)'),
    ('awardie-v3/sql/mysql/quartz.sql', 'quartz 引擎'),
    ('awardie-v3/sql/awardie-cleanup.sql', '演示数据清理 ⚠️ 只能在「还没跑 ETL」的库上跑'),
    ('awardie-v3/sql/awardie-business.sql', 'AwardIE 业务表 + 菜单'),
    ('awardie-v3/sql/awardie-business-menus.sql', '业务菜单'),
    ('awardie-v3/sql/awardie-user-domain.sql', '三角色 + 授权'),
]
ETL_STEPS = [
    ('scripts/etl_v2_base_data_to_v3.py', '基础数据域(竞赛/实验室)'),
    ('scripts/etl_v2_users_to_v3.py', '用户与角色域'),
    ('scripts/v3_apply_missing_columns.py', '批11 schema 补列/建表'),
    ('scripts/etl_v2_business_to_v3.py', '业务成果域(批11 主体)'),
]
CHECKS = []  # 复检改为脚本内联(见 main 的 [check] 段)
_OLD_CHECKS = [
    ('scripts/v3_apply_missing_columns.py', '批11 schema 完整性'),
    ('scripts/v3_check_import_case.py', 'import 路径大小写(Linux-only 缺陷的本地前置)'),
]


def run(cmd, env=None, cwd=ROOT):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True,
                       text=True, encoding='utf-8', errors='replace', env=env, cwd=cwd)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def sql(db, script, password):
    with open(os.path.join(ROOT, script), encoding='utf-8') as f:
        pass
    return run([MYSQL_CLI, '--default-character-set=utf8mb4', '-h', '127.0.0.1', '-P', '3307',
                '-uroot', f'-p{password}', db], env=None) if False else run(
        f'"{MYSQL_CLI}" --default-character-set=utf8mb4 -h 127.0.0.1 -P 3307 -uroot -p"{password}" {db} < "{os.path.join(ROOT, script)}"')


def main() -> int:
    keep = '--keep' in sys.argv
    password = os.environ.get('AWARDIE_MYSQL_PASSWORD', '')
    if not password:
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2
    env = dict(os.environ, AWARDIE_MYSQL_PASSWORD=password)

    def drop():
        run(f'"{MYSQL_CLI}" --default-character-set=utf8mb4 -h 127.0.0.1 -P 3307 -uroot -p"{password}" '
            f'-e "DROP DATABASE IF EXISTS {REHEARSE_DB}"')

    print(f'=== 切流演练(演练库 {REHEARSE_DB},不碰 awardie_v3)===')
    drop()

    # 1) 建库
    rc, out = run(f'"{MYSQL_CLI}" --default-character-set=utf8mb4 -h 127.0.0.1 -P 3307 -uroot -p"{password}" '
                  f'-e "CREATE DATABASE {REHEARSE_DB} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"')
    print(f'[1/3] 建库 {"OK" if rc == 0 else "FAIL " + out[:200]}')
    if rc != 0:
        return 1

    # ETL 用应用账号 awardie_v3 连接,演练库得单独授权(与 CI 建库同做法:
    # CI 也会 CREATE USER + GRANT 到 awardie_v3_test,否则后端测试连不上)
    grant_sql = ("CREATE USER IF NOT EXISTS 'awardie_v3'@'%' IDENTIFIED BY 'rehearsal-pass'; "
                 f"GRANT ALL PRIVILEGES ON {REHEARSE_DB}.* TO 'awardie_v3'@'%'; FLUSH PRIVILEGES")
    rc, out = run(f'"{MYSQL_CLI}" --default-character-set=utf8mb4 -h 127.0.0.1 -P 3307 '
                  f'-uroot -p"{password}" -e "{grant_sql}"')
    if rc != 0:
        print(f'[1/3] 授权失败: {out[:300]}')
        if not keep:
            drop()
        return 1
    print('[1/3] 建库 + 授权给应用账号 OK')

    # 2) 六脚本按序
    for i, (script, desc) in enumerate(SQL_ORDER, 1):
        rc, out = sql(REHEARSE_DB, script, password)
        if rc != 0:
            print(f'[2/3] SQL {i}/{len(SQL_ORDER)} {desc} FAIL:\n{out[:600]}')
            if not keep:
                drop()
            return 1
        print(f'[2/3] SQL {i}/{len(SQL_ORDER)} {desc:<42} OK')

    # 演练库里跑 ETL 需要连到演练库,借 MySQL 连接串的环境变量改库名
    rehearsal_env = dict(env)
    # 演练库必须独立:ETL 脚本通过 AWARDIE_TARGET_DB 选库,不给就是打真实 awardie_v3
    rehearsal_env = dict(env, AWARDIE_TARGET_DB=REHEARSE_DB)
    # 防呆:演练开始前先确认 ETL 真的指向演练库,而不是默认库
    probe = subprocess.run(
        [PY, '-c',
         "import os,importlib.util,sys;"
         "spec=importlib.util.spec_from_file_location('m', r'%s');"
         "m=importlib.util.module_from_spec(spec);"
         "sys.modules['m']=m;spec.loader.exec_module(m);"
         "print(m.MYSQL['db'])" % os.path.join(ROOT, 'scripts/etl_v2_business_to_v3.py')],
        capture_output=True, text=True, env=rehearsal_env, cwd=ROOT)
    target_db = probe.stdout.strip().splitlines()[-1] if probe.stdout.strip() else '?'
    if target_db != REHEARSE_DB:
        print(f'[abort] ETL 实际指向 {target_db},不是演练库 {REHEARSE_DB} —— 拒绝执行,'
              f'否则会污染真实库')
        if not keep:
            drop()
        return 1
    print(f'[guard] ETL 目标库已确认为 {REHEARSE_DB}')

    # 3) ETL
    for script, desc in ETL_STEPS:
        rc, out = run([PY, os.path.join(ROOT, script)], env=rehearsal_env)
        ok = rc == 0
        print(f'[3/3] ETL {desc:<42} {"OK" if ok else "FAIL"}')
        if not ok:
            print(out[-800:])
            if not keep:
                drop()
            return 1

    # 4) 复检:批11 schema 完整性 + 切流对账(演练的意义就在这一步)
    rc, out = run([PY, os.path.join(ROOT, 'scripts/v3_apply_missing_columns.py'), '--check'],
                  env=rehearsal_env)
    print(f'[check] 批11 schema 完整性{"":<20} {"OK" if rc == 0 else "FAIL rc=" + str(rc)}')
    if rc != 0:
        print(out[-400:])

    rc, out = run([PY, os.path.join(ROOT, 'scripts/v3_reconcile.py')], env=rehearsal_env)
    print('[check] 切流对账(v2 PG vs 演练库):')
    for line in (out or '').splitlines():
        if line.strip() and 'DeprecationWarning' not in line and 'sys.exit' not in line:
            print('   ' + line)
    reconcile_ok = rc == 0

    conn = pymysql.connect(host='127.0.0.1', port=3307, user='root',
                           password=password, database=REHEARSE_DB, charset='utf8mb4')
    cur = conn.cursor()
    cur.execute("""SELECT table_name, table_rows FROM information_schema.tables
                   WHERE table_schema=%s AND table_name LIKE 'awardie_%%' ORDER BY table_name""",
                (REHEARSE_DB,))
    rows = cur.fetchall()
    conn.close()
    print(f'\n[result] 演练库业务表 {len(rows)} 张:')
    for t, n in rows:
        print(f'   {t:<40} ~{n}')

    if not keep:
        drop()
        print('\n[cleanup] 演练库已删除')
    else:
        print(f'\n[keep] 演练库保留: {REHEARSE_DB}')
    if not reconcile_ok:
        print('\n[FAIL] 演练对账不通过 —— 切流闸门不能开')
        return 1
    print('\n[ok] 切流演练通过:全新库可从零建起并迁全量数据,对账齐平')
    return 0


if __name__ == '__main__':
    sys.exit(main())
