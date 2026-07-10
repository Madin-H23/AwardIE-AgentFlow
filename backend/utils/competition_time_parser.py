# backend/utils/competition_time_parser.py
import re
from typing import Dict, Optional

def parse_competition_time(time_str: Optional[str]) -> Dict:
    """
    解析竞赛时间字符串，提取时间范围

    Args:
        time_str: 时间字符串，格式如 "4-10月", "9月", "10-4月", None等

    Returns:
        {
            'start_month': int | None,  # 开始月份 1-12
            'end_month': int | None,    # 结束月份 1-12
            'is_cross_year': bool,      # 是否跨年
            'raw': str | None           # 原始字符串
        }
    """
    # 处理空值
    if not time_str or not isinstance(time_str, str):
        return {
            'start_month': None,
            'end_month': None,
            'is_cross_year': False,
            'raw': time_str
        }

    # 去除空格
    time_str = time_str.strip()

    if not time_str:
        return {
            'start_month': None,
            'end_month': None,
            'is_cross_year': False,
            'raw': time_str
        }

    # 正则匹配：支持 "4-10月", "4～10月", "4~10月" 等格式
    range_pattern = r'(\d{1,2})[-~～](\d{1,2})月'
    range_match = re.search(range_pattern, time_str)

    if range_match:
        start_month = int(range_match.group(1))
        end_month = int(range_match.group(2))
        # 判断是否跨年（开始月份 > 结束月份）
        is_cross_year = start_month > end_month
        return {
            'start_month': start_month,
            'end_month': end_month,
            'is_cross_year': is_cross_year,
            'raw': time_str
        }

    # 匹配单月格式："9月"
    single_pattern = r'(\d{1,2})月'
    single_match = re.search(single_pattern, time_str)

    if single_match:
        month = int(single_match.group(1))
        return {
            'start_month': month,
            'end_month': month,
            'is_cross_year': False,
            'raw': time_str
        }

    # 处理中文数字月份：如 "十月月"（提取第一个"月"前的数字）
    chinese_single_pattern = r'([一二三四五六七八九十]{1,2})月'
    chinese_single_match = re.search(chinese_single_pattern, time_str)

    if chinese_single_match:
        chinese_num = chinese_single_match.group(1)
        # 转换中文数字
        chinese_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '十一': 11, '十二': 12
        }
        month = chinese_map.get(chinese_num)
        if month:
            return {
                'start_month': month,
                'end_month': month,
                'is_cross_year': False,
                'raw': time_str
            }

    # 无法解析的格式
    return {
        'start_month': None,
        'end_month': None,
        'is_cross_year': False,
        'raw': time_str
    }
