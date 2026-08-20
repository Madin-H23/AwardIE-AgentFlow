"""
教师路由
"""
import json
import sqlite3
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, flash, current_app, redirect, url_for, Response
import logging

logger = logging.getLogger(__name__)
from app.auth import require_user_type
from backend.utils.idempotency import idempotent
from app.utils import get_app_context_instance
from app.routes.user_common import register_common_routes, get_profile_data_common, _parse_skills
from app.routes.file_import_helpers import get_data_import_types
from app.routes.admin_achievement import _get_review_service

bp = Blueprint('teacher', __name__)

# 先定义教师特定的路由（会覆盖共同路由）
@bp.route('/')
@bp.route('/dashboard')
@require_user_type('teacher')
def dashboard():
    """教师仪表板页面（真实数据）"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return render_template('teacher/dashboard_ref.html',
                                 award_count=0,
                                 skills_count=0,
                                 skills=[],
                                 laboratory=None,
                                 recent_awards=[],
                                 teacher_info=None,
                                 error='用户未登录')

        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        award_manager = app_context.get_award_manager()
        laboratory_manager = app_context.get_laboratory_manager()

        # 获取教师信息
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            return render_template('teacher/dashboard_ref.html',
                                 award_count=0,
                                 skills_count=0,
                                 skills=[],
                                 laboratory=None,
                                 recent_awards=[],
                                 teacher_info=None,
                                 error='教师信息不存在')

        # 查询教师成果（与成果页一致：第一指导教师 + 教师自身证书）
        teacher_name = (teacher.name or '').strip()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        q_kw = {
            'with_associations': True,
            'student_manager': student_manager,
            'teacher_manager': teacher_manager,
            'comp_mgr': competition_manager,
            'limit': None,
            'offset': None,
        }
        awards_as_supervisor = award_manager.query_awards(supervisor_name=teacher_name, **q_kw) if teacher_name else []
        awards_as_winner = award_manager.query_awards(winner_name=teacher_name, **q_kw) if teacher_name else []
        awards_as_winner = [a for a in awards_as_winner if a.granted_role and '教师' in a.granted_role]
        seen_ids = set()
        awards = []
        for a in awards_as_supervisor + awards_as_winner:
            if a.id not in seen_ids:
                seen_ids.add(a.id)
                awards.append(a)
        award_count = len(awards)

        # 按日期排序（最新的在前）
        def parse_date_for_sort(date_value):
            """解析日期值用于排序，支持字符串和 datetime 对象"""
            if not date_value:
                return datetime.min
            if isinstance(date_value, datetime):
                return date_value
            if isinstance(date_value, str):
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日', '%Y.%m.%d', '%Y-%m-%d %H:%M:%S']:
                    try:
                        return datetime.strptime(date_value, fmt)
                    except ValueError:
                        continue
                return datetime.min
            return datetime.min

        awards.sort(key=lambda a: parse_date_for_sort(a.date) if a.date else datetime.min, reverse=True)

        # 准备成果卡片数据（全部成果）
        recent_awards_data = []
        for award in awards:
            # 获取竞赛信息
            competition_name = award.competition_name_in_file or ''
            if award.competition_obj:
                competition_name = award.competition_obj.name

            # 构建标题：{竞赛等级}{获奖等级}
            title_parts = []
            if award.competition_level:
                title_parts.append(award.competition_level)
            if award.award_level:
                title_parts.append(award.award_level)
            title = ''.join(title_parts) if title_parts else '获奖'

            # 构建副标题：{year}年{竞赛名称}
            subtitle_parts = []
            if award.year:
                subtitle_parts.append(f"{award.year}年")
            subtitle_parts.append(competition_name)
            subtitle = ''.join(subtitle_parts) if subtitle_parts else competition_name

            # 日期
            date_str = award.date or ''

            recent_awards_data.append({
                'id': award.id,
                'title': title,
                'subtitle': subtitle,
                'date': date_str
            })

        # 计算技能标签数量
        skills = _parse_skills(teacher.skills)
        skills_count = len(skills) if skills else 0

        # 获取教师所属的实验室
        laboratory = laboratory_manager.get_laboratory_by_teacher_id(teacher.id)

        # 准备教师信息
        teacher_info = {
            'department': teacher.department if hasattr(teacher, 'department') else None,
            'teacher_id': teacher.teacher_id if hasattr(teacher, 'teacher_id') else None
        }

        return render_template('teacher/dashboard_ref.html',
                             award_count=award_count,
                             skills_count=skills_count,
                             skills=skills,  # 传递技能标签列表
                             laboratory=laboratory,  # 传递实验室信息
                             recent_awards=recent_awards_data,
                             teacher_info=teacher_info)

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"获取教师仪表板数据失败: {error_detail}")
        return render_template('teacher/dashboard_ref.html',
                             award_count=0,
                             skills_count=0,
                             skills=[],  # 错误时传递空列表
                             laboratory=None,
                             recent_awards=[],
                             teacher_info=None,
                             error=f'获取数据失败: {str(e)}')


# 个人主页已合并到仪表板，不再需要单独路由
# @bp.route('/personal')
# @require_user_type('teacher')
# def personal():
#     """教师个人主页页面（实际数据）"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return render_template('teacher/personal_ref.html', error='用户未登录')
        
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        
        # 获取教师信息
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            return render_template('teacher/personal_ref.html', error='教师信息不存在')
        
        # 获取技能标签
        skills = _parse_skills(teacher.skills)
        
        # 查询教师关联的奖状（作为获奖者和指导教师）
        # 通过查询关联表获取奖状ID列表
        conn = sqlite3.connect(award_manager.db_path)
        cursor = conn.cursor()
        
        # 查询教师作为获奖者的奖状
        cursor.execute("""
            SELECT DISTINCT award_id 
            FROM award_teacher_winners 
            WHERE teacher_id = ?
        """, (teacher.id,))
        winner_award_ids = [row[0] for row in cursor.fetchall()]
        
        # 查询教师作为指导教师的奖状
        cursor.execute("""
            SELECT DISTINCT award_id 
            FROM award_supervisors 
            WHERE teacher_id = ?
        """, (teacher.id,))
        supervisor_award_ids = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        # 合并奖状ID（去重）
        all_award_ids = list(set(winner_award_ids + supervisor_award_ids))
        
        # 获取奖状对象
        awards = []
        if all_award_ids:
            # 从内存中查找奖状
            for award in award_manager.awards:
                if award.id in all_award_ids:
                    # 加载关联数据
                    award.refresh_associations(competition_manager, app_context.get_student_manager(), teacher_manager)
                    awards.append(award)
        
        # 按日期排序（最新的在前）
        # 日期可能是字符串格式（如 "2024-12-20"）或 datetime 对象，需要统一处理
        def parse_date_for_sort(date_value):
            """解析日期值用于排序，支持字符串和 datetime 对象"""
            if not date_value:
                # 空日期返回一个最小值，确保排在最后
                return datetime.min
            
            # 如果已经是 datetime 对象，直接返回
            if isinstance(date_value, datetime):
                return date_value
            
            # 如果是字符串，尝试解析
            if isinstance(date_value, str):
                # 尝试解析常见日期格式
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日', '%Y.%m.%d', '%Y-%m-%d %H:%M:%S']:
                    try:
                        return datetime.strptime(date_value, fmt)
                    except ValueError:
                        continue
                # 如果都解析失败，返回最小值（排在最后）
                return datetime.min
            
            # 其他类型，返回最小值
            return datetime.min
        
        awards.sort(key=lambda a: parse_date_for_sort(a.date) if a.date else datetime.min, reverse=True)
        
        # 只取最近3项
        recent_awards = awards[:3]
        
        # 准备传递给模板的数据
        teacher_data = {
            'name': teacher.name,
            'teacher_id': teacher.teacher_id,
            'qq': teacher.qq or '',
            'phone': teacher.phone or '',
            'skills': skills,
            'awards': [],
            'has_more_awards': len(awards) > 3  # 标记是否有更多成果
        }
        
        # 处理奖状数据（只处理最近3项）
        for award in recent_awards:
            # 获取竞赛信息
            competition_name = award.competition_name_in_file or ''
            if award.competition_obj:
                competition_name = award.competition_obj.name
            
            # 构建标题：{竞赛等级}{获奖等级}
            title_parts = []
            if award.competition_level:
                title_parts.append(award.competition_level)
            if award.award_level:
                title_parts.append(award.award_level)
            title = ''.join(title_parts) if title_parts else '获奖'
            
            # 构建副标题：{year}年{竞赛名称}
            subtitle_parts = []
            if award.year:
                subtitle_parts.append(f"{award.year}年")
            subtitle_parts.append(competition_name)
            subtitle = ''.join(subtitle_parts) if subtitle_parts else competition_name
            
            # 日期
            date_str = award.date or ''
            
            teacher_data['awards'].append({
                'id': award.id,  # 添加奖状ID，用于生成编辑链接
                'title': title,
                'subtitle': subtitle,
                'date': date_str
            })
        
        return render_template('teacher/personal_ref.html', teacher=teacher_data)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"获取教师个人主页数据失败: {error_detail}")
        return render_template('teacher/personal_ref.html', error=f'获取数据失败: {str(e)}')

# 注册共同路由（跳过 dashboard、personal、achievements 和 activities，因为需要自定义）
register_common_routes(bp, 'teacher', skip_routes=['dashboard', 'personal', 'achievements', 'activities'])

