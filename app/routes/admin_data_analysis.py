"""
管理员 - 数据分析与可视化路由
"""
from flask import Blueprint, render_template
from app.auth import require_role

bp = Blueprint('admin_data_analysis', __name__)


@bp.route('/data-analysis')
@require_role('admin')
def data_analysis():
    """数据分析与可视化页面"""
    return render_template('admin/data_analysis.html')
