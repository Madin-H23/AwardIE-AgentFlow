"""数据分析管理器"""
from typing import Dict, List, Optional, Tuple
from backend.utils.competition_time_parser import parse_competition_time
import sqlite3
import logging

logger = logging.getLogger(__name__)


class DataAnalysisManager:
    """数据分析管理器

    提供竞赛与奖状数据的统计分析功能，包括：
    - 获取有奖状的竞赛列表（含时间解析）
    - 统计竞赛奖状时间分布
    - 计算竞赛贡献度排名
    """

    def __init__(self, db_path: str, laboratory_id: Optional[int] = None):
        """初始化数据分析管理器

        Args:
            db_path: 数据库文件路径
            laboratory_id: 实验室ID，用于过滤数据范围
        """
        self.db_path = db_path
        self.laboratory_id = laboratory_id

    def get_competitions_with_awards(
        self,
        watcher_type: Optional[str] = None,
        watcher_id: Optional[int] = None
    ) -> List[Dict]:
        """获取有奖状的竞赛列表（含时间解析）

        Args:
            watcher_type: 忽略（保留参数以兼容旧接口）
            watcher_id: 忽略（保留参数以兼容旧接口）

        Returns:
            竞赛列表，每个元素包含:
            {
                'id': int,                # 竞赛ID
                'name': str,              # 竞赛名称
                'start_month': int|None,  # 开始月份（1-12）
                'end_month': int|None,    # 结束月份（1-12）
                'is_cross_year': bool,    # 是否跨年
                'time_raw': str,          # 原始时间字符串
                'website': str,           # 官方网站
                'white_list': bool,       # 是否白名单
                'award_count': int        # 奖状数量
            }
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 获取有奖状的竞赛
        sql = '''
            SELECT DISTINCT
                c.id,
                c.competition_name,
                c.competition_time,
                c.official_website,
                c.white_list,
                COUNT(a.id) as award_count
            FROM competitions c
            INNER JOIN awards a ON c.id = a.competition_id
            WHERE 1=1
        '''

        params = []

        # 实验室过滤
        if self.laboratory_id:
            sql += ' AND a.laboratory_id = ?'
            params.append(self.laboratory_id)

        sql += ' GROUP BY c.id ORDER BY c.competition_name'

        cursor.execute(sql, params)

        competitions = []
        for row in cursor.fetchall():
            time_info = parse_competition_time(row['competition_time'])
            comp_data = {
                'id': row['id'],
                'name': row['competition_name'],
                'start_month': time_info['start_month'],
                'end_month': time_info['end_month'],
                'is_cross_year': time_info['is_cross_year'],
                'time_raw': row['competition_time'],
                'website': row['official_website'],
                'white_list': bool(row['white_list']),
                'award_count': row['award_count']
            }
            competitions.append(comp_data)

        conn.close()
        return competitions

    def get_competition_award_timeline(self, competition_id: int) -> Dict:
        """统计某个竞赛的奖状时间分布

        Args:
            competition_id: 竞赛ID

        Returns:
            {
                'competition_id': int,              # 竞赛ID
                'months': {str: int},               # 月份分布 {YYYY-MM: count}
                'peak_month': Optional[str],        # 峰值月份
                'year_range': Tuple[int|None, int|None]  # 年份范围
            }
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = '''
            SELECT date, year
            FROM awards
            WHERE competition_id = ? AND date IS NOT NULL
        '''
        params = [competition_id]

        # 实验室过滤
        if self.laboratory_id:
            sql += ' AND laboratory_id = ?'
            params.append(self.laboratory_id)

        sql += ' ORDER BY date'

        cursor.execute(sql, params)

        months = {}
        for row in cursor.fetchall():
            date_key = row['date']  # 格式: "2024-05"
            months[date_key] = months.get(date_key, 0) + 1

        # 找出峰值月份
        peak_month = None
        max_count = 0
        for date_key, count in months.items():
            if count > max_count:
                max_count = count
                peak_month = date_key

        # 计算年份范围
        years = [int(d.split('-')[0]) for d in months.keys()] if months else []
        year_range = (min(years), max(years)) if years else (None, None)

        conn.close()

        return {
            'competition_id': competition_id,
            'months': months,
            'peak_month': peak_month,
            'year_range': year_range
        }

    def get_competition_contribution(
        self,
        year_range: Optional[Tuple[int, int]] = None,
        years: Optional[List[int]] = None,
        white_list_only: bool = False,
        include_teacher_certificates: bool = False
    ) -> List[Dict]:
        """获取竞赛贡献度（按奖状数量排序）

        Args:
            year_range: 年份范围，如 (2022, 2024)，None表示不限（兼容旧版）
            years: 年份列表，如 [2022, 2023, 2025]，None表示不限（优先使用）
            white_list_only: 是否只看白名单
            include_teacher_certificates: 是否包含教师证书，默认False（只看学生奖状）

        Returns:
            [
                {
                    'competition_id': int,  # 竞赛ID
                    'name': str,            # 竞赛名称
                    'award_count': int      # 奖状数量
                },
                ...
            ]
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = '''
            SELECT
                c.id as competition_id,
                c.competition_name as name,
                COUNT(a.id) as award_count
            FROM competitions c
            INNER JOIN awards a ON c.id = a.competition_id
            WHERE 1=1
        '''

        params = []

        # 实验室过滤
        if self.laboratory_id:
            sql += ' AND a.laboratory_id = ?'
            params.append(self.laboratory_id)

        # 年份筛选：优先使用 years（精确多选），其次使用 year_range（范围）
        if years:
            placeholders = ','.join(['?' for _ in years])
            sql += f' AND a.year IN ({placeholders})'
            params.extend(years)
        elif year_range:
            sql += ' AND a.year >= ? AND a.year <= ?'
            params.extend(year_range)

        if white_list_only:
            sql += ' AND c.white_list = 1'

        # 教师/学生证书筛选
        if not include_teacher_certificates:
            # 只显示学生奖状（granted_role = '学生'）
            # 对于granted_role为空的旧数据，需要排除只有教师获奖者的
            sql += ' AND (a.granted_role = ? OR (a.granted_role IS NULL AND a.id NOT IN (SELECT award_id FROM award_teacher_winners WHERE award_id IS NOT NULL)))'
            params.append('学生')

        sql += '''
            GROUP BY c.id
            ORDER BY award_count DESC
        '''

        cursor.execute(sql, params)

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def get_competition_trend(
        self,
        competition_id: int,
        year_range: Optional[Tuple[int, int]] = None
    ) -> Dict:
        """获取竞赛历年获奖趋势

        Args:
            competition_id: 竞赛ID
            year_range: 年份范围，如 (2022, 2024)，None表示不限

        Returns:
            {'years': [2022, 2023, ...], 'counts': [10, 15, ...]}
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = '''
            SELECT year, COUNT(*) as count
            FROM awards
            WHERE competition_id = ? AND year IS NOT NULL
        '''
        params = [competition_id]

        # 实验室过滤
        if self.laboratory_id:
            sql += ' AND laboratory_id = ?'
            params.append(self.laboratory_id)

        if year_range:
            sql += ' AND year >= ? AND year <= ?'
            params.extend(year_range)

        sql += ' GROUP BY year ORDER BY year'

        cursor.execute(sql, params)

        years = []
        counts = []
        for row in cursor.fetchall():
            years.append(row['year'])
            counts.append(row['count'])

        conn.close()

        return {'years': years, 'counts': counts}

    def get_competition_heatmap(self, competition_id: int) -> Dict:
        """获取奖状月度分布热力图数据

        Args:
            competition_id: 竞赛ID

        Returns:
            {
                'years': [2022, 2023, 2024],
                'months': [1, 2, ..., 12],
                'data': [[0, 2, 0, ...], [1, 0, 3, ...], ...]
            }
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = '''
            SELECT date
            FROM awards
            WHERE competition_id = ? AND date IS NOT NULL
        '''
        params = [competition_id]

        # 实验室过滤
        if self.laboratory_id:
            sql += ' AND laboratory_id = ?'
            params.append(self.laboratory_id)

        sql += ' ORDER BY date'

        cursor.execute(sql, params)

        # 收集所有年份数据
        year_month_counts = {}

        for row in cursor.fetchall():
            date_str = row['date']  # "2024-05"
            parts = date_str.split('-')
            if len(parts) == 2:
                try:
                    year = int(parts[0])
                    month = int(parts[1])

                    if year not in year_month_counts:
                        year_month_counts[year] = {}
                    year_month_counts[year][month] = year_month_counts[year].get(month, 0) + 1
                except (ValueError, IndexError):
                    logger.warning(f"Invalid date format: {date_str}")
                    continue

        conn.close()

        # 获取所有年份（排序）
        years = sorted(year_month_counts.keys())
        months = list(range(1, 13))

        # 构建数据矩阵
        data = []
        for year in years:
            year_data = []
            for month in months:
                count = year_month_counts.get(year, {}).get(month, 0)
                year_data.append(count)
            data.append(year_data)

        return {
            'years': years,
            'months': months,
            'data': data
        }

    def get_dynamic_chart_data(
        self,
        x_axis: str,
        color_by: str,
        year_range: Optional[Tuple[int, int]] = None,
        filters: Optional[Dict] = None
    ) -> Dict:
        """获取动态图表数据

        Args:
            x_axis: 'year', 'laboratory', 'teacher'
            color_by: 'laboratory', 'year', 'competition_level'
            year_range: 年份范围
            filters: 其他筛选条件

        Returns:
            {
                'x_data': [...],
                'series_data': [{name: '实验室A', data: [...]}, ...],
                'categories': {...}
            }
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 构建SQL查询
        select_fields = []
        group_by = []

        # X轴字段
        if x_axis == 'year':
            select_fields.append('a.year as x_value')
            group_by.append('a.year')
        elif x_axis == 'laboratory':
            select_fields.append('l.name as x_value')
            group_by.append('l.id')
        elif x_axis == 'teacher':
            select_fields.append('t.name as x_value')
            group_by.append('t.id')

        # 颜色分组字段
        if color_by == 'laboratory':
            select_fields.append('l.name as color_value')
            group_by.append('l.id')
        elif color_by == 'year':
            select_fields.append('a.year as color_value')
            group_by.append('a.year')
        elif color_by == 'competition_level':
            select_fields.append("COALESCE(a.competition_level, '') as color_value")
            group_by.append('a.competition_level')

        # 统计字段
        select_fields.append('COUNT(a.id) as count')

        # 构建完整SQL
        sql = 'SELECT ' + ', '.join(select_fields)
        sql += '''
            FROM awards a
            LEFT JOIN competitions c ON a.competition_id = c.id
            LEFT JOIN laboratories l ON a.laboratory_id = l.id
            LEFT JOIN award_supervisors at ON a.id = at.award_id
            LEFT JOIN teachers t ON at.teacher_id = t.id
            WHERE 1=1
        '''

        params = []

        # 实验室过滤
        if self.laboratory_id:
            sql += ' AND a.laboratory_id = ?'
            params.append(self.laboratory_id)

        # 年份范围过滤
        if year_range:
            sql += ' AND a.year >= ? AND a.year <= ?'
            params.extend(year_range)

        # 其他过滤条件
        if filters:
            if filters.get('laboratories'):
                lab_ids = [int(x) for x in filters['laboratories'].split(',')]
                placeholders = ','.join(['?'] * len(lab_ids))
                sql += f' AND a.laboratory_id IN ({placeholders})'
                params.extend(lab_ids)

        sql += ' GROUP BY ' + ', '.join(group_by)
        sql += ' ORDER BY x_value, color_value'

        cursor.execute(sql, params)

        # 处理结果
        result_data = {}
        x_values = set()
        color_values = set()

        for row in cursor.fetchall():
            x_val = str(row['x_value'] or '未知')
            color_val = str(row['color_value'] or '未知')
            count = row['count']

            x_values.add(x_val)
            color_values.add(color_val)

            if color_val not in result_data:
                result_data[color_val] = {}
            result_data[color_val][x_val] = count

        conn.close()

        # 构建返回数据
        x_data = sorted(x_values, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
        series_data = []

        for color_val in sorted(color_values):
            series_data.append({
                'name': color_val,
                'data': [result_data.get(color_val, {}).get(x, 0) for x in x_data]
            })

        return {
            'x_data': x_data,
            'series_data': series_data
        }