@bp.route('/achievements')
@require_user_type('teacher')
def achievements():
    """教师成果页面（实际数据）"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return render_template('teacher/achievements_ref.html', error='用户未登录')
        
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        
        # 获取教师信息
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            return render_template('teacher/achievements_ref.html', error='教师信息不存在')
        
        # 查询教师成果：与管理端奖状管理保持一致，按 award.supervisor_name / winner_name 文本匹配
        # 1) 第一指导教师的学生奖状  2) 教师自身的证书（教师为获奖者）
        # 避免依赖 award_supervisors 表（导入时人名匹配失败会导致该表为空，与管理端查询结果不一致）
        teacher_name = (teacher.name or '').strip()
        student_manager = app_context.get_student_manager()
        comp_manager = competition_manager
        q_kw = {
            'with_associations': True,
            'student_manager': student_manager,
            'teacher_manager': teacher_manager,
            'comp_mgr': comp_manager,
            'limit': None,
            'offset': None,
        }
        awards_as_supervisor = award_manager.query_awards(supervisor_name=teacher_name, **q_kw) if teacher_name else []
        awards_as_winner = award_manager.query_awards(winner_name=teacher_name, **q_kw) if teacher_name else []
        # 教师自身证书：获奖者为该教师且 granted_role 含「教师」
        awards_as_winner = [a for a in awards_as_winner if a.granted_role and '教师' in a.granted_role]
        seen_ids = set()
        awards = []
        for a in awards_as_supervisor + awards_as_winner:
            if a.id not in seen_ids:
                seen_ids.add(a.id)
                awards.append(a)
        all_award_ids = list(seen_ids)
        
        # 按年份和竞赛等级统计
        stats_by_year = {}
        for award in awards:
            # 获取年份（优先使用 year 字段，如果没有则从 date 中提取）
            year = None
            if award.year:
                year = award.year
            elif award.date:
                try:
                    # 尝试从日期字符串中提取年份
                    if isinstance(award.date, datetime):
                        year = award.date.year
                    elif isinstance(award.date, str):
                        # 尝试解析日期字符串
                        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日', '%Y.%m.%d']:
                            try:
                                parsed_date = datetime.strptime(award.date, fmt)
                                year = parsed_date.year
                                break
                            except ValueError:
                                continue
                except Exception:
                    pass
            
            if not year:
                continue
            
            # 获取竞赛等级
            competition_level = award.competition_level or ''
            
            # 只统计国赛和省赛
            if competition_level in ['国赛', '省赛']:
                if year not in stats_by_year:
                    stats_by_year[year] = {'国赛': 0, '省赛': 0}
                
                if competition_level == '国赛':
                    stats_by_year[year]['国赛'] += 1
                elif competition_level == '省赛':
                    stats_by_year[year]['省赛'] += 1
        
        # 按年份排序
        sorted_years = sorted(stats_by_year.keys())
        
        # 准备图表数据
        chart_data = {
            'years': sorted_years,
            'national': [stats_by_year.get(year, {}).get('国赛', 0) for year in sorted_years],
            'provincial': [stats_by_year.get(year, {}).get('省赛', 0) for year in sorted_years]
        }
        
        # 统计总数
        total_national = sum(stats_by_year.get(year, {}).get('国赛', 0) for year in sorted_years)
        total_provincial = sum(stats_by_year.get(year, {}).get('省赛', 0) for year in sorted_years)
        total_awards = len(awards)
        
        # 获取查询参数（用于奖状列表）
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        competition_id = request.args.get('competition_id', type=int)
        year = request.args.get('year', type=int)
        competition_level = request.args.get('competition_level', '').strip()
        award_level = request.args.get('award_level', '').strip()
        include_teacher_certificates = request.args.get('include_teacher_certificates', '1') == '1'
        
        # 筛选奖状
        filtered_awards = awards
        
        # 根据include_teacher_certificates筛选教师证书
        if not include_teacher_certificates:
            conn = sqlite3.connect(award_manager.db_path)
            cursor = conn.cursor()
            winner_counts = {}
            if all_award_ids:
                placeholders = ','.join(['?'] * len(all_award_ids))
                cursor.execute(f"""
                    SELECT award_id, COUNT(*) as count FROM award_teacher_winners
                    WHERE award_id IN ({placeholders}) GROUP BY award_id
                """, all_award_ids)
                teacher_counts = {row[0]: row[1] for row in cursor.fetchall()}
                cursor.execute(f"""
                    SELECT award_id, COUNT(*) as count FROM award_student_winners
                    WHERE award_id IN ({placeholders}) GROUP BY award_id
                """, all_award_ids)
                student_counts = {row[0]: row[1] for row in cursor.fetchall()}
                for aid in all_award_ids:
                    winner_counts[aid] = {'teacher': teacher_counts.get(aid, 0), 'student': student_counts.get(aid, 0)}
            conn.close()
            filtered_awards = []
            for award in awards:
                if award.granted_role:
                    if '教师' in award.granted_role and '学生' not in award.granted_role:
                        continue
                    if '学生' in award.granted_role:
                        filtered_awards.append(award)
                        continue
                counts = winner_counts.get(award.id, {'teacher': 0, 'student': 0})
                if counts['student'] > 0:
                    filtered_awards.append(award)
                elif counts['teacher'] > 0 and counts['student'] == 0:
                    continue
                else:
                    filtered_awards.append(award)
        
        # 其他筛选条件
        if competition_id:
            filtered_awards = [a for a in filtered_awards if a.competition_id == competition_id]
        if year:
            filtered_awards = [a for a in filtered_awards if a.year == year]
        if competition_level:
            filtered_awards = [a for a in filtered_awards if a.competition_level == competition_level]
        if award_level:
            filtered_awards = [a for a in filtered_awards if a.award_level == award_level]
        
        # 分页
        total_count = len(filtered_awards)
        total_pages = (total_count + per_page - 1) // per_page
        paginated_awards = filtered_awards[(page - 1) * per_page:page * per_page]
        
        # 获取该教师关联的奖状中涉及的竞赛（用于筛选下拉框）
        teacher_competition_ids = set()
        for award in awards:  # 使用所有关联的奖状，不只是筛选后的
            if award.competition_id:
                teacher_competition_ids.add(award.competition_id)
        
        # 只获取这些竞赛
        competitions = [comp for comp in competition_manager.competitions if comp.id in teacher_competition_ids]
        # 按名称排序
        competitions.sort(key=lambda x: x.name or '')

        # 教师关联的专利（提交者为该教师）
        patents = []
        patent_manager = app_context.get_patent_manager()
        if patent_manager:
            from backend.models.patent import PatentFilter
            pf = PatentFilter(submitter_type='teacher', submitter_id=teacher.id)
            patents = patent_manager.query_patents(pf) or []

        # 教师关联的软著（提交者为该教师）
        software_list = []
        software_manager = app_context.get_software_copyright_manager()
        if software_manager:
            from backend.models.software_copyright import SoftwareCopyrightFilter
            sf = SoftwareCopyrightFilter(submitter_type='teacher', submitter_id=teacher.id)
            software_list = software_manager.query_copyrights(sf) or []

        # 教师关联的大创（指导教师姓名包含该教师）
        innovation_projects = []
        innovation_manager = app_context.get_innovation_project_manager()
        if innovation_manager:
            from backend.models.innovation_project import InnovationProjectFilter
            all_innovation = innovation_manager.query_projects(InnovationProjectFilter()) or []
            teacher_name = (teacher.name or '').strip()
            if teacher_name:
                innovation_projects = [p for p in all_innovation if p.get_supervisors_list() and teacher_name in p.get_supervisors_list()]

        return render_template('teacher/achievements_ref.html', 
                             teacher={'name': teacher.name},
                             chart_data=chart_data,
                             total_national=total_national,
                             total_provincial=total_provincial,
                             total_awards=total_awards,
                             awards=paginated_awards,
                             competitions=competitions,
                             page=page,
                             per_page=per_page,
                             total_count=total_count,
                             total_pages=total_pages,
                             competition_id=competition_id,
                             year=year,
                             competition_level=competition_level,
                             award_level=award_level,
                             include_teacher_certificates=include_teacher_certificates,
                             patents=patents,
                             software_list=software_list,
                             innovation_projects=innovation_projects)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"获取教师成果数据失败: {error_detail}")
        return render_template('teacher/achievements_ref.html', 
                             error=f'获取数据失败: {str(e)}',
                             awards=[],
                             competitions=[],
                             page=1,
                             per_page=20,
                             total_count=0,
                             total_pages=1,
                             competition_id=None,
                             year=None,
                             competition_level='',
                             award_level='',
                             include_teacher_certificates=False,
                             patents=[],
                             software_list=[],
                             innovation_projects=[])


@bp.route('/innovation/<int:project_id>')
@require_user_type('teacher')
def innovation_view(project_id):
    """教师查看大创项目详情（仅限本人为指导教师的项目）"""
    user_id = session.get('user_id')
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))
    app_context = get_app_context_instance()
    teacher_manager = app_context.get_teacher_manager()
    project_manager = app_context.get_innovation_project_manager()
    student_manager = app_context.get_student_manager()
    teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
    if not teacher:
        flash('教师信息不存在', 'error')
        return redirect(url_for('teacher.achievements'))
    project = project_manager.load_project_with_associations(project_id, student_manager)
    if not project:
        flash('大创项目不存在', 'error')
        return redirect(url_for('teacher.achievements'))
    supervisors = project.get_supervisors_list() or []
    teacher_name = (teacher.name or '').strip()
    if teacher_name not in [s.strip() for s in supervisors if s]:
        flash('您不是该项目指导教师，无权查看', 'error')
        return redirect(url_for('teacher.achievements'))
    members_data = project.get_members_list()
    members_display = []
    for m in members_data:
        if isinstance(m, dict):
            name = m.get("姓名", "")
            sid = m.get("学号", "")
            members_display.append(f"{name}({sid})" if sid else name)
        else:
            members_display.append(str(m))
    laboratory = None
    if project.laboratory_id:
        laboratory_manager = app_context.get_laboratory_manager()
        laboratory = laboratory_manager.get_laboratory_by_id(project.laboratory_id)
    return render_template('admin/innovation/view.html',
                           project=project,
                           members=members_display,
                           supervisors=supervisors,
                           laboratory=laboratory,
                           read_only=True,
                           return_url=url_for('teacher.achievements'))


@bp.route('/data_export')
@require_user_type('teacher')
def data_export():
    """教师数据导出页面"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return render_template('teacher/data_export.html', error='用户未登录')
        
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        
        # 获取教师信息
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            return render_template('teacher/data_export.html', error='教师信息不存在')
        
        # 查询教师关联的奖状（作为获奖者和指导教师）
        conn = sqlite3.connect(award_manager.db_path)
        cursor = conn.cursor()
        
        # 查询教师作为获奖者的奖状
        cursor.execute("""
            SELECT DISTINCT award_id 
            FROM award_teacher_winners 
            WHERE teacher_id = ?
        """, (teacher.id,))
        winner_award_ids = [row[0] for row in cursor.fetchall()]
        
        # 查询教师作为指导教师的奖状
        cursor.execute("""
            SELECT DISTINCT award_id 
            FROM award_supervisors 
            WHERE teacher_id = ?
        """, (teacher.id,))
        supervisor_award_ids = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        # 合并奖状ID（去重）
        all_award_ids = list(set(winner_award_ids + supervisor_award_ids))
        
        # 获取奖状对象
        awards = []
        if all_award_ids:
            student_manager = app_context.get_student_manager()
            for award in award_manager.awards:
                if award.id in all_award_ids:
                    award.refresh_associations(competition_manager, student_manager, teacher_manager)
                    awards.append(award)
        
        # 获取筛选参数
        from datetime import datetime, timedelta
        from backend.utils.export_utils import generate_department_summary_data, format_date_to_month
        
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        year = request.args.get('year', type=int)
        
        # 设置默认日期
        if not end_date:
            now = datetime.now()
            end_date = now.strftime('%Y-%m')
        
        if not start_date:
            one_year_ago = datetime.now() - timedelta(days=365)
            start_date = one_year_ago.strftime('%Y-%m')
        
        # 年份筛选
        if year:
            awards = [a for a in awards if a.year == year]
        
        # 日期范围筛选
        if start_date or end_date:
            filtered_awards = []
            for award in awards:
                if not award.date:
                    continue
                award_date_month = format_date_to_month(award.date)
                if not award_date_month:
                    continue
                if start_date and award_date_month < start_date:
                    continue
                if end_date and award_date_month > end_date:
                    continue
                filtered_awards.append(award)
            awards = filtered_awards
        
        # 获取实验室管理器（activity_manager 已废弃：AppContext 无此方法、export_utils 无此参数——对齐签名）
        laboratory_manager = app_context.get_laboratory_manager()
        
        # 生成报表数据
        report_data = generate_department_summary_data(
            awards, 
            competition_manager,
            laboratory_manager=laboratory_manager
        )
        
        # 列名
        columns = [
            "竞赛名称", "竞赛是否榜单类别", "获奖项目全称", "获奖日期", "奖项级别",
            "奖项等级", "主办单位", "参赛队伍", "队伍人数", "学生负责人",
            "学生负责人学号", "学生负责人手机", "指导教师", "所属实验室"
        ]
        
        return render_template('teacher/data_export.html',
                             teacher=teacher,
                             report_data=report_data,
                             columns=columns,
                             start_date=start_date,
                             end_date=end_date,
                             year=year,
                             total_count=len(awards))
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"获取教师数据导出失败: {error_detail}")
        return render_template('teacher/data_export.html', error=f'获取数据失败: {str(e)}')

