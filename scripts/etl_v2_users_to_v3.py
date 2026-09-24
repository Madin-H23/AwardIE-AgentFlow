#!/usr/bin/env python
"""v3 批2 存量用户 ETL:PG(v2 awardie_dev.users)→ MySQL(v3 awardie_v3)。

用法(venv python):
    AWARDIE_MYSQL_PASSWORD=<v3 应用口令> python scripts/etl_v2_users_to_v3.py

特性:
- 显式保留 v2 用户 id(INSERT ... ON DUPLICATE KEY UPDATE 按主键幂等,可重复执行);
  v2 admin(id=1)覆盖芋道 stock admin(口令随之变为 v2 的,角色按映射另授);
- 角色映射:admin→awardie_admin(100)/teacher→awardie_teacher(101)/student→awardie_student(102);
- 字段映射:login_code→username、name→nickname、phone→mobile、password_hash→password(原样,
  scrypt 格式)、user_activated→status(true→0/false→1);creator/updater='etl';tenant_id=1;
- 资料扩展字段(major/grade/title/qq/skills/profile_is_public)→ awardie_user_profile;
- 前置校验:v2 login_code 唯一性、目标库 username 异位冲突(有则中止)、口令哈希格式;
- 已知限制上报(不静默):非字母数字 login_code(芋道登录校验不通过,如 v2 的"学号"垃圾行)、
  空口令用户;
- 执行后自校:行数/id 集合差/哈希前缀分布。

环境变量:AWARDIE_MYSQL_PASSWORD(v3 MySQL 口令,必填);PGPASSWORD(默认 postgres)。
"""
import os
import re
import sys
from collections import Counter

import psycopg2
import pymysql

PG = dict(host="127.0.0.1", port=5433, dbname="awardie_dev", user="postgres",
          password=os.environ.get("PGPASSWORD", "postgres"))
MYSQL = dict(host="127.0.0.1", port=3307, db="awardie_v3", user="awardie_v3",
             password=os.environ.get("AWARDIE_MYSQL_PASSWORD", ""), charset="utf8mb4")

ROLE_MAP = {"admin": 100, "teacher": 101, "student": 102}
# v2 admin 追加 super_admin(芋道系统菜单挂超管角色;纯 awardie_admin 只有业务菜单,管不了用户/角色)
EXTRA_ROLES = {100: [1]}
# 已知预期覆盖:芋道 stock admin(id=1, username=admin)被 v2 用户 id=1 顶替(否则 v2 admin
# 登录后与 stock admin 同名双行,selectByUsername 会 TooManyResults)
STOCK_ADMIN = (1, "admin")
ALNUM = re.compile(r"^[A-Za-z0-9]+$")

USER_COLS = """id, username, password, nickname, status, mobile, sex, creator, updater, tenant_id"""


