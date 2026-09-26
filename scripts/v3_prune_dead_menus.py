#!/usr/bin/env python
"""v3 死菜单剪枝:删掉 component 指向已删除前端页面的菜单,以及剪完剩下的空壳目录。

用法(venv python,需 pymysql):
    AWARDIE_MYSQL_PASSWORD=<v3 应用口令> python scripts/v3_prune_dead_menus.py [--check] [--dry-run]

背景:前端基座只保留 infra/system 两套(24 个示例业务模块已删,见前端 README),
但芋道种子 SQL 里这些模块的菜单还在,component 字段指向已不存在的 .vue。
动态路由解析失败 = **点进去白屏**。实测 392 个带 component 的菜单里 335 个是死的,
手工维护 ID 清单必然漏(已经漏过一次:顶级目录筛掉了 type=2 且 parent_id=0 的
「报表管理」id=207)。本脚本改用真实判据——**磁盘上有没有那个 .vue**——自维护。

两轮判据:
  A. component 非空但 <前端>/src/views/<component>.vue 不存在 → 死菜单;
  B. 走完 A 之后,component 为空且**没有任何存活子菜单**的(type=1/2 的壳) → 空壳,
     留着只是侧边栏里一个点不动的条目。

保留白名单(前缀):business/、portal/ —— 我们的业务层页面,任何情况下都不剪。
type=3 按钮不参与(component 本就为空,但它们是权限点,不能按 B 删)。

删除顺序:先子后父(无外键,按逻辑顺序),并同步删 system_role_menu 授权。
--check 只检查不落盘,退出码 1 = 仍有死菜单(可挂 CI)。
"""
import os
import sys

import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS_DIR = os.path.join(ROOT, 'awardie-v3', 'yudao-ui', 'yudao-ui-admin-vue3', 'src', 'views')
# 我们的业务层页面,任何情况下都不得被剪掉
KEEP_PREFIXES = ('business', 'portal')
DB = dict(host='127.0.0.1', port=3307, user=os.environ.get('AWARDIE_MYSQL_USER', 'root'), database=os.environ.get("AWARDIE_TARGET_DB", "awardie_v3"), charset='utf8mb4')


def main() -> int:
    check_only = '--check' in sys.argv
    dry_run = '--dry-run' in sys.argv
    password = os.environ.get('AWARDIE_MYSQL_PASSWORD', '')
    if not password:
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2

    conn = pymysql.connect(**DB, password=password)
    with conn.cursor() as cur:
        cur.execute("SELECT id, parent_id, name, IFNULL(component, ''), type "
                    "FROM system_menu WHERE deleted = 0")
        rows = cur.fetchall()

    dead = []          # A 轮:文件缺失
    shells = []        # B 轮:空壳
    for mid, pid, name, comp, typ in rows:
        if typ == 3:            # 按钮是权限点,不参与剪枝
            continue
        if comp:
            if comp.startswith(KEEP_PREFIXES):
                continue
            if not os.path.isfile(os.path.join(VIEWS_DIR, comp + '.vue')):
                dead.append((mid, pid, name, comp))
        else:
            shells.append((mid, pid, name, typ))

    # B 轮:剥空壳。先把 A 轮判死的移出存活集,再反复删掉「无存活子菜单」的壳,
    # 直到不再变化(删掉一层可能让父级也变成空壳)。
    alive_ids = {r[0] for r in rows} - {d[0] for d in dead}
    shells_by_id = {s[0]: s for s in shells}
    changed = True
    while changed:
        changed = False
        parents_with_kids = {r[1] for r in rows if r[0] in alive_ids}
        for mid in list(alive_ids):
            s = shells_by_id.get(mid)
            if s is None:
                continue
            if mid not in parents_with_kids:      # 没有任何存活子菜单
                alive_ids.discard(mid)
                changed = True
    empty_shells = [shells_by_id[mid] for mid in shells_by_id if mid not in alive_ids]
    # 固定入口必须留住:1/2 是芋道系统与基础设施的根,3xxx 是我们的三个门户/工作台
    PROTECTED = {1, 2, 3000, 3100, 3200}
    empty_shells = [e for e in empty_shells if e[0] not in PROTECTED]

    with_component = [r for r in rows if r[3]]
    print(f'[scan] 菜单 {len(rows)} 个:带 component {len(with_component)} 个 / '
          f'文件缺失 {len(dead)} 个 / 空壳 {len(empty_shells)} 个')

    for mid, pid, name, comp in sorted(dead):
        print(f'  dead   {mid:>6}  parent={pid:<6} {comp:<45} {name}')
    for mid, pid, name, _ in sorted(empty_shells):
        print(f'  shell  {mid:>6}  parent={pid:<6} {"":<45} {name}')

    targets = [d[0] for d in dead] + [e[0] for e in empty_shells]
    if not targets:
        print('[ok] 没有死菜单')
        return 0

    if check_only:
        print(f'[check] 存在 {len(targets)} 个死菜单/空壳(未落盘)')
        return 1
    if dry_run:
        print('[dry-run] 未落盘')
        return 0

    id_list = ','.join(str(i) for i in targets)
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM system_role_menu WHERE menu_id IN ({id_list})")
        print(f'[exec] {cur.rowcount} 行 role_menu')
        cur.execute(f"DELETE FROM system_menu WHERE id IN ({id_list})")
        print(f'[exec] {cur.rowcount} 行 system_menu')
    conn.commit()
    conn.close()
    print(f'[done] 已删除 {len(dead)} 个死菜单 + {len(empty_shells)} 个空壳,及其授权')
    return 0


if __name__ == '__main__':
    sys.exit(main())
