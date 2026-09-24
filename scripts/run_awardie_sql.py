"""执行 awardie-v3/sql 下的 SQL 脚本到指定库(幂等重放用)。

用途:批3 起在 dev/test 库重放业务 SQL。逐行剥离 `--` 注释后按分号切分,
避免注释里的分号/中文导致切分错误。口令走环境变量,不入库。

用法:AWARDIE_MYSQL_PASSWORD=... python scripts/run_awardie_sql.py <db> <sql 文件...>
"""
import os
import sys

import pymysql


def load_statements(path: str) -> list[str]:
    lines = []
    with open(path, encoding="utf-8") as fp:
        for line in fp:
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            lines.append(line)
    body = "\n".join(lines)
    return [s.strip() for s in body.split(";") if s.strip()]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    db = sys.argv[1]
    password = os.environ.get("AWARDIE_MYSQL_PASSWORD")
    if not password:
        print("FATAL: 环境变量 AWARDIE_MYSQL_PASSWORD 未设置")
        return 1
    conn = pymysql.connect(host="127.0.0.1", port=3307, user="awardie_v3",
                           password=password, database=db)
    cur = conn.cursor()
    for path in sys.argv[2:]:
        for stmt in load_statements(path):
            cur.execute(stmt)
        print(f"{db}: applied {path} ({len(load_statements(path))} stmts)")
    conn.commit()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
