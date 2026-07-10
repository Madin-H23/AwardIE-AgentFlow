"""
重新验证 pending_achievements 中的记录

用于修复旧记录的验证结果，确保验证结果与最新的数据一致。
"""
import sys
import sqlite3
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from backend.models.pending_achievement import PendingAchievementManager


def fix_validation_results(app_context, status='submit'):
    """
    重新验证指定状态的记录

    Args:
        app_context: 应用上下文
        status: 要修复的状态，默认为 'submit'
    """
    from app.routes.admin_achievement import _get_full_validation_result

    pending_manager = app_context.get_pending_achievement_manager()
    conn = pending_manager._get_db_connection()
    cursor = conn.cursor()

    try:
        # 查询所有指定状态的记录
        cursor.execute(
            "SELECT id, achievement_type, achievement_data FROM pending_achievements WHERE status = ?",
            (status,)
        )
        rows = cursor.fetchall()

        print(f"找到 {len(rows)} 条 {status} 状态的记录")

        fixed_count = 0
        for row in rows:
            pending_id = row[0]
            achievement_type = row[1]
            achievement_data_json = row[2]

            try:
                # 解析数据
                if isinstance(achievement_data_json, str):
                    achievement_data = json.loads(achievement_data_json)
                else:
                    achievement_data = achievement_data_json

                # 重新计算验证结果
                new_validation_result = _get_full_validation_result(
                    achievement_type, achievement_data, app_context
                )

                # 更新数据库
                new_validation_json = json.dumps(new_validation_result, ensure_ascii=False)
                cursor.execute(
                    "UPDATE pending_achievements SET validation_result = ? WHERE id = ?",
                    (new_validation_json, pending_id)
                )

                fixed_count += 1
                print(f"  [{fixed_count}/{len(rows)}] 已修复 ID {pending_id}")

            except Exception as e:
                print(f"  错误：无法修复 ID {pending_id}: {e}")

        conn.commit()
        print(f"\n完成！共修复 {fixed_count} 条记录")

    except Exception as e:
        conn.rollback()
        print(f"错误：{e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    print("开始修复验证结果...")

    # 创建应用和上下文
    app = create_app()
    with app.app_context():
        from app import get_app_context_instance
        app_context = get_app_context_instance()

        # 修复 submit 状态的记录
        fix_validation_results(app_context, status='submit')

        # 如果需要，也可以修复 pending 状态的记录
        # fix_validation_results(app_context, status='pending')

    print("修复完成！")
