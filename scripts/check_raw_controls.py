"""裸控件门禁(P2 Element Plus 白名单制约定,2026-08-31 采纳)。

规则:awardie-frontend/src 下 .vue 文件禁止裸 <button>/<input>/<select>/<table>,
      一律使用 Element Plus 组件(el-button/el-input/el-select/el-table)。
白名单(唯一):
      <input type="file"> —— 原生文件选择(el-upload 对该场景过重)。
新增例外须在本脚本 WHITELIST 登记理由,否则 CI frontend job 红。

用法:python scripts/check_raw_controls.py  (在 repo 根执行)
"""
import re
import sys
from pathlib import Path

FRONTEND_SRC = Path(__file__).resolve().parents[1] / "awardie-frontend" / "src"
RAW_TAGS = re.compile(r"<(button|input|select|table)(?=[\s>])", re.I)
# 白名单:type="file" 的原生 input(登记理由:el-upload 对单文件上传过重)
FILE_INPUT = re.compile(r"<input[^>]*type=[\"']file[\"']", re.I)

violations = []
scanned = 0
for vue in FRONTEND_SRC.rglob("*.vue"):
    scanned += 1
    for i, line in enumerate(vue.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for m in RAW_TAGS.finditer(line):
            tag = m.group(1).lower()
            if tag == "input" and FILE_INPUT.search(line):
                continue  # 白名单
            violations.append(f"{vue.relative_to(FRONTEND_SRC.parents[2])}:{i}: <{tag}> (line: {line.strip()[:80]})")

print(f"扫描 {scanned} 个 .vue 文件")
if violations:
    print(f"✗ 裸控件 {len(violations)} 处(使用 Element Plus 组件替代,或在本脚本登记白名单理由):")
    for v in violations:
        print(" ", v)
    sys.exit(1)
print("✓ 无裸控件(Element Plus 白名单制约定通过)")