@bp.route('/achievements/export_filtered', methods=['POST'])
@require_user_type('teacher')
def achievements_export_filtered():
    """导出当前筛选的成果数据（zip：HTML + 佐证图片，与学生导出一致的个人成果风格）。"""
    from datetime import datetime
    from backend.utils.report import generate_personal_export_teacher
    import sqlite3
    
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '用户未登录'}), 401
        
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        
        # 获取教师信息
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            return jsonify({'success': False, 'message': '教师信息不存在'}), 404
        
        # 获取筛选参数（与成果页一致）
        data = request.get_json() or {}
        competition_id = data.get('competition_id')
        year = data.get('year')
        competition_level = data.get('competition_level', '').strip()
        award_level = data.get('award_level', '').strip()
        include_teacher_certificates = data.get('include_teacher_certificates', True)  # 默认包含教师证书
        include_images = data.get('include_images', True)  # 默认包含图片
        
        # 数据源与成果页统一：query_awards(supervisor_name) + query_awards(winner_name 且教师证书)
        teacher_name = (teacher.name or '').strip()
        q_kw = {
            'with_associations': True,
            'student_manager': student_manager,
            'teacher_manager': teacher_manager,
            'comp_mgr': competition_manager,
            'limit': None,
            'offset': None,
        }
        awards_as_supervisor = award_manager.query_awards(supervisor_name=teacher_name, **q_kw) if teacher_name else []
        awards_as_winner = award_manager.query_awards(winner_name=teacher_name, **q_kw) if teacher_name else []
        awards_as_winner = [a for a in awards_as_winner if a.granted_role and '教师' in a.granted_role]
        seen_ids = set()
        awards = []
        for a in awards_as_supervisor + awards_as_winner:
            if a.id not in seen_ids:
                seen_ids.add(a.id)
                awards.append(a)
        all_award_ids = list(seen_ids)
        
        # 应用筛选条件（与achievements路由一致）
        filtered_awards = awards
        
        # 根据include_teacher_certificates筛选教师证书
        if not include_teacher_certificates:
            conn = sqlite3.connect(award_manager.db_path)
            cursor = conn.cursor()
            winner_counts = {}
            if all_award_ids:
                placeholders = ','.join(['?'] * len(all_award_ids))
                cursor.execute(f"""
                    SELECT award_id, COUNT(*) as count FROM award_teacher_winners
                    WHERE award_id IN ({placeholders}) GROUP BY award_id
                """, all_award_ids)
                teacher_counts = {row[0]: row[1] for row in cursor.fetchall()}
                cursor.execute(f"""
                    SELECT award_id, COUNT(*) as count FROM award_student_winners
                    WHERE award_id IN ({placeholders}) GROUP BY award_id
                """, all_award_ids)
                student_counts = {row[0]: row[1] for row in cursor.fetchall()}
                for aid in all_award_ids:
                    winner_counts[aid] = {'teacher': teacher_counts.get(aid, 0), 'student': student_counts.get(aid, 0)}
            conn.close()
            filtered_awards = []
            for award in awards:
                if award.granted_role:
                    if '教师' in award.granted_role and '学生' not in award.granted_role:
                        continue
                    if '学生' in award.granted_role:
                        filtered_awards.append(award)
                        continue
                counts = winner_counts.get(award.id, {'teacher': 0, 'student': 0})
                if counts['student'] > 0:
                    filtered_awards.append(award)
                elif counts['teacher'] > 0 and counts['student'] == 0:
                    continue
                else:
                    filtered_awards.append(award)
        
        # 其他筛选条件
        if competition_id:
            filtered_awards = [a for a in filtered_awards if a.competition_id == competition_id]
        if year:
            filtered_awards = [a for a in filtered_awards if a.year == year]
        if competition_level:
            filtered_awards = [a for a in filtered_awards if a.competition_level == competition_level]
        if award_level:
            filtered_awards = [a for a in filtered_awards if a.award_level == award_level]
        
        # 获取教师关联的专利、软著、大创（与成果页一致）
        patents = []
        patent_manager = app_context.get_patent_manager()
        if patent_manager:
            from backend.models.patent import PatentFilter
            patents = patent_manager.query_patents(PatentFilter(submitter_type='teacher', submitter_id=teacher.id)) or []
        software_list = []
        software_manager = app_context.get_software_copyright_manager()
        if software_manager:
            from backend.models.software_copyright import SoftwareCopyrightFilter
            software_list = software_manager.query_copyrights(SoftwareCopyrightFilter(submitter_type='teacher', submitter_id=teacher.id)) or []
        innovation_projects = []
        innovation_manager = app_context.get_innovation_project_manager()
        if innovation_manager:
            from backend.models.innovation_project import InnovationProjectFilter
            all_innovation = innovation_manager.query_projects(InnovationProjectFilter()) or []
            if teacher_name:
                innovation_projects = [p for p in all_innovation if p.get_supervisors_list() and teacher_name in p.get_supervisors_list()]
        
        # 生成个人成果导出（与学生导出一致的布局风格）
        zip_data = generate_personal_export_teacher(
            teacher=teacher,
            awards=filtered_awards,
            patents=patents,
            software_list=software_list,
            innovation_projects=innovation_projects,
            include_images=include_images,
        )
        
        # 生成文件名（含筛选条件）
        from urllib.parse import quote
        
        filename_parts = ["teacher_filtered_export", f"teacher_{teacher.id}"]
        display_name_parts = ["筛选数据导出", teacher.name]
        
        if competition_id:
            comp = competition_manager.get_competition_by_id(competition_id)
            if comp:
                filename_parts.append(f"comp_{competition_id}")
                display_name_parts.append(comp.name)
        if year:
            filename_parts.append(str(year))
            display_name_parts.append(str(year))
        if competition_level:
            filename_parts.append(f"level_{competition_level}")
            display_name_parts.append(competition_level)
        if award_level:
            filename_parts.append(f"award_{award_level}")
            display_name_parts.append(award_level)
        
        filename_parts.append(datetime.now().strftime("%Y%m%d"))
        display_name_parts.append(datetime.now().strftime("%Y%m%d"))
        
        filename_base_ascii = "_".join(str(p) for p in filename_parts)
        display_name = "_".join(str(p) for p in display_name_parts)
        
        zip_filename_ascii = f"{filename_base_ascii}.zip"
        zip_display_name = f"{display_name}.zip"
        
        try:
            zip_encoded_filename = quote(zip_display_name, safe='')
            zip_content_disposition = f'attachment; filename="{zip_filename_ascii}"; filename*=UTF-8\'\'{zip_encoded_filename}'
            zip_content_disposition.encode('latin-1')
        except (UnicodeEncodeError, AttributeError, TypeError):
            zip_content_disposition = f'attachment; filename="{zip_filename_ascii}"'
        
        return Response(
            zip_data,
            mimetype='application/zip',
            headers={
                'Content-Disposition': zip_content_disposition
            }
        )
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"导出筛选数据失败: {e}\n{error_trace}")
        return jsonify({
            'success': False,
            'message': f'导出失败: {str(e)}',
            'error_type': type(e).__name__
        }), 500

@bp.route('/profile/data')
@require_user_type('teacher')
def get_profile_data():
    """获取教师个人信息数据"""
    return get_profile_data_common('teacher')