def main() -> int:
    if not MYSQL["password"]:
        print("FATAL: 环境变量 AWARDIE_MYSQL_PASSWORD 未设置(v3 应用口令)")
        return 2
    pg = psycopg2.connect(**PG)
    pgcur = pg.cursor()
    pgcur.execute("""
        SELECT id, login_code, name, role, password_hash, user_activated, phone,
               major, grade, title, qq, skills, profile_is_public
        FROM users ORDER BY id
    """)
    rows = pgcur.fetchall()
    pg.close()
    print(f"[read] v2 users: {len(rows)}")

    # ---- 前置校验 ----
    codes = [r[1] for r in rows]
    dup = [c for c, n in Counter(codes).items() if n > 1]
    if dup:
        print(f"FATAL: v2 login_code 重复 {dup[:5]}(共 {len(dup)} 个),中止")
        return 3
    non_alnum = [r[0] for r in rows if not (r[1] and ALNUM.match(r[1]))]
    null_pw = [r[0] for r in rows if not r[4]]
    bad_hash = [r[0] for r in rows if r[4] and not (r[4].startswith("scrypt:") or r[4].startswith("$2"))]
    unknown_role = sorted({r[3] for r in rows} - set(ROLE_MAP))
    if unknown_role:
        print(f"FATAL: v2 存在未映射角色 {unknown_role},中止")
        return 4
    print(f"[check] 非字母数字 login_code(芋道登录校验不通过,照迁但上报): {non_alnum}")
    print(f"[check] 空口令用户(无法登录,照迁但上报): {null_pw}")
    if bad_hash:
        print(f"[check] 非 scrypt/bcrypt 哈希(按原样迁,上报 id): {bad_hash[:10]}")

    my = pymysql.connect(**MYSQL)
    cur = my.cursor()
    cur.execute("SELECT id, username FROM system_users")
    existing = dict(cur.fetchall())  # id -> username
    clash = [(r[0], r[1], existing[r[0]]) for r in rows
             if r[0] in existing and existing[r[0]] != r[1]
             and (r[0], existing[r[0]]) != STOCK_ADMIN]
    if clash:
        print(f"FATAL: 目标库同 id 异 username 冲突(需人工裁决): {clash[:5]}")
        my.close()
        return 5
    if STOCK_ADMIN[0] in existing:
        print(f"[note] stock admin(id=1, username=admin)将被 v2 用户 id=1({existing[1]!r} 将被顶替)覆盖"
              "——预期行为:v2 admin 成为唯一 'admin'")

    # ---- 写 system_users(按主键幂等;v2 admin id=1 覆盖 stock admin) ----
    user_sql = f"""
        INSERT INTO system_users ({USER_COLS}, dept_id, post_ids, remark)
        VALUES (%s, %s, %s, %s, %s, %s, 1, 'etl', 'etl', 1, NULL, '[]', %s)
        ON DUPLICATE KEY UPDATE
            username = VALUES(username), password = VALUES(password), nickname = VALUES(nickname),
            status = VALUES(status), mobile = VALUES(mobile), updater = 'etl'
    """
    profile_sql = """
        INSERT INTO awardie_user_profile (user_id, major, grade, title, qq, skills, profile_is_public, creator, updater)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'etl', 'etl')
        ON DUPLICATE KEY UPDATE
            major = VALUES(major), grade = VALUES(grade), title = VALUES(title),
            qq = VALUES(qq), skills = VALUES(skills), profile_is_public = VALUES(profile_is_public),
            updater = 'etl'
    """
    ids = []
    for r in rows:
        uid, code, name, role, pw, activated, phone, major, grade, title, qq, skills, pub = r
        cur.execute(user_sql, (uid, code, pw or "", name, 0 if activated else 1,
                               phone or None, f"v2 迁移({role})"))
        cur.execute("DELETE FROM system_user_role WHERE user_id = %s", (uid,))
        role_ids = [ROLE_MAP[role]] + EXTRA_ROLES.get(ROLE_MAP[role], [])
        for rid in role_ids:
            cur.execute("INSERT INTO system_user_role (role_id, user_id, creator, updater, tenant_id) "
                        "VALUES (%s, %s, 'etl', 'etl', 1)", (rid, uid))
        cur.execute(profile_sql, (uid, major, grade, title, qq, skills, bool(pub)))
        ids.append(uid)

    # ---- 抬自增(避免后续插入撞 id) ----
    cur.execute("SELECT MAX(id) FROM system_users")
    max_id = cur.fetchone()[0] or 0
    cur.execute(f"ALTER TABLE system_users AUTO_INCREMENT = {max_id + 1}")
    my.commit()

    # ---- 自校 ----
    cur.execute("SELECT COUNT(*) FROM system_users")
    n_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM awardie_user_profile")
    n_profiles = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM system_user_role WHERE creator = 'etl'")
    n_roles = cur.fetchone()[0]
    cur.execute("SELECT password FROM system_users WHERE id IN (%s)" % ",".join(map(str, ids)))
    prefixes = Counter(("scrypt" if p.startswith("scrypt:") else "bcrypt" if p.startswith("$2") else "other")
                       for (p,) in cur.fetchall())
    cur.execute("SELECT id FROM system_users")
    mysql_ids = {r[0] for r in cur.fetchall()}
    missing = sorted(set(ids) - mysql_ids)
    my.close()
    print(f"[done] system_users={n_users} profile={n_profiles} role_links={n_roles} "
          f"hash_prefix={dict(prefixes)} missing_ids={missing[:10]}")
    print(f"[done] AUTO_INCREMENT -> {max_id + 1};已知限制:非字母数字 {len(non_alnum)} 个、空口令 {len(null_pw)} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
