# -*- coding: utf-8 -*-
"""
从 Git 历史中的旧 admin.py 提取成果相关代码，生成 admin_achievement.py。
计划中的行号为 1-based，对应约 7479 行的旧 admin.py。
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADMIN_PY_PATH = PROJECT_ROOT / "app" / "routes" / "admin.py"
OUTPUT_PATH = PROJECT_ROOT / "app" / "routes" / "admin_achievement.py"
GIT_REF = "440dba3"  # 大幅修改之前保存版本


def get_old_admin_content():
    """从 Git 获取旧版 admin.py 内容"""
    result = subprocess.run(
        ["git", "show", f"{GIT_REF}:app/routes/admin.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git show failed: {result.stderr}")
    return result.stdout


def main():
    content = get_old_admin_content()
    lines = content.splitlines()

    # 计划中的行号 1-based，转为 0-based 切片
    # Block 1: awards_list ~ award_edit (29-916)
    block1 = lines[28:916]
    # Block 2: achievements ~ api_achievements_other (3862-4501)
    block2 = lines[3860:4501]
    # Block 3: file_import ~ _get_review_service (4587-7193)
    block3 = lines[4585:7193]

    # 收集文件开头到第一个 @bp.route 之前的 imports 和 bp 定义（从原文件 1-28 行）
    header_lines = lines[:28]
    # 将 bp = Blueprint('admin', __name__) 改为 admin_achievement
    header = []
    for line in header_lines:
        if "Blueprint('admin'" in line and "admin_achievement" not in line:
            line = line.replace("Blueprint('admin'", "Blueprint('admin_achievement'")
        header.append(line)

    # 拼接：文件头只保留 imports 和 logger，去掉 dashboard 等；用新的 bp 定义
    # 原文件 1-28 可能包含 dashboard，我们只保留 import 和 bp 定义
    import_block = []
    for line in header_lines:
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            import_block.append(line)
        elif "logger =" in line:
            import_block.append(line)
        elif "bp = Blueprint" in line:
            import_block.append(
                line.replace("Blueprint('admin'", "Blueprint('admin_achievement'")
            )
            break
    if not any("Blueprint('admin_achievement'" in L for L in import_block):
        for i, line in enumerate(import_block):
            if "bp = Blueprint" in line:
                import_block[i] = line.replace("Blueprint('admin'", "Blueprint('admin_achievement'")
                break

    # 写入新文件：docstring + 公共 imports（从 block1 推断常用） + bp
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write('"""\n')
        f.write("管理员 - 成果相关路由（奖状列表/编辑、成果总览、文件导入等）\n")
        f.write('"""\n')
        for line in import_block:
            if line.strip().startswith('"""') or line.strip().endswith('"""'):
                continue
            f.write(line + "\n")
        if not any("bp = Blueprint" in L for L in import_block):
            f.write("bp = Blueprint('admin_achievement', __name__)\n\n")
        f.write("\n")
        for line in block1:
            f.write(line + "\n")
        f.write("\n")
        for line in block2:
            f.write(line + "\n")
        f.write("\n")
        for line in block3:
            f.write(line + "\n")

    print(f"Wrote {OUTPUT_PATH} ({len(block1) + len(block2) + len(block3)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
