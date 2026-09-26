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
import secrets
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
CHECKS = []  # 复检项在 main 里内联执行(见 [check] 段),这里不再维护清单


def run(cmd, env=None, cwd=ROOT, stdin_text=None):
    """只走**参数列表**,不拼 shell 字符串。

    首版用 `shell=True` 把口令与 SQL 拼成一行命令,口令里出现 `"`/`$`/反引号/`;`
    就会破甚至被当成命令执行。与 v3_apply_missing_columns.py 统一:参数列表 +
    stdin 喂 SQL,口令只作为独立 argv 元素出现,不经过任何 shell 解析。
    """
    r = subprocess.run(cmd, capture_output=True, text=True, input=stdin_text,
                       encoding='utf-8', errors='replace', env=env, cwd=cwd)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def mysql_cmd(db, password):
    return [MYSQL_CLI, '--default-character-set=utf8mb4', '-h', '127.0.0.1', '-P', '3307',
            '-uroot', f'-p{password}'] + ([db] if db else [])


def sql(db, script, password):
    """把 SQL 文件内容经 stdin 喂给 mysql(替代 shell 的 `< file` 重定向)。"""
    with open(os.path.join(ROOT, script), encoding='utf-8') as f:
        return run(mysql_cmd(db, password), stdin_text=f.read())


def main() -> int:
    keep = '--keep' in sys.argv
    password = os.environ.get('AWARDIE_MYSQL_PASSWORD', '')
    if not password:
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2
    env = dict(os.environ, AWARDIE_MYSQL_PASSWORD=password)

    def drop():
        # 账号也要回收:否则每次演练留一个账号,随机口令的账号会逐次堆积
        rc, out = run(mysql_cmd(None, password) + [
            '-e', f"DROP DATABASE IF EXISTS {REHEARSE_DB}; "
                 f"DROP USER IF EXISTS '{rehearsal_user}'@'%';"])
        if rc != 0:
            # 清理失败要说话:root 口令不对时它会静默失败,残留的半成品库会让
            # 下次运行在建库这步以「database exists」失败,掩盖真正的根因
            print(f'[warn] 演练库/账号清理失败(不阻断): {out[:200]}')

    # 演练账号名/随机口令:drop() 要用到,故先于 drop() 定义算出
    rehearsal_user = f'{REHEARSE_DB}_ro'
    rehearsal_pw = secrets.token_urlsafe(18)

    print(f'=== 切流演练(演练库 {REHEARSE_DB},不碰 awardie_v3)===')
    drop()

    # 1) 建库
    rc, out = run(mysql_cmd(None, password) +
                  ['-e', f'CREATE DATABASE {REHEARSE_DB} DEFAULT CHARACTER SET utf8mb4 '
                         f'COLLATE utf8mb4_bin'])
    print(f'[1/3] 建库 {"OK" if rc == 0 else "FAIL " + out[:200]}')
    if rc != 0:
        return 1

    # ETL 用应用账号 awardie_v3 连接,演练库得单独授权(与 CI 建库同做法:
    # CI 也会 CREATE USER + GRANT 到 awardie_v3_test,否则后端测试连不上)
    # 专用演练账号 + 每次随机口令,不用生产应用账号名(awardie_v3)——
    # 原写法在这台机上恰好是 no-op(账号已存在),换台机器就会用仓库里的明文口令
    # 在 host 通配 '%' 上建出**生产账号名**的常驻账号。口令随机 = 仓库里没有可用凭据。
    grant_sql = (f"CREATE USER IF NOT EXISTS '{rehearsal_user}'@'%' IDENTIFIED BY '{rehearsal_pw}'; "
                 f"GRANT ALL PRIVILEGES ON {REHEARSE_DB}.* TO '{rehearsal_user}'@'%'; FLUSH PRIVILEGES")
    rc, out = run(mysql_cmd(None, password) + ['-e', grant_sql])
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
    rehearsal_env = dict(env, AWARDIE_TARGET_DB=REHEARSE_DB,
                          AWARDIE_MYSQL_USER=rehearsal_user,
                          AWARDIE_MYSQL_PASSWORD=rehearsal_pw)
    # 防呆:演练开始前先确认 ETL 真的指向演练库,而不是默认库
    # 逐个探针,不能只探一个:ETL 若新增 --target-db 参数或第二条连接路径,
    # 探针会静默过期却仍打印绿灯。全部探一遍,任一不指向演练库就中止。
    # 两种选库机制都要认:ETL 系列用 MYSQL dict 的 db 键,v3_apply_missing_columns.py
    # 用模块级 TARGET_DB 常量(它走 mysql CLI 不用 pymysql)。只认一种会误报。
    probe_src = ("import importlib.util,sys;"
                 "spec=importlib.util.spec_from_file_location('m', sys.argv[1]);"
                 "m=importlib.util.module_from_spec(spec);"
                 "sys.modules['m']=m;spec.loader.exec_module(m);"
                 "print(getattr(m, 'TARGET_DB', None) or (m.MYSQL.get('db') if hasattr(m,'MYSQL') else None) or '?')")
    bad = []
    for script, _desc in ETL_STEPS:
        path = os.path.join(ROOT, script)
        probe = subprocess.run([PY, '-c', probe_src, path], capture_output=True,
                               text=True, env=rehearsal_env, cwd=ROOT)
        db = probe.stdout.strip().splitlines()[-1] if probe.stdout.strip() else '?'
        if db != REHEARSE_DB:
            bad.append(f'{os.path.basename(script)}->{db}')
    if bad:
        print(f'[abort] 下列脚本实际指向的不是演练库 {REHEARSE_DB}(可能污染真实库): '
              f'{", ".join(bad)} —— 拒绝执行')
        if not keep:
            drop()
        return 1
    print(f'[guard] {len(ETL_STEPS)} 个 ETL 的目标库均已确认为 {REHEARSE_DB}')

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