@bp.route('/profile/update', methods=['POST'])
@require_user_type('teacher')
def update_profile():
    """更新教师个人信息"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '用户未登录'}), 401
            
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        
        # 根据工号获取教师信息
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            return jsonify({'success': False, 'message': '教师信息不存在'}), 404
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '请求数据为空'}), 400

        # 调试日志
        logger.debug(f"更新教师信息 - user_id: {user_id}, teacher_id: {teacher.teacher_id}")
        logger.debug(f"请求数据: {data}")
        
        # 更新可修改字段（教师只能修改部门、QQ、手机号和技能标签。姓名和工号不允许通过此接口修改）
        update_data = {}
        
        current_app.logger.info(f"正在通过个人中心更新教师信息: ID={teacher.id}, 工号={teacher.teacher_id}")
        
        if 'department' in data:
            update_data['department'] = data['department'] if data['department'] else '未设置'
        if 'qq' in data:
            update_data['qq'] = data['qq'] if data['qq'] else None
        if 'phone' in data:
            update_data['phone'] = data['phone'] if data['phone'] else None
        if 'skills' in data:
            # 将技能标签列表转换为JSON字符串
            try:
                skills = data['skills']
                if isinstance(skills, list):
                    # 空数组也保存为JSON
                    update_data['skills'] = json.dumps(skills, ensure_ascii=False) if skills else None
                elif skills is not None:
                    update_data['skills'] = skills
                else:
                    update_data['skills'] = None
            except Exception as e:
                return jsonify({'success': False, 'message': f'技能标签格式错误: {str(e)}'}), 400
        
        # 执行更新（M1 后半②：视图化后旧表不可写，直写 users 真源）
        if update_data:
            try:
                from backend.orm.repositories import UserRepository
                UserRepository.update_profile(teacher.teacher_id, **update_data)
                current_app.logger.info(f"教师信息更新成功: ID={teacher.id}")
                if 'teacher_id' in update_data:
                    session['user_id'] = update_data['teacher_id']
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                logger.error(f"更新教师信息失败: {error_detail}")
                # 检查是否是唯一约束冲突
                error_msg = str(e)
                if 'UNIQUE constraint' in error_msg or 'unique constraint' in error_msg.lower():
                    return jsonify({'success': False, 'message': '工号已被其他教师使用，无法更新'}), 400
                return jsonify({'success': False, 'message': f'数据库更新失败: {error_msg}'}), 500
        
        return jsonify({
            'success': True,
            'message': '个人信息更新成功'
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"更新个人信息异常: {error_detail}")
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


# ==================== 成果提交相关路由 ====================

@bp.route('/achievement-submit')
@require_user_type('teacher')
def achievement_submit():
    """成果提交页面（包含文件导入和提交记录）"""
    try:
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        pending_manager = app_context.get_pending_achievement_manager()

        # 获取当前教师信息
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            flash('教师信息不存在', 'error')
            return render_template('teacher/submissions.html', submissions=[], all_submissions=[], total_count=0)

        # 全部提交记录（用于统计）；最近 10 条用于首页列表展示
        all_submissions = pending_manager.get_pending_by_submitter('teacher', teacher.id)
        recent_submissions = all_submissions[:10]

        return render_template('teacher/submissions.html',
                             submissions=recent_submissions,
                             all_submissions=all_submissions,
                             total_count=len(all_submissions))

    except Exception as e:
        flash(f'加载提交记录失败: {e}', 'error')
        return render_template('teacher/submissions.html', submissions=[], all_submissions=[], total_count=0)


@bp.route('/achievement-submit/list')
@require_user_type('teacher')
def achievement_submit_list():
    """提交记录列表页面（显示所有记录）"""
    try:
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        pending_manager = app_context.get_pending_achievement_manager()

        # 获取当前教师信息
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            flash('教师信息不存在', 'error')
            return render_template('teacher/submissions_list.html', submissions=[])

        # 获取所有提交记录
        submissions = pending_manager.get_pending_by_submitter('teacher', teacher.id)

        return render_template('teacher/submissions_list.html', submissions=submissions)

    except Exception as e:
        flash(f'加载提交记录失败: {e}', 'error')
        return render_template('teacher/submissions_list.html', submissions=[])


# 保持向后兼容
@bp.route('/submissions')
@require_user_type('teacher')
def my_submissions():
    """向后兼容：重定向到成果提交页面"""
    return redirect(url_for('teacher.achievement_submit'))


# ==================== 验证函数 ====================

def _validate_patent_data(data):
    """验证专利数据"""
    from backend.extract.types import ValidationResult

    content_issues = []
    completeness_issues = []

    # 检查必填字段
    if not data.get('patent_name'):
        completeness_issues.append('专利名称不能为空')

    # 验证申请号格式（如果提供）
    if data.get('application_number'):
        app_number = data['application_number']
        if not app_number.startswith('CN'):
            content_issues.append('申请号应以CN开头')
        if len(app_number) < 5:
            content_issues.append('申请号格式不正确')

    # 验证专利类型（如果提供）
    if data.get('patent_type'):
        valid_types = ['发明专利', '实用新型', '外观设计']
        if data['patent_type'] not in valid_types:
            content_issues.append('专利类型应为：发明专利、实用新型或外观设计')

    return ValidationResult(
        is_valid=len(content_issues) == 0 and len(completeness_issues) == 0,
        content_issues=content_issues,
        completeness_issues=completeness_issues
    )


def _validate_software_data(data):
    """验证软著数据"""
    from backend.extract.types import ValidationResult

    content_issues = []
    completeness_issues = []

    # 检查必填字段
    if not data.get('software_name'):
        completeness_issues.append('软件名称不能为空')

    # 验证登记号格式（如果提供）
    if data.get('registration_number'):
        reg_number = data['registration_number']
        if not reg_number.startswith('20') and len(reg_number) != 11:
            content_issues.append('登记号格式不正确，应为11位数字，如2023SR123456')

    return ValidationResult(
        is_valid=len(content_issues) == 0 and len(completeness_issues) == 0,
        content_issues=content_issues,
        completeness_issues=completeness_issues
    )


def _validate_award_data(data):
    """验证奖状数据"""
    from backend.extract.types import ValidationResult

    content_issues = []
    completeness_issues = []

    # 检查必填字段
    if not data.get('image_hash'):
        completeness_issues.append('证书图片不能为空')

    # 验证日期格式（如果提供）
    if data.get('date'):
        date_str = data['date']
        try:
            # 尝试解析日期，支持多种格式
            from datetime import datetime
            # 支持的格式：YYYY-MM-DD, YYYY-MM, YYYY-M, YYYY/MM/DD, YYYY年MM月DD日
            for fmt in ['%Y-%m-%d', '%Y-%m', '%Y-M', '%Y/%m/%d', '%Y年%m月%d日']:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    # 如果解析成功，检查日期是否合理
                    year = parsed_date.year
                    if year < 2000 or year > 2100:
                        content_issues.append(f'日期年份不合理: {year}，应在 2000-2100 之间')
                    break
                except ValueError:
                    continue
            else:
                content_issues.append('日期格式不正确，支持格式：YYYY-MM-DD、YYYY-MM、YYYY-M')
        except Exception:
            content_issues.append('日期格式不正确')

    return ValidationResult(
        is_valid=len(content_issues) == 0 and len(completeness_issues) == 0,
        content_issues=content_issues,
        completeness_issues=completeness_issues
    )


@bp.route('/index.html')
@require_user_type('teacher')
def index_html():
    """处理 index.html 请求，重定向到 dashboard"""
    from flask import redirect, url_for
    return redirect(url_for('teacher.dashboard'))


# ==================== 文件上传相关路由 ====================

@bp.route('/achievement-submit/progress')
@require_user_type('teacher')
def achievement_submit_progress():
    """获取文件导入进度；支持 task_id 时从 import_progress_store 读取，否则从 session 读取（兼容）。"""
    task_id = request.args.get('task_id', '').strip()
    if task_id:
        from app.import_progress_store import get_progress_or_idle
        progress = get_progress_or_idle(task_id)
        return jsonify(progress)
    progress_key = 'file_import_progress'
    progress = session.get(progress_key, {
        'total': 0,
        'current': 0,
        'current_file': '',
        'current_step': '',
        'status': 'idle',
        'uploaded_count': 0,
        'stats': {
            'award': {'valid': 0, 'invalid': 0},
            'patent': {'valid': 0, 'invalid': 0},
            'software': {'valid': 0, 'invalid': 0},
            'innovation': {'valid': 0, 'invalid': 0},
            'other': {'valid': 0, 'invalid': 0}
        },
        'errors': []
    })
    return jsonify(progress)


@bp.route('/achievement-submit/upload', methods=['POST'])
@require_user_type('teacher')
def achievement_submit_upload():
    """处理文件上传（教师版薄壳——共享逻辑在 user_common.shared_achievement_submit_upload，M2）"""
    from app.routes.user_common import shared_achievement_submit_upload
    from app.utils import get_app_context_instance
    app_context = get_app_context_instance()
    teacher_manager = app_context.get_teacher_manager()
    user_id = session.get('user_id')
    teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
    return shared_achievement_submit_upload(teacher, 'teacher', 'teacher')
@bp.route('/achievement-submit/manual/upload', methods=['POST'])
@require_user_type('teacher')
def achievement_submit_manual_upload():
    """手动导入：上传单个文件到临时目录，返回 file_path（与教师自动导入共用 results 流程）"""
    from app.routes.manual_import_helpers import handle_manual_upload
    ok, file_path, err = handle_manual_upload()
    if not ok:
        return jsonify({'success': False, 'message': err or '上传失败'}), 400 if err else 500
    return jsonify({'success': True, 'file_path': file_path})


@bp.route('/achievement-submit/manual/parse', methods=['POST'])
@require_user_type('teacher')
def achievement_submit_manual_parse():
    """手动导入：按指定类型解析文件，返回抽取结果（用于内联表单显示）"""
    try:
        from app.routes.manual_import_helpers import handle_manual_parse
        from app.utils import get_app_context_instance, get_doc_rec_context
        from backend.services.manual_import_service import ManualImportService
        from backend.extract.types import ExtractStatus
        from pathlib import Path
        from config.loader import get_config
        import hashlib
        import shutil
        from datetime import datetime
        from app.utils import calculate_file_hash
        from backend.services.unified_file_manager import get_unified_file_manager

        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id) if user_id else None
        if not teacher:
            return jsonify({'success': False, 'message': '教师信息不存在'}), 403

        # 获取请求参数
        data = request.get_json() or {}
        achievement_type = (data.get('achievement_type') or '').strip().lower()
        file_path = data.get('file_path')
        use_ocr_cache = data.get('use_ocr_cache', True)
        use_llm_cache = data.get('use_llm_cache', True)

        if not file_path:
            return jsonify({'success': False, 'message': '缺少 file_path'}), 400
        if achievement_type not in ('award', 'patent', 'software'):
            return jsonify({'success': False, 'message': f'不支持的成果类型: {achievement_type}'}), 400

        # 解析文件
        config_loader = get_config()
        base_temp_dir = config_loader.get_path("temp_dir")
        full_path = Path(base_temp_dir) / file_path if not Path(file_path).is_absolute() else Path(file_path)
        if not full_path.exists():
            return jsonify({'success': False, 'message': '文件不存在'}), 400

        framework = get_doc_rec_context().extract_framework
        service = ManualImportService(framework)
        result = service.parse_by_type(str(full_path), achievement_type, use_ocr_cache=use_ocr_cache, use_llm_cache=use_llm_cache)

        if not result or result.status != ExtractStatus.SUCCESS:
            return jsonify({
                'success': False,
                'message': getattr(result, 'error_message', None) or '解析失败'
            }), 400

        # 写入 pending
        pending_manager = app_context.get_pending_achievement_manager()
        session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()
        file_hash = calculate_file_hash(str(full_path)) or ''
        file_manager = get_unified_file_manager()
        target_dir = file_manager.files_root / 'temp_upload' / session_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / full_path.name
        shutil.copy2(str(full_path), str(target_path))
        path_for_db = f"temp_upload/{session_id}/{target_path.name}"

        if hasattr(pending_manager, 'create_from_extract_result'):
            result.metadata = result.metadata or {}
            result.metadata['session_id'] = session_id
            result.template_type = getattr(result, 'template_type', None) or achievement_type
            pending_manager.create_from_extract_result(
                result,
                submitter_type='teacher',
                submitter_id=teacher.id,
                file_path=path_for_db,
                file_hash=file_hash,
                status='pending'
            )

        # 生成 redirect_url（保留兼容性）
        redirect_url = url_for(
            'teacher.achievement_submit_results',
            session_id=session_id,
            tab=achievement_type,
            sub_tab='valid',
        )

        ocr_text = getattr(result, 'ocr_text', None) or ''
        achievement_data = result.data if hasattr(result, 'data') else {}

        # 计算学生和指导教师的状态列表（用于显示匹配状态和重名检测）
        winner_status_list = []
        supervisor_status_list = []

        if achievement_type == 'award':
            # 处理学生获奖者状态
            winner_name = achievement_data.get('winner_name', '')
            if winner_name:
                student_manager = app_context.get_student_manager()
                def _base_name(seg: str) -> str:
                    s = seg.strip()
                    if "(" in s:
                        return s.split("(")[0].strip()
                    return s
                raw_names = [n.strip() for n in winner_name.split(',') if n.strip()]
                seen_base = {}
                for n in raw_names:
                    b = _base_name(n)
                    if b not in seen_base:
                        seen_base[b] = b
                names = list(seen_base.values())
                for name in names:
                    matched_students = student_manager.find_students_by_name(name)
                    exact_matches = [s for s in matched_students if s.name.strip() == name.strip()]
                    if len(exact_matches) == 1:
                        winner_status_list.append({
                            'name': name,
                            'matched': True,
                            'obj': {'id': exact_matches[0].id, 'name': exact_matches[0].name, 'brief_desc': exact_matches[0].get_brief_desc()},
                            'ambiguous': False,
                            'not_found': False
                        })
                    elif len(exact_matches) > 1:
                        winner_status_list.append({
                            'name': name,
                            'matched': False,
                            'obj': None,
                            'ambiguous': True,
                            'not_found': False
                        })
                    else:
                        winner_status_list.append({
                            'name': name,
                            'matched': False,
                            'obj': None,
                            'ambiguous': False,
                            'not_found': True
                        })

            # 处理指导教师状态
            supervisor_name = achievement_data.get('supervisor_name', '')
            if supervisor_name:
                teacher_manager = app_context.get_teacher_manager()
                names = [n.strip() for n in supervisor_name.split(',') if n.strip()]
                for name in names:
                    matched_teachers = teacher_manager.find_teachers_by_name(name)
                    exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
                    if len(exact_matches) == 1:
                        supervisor_status_list.append({
                            'name': name,
                            'matched': True,
                            'obj': {'id': exact_matches[0].id, 'name': exact_matches[0].name},
                            'ambiguous': False,
                            'not_found': False
                        })
                    elif len(exact_matches) > 1:
                        supervisor_status_list.append({
                            'name': name,
                            'matched': False,
                            'obj': None,
                            'ambiguous': True,
                            'not_found': False
                        })
                    else:
                        supervisor_status_list.append({
                            'name': name,
                            'matched': False,
                            'obj': None,
                            'ambiguous': False,
                            'not_found': True
                        })

        return jsonify({
            'success': True,
            'redirect_url': redirect_url,  # 保留兼容性
            'data': achievement_data,
            'template_type': result.template_type,
            'session_id': session_id,
            'ocr_text': ocr_text,
            'file_path': path_for_db,
            'winner_status_list': winner_status_list,
            'supervisor_status_list': supervisor_status_list
        })
    except Exception as e:
        logger.exception("teacher manual parse failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/achievement-submit/results')
@require_user_type('teacher')
def achievement_submit_results():
    """文件导入结果处理页面（教师版本，复用管理员逻辑但使用不同路由）"""
    # 复用管理员的结果页面逻辑，但使用不同的路由前缀
    from app.routes.file_import_helpers import (
        get_file_import_params,
        calculate_type_stats,
        adjust_tab_and_status,
        query_pending_items,
        get_current_item,
        get_all_reference_data,
        process_award_item,
        process_validation_result,
        process_non_award_item,
        get_type_names,
    )
    
    try:
        # 获取参数
        result = get_file_import_params()
        if result[0] is None:
            return redirect(url_for('teacher.achievement_submit'))
        session_id, tab_type, status, index = result

        # 初始化管理器
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()
        laboratory_manager = app_context.get_laboratory_manager()

        # 类型名称映射
        type_names = get_type_names()
        
        # 计算类型统计
        type_stats = calculate_type_stats(session_id, pending_manager)
        
        # 调整tab和status
        tab_type, status, available_types = adjust_tab_and_status(tab_type, status, type_stats)
        
        # 查询pending items
        items, count = query_pending_items(tab_type, status, session_id, pending_manager)
        
        # 获取当前项
        current_item, index = get_current_item(items, count, index, tab_type, status, session_id)
        
        # 获取所有参考数据
        all_competitions, all_teachers, all_students, all_laboratories = get_all_reference_data(
            competition_manager, teacher_manager, student_manager, laboratory_manager)

        # 教师端：关联实验室仅限当前教师所属实验室，且唯一选项
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id) if user_id else None
        if teacher and laboratory_manager:
            teacher_lab = laboratory_manager.get_laboratory_by_teacher_id(teacher.id)
            if teacher_lab:
                all_laboratories = [teacher_lab]

        # 处理当前项（复用管理员逻辑）
        if current_item and tab_type == 'award':
            award_data = process_award_item(
                current_item, app_context, all_competitions, 
                all_teachers, all_students, all_laboratories
            )
            
            validation_result = current_item.get_validation_result()
            field_errors, is_valid = process_validation_result(validation_result)
            
            data = current_item.get_achievement_data()
            file_path = data.get('file_path') if isinstance(data, dict) else None
            file_url = url_for('teacher.achievement_submit_file', file_path=file_path.replace('\\', '/')) if file_path else None
            preview_image_path = award_data.get('preview_image_path')
            if not preview_image_path and file_path and file_path.lower().endswith('.pdf'):
                from pathlib import Path
                from backend.services.unified_file_manager import get_unified_file_manager
                from backend.utils.pdf_to_image import get_or_create_pdf_preview
                file_manager = get_unified_file_manager()
                full_path = file_manager.files_root / file_path.replace('\\', '/')
                if full_path.exists():
                    preview_dir = full_path.parent / 'preview'
                    preview_dir.mkdir(parents=True, exist_ok=True)
                    preview_path = get_or_create_pdf_preview(str(full_path), preview_dir)
                    if preview_path:
                        try:
                            preview_relative = Path(preview_path).relative_to(file_manager.files_root)
                            preview_image_path = str(preview_relative).replace('\\', '/')
                        except ValueError:
                            preview_image_path = None
            preview_image_url = url_for('teacher.achievement_submit_file', file_path=preview_image_path.replace('\\', '/')) if preview_image_path else None

            return render_template('admin/file_import/results.html',
                                  session_id=session_id,
                                  tab_type=tab_type,
                                  status=status,
                                  current_index=index,
                                  count=count,
                                  type_names=type_names,
                                  type_stats=type_stats,
                                  available_types=available_types,
                                  current_item=current_item,
                                  award=award_data['temp_award'],
                                  competitions=award_data['competitions'],
                                  all_teachers=all_teachers,
                                  all_students=all_students,
                                  all_laboratories=all_laboratories,
                                  winner_status_list=award_data['winner_status_list'],
                                  supervisor_status_list=award_data['supervisor_status_list'],
                                  matched_teacher_ids=award_data['matched_teacher_ids'],
                                  file_path=file_path,
                                  file_url=file_url,
                                  preview_image_url=preview_image_url,
                                  field_errors=field_errors,
                                  is_valid=is_valid,
                                  route_prefix='teacher',
                                  missing_competition_name=award_data.get('missing_competition_name'))
        else:
            # 对于非奖状类型，file_path 和 file_url 已经在 non_award_data 中
            non_award_data = process_non_award_item(
                current_item, tab_type, all_laboratories
            )

            validation_result = current_item.get_validation_result() if current_item else {}
            field_errors, is_valid = process_validation_result(validation_result)

            # 由于 non_award_data 中使用了 admin 路由，需要覆盖 file_url
            data = current_item.get_achievement_data() if current_item else {}
            file_path = data.get('file_path') if isinstance(data, dict) else None
            if file_path:
                file_url = url_for('teacher.achievement_submit_file', file_path=file_path.replace('\\', '/'))
                non_award_data['file_url'] = file_url

            return render_template('admin/file_import/results.html',
                                  session_id=session_id,
                                  tab_type=tab_type,
                                  status=status,
                                  current_index=index,
                                  count=count,
                                  type_names=type_names,
                                  type_stats=type_stats,
                                  available_types=available_types,
                                  current_item=current_item,
                                  field_errors=field_errors,
                                  is_valid=is_valid,
                                  route_prefix='teacher',
                                  all_laboratories=all_laboratories,
                                  **non_award_data)

    except Exception as e:
        logger.error(f"加载文件导入结果失败: {e}", exc_info=True)
        flash(f'加载结果失败: {str(e)}', 'error')
        return redirect(url_for('teacher.achievement_submit'))


@bp.route('/achievement-submit/award-submit/<session_id>/<int:index>', methods=['POST'])
@require_user_type('teacher')
def file_import_award_submit(session_id, index):
    """教师端：提交奖状后跳转到下一项或返回成果提交页。与 admin 逻辑一致，但使用 teacher 身份并重定向到教师端。"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()
        student_manager = app_context.get_student_manager()

        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id) if user_id else None
        if not teacher:
            flash('教师信息不存在', 'error')
            return redirect(url_for('teacher.achievement_submit'))

        tab_type = request.form.get('tab_type', 'award')
        status = request.form.get('status', 'valid')
        pending_id_raw = request.form.get('pending_id')
        try:
            pending_id = int(pending_id_raw) if pending_id_raw else None
        except (ValueError, TypeError):
            pending_id = None

        def _redirect_results(**kwargs):
            return redirect(url_for('teacher.achievement_submit_results', session_id=session_id, **kwargs))

        if pending_id is None:
            flash('缺少待提交记录标识', 'error')
            return _redirect_results(tab=tab_type, sub_tab=status)

        current_item = pending_manager.get_by_id(pending_id)
        if not current_item:
            flash('记录不存在', 'error')
            return _redirect_results(tab=tab_type, sub_tab=status)
        item_session_id = current_item.get_achievement_data().get('import_session_id')
        if item_session_id != session_id or current_item.achievement_type != tab_type:
            flash('记录与当前导入会话或类型不一致', 'error')
            return _redirect_results(tab=tab_type, sub_tab=status)
        if current_item.status != 'pending':
            flash('该记录已提交或已处理', 'error')
            return _redirect_results(tab=tab_type, sub_tab=status)
        item_id = current_item.id
        data = current_item.get_achievement_data()

        form_data = {}
        for key in request.form:
            if key not in ('tab_type', 'status', 'pending_id'):
                form_data[key] = request.form.get(key)

        related_student_ids = request.form.getlist('related_student_ids[]')
        if related_student_ids:
            related_student_names = []
            for sid in related_student_ids:
                if sid:
                    try:
                        s = student_manager.get_student_by_id(int(sid))
                        if s:
                            related_student_names.append(s.name)
                    except (ValueError, TypeError):
                        pass
            form_data['related_student_name'] = ', '.join(related_student_names) if related_student_names else ''
        else:
            form_data['related_student_name'] = ''

        if form_data:
            data.update(form_data)
            # 未选具体竞赛时用解析出的竞赛名，后端将自动创建竞赛
            if not (data.get('competition_name') or '').strip() and (data.get('original_competition_name') or '').strip():
                data['competition_name'] = (data.get('original_competition_name') or '').strip()
            pending_manager.update(
                pending_item=current_item,
                achievement_data=data,
                status=current_item.status
            )

        review_service = _get_review_service(app_context)
        result = review_service.submit_achievement(current_item.id, 'teacher', teacher.id)
        if result.action == 'auto_archive_started':
            flash('已提交，系统将自动归档', 'success')
        else:
            flash('提交成功，等待审核', 'success')

        from backend.models.pending_achievement import PendingAchievementFilter

        filter_remaining = PendingAchievementFilter(
            achievement_type=tab_type,
            status='pending',
            import_session_id=session_id,
            limit=1000
        )
        items_after = pending_manager.query_pending(filter_remaining)
        remaining_items = [item for item in items_after if item.status != 'submit']

        if remaining_items:
            return _redirect_results(tab=tab_type, sub_tab=status, index=0)
        else:
            all_empty = True
            for t in get_data_import_types():
                filter_check = PendingAchievementFilter(
                    achievement_type=t,
                    status='pending',
                    import_session_id=session_id,
                    limit=1000
                )
                check_items = pending_manager.query_pending(filter_check)
                check_items = [item for item in check_items if item.status != 'submit']
                if check_items:
                    all_empty = False
                    break
            if all_empty:
                flash('所有记录已提交，请等待审核', 'success')
                return redirect(url_for('teacher.achievement_submit'))
            else:
                return _redirect_results(tab=tab_type, sub_tab=status)

    except Exception as e:
        logger.error(f"提交奖状失败: {e}", exc_info=True)
        flash(f'提交失败: {str(e)}', 'error')
        _tab = request.form.get('tab_type', 'award')
        _sub = request.form.get('status', 'valid')
        return redirect(url_for('teacher.achievement_submit_results', session_id=session_id, tab=_tab, sub_tab=_sub, index=index))


