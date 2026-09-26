#!/usr/bin/env python
"""v3 切流前置:源库(v2 PG)与目标库(v3 MySQL)业务表**列级**比对。

为什么必须先做这个:切流是单向的,列对不上 = 数据在写进目标库那一刻就没了,
之后再补也补不回来。批9 的三条"前置债"里,`物化不写 year` 与 `awards 无
granted_role 列` 的真实成因就在这里——**不是没实现,是表根本没有这两列**。

用法(venv python,需 psycopg2 + pymysql):
    AWARDIE_MYSQL_PASSWORD=<口令> python scripts/v3_schema_diff.py [--json]

映射:PG 表名 → v3 表名。带 v2_ 前缀的是 v2 自有命名(award_*),
对应 v3 的 awardie_award_*;其余同名加 awardie_ 前缀。
"""
import json
import os
import sys

import psycopg2
import pymysql

PG_TABLES = [
    'awards', 'award_student_winners', 'award_teacher_winners', 'award_related_students',
    'competitions', 'laboratories', 'laboratory_instructors', 'laboratory_students',
    'laboratory_assistants', 'laboratory_downloads', 'laboratory_images',
    'pending_achievements', 'review_logs', 'achievement_audit_log',
    'innovation_projects', 'innovation_project_students',
    'patents', 'software_copyrights', 'other_files', 'templates',
    'users', 'old_user_map',
]

# PG → v3 表名。None = v3 没有对应表(需决策)
TABLE_MAP = {
    'awards': 'awardie_awards',
    'award_student_winners': 'awardie_award_student_winners',
    'award_teacher_winners': None,          # 批9 前置债:无教师关系表
    'award_related_students': None,
    'competitions': 'awardie_competitions',
    'laboratories': 'awardie_laboratories',
    'laboratory_instructors': 'awardie_laboratory_instructors',
    'laboratory_students': 'awardie_laboratory_students',
    'laboratory_assistants': 'awardie_laboratory_assistants',
    'laboratory_downloads': 'awardie_laboratory_downloads',
    'laboratory_images': 'awardie_laboratory_images',
    'pending_achievements': 'awardie_pending_achievements',
    'review_logs': 'awardie_achievement_audit_log',
    'achievement_audit_log': 'awardie_achievement_audit_log',
    'innovation_projects': 'awardie_innovation_projects',
    'innovation_project_students': 'awardie_innovation_project_students',
    'patents': 'awardie_patents',
    'software_copyrights': 'awardie_software_copyrights',
    'other_files': 'awardie_other_files',
    'templates': 'awardie_templates',
    'users': None,                          # 已迁为 system_users + awardie_user_profile
    'old_user_map': None,                   # ETL 中间表,无需迁
}

# v3 侧的框架列:由 BaseDO / 多租户自动填充,不是业务列
V3_BASE_COLS = {'creator', 'create_time', 'updater', 'update_time', 'deleted', 'tenant_id'}


def pg_columns(cur, table):
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (table,))
    return [r[0] for r in cur.fetchall()]


def mysql_columns(cur, table):
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position""", (table,))
    return [r[0] for r in cur.fetchall()]


def main() -> int:
    as_json = '--json' in sys.argv
    password = os.environ.get('AWARDIE_MYSQL_PASSWORD', '')
    if not password:
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2

    pg = psycopg2.connect(host='127.0.0.1', port=5433, user='postgres',
                          password=os.environ.get('PGPASSWORD', 'postgres'), dbname='awardie_dev')
    pgc = pg.cursor()
    my = pymysql.connect(host='127.0.0.1', port=3307, user=os.environ.get('AWARDIE_MYSQL_USER', 'root'),
                         password=password, database=os.environ.get("AWARDIE_TARGET_DB", "awardie_v3"), charset='utf8mb4')
    myc = my.cursor()

    result = {}
    blocked = []
    for t in PG_TABLES:
        pcols = pg_columns(pgc, t)
        if not pcols:
            continue
        target = TABLE_MAP.get(t, f"awardie_{t}")
        mcols = mysql_columns(myc, target) if target else []
        if not mcols:
            if target is None:
                result[t] = {'target': None, 'missing_columns': pcols}
                blocked.append((t, target, pcols))
            continue
        only_pg = [c for c in pcols if c not in mcols]
        only_my = [c for c in mcols if c not in pcols and c not in V3_BASE_COLS]
        result[t] = {'target': target, 'pg_cols': pcols, 'v3_cols': mcols,
                     'missing_columns': only_pg, 'extra_columns': only_my}
        if only_pg:
            blocked.append((t, target, only_pg))

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        pg.close(); my.close()
        return 0

    print(f"{'源表':<32} {'目标表':<40} {'缺列':>4}  缺失列(切流会丢的数据)")
    print('-' * 120)
    for t, target, cols in blocked:
        print(f"{t:<32} {str(target):<40} {len(cols):>4}  {', '.join(cols)}")
    print()
    if blocked:
        print(f"[FAIL] {len(blocked)} 张表存在列缺失 —— 切流前必须先做 schema 迁移,否则这些列的数据不可逆丢失")
    else:
        print('[ok] 所有待迁表列齐平')
    pg.close(); my.close()
    return 1 if blocked else 0


if __name__ == '__main__':
    sys.exit(main())
