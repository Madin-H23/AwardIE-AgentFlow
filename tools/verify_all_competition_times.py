# tools/verify_all_competition_times.py
"""
验证所有竞赛时间的解析结果
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.utils.competition_time_parser import parse_competition_time
from backend.models.competition import CompetitionManager
from config.loader import get_config


def main():
    # 加载配置
    config = get_config()
    db_path = config.get_path("database", "competitions_db")

    # 获取所有竞赛
    manager = CompetitionManager(str(db_path))
    competitions = manager.competitions

    print(f"共找到 {len(competitions)} 个竞赛\n")
    print("=" * 80)

    success_count = 0
    fail_count = 0
    empty_count = 0

    for comp in competitions:
        time_str = comp.time_range  # Competition对象使用 time_range 属性
        result = parse_competition_time(time_str)

        print(f"\n竞赛: {comp.name}")
        print(f"原始时间: {time_str if time_str else '(空)'}")

        if result['start_month'] is None:
            print(f"  解析结果: 无法解析或为空")
            if not time_str:
                empty_count += 1
            else:
                fail_count += 1
        else:
            print(f"  解析结果: {result['start_month']}月 - {result['end_month']}月")
            if result['is_cross_year']:
                print(f"  跨年: 是")
            success_count += 1

    print("\n" + "=" * 80)
    print(f"\n统计:")
    print(f"  成功解析: {success_count}")
    print(f"  解析失败: {fail_count}")
    print(f"  时间为空: {empty_count}")
    print(f"  总计: {len(competitions)}")

    if fail_count > 0:
        print(f"\n警告: 有 {fail_count} 个竞赛的时间无法解析，请检查")
        return 1
    else:
        print(f"\n✓ 所有竞赛时间解析成功")
        return 0


if __name__ == '__main__':
    sys.exit(main())