@bp.route('/achievement-submit/manual/submit', methods=['POST'])
@require_user_type('teacher')
def achievement_submit_manual_submit():
    """手动导入：更新 pending 记录并提交（教师自动归档）"""
    try:
        data = request.get_json() or {}
        achievement_type = (data.get('achievement_type') or '').strip().lower()
        achievement_data = data.get('achievement_data')
        submitter_type = data.get('submitter_type', 'teacher')
        session_id = data.get('session_id')

        if not achievement_type:
            return jsonify({'success': False, 'message': '缺少 achievement_type'}), 400
        if achievement_data is None:
            return jsonify({'success': False, 'message': '缺少 achievement_data'}), 400
        if not session_id:
            return jsonify({'success': False, 'message': '缺少 session_id'}), 400

        # 获取 app_context
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()

        # 通过 session_id 查找记录
        from backend.models.pending_achievement import PendingAchievementFilter
        filter_obj = PendingAchievementFilter(session_id=session_id)
        pending_list = pending_manager.query_pending(filter_obj)

        if not pending_list:
            return jsonify({'success': False, 'message': '未找到对应的记录'}), 404

        pending_item = pending_list[0]

        # 如果记录已经是 submit 状态，说明已经提交过了
        if pending_item.status == 'submit':
            # 检查是否已归档
            if hasattr(pending_item, 'review_status') and pending_item.review_status == 'archived':
                return jsonify({
                    'success': True,
                    'message': '该记录已归档',
                    'pending_id': pending_item.id,
                    'already_submitted': True,
                    'already_archived': True
                })
            return jsonify({
                'success': True,
                'message': '该记录已经提交过了',
                'pending_id': pending_item.id,
                'already_submitted': True
            })

        # 先更新 pending 记录的数据
        success = pending_manager.update(
            pending_item=pending_item,
            achievement_type=achievement_type,
            achievement_data=achievement_data
        )

        if not success:
            return jsonify({'success': False, 'message': '更新 pending 记录失败'}), 500

        # 调用 review_service.submit_achievement 提交（教师会自动归档）
        from backend.services.review_service import ReviewService
        teacher_manager = app_context.get_teacher_manager()
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id) if user_id else None
        teacher_id = teacher.id if teacher else 0

        review_service = ReviewService(
            pending_manager=pending_manager,
            review_log_manager=app_context.get_review_log_manager(),
            award_manager=app_context.get_award_manager(),
            patent_manager=app_context.get_patent_manager(),
            software_manager=app_context.get_software_copyright_manager(),
            innovation_manager=app_context.get_innovation_project_manager(),
            other_file_manager=app_context.get_other_file_manager(),
            laboratory_manager=app_context.get_laboratory_manager(),
            student_manager=app_context.get_student_manager(),
            teacher_manager=teacher_manager,
            competition_manager=app_context.get_competition_manager(),
            auto_archive_config_manager=app_context.get_auto_archive_config_manager()
        )
        result = review_service.submit_achievement(pending_item.id, submitter_type, teacher_id)

        if not result.success:
            return jsonify({'success': False, 'message': result.error or '提交失败'}), 500

        # 根据返回的 action 确定提示消息
        if result.action == 'approved':
            message = '已归档，数据已成功导入主数据库'
        elif result.action == 'auto_archive_started':
            message = '已提交，系统将自动归档'
        else:
            message = '提交成功，等待审核'

        logger.info(f"[教师手动导入提交] pending_id={pending_item.id}, session_id={session_id}, 类型={achievement_type}, action={result.action}")

        return jsonify({
            'success': True,
            'message': message,
            'pending_id': pending_item.id,
            'action': result.action
        })
    except Exception as e:
        logger.exception("teacher manual submit failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/achievement-submit/file/<path:file_path>')
@require_user_type('teacher')
def achievement_submit_file(file_path):
    """提供文件导入中的文件访问（教师版本）。路径为相对路径 temp_upload/... 或历史绝对路径，便于跨服务器部署。"""
    try:
        from flask import send_file
        from pathlib import Path
        from backend.services.unified_file_manager import get_unified_file_manager

        path_str = file_path.strip().replace('\\', '/')
        file_manager = get_unified_file_manager()
        files_root = file_manager.files_root.resolve()
        temp_upload_prefix = (files_root / 'temp_upload').resolve()

        if path_str.startswith('temp_upload/') or path_str.startswith('temp_upload'):
            full_path = (files_root / path_str).resolve()
            allowed_prefix = temp_upload_prefix
        elif path_str.startswith('/') or (len(path_str) > 1 and path_str[1] == ':'):
            full_path = Path(path_str).resolve()
            try:
                full_path.relative_to(temp_upload_prefix)
                allowed_prefix = temp_upload_prefix
            except ValueError:
                from flask import abort
                abort(403)
        else:
            from config.loader import get_config
            base_temp_dir = get_config().get_path("temp_dir")
            base_dir = Path(base_temp_dir)
            full_path = (base_dir / path_str).resolve()
            allowed_prefix = base_dir.resolve()

        try:
            full_path.relative_to(allowed_prefix)
        except ValueError:
            from flask import abort
            abort(403)
        
        if not full_path.exists() or not full_path.is_file():
            from flask import abort
            abort(404)
        
        # 根据文件扩展名设置MIME类型
        ext = full_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.jfif': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel'
        }
        mimetype = mime_types.get(ext, 'application/octet-stream')
        
        # 对于下载类型的文件，设置为附件下载
        download_extensions = ['.xlsx', '.xls']
        if ext in download_extensions:
            return send_file(str(full_path), mimetype=mimetype, as_attachment=True, 
                           download_name=full_path.name)
        
        return send_file(str(full_path), mimetype=mimetype)

    except Exception as e:
        logger.error(f"文件访问失败: {e}", exc_info=True)
        from flask import abort
        abort(404)


