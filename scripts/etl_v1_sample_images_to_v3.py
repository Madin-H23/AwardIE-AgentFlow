#!/usr/bin/env python
"""批22(D-03):把 V1 的 20 张模板样本图落位到 v3 存储根,修正悬空路径。

背景:批12 从 V1 BLOB 还原 sample_image_path 时,沿用了 v2 迁移脚本的
「files/v2/<sha16>.<ext>」相对 CWD 全路径;而 v3 的 AwardieFileStorage 按
awardie.file.root(默认 files/v3,相对**服务进程 CWD** = awardie-v3/yudao-server)解析,
两者对不上——20 条引用自批12 起悬空(批13-19 如实维持现状,本批修正)。

做三件事(幂等,可重跑):
  1. 从 V1 读 sample_image_blob,按内容寻址命名(sha256[:16] + 魔数判型)写到
     awardie-v3/yudao-server/files/v3/(已存在则跳过写盘,仍做哈希校验)
  2. UPDATE awardie_templates.sample_image_path = '<sha16>.<ext>'
     (root 相对路径,与 AwardieFileStorage.store() 的 root.relativize() 产物同构)
  3. 回读校验:存储文件 sha256 与 V1 BLOB 一致;DB 路径 = 期望值

用法(venv python):
    AWARDIE_MYSQL_PASSWORD=<口令> python scripts/etl_v1_sample_images_to_v3.py [--dry-run]

安全:V1 以 mode=ro 只读打开;MySQL 只 UPDATE awardie_templates 一列;
口令走环境变量。存储根可用 AWARDIE_FILE_ROOT 覆盖(默认按服务运行时解析出的
awardie-v3/yudao-server/files/v3)。
"""
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
V1_DB = ROOT / 'database' / 'competitions.db'
DEFAULT_STORE = ROOT / 'awardie-v3' / 'yudao-server' / 'files' / 'v3'
STORE = Path(os.environ.get('AWARDIE_FILE_ROOT', str(DEFAULT_STORE)))

# 与 migrate_template_image_blobs.py / AwardieFileStorage 同一套魔数判型白名单。
# 注意 JPEG 魔数只有 3 字节(第 4 字节是 APP0/EXIF 标记位,实测 V1 全部 20 张是 FF D8 FF E0)
BLOB_MAGIC = [(b'\xff\xd8\xff', 'jpg'), (b'\x89PNG', 'png'), (b'%PDF', 'pdf')]

MYSQL = dict(host='127.0.0.1', port=3307, db=os.environ.get('AWARDIE_TARGET_DB', 'awardie_v3'),
             user=os.environ.get('AWARDIE_MYSQL_USER', 'awardie_v3'),
             password=os.environ.get('AWARDIE_MYSQL_PASSWORD', ''), charset='utf8mb4')


def main() -> int:
    dry = '--dry-run' in sys.argv
    if not MYSQL['password']:
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2

    src = sqlite3.connect(f'file:{V1_DB}?mode=ro', uri=True)
    blobs = {tid: bytes(b) for tid, b in src.execute(
        'SELECT id, sample_image_blob FROM templates WHERE sample_image_blob IS NOT NULL')}
    print(f'[read] V1 模板 BLOB: {len(blobs)} 张;存储根: {STORE}')

    my = pymysql.connect(**MYSQL)
    cur = my.cursor()
    cur.execute("SELECT id, sample_image_path FROM awardie_templates WHERE deleted = b'0'")
    db_paths = dict(cur.fetchall())

    updated = skipped_same = missing_blob = 0
    for tid, blob in sorted(blobs.items()):
        digest = hashlib.sha256(blob).hexdigest()
        ext = next((e for magic, e in BLOB_MAGIC if blob.startswith(magic)), None)
        if ext is None:
            print(f'[warn] 模板 {tid} 魔数不在白名单(头4字节={blob[:4].hex()}),跳过')
            continue
        name = f'{digest[:16]}.{ext}'
        rel = name  # root 相对路径,与 AwardieFileStorage.store() 返回值同构
        dest = STORE / name

        if dry:
            print(f'[dry] 模板 {tid} -> {rel}')
            continue

        # 1) 落盘(已存在则只校验,不重写)
        if dest.is_file():
            if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                print(f'[FAIL] {dest} 已存在但哈希不符(内容寻址被破坏?),中止不覆盖')
                return 1
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)

        # 2) 路径已是目标值则跳过 UPDATE
        if db_paths.get(tid) == rel:
            skipped_same += 1
        else:
            cur.execute('UPDATE awardie_templates SET sample_image_path = %s WHERE id = %s', (rel, tid))
            updated += 1

        # 3) 回读校验
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            print(f'[FAIL] 模板 {tid} 回读哈希不一致,中止')
            return 1

    if dry:
        print('[dry-run] 未落盘')
        return 0
    my.commit()

    # 终态自校:DB 每条路径对应的文件都存在且哈希与 V1 BLOB 一致
    cur.execute("SELECT id, sample_image_path FROM awardie_templates WHERE deleted = b'0'")
    bad = 0
    for tid, path in cur.fetchall():
        f = STORE / str(path) if path else None
        if not path or not f.is_file():
            print(f'[FAIL] 模板 {tid} 路径 {path!r} 无对应文件')
            bad += 1
            continue
        v1 = blobs.get(tid)
        if v1 is not None and hashlib.sha256(f.read_bytes()).hexdigest() != hashlib.sha256(v1).hexdigest():
            print(f'[FAIL] 模板 {tid} 文件哈希与 V1 BLOB 不一致')
            bad += 1
    src.close()
    my.close()

    print(f'[done] 落盘+更新 {updated},路径已同值跳过 {skipped_same},'
          f'无 BLOB 的模板 {len(db_paths) - len(blobs)} 条(不在处理范围)')
    if bad:
        print(f'[FAIL] {bad} 条校验不过')
        return 1
    print('[ok] 20 张样本图已落位,路径与存储根对齐')
    return 0


if __name__ == '__main__':
    sys.exit(main())
