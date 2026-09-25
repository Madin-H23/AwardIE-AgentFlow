#!/usr/bin/env python3
"""大创 project_no 唯一性改造的一次性迁移(批8 决策2,2026-09-25 用户拍板)

背景
----
改造前 ``awardie_innovation_projects`` 的唯一键是 ``UNIQUE(project_no)``——**全表**唯一:
  · A 租户用了 DC-001,B 租户就不能用(多租户语义错误);
  · 逻辑删除后该编号仍被唯一键占着,无法用同一编号重建(永久占位)。

改造后
------
用生成列 ``active_project_no``(活动行时等于 project_no,已删行为 NULL)+ 复合唯一键
``(tenant_id, active_project_no)``。MySQL 唯一索引不约束 NULL,故"仅活动行参与唯一",
一次性满足三条语义:
  1. 同租户同编号的活动行唯一(导入幂等判据)
  2. 不同租户可各自使用相同编号(多租户隔离)
  3. 逻辑删除后可复用同一编号(不留永久占位)

适用范围
--------
**只对批8 之前已建过该表的环境**(dev 库 / 任何旧 test 库)。全新库由
``sql/awardie-business.sql`` 的建表语句直接给出最终形态,不需要本脚本。

幂等
----
重复执行安全:已改造过的库会跳过(检测生成列是否存在)。

用法
----
    AWARDIE_MYSQL_PASSWORD=*** python scripts/migrate_project_no_tenant_unique.py [库名]
"""
import os
import sys

import pymysql

DB_DEFAULT = "awardie_v3"


def main() -> int:
    db = sys.argv[1] if len(sys.argv) > 1 else DB_DEFAULT
    password = os.environ.get("AWARDIE_MYSQL_PASSWORD")
    if not password:
        print("FATAL: 环境变量 AWARDIE_MYSQL_PASSWORD 未设置")
        return 1

    conn = pymysql.connect(host="127.0.0.1", port=3307, user="awardie_v3",
                           password=password, database=db, autocommit=True)
    cur = conn.cursor()

    # 幂等守卫:生成列已存在说明本库已改造
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'awardie_innovation_projects' "
        "AND COLUMN_NAME = 'active_project_no'")
    if cur.fetchone()[0] > 0:
        print(f"[skip] {db}: 生成列 active_project_no 已存在,本库已改造")
        conn.close()
        return 0

    # 前置检查:改造前若存在"同编号跨租户"或"同编号含已删行"的数据,新键会冲突
    cur.execute("SELECT COUNT(*) FROM awardie_innovation_projects WHERE deleted = b'0'")
    active = cur.fetchone()[0]
    cur.execute(
        "SELECT tenant_id, project_no, COUNT(*) FROM awardie_innovation_projects "
        "WHERE deleted = b'0' AND project_no IS NOT NULL AND project_no <> '' "
        "GROUP BY tenant_id, project_no HAVING COUNT(*) > 1")
    dupes = cur.fetchall()
    if dupes:
        print("FATAL: 以下 (tenant_id, project_no) 在活动行中重复,新唯一键无法建立:")
        for row in dupes[:10]:
            print("   ", row)
        print("请先人工清理重复数据再迁移。中止。")
        conn.close()
        return 1

    cur.execute(
        "ALTER TABLE awardie_innovation_projects "
        "ADD COLUMN active_project_no VARCHAR(50) "
        "GENERATED ALWAYS AS (IF(deleted = b'0', project_no, NULL)) VIRTUAL "
        "COMMENT '活动行的项目编号(逻辑删除后置 NULL 以释放唯一键)'")
    print("[1/2] 已加生成列 active_project_no")

    # 旧唯一键可能已被上一轮迁移改过,两种情况都处理
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'awardie_innovation_projects' "
        "AND INDEX_NAME = 'uk_innovation_project_no'")
    if cur.fetchone()[0] > 0:
        cur.execute("ALTER TABLE awardie_innovation_projects DROP INDEX uk_innovation_project_no")
        print("[2/2] 已删旧唯一键 uk_innovation_project_no")

    cur.execute(
        "ALTER TABLE awardie_innovation_projects "
        "ADD UNIQUE KEY uk_innovation_project_no_active (tenant_id, active_project_no)")
    print("[2/2] 已加新唯一键 uk_innovation_project_no_active (tenant_id, active_project_no)")

    cur.execute("SHOW INDEX FROM awardie_innovation_projects WHERE Key_name = 'uk_innovation_project_no_active'")
    cols = [r[4] for r in cur.fetchall()]
    assert cols == ["tenant_id", "active_project_no"], f"唯一键列顺序异常: {cols}"
    print(f"[check] 活动行 {active} 条,唯一键列 = {cols}")
    print(f"[done] {db} 迁移完成")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
