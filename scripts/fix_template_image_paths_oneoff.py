# -*- coding: utf-8 -*-
"""一次性归正:批 1 迁移脚本初版把绝对路径写进了 sample_image_path,统一改回 FileStorageService.resolve
白名单要求的相对路径(files/v2/...)。文件本体已在 files/v2/ 下,不动。"""
import os
import psycopg2

DSN = "host=127.0.0.1 port=5433 dbname=awardie_dev user=postgres password=postgres"

conn = psycopg2.connect(DSN)
cur = conn.cursor()
cur.execute("SELECT id, sample_image_path FROM templates WHERE sample_image_path IS NOT NULL")
rows = cur.fetchall()
fixed = 0
for tid, pth in rows:
    norm = pth.replace("\\", "/")
    i = norm.rfind("files/v2/")
    if i < 0:
        print(f"[skip] id={tid} 路径不含 files/v2/: {pth}")
        continue
    rel = os.path.join("files", "v2", norm[i + len("files/v2/"):])
    if rel != pth:
        cur.execute("UPDATE templates SET sample_image_path = %s WHERE id = %s", (rel, tid))
        fixed += 1
conn.commit()
print(f"归正 {fixed}/{len(rows)} 行")
cur.execute("SELECT id, sample_image_path FROM templates WHERE sample_image_path IS NOT NULL ORDER BY id LIMIT 3")
for r in cur.fetchall():
    print("样例:", r[0], r[1])
conn.close()
