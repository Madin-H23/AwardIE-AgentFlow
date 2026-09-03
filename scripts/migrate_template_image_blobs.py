# -*- coding: utf-8 -*-
"""批 1 文件域收敛(D1a/D2a 拍板):templates.sample_image_blob BYTEA → files/v2/ 目录存储。

对每条有 blob 且无 path 的模板:
  1. 读出字节,按 FileStorageService 同款命名(sha256 前 16 位 + 魔数判型扩展名)落盘 files/v2/
  2. UPDATE sample_image_path = <相对路径>, sample_image_blob = NULL
  3. 回读文件与原始字节做哈希比对(全量校验,量小不做抽样)

幂等:只处理 blob 非空且 path 为空的行,重复执行自动跳过。
用法:venv python scripts/migrate_template_image_blobs.py [--apply]   (不带 --apply 仅预览)
"""
import argparse
import hashlib
import sys
from pathlib import Path

import psycopg2

DSN = "host=127.0.0.1 port=5433 dbname=awardie_dev user=postgres password=postgres"
ROOT = Path(__file__).resolve().parent.parent / "files" / "v2"


def ext_of(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"\x89PNG":
        return "png"
    if data[:4] == b"%PDF":
        return "pdf"
    raise ValueError(f"template blob 魔数不在白名单内,头 4 字节={data[:4].hex()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际写入;缺省仅预览")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, sample_image_blob FROM templates "
            "WHERE sample_image_blob IS NOT NULL AND (sample_image_path IS NULL OR sample_image_path = '') "
            "ORDER BY id")
        rows = [(tid, bytes(blob)) for tid, blob in cur.fetchall()]  # psycopg2 BYTEA=memoryview,须转 bytes
    print(f"待迁移模板样本图:{len(rows)} 条")
    if not rows:
        return 0
    if not args.apply:
        for tid, blob in rows:
            print(f"  [dry] id={tid} {len(blob)} bytes ext={ext_of(blob)}")
        print("预览模式,未写入;加 --apply 执行")
        return 0

    ok = 0
    for tid, blob in rows:
        ext = ext_of(blob)
        name = hashlib.sha256(blob).hexdigest()[:16] + "." + ext
        dest = ROOT / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        rel = str(Path('files') / 'v2' / name)  # 与 FileStorageService.store 同款相对路径(resolve 白名单)
        # 回读校验:与原始字节哈希比对
        if hashlib.sha256(dest.read_bytes()).hexdigest() != hashlib.sha256(blob).hexdigest():
            print(f"  [FAIL] id={tid} 回读哈希不一致,中止(该行未更新)")
            return 1
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE templates SET sample_image_path = %s, sample_image_blob = NULL WHERE id = %s",
                (rel, tid))
        conn.commit()
        ok += 1
        print(f"  [ok] id={tid} -> {dest.name} ({len(blob)} bytes)")
    print(f"完成:{ok}/{len(rows)} 条迁移,全部回读校验通过;sample_image_blob 已置空(列退役于批 3 DROP)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
