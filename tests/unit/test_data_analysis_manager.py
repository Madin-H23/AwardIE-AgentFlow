"""DataAnalysisManager 单元测试"""
import pytest
from backend.managers.data_analysis_manager import DataAnalysisManager


def test_get_competitions_with_awards(temp_db):
    """测试获取有奖状的竞赛列表"""
    manager = DataAnalysisManager(temp_db)
    result = manager.get_competitions_with_awards()

    assert isinstance(result, list)
    assert len(result) > 0

    # 验证第一个竞赛的结构
    first_comp = result[0]
    assert 'id' in first_comp
    assert 'name' in first_comp
    assert 'start_month' in first_comp
    assert 'end_month' in first_comp
    assert 'is_cross_year' in first_comp
    assert 'time_raw' in first_comp
    assert 'website' in first_comp
    assert 'white_list' in first_comp

    # 验证时间解析
    if first_comp['time_raw'] == '4-10月':
        assert first_comp['start_month'] == 4
        assert first_comp['end_month'] == 10
        assert first_comp['is_cross_year'] is False


def test_get_competition_award_timeline(temp_db):
    """测试获取竞赛奖状时间分布"""
    manager = DataAnalysisManager(temp_db)
    result = manager.get_competition_award_timeline(competition_id=1)

    assert 'competition_id' in result
    assert result['competition_id'] == 1
    assert 'months' in result
    assert 'peak_month' in result
    assert 'year_range' in result

    # 验证月份数据
    months = result['months']
    assert isinstance(months, dict)
    # 应该有 2023-06 和 2024-05, 2024-06, 2024-07
    assert '2023-06' in months
    assert '2024-05' in months or '2024-06' in months

    # 验证峰值月份
    peak = result['peak_month']
    assert peak is not None
    assert peak in months

    # 验证年份范围
    year_range = result['year_range']
    assert isinstance(year_range, tuple)
    assert len(year_range) == 2
    assert year_range[0] <= year_range[1]


def test_get_competition_contribution(temp_db):
    """测试获取竞赛贡献度"""
    manager = DataAnalysisManager(temp_db)
    result = manager.get_competition_contribution(year_range=None)

    assert isinstance(result, list)
    assert len(result) > 0

    # 验证结果结构
    first_item = result[0]
    assert 'competition_id' in first_item
    assert 'name' in first_item
    assert 'award_count' in first_item

    # 验证按数量排序（第一个应该是最多的）
    if len(result) > 1:
        assert result[0]['award_count'] >= result[1]['award_count']


def test_get_competition_contribution_with_year_range(temp_db):
    """测试带年份范围的竞赛贡献度"""
    manager = DataAnalysisManager(temp_db)
    result = manager.get_competition_contribution(year_range=(2024, 2024))

    assert isinstance(result, list)
    # 应该只返回2024年的数据
    for item in result:
        assert item['award_count'] >= 0


def test_get_competition_contribution_white_list_only(temp_db):
    """测试只查看白名单竞赛的贡献度"""
    manager = DataAnalysisManager(temp_db)
    result = manager.get_competition_contribution(white_list_only=True)

    assert isinstance(result, list)
    # 验证所有结果都是白名单竞赛
    # 根据测试数据，ID为1,2,3,5的是白名单，ID为4的不是
    white_list_ids = {1, 2, 3, 5}
    for item in result:
        assert item['competition_id'] in white_list_ids


def test_get_competition_award_timeline_empty(temp_db):
    """测试获取不存在竞赛的时间分布"""
    manager = DataAnalysisManager(temp_db)
    result = manager.get_competition_award_timeline(competition_id=999)

    assert result['competition_id'] == 999
    assert result['months'] == {}
    assert result['peak_month'] is None
    assert result['year_range'] == (None, None)
