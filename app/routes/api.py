"""
API路由（AJAX接口）

通用API端点
"""
import logging
from flask import Blueprint, jsonify, request
from app.auth import require_login, require_role_api

bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)


@bp.route('/health')
def health():
    """健康检查接口"""
    return jsonify({'status': 'ok', 'message': 'API is running'})


@bp.route('/metrics')
def metrics_export():
    """Prometheus 指标暴露（4.7/部署 §3——仅内网访问，nginx 侧可加白名单）。"""
    from backend.utils.metrics import exporter_response
    body, code, headers = exporter_response()
    return body, code, headers


@bp.route('/audit/timeline/<kind>/<int:entity_id>')
@require_role_api('admin', 'teacher')
def audit_timeline(kind, entity_id):
    """成果审核轨迹时间线（FR-AUDIT-03 / FR-UI-01 数据源 / 设计 API §2）。

    kind ∈ award|patent|software|innovation|other；返回按时间正序的留痕列表
    （动作类型/操作人含 AI/时间/变更摘要），供时间轴组件渲染。
    学生侧本人轨迹可后续按需开放（当前管理员+教师）。
    """
    if kind not in ('award', 'patent', 'software', 'innovation', 'other'):
        return jsonify({'success': False, 'message': f'无效成果类型: {kind}'}), 400
    try:
        from backend.utils.db_connection import get_connection
        from config.loader import get_config
        from backend.utils.audit_logger import ACTION_LABELS
        conn = get_connection(get_config().get_path('database', 'competitions_db'))
        rows = conn.execute(
            """SELECT id, action_type, action_result, operator_code, operator_name, operator_role,
                      trace_id, change_detail, remark, created_at
               FROM achievement_audit_log
               WHERE achievement_kind = ? AND achievement_id = ?
               ORDER BY created_at ASC, id ASC""",
            (kind, entity_id)).fetchall()
        # 历史数据兼容：M1 后 operator_name 曾存 users.id（纯数字）——批量解析为 "学号 姓名"
        disp_map = {}
        num_ids = {r['operator_name'] for r in rows
                   if r['operator_name'] and str(r['operator_name']).isdigit()}
        if num_ids:
            try:
                placeholders = ",".join("?" * len(num_ids))
                c2 = get_connection(get_config().get_path('database', 'competitions_db'))
                for ur in c2.execute(
                        f"SELECT id, login_code, name FROM users WHERE id IN ({placeholders})",
                        tuple(num_ids)):
                    disp_map[str(ur['id'])] = f"{ur['login_code']} {ur['name'] or ur['login_code']}".strip()
                c2.close()
            except Exception:
                pass
        conn.close()
        ROLE_LABELS = {1: '学生', 2: '教师', 3: 'AI', 4: '管理员'}
        timeline = [{
            'id': r['id'],
            'action': ACTION_LABELS.get(r['action_type'], str(r['action_type'])),
            'action_type': r['action_type'],
            'operator': disp_map.get(str(r['operator_name']), r['operator_name']),
            'operator_role': ROLE_LABELS.get(r['operator_role'], ''),
            'is_ai': r['operator_role'] == 3,
            'trace_id': r['trace_id'],
            'remark': r['remark'],
            'change_detail': r['change_detail'],
            'created_at': r['created_at'],
        } for r in rows]
        return jsonify({'success': True, 'kind': kind, 'entity_id': entity_id,
                        'timeline': timeline, 'count': len(timeline)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/user/info')
@require_login
def user_info():
    """获取当前用户信息"""
    from flask import session
    return jsonify({
        'user_id': session.get('user_id'),
        'user_type': session.get('user_type'),
        'name': session.get('user_name'),
        'role': session.get('role')
    })


# ==================== 辅助函数 ====================

def _get_manager(laboratory_id=None):
    """获取数据分析管理器实例

    Args:
        laboratory_id: 实验室ID，用于过滤数据范围

    Returns:
        DataAnalysisManager实例
    """
    from config.loader import get_config
    from backend.managers.data_analysis_manager import DataAnalysisManager

    config = get_config()
    db_path = config.get_path("database", "competitions_db")
    return DataAnalysisManager(str(db_path), laboratory_id=laboratory_id)


def _parse_years(years_str):
    """解析年份列表字符串，支持多个年份（逗号分隔）"""
    if not years_str:
        return None
    try:
        years = [int(y.strip()) for y in years_str.split(',') if y.strip()]
        return years if years else None
    except:
        return None


def _parse_year_range(year_range_str):
    """解析年份范围字符串（保留兼容性）"""
    if not year_range_str:
        return None
    try:
        years = [int(y.strip()) for y in year_range_str.split(',')]
        return tuple(years) if len(years) == 2 else None
    except:
        return None


# ==================== 数据分析API ====================

@bp.route('/admin/data-analysis/competitions', methods=['GET'])
@require_role_api('admin')
def get_competitions():
    """获取有奖状的竞赛列表"""
    manager = _get_manager()
    competitions = manager.get_competitions_with_awards()
    return jsonify(competitions)


@bp.route('/admin/data-analysis/award-timeline', methods=['GET'])
@require_role_api('admin')
def get_award_timeline():
    """获取奖状时间分布"""
    competition_id = request.args.get('competition_id', type=int)
    if not competition_id:
        return jsonify({'error': 'Missing competition_id'}), 400

    manager = _get_manager()
    result = manager.get_competition_award_timeline(competition_id)
    return jsonify(result)


@bp.route('/admin/data-analysis/contribution', methods=['GET'])
@require_role_api('admin')
def get_contribution():
    """获取竞赛贡献度

    参数:
        years: 年份列表，逗号分隔，如 "2022,2023,2024"（精确多选）
        year_range: 年份范围，逗号分隔，如 "2022,2024"（兼容旧版）
        white_list_only: 是否仅白名单，true/false
        include_teacher_certificates: 是否包含教师证书，true/false（默认false）
    """
    years_str = request.args.get('years')
    year_range_str = request.args.get('year_range')
    white_list_only = request.args.get('white_list_only', 'false').lower() == 'true'
    include_teacher_certificates = request.args.get('include_teacher_certificates', 'false').lower() == 'true'

    # 解析年份：支持多选年份列表
    years = None
    year_range = None

    if years_str:
        # 使用精确年份列表
        years = _parse_years(years_str)
    elif year_range_str:
        # 兼容旧版：使用年份范围
        year_range = _parse_year_range(year_range_str)

    manager = _get_manager()
    result = manager.get_competition_contribution(
        years=years,
        year_range=year_range,
        white_list_only=white_list_only,
        include_teacher_certificates=include_teacher_certificates
    )
    return jsonify(result)


@bp.route('/admin/data-analysis/trend', methods=['GET'])
@require_role_api('admin')
def get_trend():
    """获取竞赛历年获奖趋势"""
    competition_id = request.args.get('competition_id', type=int)
    year_range_str = request.args.get('year_range')

    if not competition_id:
        return jsonify({'error': 'Missing competition_id'}), 400

    year_range = _parse_year_range(year_range_str)

    manager = _get_manager()
    result = manager.get_competition_trend(
        competition_id=competition_id,
        year_range=year_range
    )
    return jsonify(result)


@bp.route('/admin/data-analysis/heatmap', methods=['GET'])
@require_role_api('admin')
def get_heatmap():
    """获取奖状月度分布热力图数据（旧版，保留兼容性）"""
    competition_id = request.args.get('competition_id', type=int)

    if not competition_id:
        return jsonify({'error': 'Missing competition_id'}), 400

    manager = _get_manager()
    result = manager.get_competition_heatmap(competition_id=competition_id)
    return jsonify(result)


@bp.route('/admin/data-analysis/lab-competition-heatmap', methods=['GET'])
@require_role_api('admin', 'teacher', 'student')
def get_lab_competition_heatmap():
    """获取实验室×竞赛热力图数据（新版）

    参数:
        years: 年份列表，逗号分隔，如 "2022,2023,2024"（可选）
        white_list_only: 是否仅白名单竞赛，true/false（默认false）
        include_teacher_certificates: 是否包含教师证书，true/false（默认false）
    """
    from config.loader import get_config
    from backend.services.heatmap_service import get_heatmap_service, HeatmapFilters

    config = get_config()
    db_path = str(config.get_path("database", "competitions_db"))

    # 解析参数
    years_str = request.args.get('years')
    years = _parse_years(years_str) if years_str else None
    white_list_only = request.args.get('white_list_only', 'false').lower() == 'true'
    include_teacher_certificates = request.args.get('include_teacher_certificates', 'false').lower() == 'true'

    # 构建筛选条件
    filters = HeatmapFilters(
        years=years,
        white_list_only=white_list_only,
        include_teacher_certificates=include_teacher_certificates
    )

    # 获取热力图数据
    service = get_heatmap_service(db_path, laboratory_id=None)  # 管理员视图
    result = service.get_lab_competition_heatmap(filters)

    return jsonify({
        'competitions': result.competitions,
        'laboratories': result.laboratories,
        'data': result.data
    })


@bp.route('/admin/data-analysis/dynamic-chart', methods=['GET'])
@require_role_api('admin')
def get_dynamic_chart():
    """获取动态图表数据"""
    x_axis = request.args.get('x_axis', 'year')
    color_by = request.args.get('color_by', 'laboratory')
    year_range_str = request.args.get('year_range')
    filters = request.args.to_dict()

    # 检查冲突组合
    conflicts = [
        ('year', 'year'),
        ('laboratory', 'laboratory')
    ]
    if (x_axis, color_by) in conflicts:
        return jsonify({'error': f'冲突的X轴和颜色分组: {x_axis} + {color_by}'}), 400

    year_range = _parse_year_range(year_range_str)

    manager = _get_manager()
    result = manager.get_dynamic_chart_data(
        x_axis=x_axis,
        color_by=color_by,
        year_range=year_range,
        filters=filters
    )
    return jsonify(result)


# ==================== 实验室数据分析API ====================

@bp.route('/laboratory/<int:lab_id>/data-analysis/competitions', methods=['GET'])
@require_role_api('teacher')
def get_laboratory_competitions(lab_id):
    """获取实验室有奖状的竞赛列表（含关注状态）"""
    try:
        manager = _get_manager(laboratory_id=lab_id)
        competitions = manager.get_competitions_with_awards(
            watcher_type='laboratory',
            watcher_id=lab_id
        )
        return jsonify(competitions)
    except Exception as e:
        logger.exception('实验室竞赛列表接口异常 lab_id=%s', lab_id)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/laboratory/<int:lab_id>/data-analysis/award-timeline', methods=['GET'])
@require_role_api('teacher')
def get_laboratory_award_timeline(lab_id):
    """获取实验室奖状时间分布"""
    competition_id = request.args.get('competition_id', type=int)
    if not competition_id:
        return jsonify({'error': 'Missing competition_id'}), 400

    manager = _get_manager(laboratory_id=lab_id)
    result = manager.get_competition_award_timeline(competition_id)
    return jsonify(result)


@bp.route('/laboratory/<int:lab_id>/data-analysis/contribution', methods=['GET'])
@require_role_api('teacher')
def get_laboratory_contribution(lab_id):
    """获取实验室竞赛贡献度

    参数:
        years: 年份列表，逗号分隔，如 "2022,2023,2024"（精确多选）
        year_range: 年份范围，逗号分隔，如 "2022,2024"（兼容旧版）
        white_list_only: 是否仅白名单，true/false
        include_teacher_certificates: 是否包含教师证书，true/false（默认false）
    """
    years_str = request.args.get('years')
    year_range_str = request.args.get('year_range')
    white_list_only = request.args.get('white_list_only', 'false').lower() == 'true'
    include_teacher_certificates = request.args.get('include_teacher_certificates', 'false').lower() == 'true'

    # 解析年份：支持多选年份列表
    years = None
    year_range = None

    if years_str:
        # 使用精确年份列表
        years = _parse_years(years_str)
    elif year_range_str:
        # 兼容旧版：使用年份范围
        year_range = _parse_year_range(year_range_str)

    manager = _get_manager(laboratory_id=lab_id)
    result = manager.get_competition_contribution(
        years=years,
        year_range=year_range,
        white_list_only=white_list_only,
        include_teacher_certificates=include_teacher_certificates
    )
    return jsonify(result)


@bp.route('/laboratory/<int:lab_id>/data-analysis/trend', methods=['GET'])
@require_role_api('teacher')
def get_laboratory_trend(lab_id):
    """获取实验室竞赛历年获奖趋势"""
    competition_id = request.args.get('competition_id', type=int)
    year_range_str = request.args.get('year_range')

    if not competition_id:
        return jsonify({'error': 'Missing competition_id'}), 400

    year_range = _parse_year_range(year_range_str)

    manager = _get_manager(laboratory_id=lab_id)
    result = manager.get_competition_trend(
        competition_id=competition_id,
        year_range=year_range
    )
    return jsonify(result)


@bp.route('/laboratory/<int:lab_id>/data-analysis/heatmap', methods=['GET'])
@require_role_api('teacher')
def get_laboratory_heatmap(lab_id):
    """获取实验室奖状月度分布热力图数据"""
    competition_id = request.args.get('competition_id', type=int)

    if not competition_id:
        return jsonify({'error': 'Missing competition_id'}), 400

    manager = _get_manager(laboratory_id=lab_id)
    result = manager.get_competition_heatmap(competition_id=competition_id)
    return jsonify(result)


# ==================== 管理员实验室数据分析API ====================

@bp.route('/admin/laboratory/<int:lab_id>/data-analysis/competitions', methods=['GET'])
@require_role_api('admin', 'teacher', 'student')
def get_admin_laboratory_competitions(lab_id):
    """获取实验室有奖状的竞赛列表（含关注状态）- 管理员视图"""
    try:
        manager = _get_manager(laboratory_id=lab_id)
        competitions = manager.get_competitions_with_awards(
            watcher_type='laboratory',
            watcher_id=lab_id
        )
        return jsonify(competitions)
    except Exception as e:
        logger.exception('get_admin_laboratory_competitions failed: lab_id=%s', lab_id)
        return jsonify({'success': False, 'message': str(e), 'competitions': []}), 500


@bp.route('/admin/laboratory/<int:lab_id>/data-analysis/award-timeline', methods=['GET'])
@require_role_api('admin', 'teacher', 'student')
def get_admin_laboratory_award_timeline(lab_id):
    """获取实验室奖状时间分布 - 管理员视图"""
    competition_id = request.args.get('competition_id', type=int)
    if not competition_id:
        return jsonify({'error': 'Missing competition_id'}), 400
    try:
        manager = _get_manager(laboratory_id=lab_id)
        result = manager.get_competition_award_timeline(competition_id)
        return jsonify(result)
    except Exception as e:
        logger.exception('get_admin_laboratory_award_timeline failed: lab_id=%s', lab_id)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/admin/laboratory/<int:lab_id>/data-analysis/contribution', methods=['GET'])
@require_role_api('admin', 'teacher', 'student')
def get_admin_laboratory_contribution(lab_id):
    """获取实验室竞赛贡献度 - 管理员视图

    参数:
        years: 年份列表，逗号分隔，如 "2022,2023,2024"（精确多选）
        year_range: 年份范围，逗号分隔，如 "2022,2024"（兼容旧版）
        white_list_only: 是否仅白名单，true/false
        include_teacher_certificates: 是否包含教师证书，true/false（默认false）
    """
    years_str = request.args.get('years')
    year_range_str = request.args.get('year_range')
    white_list_only = request.args.get('white_list_only', 'false').lower() == 'true'
    include_teacher_certificates = request.args.get('include_teacher_certificates', 'false').lower() == 'true'

    # 解析年份：支持多选年份列表
    years = None
    year_range = None

    if years_str:
        # 使用精确年份列表
        years = _parse_years(years_str)
    elif year_range_str:
        # 兼容旧版：使用年份范围
        year_range = _parse_year_range(year_range_str)

    try:
        manager = _get_manager(laboratory_id=lab_id)
        result = manager.get_competition_contribution(
            years=years,
            year_range=year_range,
            white_list_only=white_list_only,
            include_teacher_certificates=include_teacher_certificates
        )
        return jsonify(result)
    except Exception as e:
        logger.exception('get_admin_laboratory_contribution failed: lab_id=%s', lab_id)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/admin/laboratory/<int:lab_id>/data-analysis/lab-competition-heatmap', methods=['GET'])
@require_role_api('admin', 'teacher', 'student')
def get_admin_laboratory_heatmap(lab_id):
    """获取实验室奖状分布统计 - 管理员视图

    参数:
        years: 年份列表，逗号分隔（可选）
        white_list_only: 是否仅白名单竞赛（默认false）
        include_teacher_certificates: 是否包含教师证书（默认false）
    """
    from config.loader import get_config
    from backend.services.heatmap_service import get_heatmap_service, HeatmapFilters

    config = get_config()
    db_path = str(config.get_path("database", "competitions_db"))

    # 解析参数
    years_str = request.args.get('years')
    years = _parse_years(years_str) if years_str else None
    white_list_only = request.args.get('white_list_only', 'false').lower() == 'true'
    include_teacher_certificates = request.args.get('include_teacher_certificates', 'false').lower() == 'true'

    # 构建筛选条件
    filters = HeatmapFilters(
        years=years,
        white_list_only=white_list_only,
        include_teacher_certificates=include_teacher_certificates
    )

    try:
        # 获取实验室×竞赛热力图数据
        service = get_heatmap_service(db_path, laboratory_id=lab_id)
        result = service.get_lab_competition_heatmap(filters)
        return jsonify({
            'competitions': result.competitions,
            'laboratories': result.laboratories,
            'data': result.data
        })
    except Exception as e:
        logger.exception('get_admin_laboratory_heatmap failed: lab_id=%s', lab_id)
        return jsonify({'success': False, 'message': str(e)}), 500

