"""
热力图数据服务

提供竞赛×实验室热力图的数据查询服务，支持管理员和实验室视图复用
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import sqlite3
import logging

logger = logging.getLogger(__name__)


@dataclass
class HeatmapFilters:
    """热力图筛选条件"""
    years: Optional[List[int]] = None        # 年份列表，None表示全部年份
    white_list_only: bool = False            # 是否仅白名单竞赛
    include_teacher_certificates: bool = False  # 是否包含教师证书，默认false（只看学生奖状）


@dataclass
class HeatmapData:
    """热力图数据"""
    competitions: List[str]    # 竞赛名称列表（Y轴）
    laboratories: List[str]    # 实验室名称列表（X轴）
    data: List[List[int]]      # 数据矩阵 [竞赛][实验室] = 数量


class HeatmapService:
    """热力图数据服务

    支持管理员视图（全部实验室）和实验室视图（指定实验室）
    """

    def __init__(self, db_path: str, laboratory_id: Optional[int] = None):
        """初始化热力图服务

        Args:
            db_path: 数据库文件路径
            laboratory_id: 实验室ID，None表示管理员视图（全部实验室），有值表示实验室视图
        """
        self.db_path = db_path
        self.laboratory_id = laboratory_id

    def get_lab_competition_heatmap(self, filters: HeatmapFilters) -> HeatmapData:
        """获取实验室×竞赛热力图数据

        Args:
            filters: 筛选条件

        Returns:
            HeatmapData: 包含竞赛列表、实验室列表和数量矩阵
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 查询所有实验室
        if self.laboratory_id:
            # 实验室视图：只查指定实验室
            cursor.execute('SELECT id, name FROM laboratories WHERE id = ?', (self.laboratory_id,))
            labs = [dict(row) for row in cursor.fetchall()]
        else:
            # 管理员视图：查全部实验室
            cursor.execute('SELECT id, name FROM laboratories ORDER BY name')
            labs = [dict(row) for row in cursor.fetchall()]

        # 构建实验室ID到索引的映射
        lab_id_to_idx = {lab['id']: i for i, lab in enumerate(labs)}

        # 查询竞赛及其获奖数据
        sql = '''
            SELECT
                c.id as competition_id,
                c.competition_name as competition_name,
                l.id as laboratory_id,
                COUNT(a.id) as award_count
            FROM competitions c
            INNER JOIN awards a ON c.id = a.competition_id
            INNER JOIN laboratories l ON a.laboratory_id = l.id
            WHERE 1=1
        '''

        params = []

        # 年份筛选
        if filters.years:
            placeholders = ','.join(['?' for _ in filters.years])
            sql += f' AND a.year IN ({placeholders})'
            params.extend(filters.years)

        # 白名单筛选
        if filters.white_list_only:
            sql += ' AND c.white_list = 1'

        # 教师/学生证书筛选
        if not filters.include_teacher_certificates:
            # 只显示学生奖状（granted_role = '学生'）
            # 对于granted_role为空的旧数据，需要排除只有教师获奖者的
            sql += ' AND (a.granted_role = ? OR (a.granted_role IS NULL AND a.id NOT IN (SELECT award_id FROM award_teacher_winners WHERE award_id IS NOT NULL)))'
            params.append('学生')

        # 实验室筛选
        if self.laboratory_id:
            sql += ' AND a.laboratory_id = ?'
            params.append(self.laboratory_id)

        sql += '''
            GROUP BY c.id, l.id
            ORDER BY c.competition_name, l.name
        '''

        cursor.execute(sql, params)

        # 组织数据：competition_id -> {laboratory_id -> count}
        comp_data = {}
        for row in cursor.fetchall():
            comp_id = row['competition_id']
            lab_id = row['laboratory_id']
            count = row['award_count']

            if comp_id not in comp_data:
                comp_data[comp_id] = {'name': row['competition_name'], 'counts': {}}
            comp_data[comp_id]['counts'][lab_id] = count

        conn.close()

        # 构建返回数据
        competitions = []
        data = []

        for comp_id, comp_info in comp_data.items():
            competitions.append(comp_info['name'])
            row_data = []
            for lab in labs:
                lab_id = lab['id']
                row_data.append(comp_info['counts'].get(lab_id, 0))
            data.append(row_data)

        laboratories = [lab['name'] for lab in labs]

        logger.info(f"热力图数据: {len(competitions)}个竞赛, {len(laboratories)}个实验室")

        return HeatmapData(
            competitions=competitions,
            laboratories=laboratories,
            data=data
        )


# 全局实例缓存
_heatmap_services: Dict[int, HeatmapService] = {}  # laboratory_id -> service


def get_heatmap_service(db_path: str, laboratory_id: Optional[int] = None) -> HeatmapService:
    """获取热力图服务实例

    Args:
        db_path: 数据库文件路径
        laboratory_id: 实验室ID，None表示管理员视图

    Returns:
        HeatmapService: 热力图服务实例
    """
    key = laboratory_id if laboratory_id is not None else -1

    if key not in _heatmap_services:
        _heatmap_services[key] = HeatmapService(db_path, laboratory_id)

    return _heatmap_services[key]