# ==================== 成果审核相关路由 ====================

@bp.route('/achievement-review')
@require_user_type('teacher')
def achievement_review_list():
    """待审核成果列表 - 重定向到单页式审核界面"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()
        
        # 获取当前教师信息
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            flash('教师信息不存在', 'error')
            return redirect(url_for('teacher.dashboard'))
        
        # 获取教师可审核的记录
        teacher_pendings = pending_manager.get_pending_for_teacher(
            teacher.id,
            teacher_manager=teacher_manager,
            teacher_name=teacher.name
        )

        # 无内容时直接显示空状态，不跳转
        if not teacher_pendings:
            from app.routes.file_import_helpers import get_type_names
            return render_template(
                'admin/file_import/results.html',
                session_id=None,
                route_prefix='teacher_review',
                available_types=[],
                type_names=get_type_names(),
                title_prefix='成果审核',
            )

        # 统计各类型数量
        type_stats = {}
        for pending in teacher_pendings:
            t = pending.achievement_type
            if t not in type_stats:
                type_stats[t] = {'total': 0}
            type_stats[t]['total'] += 1

        # 找到第一个有数据的类型
        first_type = 'award'
        for type_key in ['award', 'patent', 'software', 'innovation', 'other']:
            if type_stats.get(type_key, {}).get('total', 0) > 0:
                first_type = type_key
                break

        # 有内容时重定向到单页式审核
        return redirect(url_for('teacher.achievement_review_single',
                               type=first_type, sub_tab='valid', index=0))
    
    except Exception as e:
        logger.error(f"Error loading review list: {e}", exc_info=True)
        flash(f'加载待审核列表失败: {e}', 'error')
        return redirect(url_for('teacher.dashboard'))


@bp.route('/achievement-review/<type>/<sub_tab>/<int:index>')
@require_user_type('teacher')
def achievement_review_single(type, sub_tab, index):
    """
    单页式审核页面 - 成果审核（只显示教师可以审核的记录）
    """
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()
        
        # 获取当前教师信息
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            flash('教师信息不存在', 'error')
            return redirect(url_for('teacher.dashboard'))
        
        # 获取教师可审核的记录
        teacher_pendings = pending_manager.get_pending_for_teacher(
            teacher.id,
            teacher_manager=teacher_manager,
            teacher_name=teacher.name
        )
        
        # 由于 render_review_page 不支持自定义数据源，我们需要手动过滤和渲染
        # 复用管理员的结果页面逻辑，但使用过滤后的数据
        from app.routes.file_import_helpers import (
            get_current_item,
            get_all_reference_data,
            process_award_item,
            process_validation_result,
            process_non_award_item,
            get_type_names,
        )
        from backend.models.pending_achievement import PendingAchievementFilter
        from backend.services.review_service import IMAGE_EXTENSIONS
        from pathlib import Path
        
        type_names = get_type_names()
        
        # 从教师可审核的记录中过滤出当前类型和状态的记录
        filtered_by_type = [p for p in teacher_pendings if p.achievement_type == type]
        
        # 根据状态进一步过滤
        if type == 'other':
            # other 类型：按图片/文件分类
            items = []
            for item in filtered_by_type:
                file_path = item.file_path if hasattr(item, 'file_path') else None
                if file_path:
                    ext = Path(file_path).suffix.lower()
                    is_image = ext in IMAGE_EXTENSIONS
                    if sub_tab == 'image' and is_image:
                        items.append(item)
                    elif sub_tab == 'file' and not is_image:
                        items.append(item)
        else:
            # 其他类型：按验证结果分类
            if sub_tab == 'valid':
                items = [item for item in filtered_by_type if item.validation_passed()]
            else:
                items = [item for item in filtered_by_type if not item.validation_passed()]
        
        count = len(items)
        
        # 计算类型统计（基于过滤后的记录）
        type_stats = {}
        for t in ['award', 'patent', 'software', 'innovation', 'other']:
            type_pendings = [p for p in teacher_pendings if p.achievement_type == t]
            if t == 'other':
                image_count = sum(1 for p in type_pendings if p.file_path and Path(p.file_path).suffix.lower() in IMAGE_EXTENSIONS)
                file_count = len(type_pendings) - image_count
                type_stats[t] = {
                    'total': len(type_pendings),
                    'image': image_count,
                    'file': file_count
                }
            elif t == 'innovation':
                type_stats[t] = {'total': len(type_pendings)}
            else:
                valid_count = sum(1 for p in type_pendings if p.validation_passed())
                invalid_count = len(type_pendings) - valid_count
                type_stats[t] = {
                    'total': len(type_pendings),
                    'valid': valid_count,
                    'invalid': invalid_count
                }
        
        # 调整tab和status
        available_types = [t for t in ['award', 'patent', 'software', 'innovation', 'other'] 
                          if type_stats.get(t, {}).get('total', 0) > 0]
        if type not in available_types and available_types:
            type = available_types[0]
            if type == 'other':
                sub_tab = 'image' if type_stats['other'].get('image', 0) > 0 else 'file'
            else:
                sub_tab = 'valid' if type_stats[type].get('valid', 0) > 0 else 'invalid'
            # 重新过滤
            filtered_by_type = [p for p in teacher_pendings if p.achievement_type == type]
            if type == 'other':
                items = []
                for item in filtered_by_type:
                    file_path = item.file_path if hasattr(item, 'file_path') else None
                    if file_path:
                        ext = Path(file_path).suffix.lower()
                        is_image = ext in IMAGE_EXTENSIONS
                        if sub_tab == 'image' and is_image:
                            items.append(item)
                        elif sub_tab == 'file' and not is_image:
                            items.append(item)
            else:
                if sub_tab == 'valid':
                    items = [item for item in filtered_by_type if item.validation_passed()]
                else:
                    items = [item for item in filtered_by_type if not item.validation_passed()]
            count = len(items)
        
        # 当前 Tab 的 pending ID 列表（「全部提交」批量审核时使用）
        current_tab_pending_ids = [item.id for item in items]
        if type == 'innovation':
            submit_display_count = sum(
                len((item.get_achievement_data() or {}).get('projects') or [])
                for item in items
            )
        else:
            submit_display_count = count

        # 获取当前项
        current_item, index = get_current_item(items, count, index, type, sub_tab, None)
        
        # 获取所有参考数据
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        laboratory_manager = app_context.get_laboratory_manager()
        all_competitions, all_teachers, all_students, all_laboratories = get_all_reference_data(
            competition_manager, teacher_manager, student_manager, laboratory_manager)

        # 处理当前项
        if current_item and type == 'award':
            award_data = process_award_item(
                current_item, app_context, all_competitions, 
                all_teachers, all_students, all_laboratories
            )
            
            validation_result = current_item.get_validation_result()
            field_errors, is_valid = process_validation_result(validation_result)
            
            # 与管理员端一致：file_path 从 pending 记录取（学生手工提交等场景下 achievement_data 可能无 file_path）
            data = current_item.get_achievement_data() or {}
            file_path = current_item.get_file_path()
            file_url = url_for('teacher.achievement_review_file', file_path=file_path.replace('\\', '/')) if file_path else None
            preview_image_path = data.get('preview_image_path') if isinstance(data, dict) else None
            preview_image_url = url_for('teacher.achievement_review_file', file_path=preview_image_path.replace('\\', '/')) if preview_image_path else None
            
            return render_template('admin/file_import/results.html',
                                  session_id=None,
                                  tab_type=type,
                                  status=sub_tab,
                                  current_index=index,
                                  count=count,
                                  type_names=type_names,
                                  type_stats=type_stats,
                                  available_types=available_types,
                                  current_item=current_item,
                                  current_tab_pending_ids=current_tab_pending_ids,
                                  submit_display_count=submit_display_count,
                                  award=award_data['temp_award'],
                                  competitions=award_data['competitions'],
                                  all_teachers=all_teachers,
                                  all_students=all_students,
                                  all_laboratories=all_laboratories,
                                  winner_status_list=award_data['winner_status_list'],
                                  supervisor_status_list=award_data['supervisor_status_list'],
                                  matched_teacher_ids=award_data['matched_teacher_ids'],
                                  file_path=file_path,
                                  file_url=file_url,
                                  preview_image_url=preview_image_url,
                                  field_errors=field_errors,
                                  is_valid=is_valid,
                                  route_prefix='teacher_review',
                                  missing_competition_name=award_data.get('missing_competition_name'))
        else:
            # 对于非奖状类型，file_path 和 file_url 已经在 non_award_data 中
            non_award_data = process_non_award_item(
                current_item, type, all_laboratories
            )

            validation_result = current_item.get_validation_result() if current_item else {}
            field_errors, is_valid = process_validation_result(validation_result)

            # 由于 non_award_data 中使用了 admin 路由，需要覆盖 file_url
            data = current_item.get_achievement_data() if current_item else {}
            file_path = data.get('file_path') if isinstance(data, dict) else None
            if file_path:
                file_url = url_for('teacher.achievement_review_file', file_path=file_path.replace('\\', '/'))
                non_award_data['file_url'] = file_url

            return render_template('admin/file_import/results.html',
                                  session_id=None,
                                  tab_type=type,
                                  status=sub_tab,
                                  current_index=index,
                                  count=count,
                                  type_names=type_names,
                                  type_stats=type_stats,
                                  available_types=available_types,
                                  current_item=current_item,
                                  current_tab_pending_ids=current_tab_pending_ids,
                                  submit_display_count=submit_display_count,
                                  field_errors=field_errors,
                                  is_valid=is_valid,
                                  route_prefix='teacher_review',
                                  **non_award_data)

    except Exception as e:
        logger.error(f"加载成果审核页面失败: {e}", exc_info=True)
        flash(f'加载审核页面失败: {str(e)}', 'error')
        return redirect(url_for('teacher.dashboard'))


@bp.route('/achievement-review/file/<path:file_path>')
@require_user_type('teacher')
def achievement_review_file(file_path):
    """提供成果审核中的文件访问（教师版本）"""
    try:
        from flask import send_file
        from pathlib import Path
        
        # 安全检查：确保文件路径在文件目录下
        from backend.services.unified_file_manager import get_unified_file_manager
        file_manager = get_unified_file_manager()
        files_root = file_manager.files_root
        
        # 构建完整路径
        full_path = Path(files_root) / file_path
        
        # 安全检查：确保文件在文件目录下
        try:
            resolved_full_path = full_path.resolve()
            resolved_files_root = Path(files_root).resolve()
            resolved_full_path.relative_to(resolved_files_root)
        except ValueError:
            from flask import abort
            abort(403)
        
        if not full_path.exists() or not full_path.is_file():
            from flask import abort
            abort(404)
        
        # 根据文件扩展名设置MIME类型
        ext = full_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.jfif': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel'
        }
        mimetype = mime_types.get(ext, 'application/octet-stream')
        
        return send_file(str(full_path), mimetype=mimetype)

    except Exception as e:
        logger.error(f"文件访问失败: {e}", exc_info=True)
        from flask import abort
        abort(404)


@bp.route('/achievement-submit/withdraw/<int:pending_id>', methods=['POST'])
@require_user_type('teacher')
def withdraw_submission(pending_id):
    """教师撤回已提交记录（submit→pending），重新编辑。"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id) if user_id else None
        pending = pending_manager.get_by_id(pending_id) if pending_id else None
        if not pending or not teacher:
            flash('记录不存在', 'error')
            return redirect(url_for('teacher.dashboard'))
        if not (pending.submitter_type == 'teacher' and pending.submitter_id == teacher.id):
            flash('无权操作该记录', 'error')
            return redirect(url_for('teacher.dashboard'))
        if pending.status != 'submit':
            flash('仅"等待审核"的记录可撤回', 'error')
            return redirect(url_for('teacher.dashboard'))
        session_id = getattr(pending, 'session_id', None) or (pending.get_achievement_data() or {}).get('import_session_id')
        tab_type = pending.achievement_type or 'award'
        pending_manager.update(pending, status='pending')
        # P1-13 留痕：动作11=撤回
        try:
            from backend.utils.audit_logger import audit_log
            audit_log(11, pending_id, pending.achievement_type,
                      operator={"id": teacher.id, "code": str(teacher.teacher_id), "user_type": "teacher"})
        except Exception:
            pass
        flash('已撤回，可重新编辑并提交', 'success')
        return redirect(url_for('teacher.achievement_submit_results', session_id=session_id, tab=tab_type))
    except Exception as e:
        logger.error(f"撤回提交失败: {e}", exc_info=True)
        flash(f'撤回失败: {str(e)}', 'error')
        return redirect(url_for('teacher.dashboard'))


