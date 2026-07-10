"""
检查 awards 表是否含 extract_json 列，若存在则执行 remove_extract_json_from_awards.sql。
在项目根目录执行: python database/migrations/run_remove_extract_json.py
"""
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT, "database", "competitions.db")
SQL_PATH = os.path.join(ROOT, "database", "migrations", "remove_extract_json_from_awards.sql")


def main():
    if not os.path.isfile(DB_PATH):
        print("DB not found:", DB_PATH)
        return 1
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("PRAGMA table_info(awards)")
    cols = [r[1] for r in cur.fetchall()]
    if "extract_json" not in cols:
        print("awards has no extract_json; migration already applied or not needed.")
        conn.close()
        return 0
    print("awards has extract_json; running migration...")
    conn.close()
    with open(SQL_PATH, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(sql)
    conn.close()
    print("Migration completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
