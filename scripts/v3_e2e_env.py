# -*- coding: utf-8 -*-
"""批33:构建 E2E 隔离测试库 awardie_v3_e2e(全功能 GUI 测试的写入沙箱)。

与真实库 awardie_v3、后端集成测试库 awardie_v3_test 三库并立:
  - awardie_v3      真实数据(V1 迁入),E2E 决不写入
  - awardie_v3_test 后端 MockMvc 集成测试用(CI/本地,用例自清表)
  - awardie_v3_e2e  本脚本构建:七脚本链全新库 + 真实三账号克隆,Playwright 业务流写入沙箱

流程:drop 旧库/旧用户 → 建库 → 七脚本链(官方+cleanup+业务+菜单+用户域+菜单瘦身)
  → 租户改名 AwardIE(登录页按名解析) → 从真实库克隆三账号(admin/02110606/212306413,
  连同 bcrypt 口令哈希与角色绑定,凭据与既有约定一致) → 建专用应用用户并授权。

幂等:每次运行全量重建。用法:
    AWARDIE_MYSQL_ROOT_PASSWORD=<root 口令> python scripts/v3_e2e_env.py --apply
    (不带 --apply 仅打印计划;随机口令打印一次供编排脚本取用)
"""
import argparse
import secrets
import subprocess
import sys
import os

DB = 'awardie_v3_e2e'
USER = 'awardie_e2e_ro'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MYSQL_CLI = os.environ.get('AWARDIE_MYSQL_CLI',
                           r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe')
SQL_ORDER = [
    ('awardie-v3/sql/mysql/ruoyi-vue-pro.sql', '官方基线(脱敏版)'),
    ('awardie-v3/sql/mysql/quartz.sql', 'quartz 引擎'),
    ('awardie-v3/sql/awardie-cleanup.sql', '演示数据清理'),
    ('awardie-v3/sql/awardie-business.sql', '业务表+菜单'),
    ('awardie-v3/sql/awardie-business-menus.sql', '业务菜单'),
    ('awardie-v3/sql/awardie-user-domain.sql', '三角色+授权'),
    ('awardie-v3/sql/awardie-menu-slim.sql', '菜单瘦身'),
]
# 克隆的账号(真实库中的既有约定账号,凭据见 README/CLAUDE)
CLONE_USERNAMES = ('admin', '02110606', '212306413')
CLONE_LIST = ','.join(f"'{u}'" for u in CLONE_USERNAMES)


def run_root(password, sql, db=None):
    cmd = [MYSQL_CLI, '--default-character-set=utf8mb4', '-h', '127.0.0.1', '-P', '3307',
           '-uroot', f'-p{password}']
    if db:
        cmd.append(db)
    r = subprocess.run(cmd, input=sql, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='实际构建;缺省仅打印计划')
    ap.add_argument('--e2e-password', default=secrets.token_urlsafe(12),
                    help='专用应用用户口令(缺省随机,由编排脚本传给后端)')
    args = ap.parse_args()
    root_pw = os.environ.get('AWARDIE_MYSQL_ROOT_PASSWORD', '')
    if not root_pw:
        print('缺少环境变量 AWARDIE_MYSQL_ROOT_PASSWORD', file=sys.stderr)
        return 2

    print(f'== E2E 库构建计划: {DB} / 应用用户 {USER} ==')
    if not args.apply:
        for script, desc in SQL_ORDER:
            print(f'  [plan] {desc}: {script}')
        print('预览模式,加 --apply 执行')
        return 0

    # 1) drop 旧库与旧用户
    rc, out = run_root(root_pw,
                       f'DROP DATABASE IF EXISTS {DB}; DROP USER IF EXISTS \'{USER}\'@\'%\';')
    if rc != 0:
        print(f'[1] 清理旧库失败: {out[:300]}', file=sys.stderr)
        return 1
    print('[1] 旧库/旧用户清理 OK')

    # 2) 建库 + 建专用用户
    rc, out = run_root(root_pw,
                       f'CREATE DATABASE {DB} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin; '
                       f'CREATE USER \'{USER}\'@\'%\' IDENTIFIED BY \'{args.e2e_password}\'; '
                       f'GRANT ALL PRIVILEGES ON {DB}.* TO \'{USER}\'@\'%\'; FLUSH PRIVILEGES;')
    if rc != 0:
        print(f'[2] 建库/授权失败: {out[:300]}', file=sys.stderr)
        return 1
    print('[2] 建库+专用用户 OK')

    # 3) 七脚本链
    for i, (script, desc) in enumerate(SQL_ORDER, 1):
        with open(os.path.join(ROOT, script), encoding='utf-8') as f:
            rc, out = run_root(root_pw, f.read(), db=DB)
        if rc != 0:
            print(f'[3] SQL {i}/{len(SQL_ORDER)} {desc} FAIL:\n{out[:600]}', file=sys.stderr)
            return 1
        print(f'[3] SQL {i}/{len(SQL_ORDER)} {desc:<24} OK')

    # 4) 租户改名(登录页按名解析;官方基线种的是上游名)
    rc, out = run_root(root_pw,
                       f"UPDATE system_tenant SET name='AwardIE', contact_name='AwardIE 项目组' WHERE id=1;",
                       db=DB)
    if rc != 0:
        print(f'[4] 租户改名失败: {out[:300]}', file=sys.stderr)
        return 1
    print('[4] 租户改名 AwardIE OK')

    # 5) 克隆三账号+角色绑定(跨库 INSERT SELECT,连 bcrypt 哈希一起拿,凭据即既有约定)
    clone_sql = (
        f'INSERT INTO {DB}.system_users SELECT * FROM awardie_v3.system_users '
        f'WHERE username IN ({CLONE_LIST}); '
        f'INSERT INTO {DB}.system_user_role SELECT * FROM awardie_v3.system_user_role '
        f'WHERE deleted = 0 AND user_id IN '
        f'(SELECT id FROM awardie_v3.system_users WHERE username IN ({CLONE_LIST}));')
    rc, out = run_root(root_pw, clone_sql, db=DB)
    if rc != 0:
        print(f'[5] 账号克隆失败: {out[:300]}', file=sys.stderr)
        return 1
    rc, n = run_root(root_pw, f'SELECT COUNT(*) FROM system_users;', db=DB)
    print(f'[5] 账号克隆 OK(system_users 行数: {n.strip().splitlines()[-1] if n else "?"})')

    # 6) 删官方基线自带的 admin(id=1):与克隆的真实 admin(1832) 同 username,登录 selectOne 会撞。
    #    真实 admin 绑定 awardie_admin+super_admin 双角色,删官方后权限无损(已实证)。
    rc, out = run_root(root_pw,
                       'DELETE FROM system_user_role WHERE user_id = 1; '
                       'DELETE FROM system_users WHERE id = 1;',
                       db=DB)
    if rc != 0:
        print(f'[6] 删官方 admin 失败: {out[:300]}', file=sys.stderr)
        return 1
    print('[6] 官方 admin(id=1) 去重 OK(保留克隆的真实 admin)')

    print(f'\n[ok] {DB} 就绪。后端连接参数:')
    print(f'  url={f"jdbc:mysql://127.0.0.1:3307/{DB}"}')
    print(f'  username={USER}')
    print(f'  password={args.e2e_password}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
