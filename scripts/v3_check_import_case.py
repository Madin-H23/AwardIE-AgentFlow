#!/usr/bin/env python
"""v3 前端:检查 import 路径的大小写与磁盘实际是否一致。

为什么需要:Windows 文件系统大小写不敏感,`@/views/Home/Index.vue` 能解析;
Linux CI 上会直接解析失败(TS1261 / 运行时找不到模块)。本脚本在 Windows 上
就能提前抓出来。

用法(纯 python,无依赖):
    python scripts/v3_check_import_case.py
退出码 1 = 存在大小写不匹配,可挂 CI。
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'awardie-v3', 'yudao-ui', 'yudao-ui-admin-vue3', 'src')

# 只查静态字面量路径;模板拼接/glob 交给框架
PAT = re.compile(r"""['"](@/[^'"]+?)['"]""")


def resolve_case_insensitive(disk_path):
    """逐段按不区分大小写找真实路径;找不到返回 None,找到返回真实相对路径。"""
    cur = ''
    for seg in disk_path.split('/'):
        if not cur and not os.path.isdir(SRC):
            return None
        try:
            entries = os.listdir(cur if cur else SRC)
        except OSError:
            return None
        match = [e for e in entries if e.lower() == seg.lower()]
        if not match:
            return None
        cur = os.path.join(cur, match[0])
    return cur


def main() -> int:
    bad = []
    files = glob.glob(os.path.join(SRC, '**', '*.ts'), recursive=True) + \
        glob.glob(os.path.join(SRC, '**', '*.vue'), recursive=True)
    for f in files:
        with open(f, encoding='utf-8') as fh:
            src = fh.read()
        for m in PAT.finditer(src):
            p = m.group(1)
            if '${' in p or '*' in p or '!' in p:
                continue
            rel = p[2:]
            direct = os.path.join(SRC, rel)
            if os.path.isfile(direct):
                continue
            real = resolve_case_insensitive(rel)
            if real and os.path.isfile(real):
                bad.append((os.path.relpath(f, ROOT).replace(os.sep, '/'),
                            p, os.path.relpath(real, ROOT).replace(os.sep, '/')))
    print(f'[scan] import 路径大小写不匹配:{len(bad)} 处')
    for f, p, real in bad:
        print(f'  {f}: {p}  →  实际 {real}')
    if bad:
        print('[fail] 修完再跑;Linux CI 上这些路径会解析失败')
        return 1
    print('[ok] 全部 import 路径大小写一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
