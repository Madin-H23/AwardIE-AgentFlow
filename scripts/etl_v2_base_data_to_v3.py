#!/usr/bin/env python
"""v3 批3 基础数据域 ETL:PG(v2 awardie_dev 的 competitions/laboratories)→ MySQL(v3 awardie_v3)。

用法(venv python):
    AWARDIE_MYSQL_PASSWORD=<v3 应用口令> python scripts/etl_v2_base_data_to_v3.py

特性:
- 显式保留 v2 主键 id(INSERT ... ON DUPLICATE KEY UPDATE 按主键幂等,可重复执行);
  为批12 成果表外键迁移(competition_id/laboratory_id)铺路;
- competitions:11 业务列全迁,布尔 → BIT(1);v2 competition_name 唯一性前置校验;
- laboratories:仅 name/description(cover_image 属批4 文件域,不迁);
- 前置清理:dev 库批1 遗留的实验室测试行(deleted=1)物理删除,保证迁后即干净;
- 前置校验:v2 竞赛名唯一、目标库 id 异位冲突(同 id 不同名则中止,不静默覆盖);
- 执行后自校:行数 / id 集合差 / 布尔计数分布 / AUTO_INCREMENT。

环境变量:AWARDIE_MYSQL_PASSWORD(v3 MySQL 口令,必填);PGPASSWORD(默认 postgres)。
"""
import os
import sys

import psycopg2
import pymysql

PG = dict(host="127.0.0.1", port=5433, dbname="awardie_dev", user="postgres",
          password=os.environ.get("PGPASSWORD", "postgres"))
MYSQL = dict(host="127.0.0.1", port=3307, db="awardie_v3", user="awardie_v3",
             password=os.environ.get("AWARDIE_MYSQL_PASSWORD", ""), charset="utf8mb4")

COMPETITION_COLS = [
    "id", "competition_name", "official_website", "organizer", "competition_time",
    "participant_requirements", "grade_category", "brief_description", "alias_list",
    "white_list", "watch_list", "is_auto_added", "creator", "updater", "tenant_id",
]
LAB_COLS = ["id", "name", "description", "creator", "updater", "tenant_id"]


def read_source():
    pg = psycopg2.connect(**PG)
    cur = pg.cursor()
    cur.execute("""
        SELECT id, competition_name, official_website, organizer, competition_time,
               participant_requirements, grade_category, brief_description, alias_list,
               white_list, watch_list, is_auto_added
        FROM competitions ORDER BY id
    """)
    competitions = cur.fetchall()
    cur.execute("SELECT id, name, description FROM laboratories ORDER BY id")
    laboratories = cur.fetchall()
    pg.close()
    return competitions, laboratories


def validate_source(competitions, laboratories):
    names = [row[1] for row in competitions]
    if len(set(names)) != len(names):
        dup = [n for n in set(names) if names.count(n) > 1]
        print(f"FATAL: v2 竞赛名重复(ETL 依赖唯一语义): {dup[:5]}")
        return False
    lab_names = [row[1] for row in laboratories]
    if len(set(lab_names)) != len(lab_names):
        dup = [n for n in set(lab_names) if lab_names.count(n) > 1]
        print(f"FATAL: v2 实验室名重复: {dup[:5]}")
        return False
    return True


def upsert(cur, table, cols, rows, bool_cols=()):
    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(f"`{c}`" for c in cols)
    updates = ", ".join(f"`{c}` = VALUES(`{c}`)" for c in cols if c != "id")
    sql = f"INSERT INTO `{table}` ({col_sql}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}"
    # 源行只含业务列,审计/租户列由本脚本补齐
    extra = {c: ("etl" if c in ("creator", "updater") else 1) for c in cols}
    payload = []
    for row in rows:
        values = list(row)
        for col in cols[len(row):]:
            values.append(extra[col])
        for idx, col in enumerate(cols):
            if col in bool_cols:
                values[idx] = 1 if values[idx] else 0
        payload.append(tuple(values))
    cur.executemany(sql, payload)


