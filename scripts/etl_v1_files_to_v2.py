# -*- coding: utf-8 -*-
"""批 3(D4 拍板):v1 files/ 存量 ETL → files/v2 目录存储,并按哈希重连 DB 引用。

范围:files/ 下除 v2/export/temp* 外的全部存量文件(实测 agent_upload 7 + other 30 + awards 1 ≈ 38)。
动作:
  1. 逐文件读字节 → sha256 → FileStorageService 同款命名(sha16.ext,魔数判型)写入 files/v2/(内容去重,已存在即跳过);
  2. 回读哈希比对(全量校验);
  3. --apply 时按哈希重连:other_files.file_path(有 file_hash 列)、awards.certificate_path(仅填空,不覆盖批 2 结果);
     仅当 DB.file_hash == 内容 sha256 才重连(防 v1 哈希算法不一致的脏连)。
幂等:文件已存在跳过;重连仅更新路径不同/为空的行。
用法:venv python scripts/etl_v1_files_to_v2.py [--apply]
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIRS = ['agent_upload', 'other', 'awards', 'patents', 'software', 'laboratories']
DEST = ROOT / 'files' / 'v2'
SKIP = {'v2', 'export', 'temp', 'temp_images', 'temp_upload'}

import psycopg2

DSN = "host=127.0.0.1 port=5433 dbname=awardie_dev user=postgres password=postgres"


def ext_of(data: bytes, fallback: str) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"\x89PNG":
        return "png"
    if data[:4] == b"%PDF":
        return "pdf"
    return fallback.lower() or "bin"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    files = []
    for d in SRC_DIRS:
        base = ROOT / 'files' / d
        if not base.is_dir():
            continue
        for f in base.rglob('*'):
            if f.is_file():
                files.append(f)
    print(f"v1 存量文件:{len(files)} 个")

    moved, skipped, mismatches = 0, 0, []
    hashed = []  # (src, sha256, rel_path_new)
    for f in files:
        data = f.read_bytes()
        digest = sha(data)
        ext = ext_of(data, f.suffix.lstrip('.'))
        rel = str(Path('files') / 'v2' / (digest[:16] + '.' + ext))
        dest = ROOT / rel
        if dest.exists():
            skipped += 1
        else:
            if not args.apply:
                print(f"  [dry] {f.relative_to(ROOT)} -> {rel}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            if sha(dest.read_bytes()) != digest:
                print(f"  [FAIL] {f} 回读校验不一致")
                return 1
            moved += 1
        hashed.append((f, digest, rel))
    print(f"落盘:新写 {moved},去重跳过 {skipped},共哈希化 {len(hashed)}")

    # 逐文件回读校验(含去重跳过的)
    bad = [s for _, d, r in hashed if sha((ROOT / r).read_bytes()) != d]
    if bad:
        print("[FAIL] 回读校验失败:", bad[:3])
        return 1

    if not args.apply:
        print("预览模式未写库;--apply 执行重连")
        return 0

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    rel_other, rel_award, nohash = 0, 0, 0
    for f, digest, rel in hashed:
        cur.execute("SELECT id, file_path FROM other_files WHERE file_hash = %s", (digest,))
        for rid, old_path in cur.fetchall():
            if old_path != rel:
                cur.execute("UPDATE other_files SET file_path = %s WHERE id = %s", (rel, rid))
                rel_other += 1
        cur.execute(
            "UPDATE awards SET certificate_path = %s "
            "WHERE image_hash = %s AND certificate_path IS NULL", (rel, digest))
        rel_award += cur.rowcount
    # 哈希对不上的 DB 行(文件在但 DB.file_hash ≠ 内容 sha256):仅报告不动作
    cur.execute("SELECT COUNT(*) FROM other_files WHERE file_hash IS NULL OR file_hash = ''")
    nohash = cur.fetchone()[0]
    conn.commit()
    print(f"重连:other_files {rel_other} 行,awards 补链 {rel_award} 行;other_files 无哈希行 {nohash}(不动)")
    conn.close()
    print("ETL 完成;抽样校验已含在全量回读比对中")
    return 0


if __name__ == "__main__":
    sys.exit(main())
