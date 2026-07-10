# tests/tools/test_competition_time_parser.py
import pytest
from backend.utils.competition_time_parser import parse_competition_time

def test_parse_time_range():
    """测试解析时间范围 '4-10月'"""
    result = parse_competition_time('4-10月')
    assert result['start_month'] == 4
    assert result['end_month'] == 10
    assert result['is_cross_year'] == False
    assert result['raw'] == '4-10月'

def test_parse_single_month():
    """测试解析单月 '9月'"""
    result = parse_competition_time('9月')
    assert result['start_month'] == 9
    assert result['end_month'] == 9
    assert result['is_cross_year'] == False
    assert result['raw'] == '9月'

def test_parse_cross_year():
    """测试解析跨年 '10-4月'"""
    result = parse_competition_time('10-4月')
    assert result['start_month'] == 10
    assert result['end_month'] == 4
    assert result['is_cross_year'] == True
    assert result['raw'] == '10-4月'

def test_parse_empty():
    """测试解析空值"""
    result = parse_competition_time('')
    assert result['start_month'] is None
    assert result['end_month'] is None
    assert result['is_cross_year'] == False
    assert result['raw'] == ''

def test_parse_none():
    """测试解析None"""
    result = parse_competition_time(None)
    assert result['start_month'] is None
    assert result['end_month'] is None
    assert result['is_cross_year'] == False
    assert result['raw'] is None

def test_parse_various_formats():
    """测试各种格式"""
    # "3-5月"
    result = parse_competition_time('3-5月')
    assert result['start_month'] == 3
    assert result['end_month'] == 5

    # "7-8月"
    result = parse_competition_time('7-8月')
    assert result['start_month'] == 7
    assert result['end_month'] == 8

    # 带波浪号 "3～7月"
    result = parse_competition_time('3～7月')
    assert result['start_month'] == 3
    assert result['end_month'] == 7