def main() -> int:
    if not MYSQL["password"]:
        print("FATAL: 环境变量 AWARDIE_MYSQL_PASSWORD 未设置(v3 应用口令)")
        return 2
    competitions, laboratories = read_source()
    print(f"[read] v2 competitions={len(competitions)} laboratories={len(laboratories)}")
    if not validate_source(competitions, laboratories):
        return 1

    my = pymysql.connect(**MYSQL)
    cur = my.cursor()

    # 前置清理:批1 遗留的实验室测试行(全为 deleted=1),物理删除后再迁,dev 库即干净
    cur.execute("SELECT COUNT(*) FROM awardie_laboratories WHERE deleted = b'1'")
    stale = cur.fetchone()[0]
    if stale:
        cur.execute("DELETE FROM awardie_laboratories WHERE deleted = b'1'")
        print(f"[clean] 清理批1 遗留实验室测试行 {stale} 条")

    # 前置校验:目标库已有行(非本脚本迁入的)与 v2 id 冲突则中止,不静默覆盖
    # 口径:只计未逻辑删除的行(v3 为逻辑删除,已删行不占位)
    cur.execute("SELECT id, competition_name FROM awardie_competitions WHERE deleted = b'0'")
    existing = dict(cur.fetchall())
    conflict = [row[0] for row in competitions
                if row[0] in existing and existing[row[0]] != row[1]]
    if conflict:
        print(f"FATAL: 目标库同 id 竞赛名与 v2 不一致(需人工确认): {conflict[:5]}")
        my.close()
        return 1
    cur.execute("SELECT id, name FROM awardie_laboratories WHERE deleted = b'0'")
    existing_labs = dict(cur.fetchall())
    conflict_labs = [row[0] for row in laboratories
                     if row[0] in existing_labs and existing_labs[row[0]] != row[1]]
    if conflict_labs:
        print(f"FATAL: 目标库同 id 实验室名与 v2 不一致(需人工确认): {conflict_labs[:5]}")
        my.close()
        return 1

    upsert(cur, "awardie_competitions", COMPETITION_COLS, competitions,
           bool_cols=("white_list", "watch_list", "is_auto_added"))
    upsert(cur, "awardie_laboratories", LAB_COLS, laboratories)
    my.commit()

    # 末尾抬自增
    for table in ("awardie_competitions", "awardie_laboratories"):
        cur.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}")
        nxt = cur.fetchone()[0]
        cur.execute(f"ALTER TABLE {table} AUTO_INCREMENT = {nxt}")
    my.commit()

    # 自校
    # 口径:只计未逻辑删除的行(v3 逻辑删除,已删行不计入)
    cur.execute("SELECT COUNT(*), COALESCE(SUM(white_list), 0), COALESCE(SUM(watch_list), 0),"
                " COALESCE(SUM(is_auto_added), 0) FROM awardie_competitions WHERE deleted = b'0'")
    total, white, watch, auto = cur.fetchone()
    cur.execute("SELECT id FROM awardie_competitions WHERE deleted = b'0'")
    v3_ids = {r[0] for r in cur.fetchall()}
    v2_ids = {r[0] for r in competitions}
    cur.execute("SELECT COUNT(*) FROM awardie_laboratories WHERE deleted = b'0'")
    lab_total = cur.fetchone()[0]
    cur.execute("SELECT id FROM awardie_laboratories WHERE deleted = b'0'")
    v3_lab_ids = {r[0] for r in cur.fetchall()}
    v2_lab_ids = {r[0] for r in laboratories}
    cur.execute("SHOW TABLE STATUS LIKE 'awardie_competitions'")
    auto_inc = cur.fetchone()[10]
    my.close()

    print(f"[verify] competitions={total}(期望 {len(competitions)}) id 差={sorted(v2_ids ^ v3_ids)}")
    print(f"[verify] white/watch/auto={white}/{watch}/{auto}(v2 期望 117/51/45)")
    print(f"[verify] laboratories={lab_total}(期望 {len(laboratories)}) id 差={sorted(v2_lab_ids ^ v3_lab_ids)}")
    print(f"[verify] competitions AUTO_INCREMENT={auto_inc} (max id={max(v2_ids)})")
    ok = (total == len(competitions) and not (v2_ids ^ v3_ids)
          and lab_total == len(laboratories) and not (v2_lab_ids ^ v3_lab_ids))
    print("[result] " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
