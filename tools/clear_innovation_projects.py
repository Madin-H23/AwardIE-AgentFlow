#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清空大创主表及关联表（innovation_projects、innovation_project_students）

数据库路径来自 config/settings.json 的 database.competitions_db。
执行前会打印当前行数，需确认后执行。

使用: python tools/clear_innovation_projects.py
      python tools/clear_innovation_projects.py --dry-run   # 仅打印条数，不执行
      python tools/clear_innovation_projects.py --yes      # 跳过确认直接执行
"""
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.loader import get_config


def main():
    parser = argparse.ArgumentParser(description="清空大创表（innovation_projects、innovation_project_students）")
    parser.add_argument("--dry-run", action="store_true", help="仅统计条数，不执行删除")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认直接执行")
    args = parser.parse_args()

    config = get_config()
    db_path = config.get_path("database", "competitions_db")
    if not db_path or not Path(db_path).exists():
        print(f"数据库不存在: {db_path}")
        return 1

    from backend.models.innovation_project import InnovationProjectManager

    manager = InnovationProjectManager(str(db_path))
    count = len(manager.projects)
    print(f"innovation_projects 当前条数: {count}")

    if count == 0:
        print("无需清空")
        return 0

    if args.dry_run:
        print("--dry-run: 未执行删除")
        return 0

    if not args.yes:
        confirm = input(f"确认删除全部 {count} 条大创项目记录？(y/N): ")
        if confirm.strip().lower() != "y":
            print("已取消")
            return 0

    deleted = manager.delete_all()
    print(f"已删除 innovation_projects 行数: {deleted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