@bp.route('/api/competitions')
@require_user_type('teacher')
def api_competitions():
    """获取所有竞赛列表API"""
    try:
        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()

        if hasattr(competition_manager, 'competitions'):
            competitions = competition_manager.competitions
        elif hasattr(competition_manager, '_competitions'):
            competitions = competition_manager._competitions
        else:
            competitions = []

        results = []
        for comp in competitions:
            results.append({
                'id': comp.id,
                'name': comp.name
            })

        return jsonify({'success': True, 'competitions': results})
    except Exception as e:
        logger.error(f"获取竞赛列表失败: {e}")
        return jsonify({'success': False, 'competitions': [], 'error': str(e)}), 500


@bp.route('/api/teachers')
@require_user_type('teacher')
def api_teachers():
    """获取所有教师列表API（包含实验室信息用于前端自动关联）"""
    try:
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        laboratory_manager = app_context.get_laboratory_manager()

        if hasattr(teacher_manager, 'teachers'):
            teachers = teacher_manager.teachers
        elif hasattr(teacher_manager, '_teachers'):
            teachers = teacher_manager._teachers
        else:
            teachers = []

        # 获取每个教师所属的实验室信息（用于前端自动关联）
        teacher_lab_map = {}
        if laboratory_manager:
            for teacher in teachers:
                lab = laboratory_manager.get_laboratory_by_teacher_id(teacher.id)
                if lab:
                    teacher_lab_map[teacher.id] = lab.id

        results = []
        for teacher in teachers:
            results.append({
                'id': teacher.id,
                'teacher_id': teacher.teacher_id,
                'name': teacher.name,
                'laboratory_id': teacher_lab_map.get(teacher.id)
            })

        return jsonify({'success': True, 'teachers': results})
    except Exception as e:
        logger.error(f"获取教师列表失败: {e}")
        return jsonify({'success': False, 'teachers': [], 'error': str(e)}), 500


