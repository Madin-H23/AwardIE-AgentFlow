"""
将 innovation_projects 表的 project_type CHECK 从（国家级,省级,校级）改为（国家级,省级,院级）。
在项目根目录执行: python database/migrations/run_innovation_allow_yuanji.py
"""
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT, "database", "competitions.db")
SQL_PATH = os.path.join(os.path.dirname(__file__), "innovation_projects_allow_yuanji.sql")


def main():
    if not os.path.isfile(DB_PATH):
        print("DB not found:", DB_PATH)
        return 1
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='innovation_projects'"
    )
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        print("innovation_projects table not found; skip migration.")
        return 0
    if "院级" in row[0] and "校级" not in row[0]:
        print("innovation_projects already has 院级 (migration already applied).")
        return 0
    if "校级" not in row[0]:
        print("Current CHECK does not contain 校级; run migration anyway to ensure 院级.")
    print("Running migration: project_type 校级 -> 院级 ...")
    with open(SQL_PATH, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(sql)
    conn.close()
    print("Migration completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
