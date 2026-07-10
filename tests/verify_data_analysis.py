"""验证 DataAnalysisManager 功能"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from backend.managers.data_analysis_manager import DataAnalysisManager


def main():
    # 使用真实数据库
    db_path = "D:/code/教学工具/信息管理rebuild/database/competitions.db"

    print("=" * 60)
    print("DataAnalysisManager 功能验证")
    print("=" * 60)

    manager = DataAnalysisManager(db_path)

    # 测试1: 获取有奖状的竞赛列表
    print("\n1. 获取有奖状的竞赛列表（前5个）:")
    print("-" * 60)
    competitions = manager.get_competitions_with_awards()
    for i, comp in enumerate(competitions[:5], 1):
        print(f"{i}. {comp['name']}")
        print(f"   时间: {comp['time_raw']} => {comp['start_month']}月-{comp['end_month']}月 (跨年: {comp['is_cross_year']})")
        print(f"   白名单: {comp['white_list']}, 官网: {comp['website'] or '无'}")

    # 测试2: 获取竞赛奖状时间分布
    if competitions:
        print(f"\n2. 统计「{competitions[0]['name']}」的奖状时间分布:")
        print("-" * 60)
        timeline = manager.get_competition_award_timeline(competitions[0]['id'])
        print(f"竞赛ID: {timeline['competition_id']}")
        print(f"年份范围: {timeline['year_range']}")
        print(f"峰值月份: {timeline['peak_month']}")
        print(f"月度分布:")
        for month, count in sorted(timeline['months'].items()):
            print(f"  {month}: {count} 个")

    # 测试3: 获取竞赛贡献度排名
    print("\n3. 竞赛贡献度排名（按奖状数量，前10名）:")
    print("-" * 60)
    contributions = manager.get_competition_contribution()
    for i, item in enumerate(contributions[:10], 1):
        print(f"{i:2d}. {item['name']:40s} - {item['award_count']} 个奖状")

    # 测试4: 2024年的竞赛贡献度
    print("\n4. 2024年竞赛贡献度排名（前5名）:")
    print("-" * 60)
    contributions_2024 = manager.get_competition_contribution(year_range=(2024, 2024))
    for i, item in enumerate(contributions_2024[:5], 1):
        print(f"{i}. {item['name']:40s} - {item['award_count']} 个奖状")

    # 测试5: 白名单竞赛贡献度
    print("\n5. 白名单竞赛贡献度排名（前5名）:")
    print("-" * 60)
    white_list_contributions = manager.get_competition_contribution(white_list_only=True)
    for i, item in enumerate(white_list_contributions[:5], 1):
        print(f"{i}. {item['name']:40s} - {item['award_count']} 个奖状")

    print("\n" + "=" * 60)
    print("验证完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