@bp.route('/api/laboratories')
@require_user_type('teacher')
def api_laboratories():
    """获取所有实验室列表API"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        if hasattr(laboratory_manager, 'get_all_laboratories'):
            laboratories = laboratory_manager.get_all_laboratories()
        elif hasattr(laboratory_manager, 'laboratories'):
            laboratories = laboratory_manager.laboratories
        elif hasattr(laboratory_manager, '_laboratories'):
            laboratories = laboratory_manager._laboratories
        else:
            laboratories = []

        results = []
        for lab in laboratories:
            results.append({
                'id': lab.id,
                'name': lab.name
            })

        return jsonify({'success': True, 'laboratories': results})
    except Exception as e:
        logger.error(f"获取实验室列表失败: {e}")
        return jsonify({'success': False, 'laboratories': [], 'error': str(e)}), 500


@bp.route('/api/students/search')
@require_user_type('teacher')
def api_students_search():
    """学生搜索API"""
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify({'success': True, 'students': []})

    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()

        students = student_manager.find_students_by_name(query)

        results = []
        for student in students[:10]:
            brief_parts = []
            if student.student_id:
                brief_parts.append(student.student_id)
            if student.major:
                brief_parts.append(student.major)
            if student.grade:
                brief_parts.append(student.grade)
            brief_desc = ' | '.join(brief_parts) if brief_parts else ''

            results.append({
                'id': student.id,
                'student_id': student.student_id,
                'name': student.name,
                'major': student.major,
                'grade': student.grade,
                'brief_desc': brief_desc,
                'display': f"({student.student_id})" if student.student_id else ''
            })

        return jsonify({'success': True, 'students': results})
    except Exception as e:
        logger.error(f"学生搜索失败: {e}")
        return jsonify({'success': False, 'students': [], 'error': str(e)}), 500


@bp.route('/file-preview/<path:file_path>')
@require_user_type('teacher')
def file_preview(file_path):
    """提供文件预览功能。PDF 请求时返回第一页预览图供 <img> 显示。"""
    try:
        from flask import send_file
        from pathlib import Path
        from urllib.parse import unquote
        from backend.services.unified_file_manager import get_unified_file_manager

        path_str = unquote(file_path).strip().replace('\\', '/')
        file_manager = get_unified_file_manager()
        files_root = file_manager.files_root.resolve()
        temp_upload_prefix = (files_root / 'temp_upload').resolve()

        full_path = None
        is_absolute = path_str.startswith('/') or (len(path_str) > 1 and path_str[1] == ':')

        if is_absolute:
            full_path = Path(path_str).resolve()
            try:
                full_path.relative_to(temp_upload_prefix)
            except ValueError:
                logger.warning(f"绝对路径不在 temp_upload 下: {full_path}")
                from flask import abort
                abort(403)
        elif path_str.startswith('temp_upload/') or path_str.startswith('temp_upload\\'):
            full_path = (files_root / path_str).resolve()
        elif path_str.startswith('manual_import/') or path_str.startswith('manual_import\\'):
            # 手动导入的文件存储在 temp_upload/manual_import/ 下
            full_path = (files_root / 'temp_upload' / path_str).resolve()

        if full_path is None or not full_path.exists() or not full_path.is_file():
            logger.warning(f"文件不存在: {full_path}")
            from flask import abort
            abort(404)

        # PDF 时返回第一页预览图，供 <img> 显示
        if full_path.suffix.lower() == '.pdf':
            preview_dir = full_path.parent / 'preview'
            preview_path = preview_dir / f"{full_path.stem}.png"
            if preview_path.exists():
                return send_file(str(preview_path), mimetype='image/png')
            try:
                from backend.utils.pdf_to_image import get_or_create_pdf_preview
                created = get_or_create_pdf_preview(str(full_path), preview_dir)
                if created and Path(created).exists():
                    return send_file(created, mimetype='image/png')
            except Exception as e:
                logger.warning("教师 file_preview PDF 预览图生成失败: %s", e)
            return send_file(str(full_path), mimetype='application/pdf')

        return send_file(str(full_path))
    except Exception as e:
        logger.error(f"文件访问失败: {e}", exc_info=True)
        from flask import abort
        abort(404)


@bp.route('/api/achievement-review/<int:pending_id>/approve-with-data', methods=['POST'])
@require_user_type('teacher')
def api_achievement_review_approve_with_data(pending_id):
    """
    审核通过单条记录（JSON API），教师版本
    """
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()
        
        # 获取当前教师信息
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            return jsonify({'success': False, 'message': '教师信息不存在'}), 400
        
        # 验证教师是否有权限审核此记录
        teacher_pendings = pending_manager.get_pending_for_teacher(
            teacher.id,
            teacher_manager=teacher_manager,
            teacher_name=teacher.name
        )
        pending_ids = [p.id for p in teacher_pendings]
        if pending_id not in pending_ids:
            return jsonify({'success': False, 'message': '无权审核此记录'}), 403
        
        payload = request.get_json() or {}
        modified_data = payload.get('data') or {}

        pending = pending_manager.get_pending_by_id(pending_id)
        if not pending:
            return jsonify({'success': False, 'message': '记录不存在'}), 404

        if modified_data:
            from app.routes.review_helpers import normalize_laboratory_id, normalize_related_student_from_ids
            if pending.achievement_type == 'award':
                normalize_related_student_from_ids(modified_data, app_context.get_student_manager())
            current = pending.get_achievement_data()
            if isinstance(current, dict):
                current = dict(current)
                current.update(modified_data)
                current['laboratory_id'] = normalize_laboratory_id(current.get('laboratory_id'))
                # 未选具体竞赛时用解析出的竞赛名，后端将自动创建竞赛
                if not (current.get('competition_name') or '').strip() and (current.get('original_competition_name') or '').strip():
                    current['competition_name'] = (current.get('original_competition_name') or '').strip()

                # 重新计算验证结果
                achievement_type = pending.achievement_type or 'award'
                from app.routes.admin_achievement import _get_full_validation_result
                import json
                new_validation_result = _get_full_validation_result(achievement_type, current, app_context)
                new_validation_json = json.dumps(new_validation_result, ensure_ascii=False)

                # 同时更新 achievement_data 和 validation_result
                pending_manager.update(
                    pending_item=pending,
                    achievement_data=current,
                    validation_result=new_validation_json,
                    status=pending.status
                )
                pending = pending_manager.get_pending_by_id(pending_id)

        lab_id = None
        if isinstance(modified_data, dict) and modified_data.get('laboratory_id') is not None:
            from app.routes.review_helpers import normalize_laboratory_id
            lab_id = normalize_laboratory_id(modified_data['laboratory_id'])

        from backend.services.review_service import ReviewService, Reviewer
        from app.routes.admin_review import _get_review_service
        review_service = _get_review_service(app_context)
        reviewer_id = session.get('user_id')
        reviewer = Reviewer(reviewer_type='teacher', reviewer_id=reviewer_id)
        result = review_service.approve_single(
            pending_id, reviewer, lab_id=lab_id or None, force=True
        )

        if result.success:
            return jsonify({
                'success': True,
                'message': '审核通过，成果已入库',
                'target_id': result.target_id,
                'target_table': result.target_table,
            })
        return jsonify({
            'success': False,
            'message': result.error or '审核失败',
        }), 400

    except Exception as e:
        logger.error(f"api_achievement_review_approve_with_data 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/achievement-review/<int:pending_id>/reject', methods=['POST'])
@require_user_type('teacher')
def api_achievement_review_reject(pending_id):
    """驳回打回（FR-APPROVE-07）：submit→rejected，提交人可见原因并修改后重交。

    越权防护：仅可驳回 get_pending_for_teacher 范围内的记录（同 approve 路由）。
    """
    try:
        data = request.get_json(silent=True) or {}
        reason = (data.get('reason') or '').strip()
        if not reason:
            return jsonify({'success': False, 'message': '请填写驳回原因'}), 400

        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()

        teacher = None
        user_id = session.get('user_id')
        try:
            teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        except Exception:
            pass

        # 越权校验：该记录必须在教师可审范围内
        allowed_ids = [p.id for p in pending_manager.get_pending_for_teacher(
            teacher.id if teacher else 0, teacher_manager=teacher_manager,
            teacher_name=teacher.name if teacher else None)]
        if pending_id not in allowed_ids:
            return jsonify({'success': False, 'message': '无权操作该记录'}), 403

        reviewer_id = session.get('user_id')
        if pending_manager.reject(pending_id, 'teacher', reviewer_id, reason):
            from backend.utils.audit_logger import audit_log
            audit_log(7, pending_id, None, operator={"id": reviewer_id, "code": str(reviewer_id), "user_type": "teacher"},
                      action_result=2, remark=reason[:200])
            return jsonify({'success': True, 'message': '已驳回，提交人可查看原因并修改后重新提交'})
        return jsonify({'success': False, 'message': '驳回失败：记录不存在或状态已变化'}), 409
    except Exception as e:
        logger.error(f"api_achievement_review_reject 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/achievement-review/batch-approve', methods=['POST'])
@require_user_type('teacher')
@idempotent(ttl=600)
def api_achievement_review_batch_approve():
    """批量审核通过（AJAX）- 教师版本（幂等：同 Idempotency-Key 10 分钟窗口复用结果，防双击重复入库）"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()
        
        # 获取当前教师信息
        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            return jsonify({'success': False, 'error': '教师信息不存在'}), 400
        
        data = request.get_json()
        pending_ids = data.get('pending_ids', [])
        comment = data.get('comment', '').strip() or None

        if not pending_ids:
            return jsonify({'success': False, 'error': '未选择任何记录'}), 400

        # 验证教师是否有权限审核这些记录
        teacher_pendings = pending_manager.get_pending_for_teacher(
            teacher.id,
            teacher_manager=teacher_manager,
            teacher_name=teacher.name
        )
        allowed_pending_ids = set(p.id for p in teacher_pendings)
        filtered_pending_ids = [pid for pid in pending_ids if pid in allowed_pending_ids]
        
        if not filtered_pending_ids:
            return jsonify({'success': False, 'error': '没有可审核的记录'}), 400

        from backend.services.review_service import ReviewService, Reviewer
        from app.routes.admin_review import _get_review_service
        review_service = _get_review_service(app_context)
        reviewer_id = session.get('user_id')
        reviewer = Reviewer(reviewer_type='teacher', reviewer_id=reviewer_id)

        # 使用 ReviewService 批量审核
        results = review_service.approve_batch(filtered_pending_ids, reviewer, force=True)

        # 统计结果
        approved_count = sum(1 for r in results if r.success)
        failed_count = len(results) - approved_count

        return jsonify({
            'success': True,
            'approved': approved_count,
            'failed': failed_count
        })

    except Exception as e:
        logger.error(f"Error in batch approve: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/achievement-review/batch-discard', methods=['POST'])
@require_user_type('teacher')
def api_achievement_review_batch_discard():
    """批量放弃当前 Tab 的待审核记录（教师版本）。仅可放弃本人有权限审核的记录。"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()

        user_id = session.get('user_id')
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            return jsonify({'success': False, 'message': '教师信息不存在'}), 400

        data = request.get_json() or {}
        pending_ids = data.get('pending_ids', [])
        if not pending_ids:
            return jsonify({'success': True, 'count': 0, 'files_deleted': 0})

        teacher_pendings = pending_manager.get_pending_for_teacher(
            teacher.id,
            teacher_manager=teacher_manager,
            teacher_name=teacher.name
        )
        allowed_ids = {p.id for p in teacher_pendings}
        to_discard = [pid for pid in pending_ids if pid in allowed_ids]

        count = 0
        files_deleted = 0
        achievement_type = data.get('type', 'award')

        for pid in to_discard:
            item = pending_manager.get_pending_by_id(pid)
            if not item or item.achievement_type != achievement_type:
                continue
            if achievement_type == 'innovation':
                data_obj = item.get_achievement_data() or {}
                project_count = max(1, len(data_obj.get('projects') or []))
            else:
                project_count = 1
            result = pending_manager.safe_delete_with_file(pid)
            if result.get('success'):
                count += project_count
                if result.get('file_deleted'):
                    files_deleted += 1
                # P1-13 留痕：动作10=放弃（教师审核侧）
                try:
                    from backend.utils.audit_logger import audit_log
                    audit_log(10, pid, item.achievement_type,
                              operator={"id": user_id, "code": str(user_id), "user_type": "teacher"})
                except Exception:
                    pass

        return jsonify({
            'success': True,
            'count': count,
            'files_deleted': files_deleted
        })
    except Exception as e:
        logger.error(f"api_achievement_review_batch_discard 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/laboratory/<int:lab_id>/data-analysis')
@require_user_type('teacher')
def laboratory_data_analysis(lab_id):
    """实验室数据分析页面"""
    try:
        # 验证教师是否有权限访问该实验室
        user_id = session.get('user_id')
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        laboratory_manager = app_context.get_laboratory_manager()

        teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
        if not teacher:
            flash('教师信息不存在', 'error')
            return redirect(url_for('teacher.dashboard'))

        # 获取实验室信息
        laboratory = laboratory_manager.get_laboratory_by_id(lab_id)
        if not laboratory:
            flash('实验室不存在', 'error')
            return redirect(url_for('teacher.dashboard'))

        # 检查教师是否属于该实验室（作为指导教师或助理）
        is_member = (teacher.id in [t.id for t in laboratory.instructors] or
                    teacher.id in [t.id for t in laboratory.assistants])

        if not is_member:
            flash('您没有权限访问该实验室的数据分析', 'error')
            return redirect(url_for('teacher.dashboard'))

        return render_template('laboratory/data_analysis.html', lab_id=lab_id)

    except Exception as e:
        logger.error(f"Error loading laboratory data analysis: {e}", exc_info=True)
        flash(f'加载数据分析页面失败: {str(e)}', 'error')
        return redirect(url_for('teacher.dashboard'))
