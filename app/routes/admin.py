"""
管理员路由
"""
import logging
import json
import os
import shutil
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, session
from pathlib import Path

# 导入认证装饰器
from app.auth import require_role, require_role_api

from app.utils import get_app_context_instance, calculate_file_hash
from backend.services.award_processing_service import AwardProcessingService

logger = logging.getLogger(__name__)
bp = Blueprint('admin', __name__)

@bp.route('/')
@bp.route('/dashboard')
@require_role('admin')
def dashboard():
    """管理员首页：成果数据总览看板"""
    return render_template('admin/dashboard.html')

@bp.route('/api/dashboard/overview', methods=['GET'])
@require_role('admin')
def api_dashboard_overview():
    """成果数据总览聚合接口——dashboard 看板数据源（仿百度云消费总览的信息架构）。
    参数 months：近 N 个月（影响趋势与环比）；缺省=全部。"""
    from backend.utils.db_connection import get_connection
    from datetime import date, timedelta
    months = request.args.get('months', type=int)
    try:
        from config.loader import get_config
        db_path = get_config()['database']['competitions_db']
    except Exception:
        db_path = current_app.config.get('DATABASE', 'database/competitions.db')
    try:
        conn = get_connection(db_path)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    try:
        cur = conn.cursor()

        def one(sql, *args):
            r = cur.execute(sql, args).fetchone()
            return r[0] if r else 0

        # 口径对齐成果管理页：奖状统计排除教师证书（granted_role='教师'，含 NULL 保留——三值逻辑注意），
        # 分类集合与成果管理五类一致（奖状/专利/软著/大创/其他）
        award_scope = "(granted_role IS NULL OR granted_role <> '教师')"

        summary = {
            'total_awards': one(f"SELECT COUNT(*) FROM awards WHERE {award_scope}"),
            'pending': one("SELECT COUNT(*) FROM pending_achievements WHERE status='pending'"),
            'whitelist': one("SELECT COUNT(*) FROM competitions WHERE white_list=1"),
            'competitions': one("SELECT COUNT(*) FROM competitions"),
        }
        category = {
            'award': summary['total_awards'],
            'patent': one("SELECT COUNT(*) FROM patents"),
            'software': one("SELECT COUNT(*) FROM software_copyrights"),
            'innovation': one("SELECT COUNT(*) FROM innovation_projects"),
            'other': one("SELECT COUNT(*) FROM other_files"),
        }

        # 近 N 月起点（含当月）
        start_month = None
        if months:
            today = date.today()
            start = today.replace(day=1)
            for _ in range(months - 1):
                start = (start - timedelta(days=1)).replace(day=1)
            start_month = start.strftime('%Y-%m')

        trend_sql = ("SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS count "
                     f"FROM awards WHERE created_at IS NOT NULL AND {award_scope}")
        trend_args = []
        if start_month:
            trend_sql += " AND strftime('%Y-%m', created_at) >= ?"
            trend_args.append(start_month)
        trend_sql += " GROUP BY month ORDER BY month"
        trend = [dict(r) for r in cur.execute(trend_sql, trend_args).fetchall()]

        # 环比：本月 vs 上月奖状新增（映射百度云"消费环比"）
        this_m = date.today().strftime('%Y-%m')
        last_m = (date.today().replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
        this_n = one(f"SELECT COUNT(*) FROM awards WHERE strftime('%Y-%m', created_at)=? AND {award_scope}", this_m)
        last_n = one(f"SELECT COUNT(*) FROM awards WHERE strftime('%Y-%m', created_at)=? AND {award_scope}", last_m)
        compare = {'period': this_m, 'this': this_n, 'last': last_n}
        if last_n:
            compare['delta_pct'] = round((this_n - last_n) / last_n * 100, 1)
        else:
            compare['delta_pct'] = None

        by_comp = [dict(r) for r in cur.execute(
            f"SELECT COALESCE(c.competition_name, '未关联') AS name, COUNT(*) AS total "
            f"FROM awards a LEFT JOIN competitions c ON a.competition_id = c.id "
            f"WHERE {award_scope.replace('granted_role', 'a.granted_role')} "
            "GROUP BY COALESCE(c.competition_name, '未关联') ORDER BY total DESC LIMIT 12").fetchall()]
        recent = [dict(r) for r in cur.execute(
            "SELECT a.id, a.date, COALESCE(c.competition_name, '-') AS competition, "
            "a.award_level, a.winner_name, a.submit_time "
            "FROM awards a LEFT JOIN competitions c ON a.competition_id = c.id "
            "ORDER BY a.created_at DESC, a.id DESC LIMIT 10").fetchall()]
        return jsonify({'ok': True, 'summary': summary, 'category': category,
                        'trend': trend, 'compare': compare,
                        'by_competition': by_comp, 'recent': recent})
    finally:
        conn.close()

@bp.route('/api/config/competition-levels', methods=['GET'])
@require_role('admin')
def api_get_competition_levels():
    """获取竞赛等级配置API（包括列表和颜色映射）"""
    try:
        # 使用统一的 get_config() 函数，它会处理缓存和开发环境重新加载
        from app.utils import get_config
        config = get_config()
        
        # 获取竞赛等级列表
        # 使用 validation.competition_levels（用于验证，更严格，不包含会被映射的等级如"区域赛"）
        competition_levels = []
        if "validation" in config and "competition_levels" in config["validation"]:
            competition_levels = config["validation"]["competition_levels"]
        else:
            raise ValueError(
                "竞赛等级配置缺失：请在 config/settings.json 中配置 "
                "validation.competition_levels"
            )
        
        if not competition_levels:
            raise ValueError("竞赛等级配置为空")
        
        # 获取颜色映射配置（禁止硬编码默认值）
        if "ui" not in config or "competition_level_colors" not in config["ui"]:
            raise ValueError(
                "竞赛等级颜色配置缺失：请在 config/settings.json 中配置 ui.competition_level_colors"
            )
        
        color_map = config["ui"]["competition_level_colors"]
        if not color_map:
            raise ValueError("ui.competition_level_colors 配置为空")
        
        return jsonify({
            'success': True,
            'data': {
                'levels': competition_levels,
                'color_map': color_map
            }
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': f'获取竞赛等级配置失败: {str(e)}',
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500

@bp.route('/api/competitions/add', methods=['POST'])
@require_role('admin')
def api_add_competition():
    """API：快速添加竞赛（只设置名称和ID，其他为空）"""
    try:
        data = request.get_json()
        competition_name = data.get('name', '').strip()
        
        if not competition_name:
            return jsonify({'success': False, 'message': '竞赛名称不能为空'}), 400
        
        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()
        
        # 检查是否已存在
        existing = competition_manager.match_competition(competition_name)
        if existing:
            return jsonify({
                'success': True, 
                'message': '竞赛已存在',
                'competition': {'id': existing.id, 'name': existing.name}
            })
        
        # 添加竞赛（只设置名称，其他为空）
        new_id = competition_manager.add_competition(
            name=competition_name,
            alias_list="",
            is_auto_added=False  # 手动添加
        )
        
        if new_id:
            new_comp = competition_manager.get_competition_by_id(new_id)
            return jsonify({
                'success': True,
                'message': '竞赛添加成功',
                'competition': {'id': new_id, 'name': new_comp.name}
            })
        else:
            return jsonify({'success': False, 'message': '添加竞赛失败'}), 500
            
    except Exception as e:
        current_app.logger.error(f"添加竞赛失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'添加竞赛失败: {str(e)}'}), 500

@bp.route('/api/competitions/<int:competition_id>/add-alias', methods=['POST'])
@require_role('admin')
def api_add_competition_alias(competition_id):
    """API：添加竞赛别名"""
    try:
        data = request.get_json()
        alias = data.get('alias', '').strip()
        
        if not alias:
            return jsonify({'success': False, 'message': '别名不能为空'}), 400
        
        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()
        
        # 检查竞赛是否存在
        comp = competition_manager.get_competition_by_id(competition_id)
        if not comp:
            return jsonify({'success': False, 'message': '竞赛不存在'}), 404
        
        # 添加别名
        success = competition_manager.add_alias(competition_id, alias)
        
        if success:
            # 重新加载竞赛对象
            comp = competition_manager.get_competition_by_id(competition_id)
            return jsonify({
                'success': True,
                'message': '别名添加成功',
                'aliases': comp.aliases
            })
        else:
            return jsonify({'success': False, 'message': '添加别名失败'}), 500
            
    except Exception as e:
        current_app.logger.error(f"添加别名失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'添加别名失败: {str(e)}'}), 500

@bp.route('/competitions')
@require_role('admin')
def competitions_list():
    """竞赛列表页面"""
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20  # 每页显示20条

    try:
        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()

        # 获取所有竞赛
        all_competitions = []
        if hasattr(competition_manager, 'competitions'):
            all_competitions = competition_manager.competitions
        elif hasattr(competition_manager, '_competitions'):
            all_competitions = competition_manager._competitions

        # 搜索过滤
        if search:
            all_competitions = [c for c in all_competitions if search.lower() in c.name.lower()]

        # 计算分页
        total = len(all_competitions)
        total_pages = (total + per_page - 1) // per_page
        page = max(1, min(page, total_pages)) if total_pages > 0 else 1

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        competitions = all_competitions[start_idx:end_idx]

        return render_template('admin/competitions/list.html',
                             competitions=competitions,
                             search=search,
                             page=page,
                             per_page=per_page,
                             total=total,
                             total_pages=total_pages)
    except Exception as e:
        flash(f'加载竞赛列表失败: {str(e)}', 'error')
        return render_template('admin/competitions/list.html',
                             competitions=[],
                             search='',
                             page=1,
                             per_page=per_page,
                             total=0,
                             total_pages=0)

@bp.route('/competitions/<int:competition_id>')
@require_role('admin')
def competition_detail(competition_id):
    """竞赛详情页面"""
    try:
        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()
        
        competition = competition_manager.get_competition_by_id(competition_id)
        if not competition:
            flash('竞赛不存在', 'error')
            return redirect(url_for('admin.competitions_list'))
        
        return render_template('admin/competitions/detail.html', competition=competition)
    except Exception as e:
        flash(f'加载竞赛详情失败: {str(e)}', 'error')
        return redirect(url_for('admin.competitions_list'))

@bp.route('/competitions/new', methods=['GET', 'POST'])
@bp.route('/competitions/<int:competition_id>/edit', methods=['GET', 'POST'])
@require_role('admin')
def competition_edit(competition_id=None):
    """竞赛编辑页面"""
    try:
        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()
        
        competition = None
        if competition_id:
            competition = competition_manager.get_competition_by_id(competition_id)
            if not competition:
                flash('竞赛不存在', 'error')
                return redirect(url_for('admin.competitions_list'))
        
        if request.method == 'POST':
            try:
                name = request.form.get('name', '').strip()
                if not name:
                    flash('竞赛名称不能为空', 'error')
                    return render_template('admin/competitions/edit.html', competition=competition)

                # 获取别名（逗号分隔）
                aliases_str = request.form.get('aliases', '').strip()
                aliases = [a.strip() for a in aliases_str.split(',') if a.strip()] if aliases_str else []

                # 获取其他字段
                grade_category = request.form.get('grade_category', '').strip() or None
                competition_time = request.form.get('competition_time', '').strip() or None
                organizer = request.form.get('organizer', '').strip() or None
                official_website = request.form.get('official_website', '').strip() or None
                participant_requirements = request.form.get('participant_requirements', '').strip() or None
                brief_description = request.form.get('description', '').strip() or None

                if competition_id:
                    # 更新现有竞赛
                    alias_list_str = ','.join(aliases) if aliases else ''
                    competition_manager.update_competition(
                        competition_id,
                        name=name,
                        alias_list=alias_list_str,
                        white_list=bool(request.form.get('white_list')),
                        watch_list=bool(request.form.get('watch_list')),
                        brief_description=brief_description,
                        grade_category=grade_category,
                        competition_time=competition_time,
                        organizer=organizer,
                        official_website=official_website,
                        participant_requirements=participant_requirements
                    )
                    competition = competition_manager.get_competition_by_id(competition_id)
                else:
                    # 创建新竞赛
                    alias_list_str = ','.join(aliases) if aliases else ''
                    competition_id = competition_manager.add_competition(
                        name=name,
                        alias_list=alias_list_str,
                        white_list=bool(request.form.get('white_list')),
                        watch_list=bool(request.form.get('watch_list')),
                        brief_description=brief_description,
                        grade_category=grade_category,
                        competition_time=competition_time,
                        organizer=organizer,
                        official_website=official_website,
                        participant_requirements=participant_requirements
                    )
                    if competition_id:
                        competition = competition_manager.get_competition_by_id(competition_id)
                    else:
                        competition = None

                flash('竞赛保存成功', 'success')
                return redirect(url_for('admin.competition_detail', competition_id=competition.id))
            except Exception as e:
                import traceback
                flash(f'保存失败: {str(e)}', 'error')
                if current_app.config.get('DEBUG'):
                    flash(f'错误详情: {traceback.format_exc()}', 'error')
        
        return render_template('admin/competitions/edit.html', competition=competition)
    except Exception as e:
        flash(f'加载编辑页面失败: {str(e)}', 'error')
        return redirect(url_for('admin.competitions_list'))

def _do_delete_competition(competition_id):
    """执行删除竞赛，返回 (success, message)。"""
    app_context = get_app_context_instance()
    competition_manager = app_context.get_competition_manager()
    competition = competition_manager.get_competition_by_id(competition_id)
    if not competition:
        return False, '竞赛不存在'
    conn = competition_manager._get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM competitions WHERE id = ?', (competition_id,))
    conn.commit()
    conn.close()
    return True, '删除成功'


@bp.route('/competitions/<int:competition_id>/delete', methods=['POST'])
@require_role('admin')
def competition_delete_post(competition_id):
    """删除竞赛（表单 POST），删除后重定向到列表。"""
    try:
        success, message = _do_delete_competition(competition_id)
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
    except Exception as e:
        flash(f'删除失败: {str(e)}', 'error')
    return redirect(url_for('admin.competitions_list', search=request.args.get('search', ''), page=request.args.get('page', 1)))


@bp.route('/competitions/<int:competition_id>', methods=['DELETE'])
@require_role('admin')
def competition_delete(competition_id):
    """删除竞赛（JSON API）。"""
    try:
        success, message = _do_delete_competition(competition_id)
        if not success:
            return jsonify({'success': False, 'message': message}), 404
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500

# ==================== 学生管理 ====================

@bp.route('/students')
@require_role('admin')
def students_list():
    """学生列表页面"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    
    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        
        # 获取所有学生或搜索（姓名支持部分匹配）
        if search:
            students = student_manager.search_students_by_name(search)
            # 尝试按学号查找
            try:
                student_by_student_id = student_manager.get_student_by_student_id(search)
                if student_by_student_id and student_by_student_id not in students:
                    students.append(student_by_student_id)
            except (ValueError, TypeError):
                pass
            # 尝试按ID查找（如果search是数字）
            try:
                search_id = int(search)
                student_by_id = student_manager.get_student_by_id(search_id)
                if student_by_id and student_by_id not in students:
                    students.append(student_by_id)
            except (ValueError, TypeError):
                pass
        else:
            # 获取所有学生（从数据库查询）
            import sqlite3
            from pathlib import Path
            db_path = student_manager.db_path
            students = []
            if Path(db_path).exists():
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM students ORDER BY student_id LIMIT ? OFFSET ?", 
                             (per_page, (page - 1) * per_page))
                rows = cursor.fetchall()
                students = [student_manager.get_student_by_id(row['id']) for row in rows if row['id']]
                # 获取总数
                cursor.execute("SELECT COUNT(*) as count FROM students")
                total_count = cursor.fetchone()['count']
                conn.close()
            else:
                total_count = 0
        
        # 计算分页信息
        if not search:
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        else:
            total_count = len(students)
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            # 分页
            students = students[(page - 1) * per_page:page * per_page]
        
        return render_template('admin/students/list.html',
                             students=students or [],
                             page=page,
                             per_page=per_page,
                             total_count=total_count,
                             total_pages=total_pages,
                             search=search)
    except Exception as e:
        flash(f'加载学生列表失败: {str(e)}', 'error')
        return render_template('admin/students/list.html',
                             students=[],
                             page=1,
                             per_page=20,
                             total_count=0,
                             total_pages=1,
                             search='')

@bp.route('/students/new', methods=['GET', 'POST'])
@bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@require_role('admin')
def student_edit(student_id=None):
    """学生编辑页面"""
    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        
        student = None
        if student_id:
            student = student_manager.get_student_by_id(student_id)
            if not student:
                flash('学生不存在', 'error')
                return redirect(url_for('admin.students_list'))
        
        if request.method == 'POST':
            try:
                student_id_str = request.form.get('student_id', '').strip()
                name = request.form.get('name', '').strip()
                major = request.form.get('major', '').strip() or None
                grade = request.form.get('grade', '').strip() or None
                phone = request.form.get('phone', '').strip() or None
                user_activated = bool(request.form.get('user_activated'))
                
                if not student_id_str or not name:
                    flash('学号和姓名不能为空', 'error')
                    return render_template('admin/students/edit.html', student=student)
                
                if student_id:
                    # 更新
                    # 学号不允许修改
                    current_app.logger.info(f"正在更新学生信息: ID={student.id}, 学号={student.student_id}")
                    
                    # M1 后半②：视图化后旧表不可写，基本信息直写 users 真源
                    from backend.orm.repositories import UserRepository
                    UserRepository.update_profile(
                        student.student_id,
                        name=name, major=major, grade=grade,
                        phone=phone, user_activated=user_activated)
                    current_app.logger.info(f"学生信息更新成功: ID={student.id}")
                else:
                    # 创建
                    # 检查学号是否已存在
                    existing = student_manager.get_student_by_student_id(student_id_str)
                    if existing:
                        flash(f'学号 {student_id_str} 已被使用', 'error')
                        return render_template('admin/students/edit.html', student=None)
                    
                    from werkzeug.security import generate_password_hash
                    from app.password_policy import generate_strong_password
                    initial_password = generate_strong_password()
                    password_hash = generate_password_hash(initial_password)
                    # M1 后半②：视图化后旧表不可写，创建直写 users 真源
                    from backend.orm.repositories import UserRepository
                    UserRepository.create_user(
                        student_id_str, name, 'student', password_hash, needs_password_change=1,
                        major=major, grade=grade, phone=phone, user_activated=user_activated)
                    flash(f'学生创建成功，初始密码（仅此一次展示）：{initial_password}', 'warning')
                
                flash('学生保存成功', 'success')
                return redirect(url_for('admin.students_list'))
            except Exception as e:
                import traceback
                flash(f'保存失败: {str(e)}', 'error')
                if current_app.config.get('DEBUG'):
                    flash(f'错误详情: {traceback.format_exc()}', 'error')
        
        return render_template('admin/students/edit.html', student=student)
    except Exception as e:
        flash(f'加载编辑页面失败: {str(e)}', 'error')
        return redirect(url_for('admin.students_list'))

@bp.route('/students/<int:student_id>', methods=['DELETE'])
@require_role('admin')
def student_delete(student_id):
    """删除学生"""
    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        
        student = student_manager.get_student_by_id(student_id)
        if not student:
            return jsonify({'success': False, 'message': '学生不存在'}), 404
        
        # 删除学生（M1 后半②：视图化后软删 users，防历史引用悬空）
        try:
            from backend.orm.repositories import UserRepository
            UserRepository.deactivate(student.student_id)
            return jsonify({'success': True, 'message': '已禁用（软删除）'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500

@bp.route('/students/<int:student_id>/reset-password', methods=['POST'])
@require_role('admin')
def student_reset_password(student_id):
    """重置学生密码"""
    try:
        from werkzeug.security import generate_password_hash
        
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        
        student = student_manager.get_student_by_id(student_id)
        if not student:
            return jsonify({'success': False, 'message': '学生不存在'}), 404
        
        # 随机强密码 + 强制改密标记（P1-2/T22：废除默认密码重置）
        from app.password_policy import generate_strong_password
        initial_password = generate_strong_password()
        password_hash = generate_password_hash(initial_password)
        
        # M1 后半②：视图化后旧表不可写，重置密码直写 users 真源
        from backend.orm.repositories import UserRepository
        UserRepository.update_password(student.student_id, password_hash, needs_password_change=1)
        
        return jsonify({
            'success': True, 
            'message': f'密码已重置，初始密码（仅此一次展示）：{initial_password}'
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False, 
            'message': f'重置密码失败: {str(e)}',
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500

# ==================== 教师管理 ====================

@bp.route('/teachers')
@require_role('admin')
def teachers_list():
    """教师列表页面"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    
    try:
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        
        # 获取所有教师或搜索
        if search:
            teachers = teacher_manager.find_teachers_by_name(search)
            # 尝试按工号查找
            try:
                teacher_by_teacher_id = teacher_manager.get_teacher_by_teacher_id(search)
                if teacher_by_teacher_id and teacher_by_teacher_id not in teachers:
                    teachers.append(teacher_by_teacher_id)
            except (ValueError, TypeError):
                pass
            # 尝试按ID查找（如果search是数字）
            try:
                search_id = int(search)
                teacher_by_id = teacher_manager.get_teacher_by_id(search_id)
                if teacher_by_id and teacher_by_id not in teachers:
                    teachers.append(teacher_by_id)
            except (ValueError, TypeError):
                pass
        else:
            # 获取所有教师（从数据库查询）
            import sqlite3
            from pathlib import Path
            db_path = teacher_manager.db_path
            teachers = []
            if Path(db_path).exists():
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM teachers ORDER BY teacher_id LIMIT ? OFFSET ?", 
                             (per_page, (page - 1) * per_page))
                rows = cursor.fetchall()
                teachers = [teacher_manager.get_teacher_by_id(row['id']) for row in rows if row['id']]
                # 获取总数
                cursor.execute("SELECT COUNT(*) as count FROM teachers")
                total_count = cursor.fetchone()['count']
                conn.close()
            else:
                total_count = 0
        
        # 计算分页信息
        if not search:
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        else:
            total_count = len(teachers)
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            # 分页
            teachers = teachers[(page - 1) * per_page:page * per_page]
        
        return render_template('admin/teachers/list.html',
                             teachers=teachers or [],
                             page=page,
                             per_page=per_page,
                             total_count=total_count,
                             total_pages=total_pages,
                             search=search)
    except Exception as e:
        flash(f'加载教师列表失败: {str(e)}', 'error')
        return render_template('admin/teachers/list.html',
                             teachers=[],
                             page=1,
                             per_page=20,
                             total_count=0,
                             total_pages=1,
                             search='')

@bp.route('/teachers/new', methods=['GET', 'POST'])
@bp.route('/teachers/<int:teacher_id>/edit', methods=['GET', 'POST'])
@require_role('admin')
def teacher_edit(teacher_id=None):
    """教师编辑页面"""
    try:
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        
        teacher = None
        if teacher_id:
            teacher = teacher_manager.get_teacher_by_id(teacher_id)
            if not teacher:
                flash('教师不存在', 'error')
                return redirect(url_for('admin.teachers_list'))
        
        if request.method == 'POST':
            try:
                teacher_id_str = request.form.get('teacher_id', '').strip()
                name = request.form.get('name', '').strip()
                department = request.form.get('department', '').strip() or None
                title = request.form.get('title', '').strip() or None
                phone = request.form.get('phone', '').strip() or None
                user_activated = bool(request.form.get('user_activated'))
                
                if not teacher_id_str or not name:
                    flash('工号和姓名不能为空', 'error')
                    return render_template('admin/teachers/edit.html', teacher=teacher)
                
                if teacher_id:
                    # 更新
                    # 工号不允许修改
                    current_app.logger.info(f"正在更新教师信息: ID={teacher.id}, 工号={teacher.teacher_id}")
                    
                    # M1 后半②：视图化后旧表不可写，基本信息直写 users 真源
                    from backend.orm.repositories import UserRepository
                    UserRepository.update_profile(
                        teacher.teacher_id,
                        name=name, department=department, title=title,
                        phone=phone, user_activated=user_activated)
                    current_app.logger.info(f"教师信息更新成功: ID={teacher.id}")
                else:
                    # 创建（设置默认密码，确保新教师可登录）
                    try:
                        from werkzeug.security import generate_password_hash
                        from app.password_policy import generate_strong_password
                        initial_password = generate_strong_password()
                        password_hash = generate_password_hash(initial_password)
                        # M1 后半②：视图化后旧表不可写，创建直写 users 真源
                        from backend.orm.repositories import UserRepository
                        UserRepository.create_user(
                            teacher_id_str, name, 'teacher', password_hash, needs_password_change=1,
                            department=department, title=title, phone=phone,
                            user_activated=user_activated)
                        flash(f'教师创建成功，初始密码（仅此一次展示）：{initial_password}', 'warning')
                    except ValueError as e:
                        # 处理重名或工号重复的错误
                        flash(str(e), 'error')
                        return render_template('admin/teachers/edit.html', teacher=None)
                
                flash('教师保存成功', 'success')
                return redirect(url_for('admin.teachers_list'))
            except Exception as e:
                import traceback
                flash(f'保存失败: {str(e)}', 'error')
                if current_app.config.get('DEBUG'):
                    flash(f'错误详情: {traceback.format_exc()}', 'error')
        
        return render_template('admin/teachers/edit.html', teacher=teacher)
    except Exception as e:
        flash(f'加载编辑页面失败: {str(e)}', 'error')
        return redirect(url_for('admin.teachers_list'))

@bp.route('/teachers/<int:teacher_id>', methods=['DELETE'])
@require_role('admin')
def teacher_delete(teacher_id):
    """删除教师"""
    try:
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        
        teacher = teacher_manager.get_teacher_by_id(teacher_id)
        if not teacher:
            return jsonify({'success': False, 'message': '教师不存在'}), 404
        
        # 删除教师（M1 后半②：视图化后软删 users，防历史引用悬空）
        try:
            from backend.orm.repositories import UserRepository
            UserRepository.deactivate(teacher.teacher_id)
            return jsonify({'success': True, 'message': '已禁用（软删除）'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500

@bp.route('/teachers/<int:teacher_id>/reset-password', methods=['POST'])
@require_role('admin')
def teacher_reset_password(teacher_id):
    """重置教师密码"""
    try:
        from werkzeug.security import generate_password_hash
        
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()
        
        teacher = teacher_manager.get_teacher_by_id(teacher_id)
        if not teacher:
            return jsonify({'success': False, 'message': '教师不存在'}), 404
        
        from app.password_policy import generate_strong_password
        initial_password = generate_strong_password()
        password_hash = generate_password_hash(initial_password)
        
        # M1 后半②：视图化后旧表不可写，重置密码直写 users 真源
        from backend.orm.repositories import UserRepository
        UserRepository.update_password(teacher.teacher_id, password_hash, needs_password_change=1)
        
        return jsonify({
            'success': True, 
            'message': f'密码已重置，初始密码（仅此一次展示）：{initial_password}'
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False, 
            'message': f'重置密码失败: {str(e)}',
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500

@bp.route('/api/students/search')
@require_role('admin', 'teacher', 'student')
def api_students_search():
    """学生搜索API"""
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify({'success': True, 'students': []})

    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()

        # 使用student_manager的搜索方法
        students = student_manager.find_students_by_name(query)

        results = []
        for student in students[:10]:  # 限制结果数量
            # 构建简要描述
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
        current_app.logger.error(f"学生搜索失败: {e}")
        return jsonify({'success': False, 'students': [], 'error': str(e)})

@bp.route('/api/teachers/search')
@require_role('admin', 'teacher', 'student')
def api_teachers_search():
    """教师搜索API"""
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify({'success': True, 'teachers': []})

    try:
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()

        # 使用teacher_manager的搜索方法
        teachers = teacher_manager.find_teachers_by_name(query)

        results = []
        for teacher in teachers[:10]:  # 限制结果数量
            results.append({
                'id': teacher.id,
                'teacher_id': teacher.teacher_id,
                'name': teacher.name,
                'title': teacher.title if hasattr(teacher, 'title') else ''
            })

        return jsonify({'success': True, 'teachers': results})
    except Exception as e:
        current_app.logger.error(f"教师搜索失败: {e}")
        return jsonify({'success': False, 'teachers': [], 'error': str(e)})

@bp.route('/api/laboratories')
@require_role('admin')
def api_laboratories():
    """获取所有实验室列表API"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        # 获取所有实验室
        if hasattr(laboratory_manager, 'get_all_laboratories'):
            laboratories = laboratory_manager.get_all_laboratories()
        elif hasattr(laboratory_manager, 'laboratories'):
            laboratories = laboratory_manager.laboratories
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
        current_app.logger.error(f"获取实验室列表失败: {e}")
        return jsonify({'success': False, 'laboratories': [], 'error': str(e)}), 500


@bp.route('/api/teachers')
@require_role('admin')
def api_teachers():
    """获取所有教师列表API"""
    try:
        app_context = get_app_context_instance()
        teacher_manager = app_context.get_teacher_manager()

        # 获取所有教师
        if hasattr(teacher_manager, 'teachers'):
            teachers = teacher_manager.teachers
        elif hasattr(teacher_manager, '_teachers'):
            teachers = teacher_manager._teachers
        else:
            teachers = []

        results = []
        for teacher in teachers:
            results.append({
                'id': teacher.id,
                'teacher_id': teacher.teacher_id,
                'name': teacher.name
            })

        return jsonify({'success': True, 'teachers': results})
    except Exception as e:
        current_app.logger.error(f"获取教师列表失败: {e}")
        return jsonify({'success': False, 'teachers': [], 'error': str(e)}), 500


@bp.route('/api/competitions')
@require_role('admin')
def api_competitions():
    """获取所有竞赛列表API"""
    try:
        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()

        # 获取所有竞赛
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
        current_app.logger.error(f"获取竞赛列表失败: {e}")
        return jsonify({'success': False, 'competitions': [], 'error': str(e)}), 500

@bp.route('/api/students/duplicates')
@require_role('admin')
def api_students_duplicates():
    """检查重复学生API"""
    name = request.args.get('name', '').strip()

    if not name:
        return jsonify({'duplicates': []})

    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()

        # 搜索同名学生
        students = student_manager.find_students_by_name(name)

        duplicates = []
        for student in students:
            duplicates.append({
                'id': student.id,
                'student_id': student.student_id,
                'name': student.name,
                'major': student.major,
                'grade': student.grade
            })

        return jsonify({'duplicates': duplicates})
    except Exception as e:
        current_app.logger.error(f"检查重复学生失败: {e}")
        return jsonify({'duplicates': []})
# ==================== 奖状模板管理 ====================
def _sync_auto_archive_config_from_settings(config_loader, auto_archive_config_manager):
    """
    从配置文件同步自动归档设置到数据库

    Args:
        config_loader: ConfigLoader 实例
        auto_archive_config_manager: AutoArchiveConfigManager 实例
    """
    try:
        app_config = config_loader.load_config()
        auto_archive_config = app_config.get('auto_archive', {})

        # 同步奖状配置
        auto_archive_config_manager.update_config('award', 'valid', auto_archive_config.get('award_valid', False))
        auto_archive_config_manager.update_config('award', 'invalid', auto_archive_config.get('award_invalid', False))

        # 同步专利配置
        auto_archive_config_manager.update_config('patent', 'valid', auto_archive_config.get('patent_valid', False))
        auto_archive_config_manager.update_config('patent', 'invalid', auto_archive_config.get('patent_invalid', False))

        # 同步软著配置
        auto_archive_config_manager.update_config('software', 'valid', auto_archive_config.get('software_valid', False))
        auto_archive_config_manager.update_config('software', 'invalid', auto_archive_config.get('software_invalid', False))

        # 同步大创配置
        auto_archive_config_manager.update_config('innovation', None, auto_archive_config.get('innovation', False))

        # 同步其他文件配置
        auto_archive_config_manager.update_config('other', None, auto_archive_config.get('other', False))

        logger.info("自动归档配置已从配置文件同步到数据库")
    except Exception as e:
        logger.error(f"同步自动归档配置失败: {e}")



@bp.route('/settings')
@require_role('admin')
def settings():
    """系统设置页面"""
    try:
        from pathlib import Path
        import json
        from config.loader import get_config
        
        # 使用统一的配置加载器获取配置
        config_loader = get_config()
        app_config = config_loader.load_config()
        
        # 加载 apikey.json（如果存在）以获取当前的 API Keys
        root_path = Path(current_app.root_path).parent
        apikey_path = root_path / 'apikey' / 'apikey.json'
        
        user_keys = {}
        if apikey_path.exists():
            try:
                with open(apikey_path, 'r', encoding='utf-8') as f:
                    user_keys = json.load(f)
            except Exception as e:
                logger.error(f"读取 apikey.json 失败: {e}")

        available_ocr_providers = []
        available_llm_providers = []
        
        # 准备前端需要的数据结构
        # providers_config = {
        #   "ocr": { "zhipu": { "api_key": "xxx", "has_key": true, "key_env": "..." } },
        #   "llm": { ... }
        # }
        providers_config = {"ocr": {}, "llm": {}}

        # 获取可用的OCR供应商（从 settings.json）
        if 'ocr' in app_config and 'providers' in app_config['ocr']:
            for name, conf in app_config['ocr']['providers'].items():
                available_ocr_providers.append(name)
                # 检查是否需要 API Key
                api_key_env = conf.get('api_key_env')
                current_key = user_keys.get('ocr', {}).get(name, '')
                providers_config['ocr'][name] = {
                    'needs_key': bool(api_key_env),
                    'api_key': current_key,
                    'type': conf.get('type')
                }

        # 获取可用的LLM供应商（从 settings.json）
        if 'llm' in app_config and 'providers' in app_config['llm']:
            for name, conf in app_config['llm']['providers'].items():
                available_llm_providers.append(name)
                api_key_env = conf.get('api_key_env')
                current_key = user_keys.get('llm', {}).get(name, '')
                providers_config['llm'][name] = {
                    'needs_key': bool(api_key_env),
                    'api_key': current_key,
                    'type': conf.get('type')
                }

        # 获取当前默认设置
        default_ocr_provider = app_config.get('ocr', {}).get('default_provider', '')
        default_llm_provider = app_config.get('llm', {}).get('default_provider', '')

        # OCR 运行时状态（当前使用的高精度、各供应商禁用状态及故障理由）
        ocr_status = None
        try:
            from app.utils import get_doc_rec_context
            doc_rec_context = get_doc_rec_context()
            engine = doc_rec_context.extract_framework.ocr_engine
            status_mgr = engine.get_status_manager()
            disabled = status_mgr.get_disabled_providers()
            ocr_status = {
                'current_effective_provider': engine.get_current_effective_precise_provider_name(),
                'default_provider': default_ocr_provider,
                'precise_order': engine.get_precise_order(),
                'all_providers': [
                    {
                        'name': name,
                        'is_precise': app_config.get('ocr', {}).get('providers', {}).get(name, {}).get('is_precise', True) is True,
                        'disabled': name in disabled,
                        'disabled_reason': disabled.get(name, {}).get('reason', ''),
                        'disabled_at': disabled.get(name, {}).get('disabled_at', ''),
                    }
                    for name in available_ocr_providers
                ],
            }
        except Exception as e:
            logger.warning("加载 OCR 运行时状态失败（将不显示供应商状态表）: %s", e)

        # 获取自动归档配置
        auto_archive_config = app_config.get('auto_archive', {})
        configs = {
            'award_valid': auto_archive_config.get('award_valid', False),
            'award_invalid': auto_archive_config.get('award_invalid', False),
            'patent_valid': auto_archive_config.get('patent_valid', False),
            'patent_invalid': auto_archive_config.get('patent_invalid', False),
            'software_valid': auto_archive_config.get('software_valid', False),
            'software_invalid': auto_archive_config.get('software_invalid', False),
            'innovation': auto_archive_config.get('innovation', False),
            'other': auto_archive_config.get('other', False)
        }

        # 获取系统默认密码
        default_password = app_config.get('system', {}).get('default_password', 'P@ss301')

        return render_template('admin/settings.html',
                             available_ocr_providers=available_ocr_providers,
                             available_llm_providers=available_llm_providers,
                             default_ocr_provider=default_ocr_provider,
                             default_llm_provider=default_llm_provider,
                             providers_config=providers_config,
                             configs=configs,
                             ocr_status=ocr_status,
                             default_password=default_password)

    except Exception as e:
        logger.error(f"加载设置页面失败: {e}", exc_info=True)
        flash(f'加载设置失败: {str(e)}', 'error')
        return render_template('admin/settings.html',
                             available_ocr_providers=[],
                             available_llm_providers=[],
                             default_ocr_provider='',
                             default_llm_provider='',
                             providers_config={"ocr": {}, "llm": {}},
                             configs={
                                 'award_valid': False,
                                 'award_invalid': False,
                                 'patent_valid': False,
                                 'patent_invalid': False,
                                 'software_valid': False,
                                 'software_invalid': False,
                                 'innovation': False,
                                 'other': False
                             },
                             ocr_status=None,
                             default_password='P@ss301')


def _delete_tree_and_count(path: Path) -> int:
    """递归删除目录及其内容，返回删除的文件和文件夹总数（每个文件或目录计 1）。"""
    total = 0
    for item in path.iterdir():
        if item.is_file():
            item.unlink()
            total += 1
        else:
            total += _delete_tree_and_count(item)
    path.rmdir()
    total += 1
    return total


def _delete_dir_contents_and_count(dir_path: Path) -> int:
    """删除目录下所有内容（不删目录本身），返回删除的文件和文件夹总数。"""
    total = 0
    for item in dir_path.iterdir():
        if item.is_file():
            item.unlink()
            total += 1
        else:
            total += _delete_tree_and_count(item)
    return total


def _run_cache_cleanup() -> dict:
    """
    执行缓存清理：
    1. 删除所有 status='pending' 的待处理记录（未提交审核的）；
    2. 清空 files/temp_upload 下全部内容；
    3. 清理 files/review 中未被任一 pending 记录引用的会话目录与文件。
    不包含 config temp_dir/manual_import（手动导入上传目录），该目录需另行或定时清理。
    返回统计：pending_deleted, temp_upload_deleted, review_deleted, total_files_folders。
    """
    from app.utils import get_app_context_instance
    from backend.services.unified_file_manager import get_unified_file_manager

    app_ctx = get_app_context_instance()
    pending_manager = app_ctx.get_pending_achievement_manager()
    file_manager = get_unified_file_manager()
    files_root = file_manager.files_root
    temp_upload_dir = files_root / "temp_upload"
    review_dir = files_root / "review"

    # 1) 从 pending_achievements 收集被引用的 review 会话 ID（表内 session_id 或 file_path 中 review/ 下第一段）
    kept_review_sessions = set()
    conn = pending_manager._get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, file_path FROM pending_achievements")
        for row in cursor.fetchall():
            sid = row["session_id"] if row["session_id"] else None
            if sid:
                kept_review_sessions.add(sid)
            fp = row["file_path"] if row["file_path"] else ""
            fp = (fp or "").strip().replace("\\", "/")
            if fp.startswith("review/"):
                parts = fp.split("/")
                if len(parts) >= 2:
                    kept_review_sessions.add(parts[1])
    finally:
        conn.close()

    # 2) 删除所有 status='pending' 的 pending_achievements（使用 pending_manager 接口）
    from backend.models.pending_achievement import PendingAchievementFilter
    filter_obj = PendingAchievementFilter(status='pending')
    pending_to_delete = pending_manager.query_pending(filter_obj)

    pending_deleted = 0
    for pending in pending_to_delete:
        if pending_manager.delete_pending(pending.id):
            pending_deleted += 1

    # 3) 清理 temp_upload 下所有文件和文件夹
    temp_upload_deleted = 0
    if temp_upload_dir.exists():
        temp_upload_deleted = _delete_dir_contents_and_count(temp_upload_dir)

    # 4) 清理 review 下除“被引用会话”外的文件夹和根目录文件
    review_deleted = 0
    if review_dir.exists():
        for item in list(review_dir.iterdir()):
            if item.is_file():
                item.unlink()
                review_deleted += 1
            elif item.name not in kept_review_sessions:
                review_deleted += _delete_tree_and_count(item)

    total_files_folders = temp_upload_deleted + review_deleted
    return {
        "pending_deleted": pending_deleted,
        "temp_upload_deleted": temp_upload_deleted,
        "review_deleted": review_deleted,
        "total_files_folders": total_files_folders,
    }


@bp.route('/settings/cache-cleanup', methods=['POST'])
@require_role_api('admin')
def settings_cache_cleanup():
    """管理员缓存清理：删除未提交的待处理记录（status=pending）、清空 temp_upload、清理 review 中未引用会话与文件。"""
    try:
        result = _run_cache_cleanup()
        return jsonify({
            "success": True,
            "message": "缓存清理完成。",
            "pending_deleted": result["pending_deleted"],
            "temp_upload_deleted": result["temp_upload_deleted"],
            "review_deleted": result["review_deleted"],
            "total_files_folders": result["total_files_folders"],
        })
    except Exception as e:
        logger.error("缓存清理失败: %s", e, exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@bp.route('/settings/ocr-status', methods=['GET'])
@require_role_api('admin')
def settings_ocr_status():
    """获取 OCR 供应商状态：当前使用的高精度供应商、各供应商可用/禁用及故障理由。"""
    try:
        from app.utils import get_doc_rec_context
        from config.loader import get_config

        config_loader = get_config()
        app_config = config_loader.load_config()
        ocr_providers = app_config.get('ocr', {}).get('providers', {})
        default_ocr = app_config.get('ocr', {}).get('default_provider', '')

        doc_rec_context = get_doc_rec_context()
        engine = doc_rec_context.extract_framework.ocr_engine
        status_mgr = engine.get_status_manager()
        disabled = status_mgr.get_disabled_providers()
        current_effective = engine.get_current_effective_precise_provider_name()
        precise_order = engine.get_precise_order()

        all_providers = []
        for name, conf in ocr_providers.items():
            is_precise = conf.get('is_precise', True) is True
            info = disabled.get(name, {})
            all_providers.append({
                'name': name,
                'is_precise': is_precise,
                'disabled': name in disabled,
                'disabled_reason': info.get('reason', ''),
                'disabled_at': info.get('disabled_at', ''),
            })

        return jsonify({
            'success': True,
            'current_effective_provider': current_effective,
            'default_provider': default_ocr,
            'precise_order': precise_order,
            'all_providers': all_providers,
        })
    except Exception as e:
        logger.error("获取 OCR 状态失败: %s", e, exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/settings/ocr-provider/reenable', methods=['POST'])
@require_role_api('admin')
def settings_ocr_provider_reenable():
    """重新启用某 OCR 供应商（清除禁用状态）。"""
    try:
        from app.utils import get_doc_rec_context

        data = request.get_json() or {}
        provider = (data.get('provider') or '').strip()
        if not provider:
            return jsonify({'success': False, 'message': '请提供 provider'}), 400

        doc_rec_context = get_doc_rec_context()
        engine = doc_rec_context.extract_framework.ocr_engine
        engine.get_status_manager().clear_disabled(provider)
        return jsonify({'success': True, 'message': f'已重新启用供应商: {provider}'})
    except Exception as e:
        logger.error("重新启用 OCR 供应商失败: %s", e, exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/settings/ocr-provider/disable', methods=['POST'])
@require_role_api('admin')
def settings_ocr_provider_disable():
    """手动禁用某 OCR 供应商（写入运行时状态，引擎将跳过该供应商）。"""
    try:
        from app.utils import get_doc_rec_context
        from config.loader import get_config

        data = request.get_json() or {}
        provider = (data.get('provider') or '').strip()
        if not provider:
            return jsonify({'success': False, 'message': '请提供 provider'}), 400

        config_loader = get_config()
        app_config = config_loader.load_config()
        if provider not in app_config.get('ocr', {}).get('providers', {}):
            return jsonify({'success': False, 'message': f'供应商 {provider} 不在配置中'}), 400

        reason = (data.get('reason') or '').strip() or '管理员手动禁用'

        doc_rec_context = get_doc_rec_context()
        engine = doc_rec_context.extract_framework.ocr_engine
        engine.get_status_manager().mark_disabled(provider, reason)
        return jsonify({'success': True, 'message': f'已禁用供应商: {provider}'})
    except Exception as e:
        logger.error("禁用 OCR 供应商失败: %s", e, exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/settings/ocr-provider/set-current', methods=['POST'])
@require_role_api('admin')
def settings_ocr_provider_set_current():
    """将某 OCR 供应商设为当前默认（写 settings.json 并清除该供应商禁用状态）。"""
    try:
        import json
        from app.utils import get_doc_rec_context
        from config.loader import get_config

        data = request.get_json() or {}
        provider = (data.get('provider') or '').strip()
        if not provider:
            return jsonify({'success': False, 'message': '请提供 provider'}), 400

        config_loader = get_config()
        app_config = config_loader.load_config()
        if provider not in app_config.get('ocr', {}).get('providers', {}):
            return jsonify({'success': False, 'message': f'供应商 {provider} 不在配置中'}), 400

        settings_path = config_loader.config_path
        if not settings_path.exists():
            return jsonify({'success': False, 'message': '配置文件 settings.json 不存在'}), 404

        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
            content = getattr(config_loader, '_strip_json_comments', lambda x: x)(content)
            settings_config = json.loads(content)
        if 'ocr' not in settings_config:
            settings_config['ocr'] = {}
        settings_config['ocr']['default_provider'] = provider
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings_config, f, ensure_ascii=False, indent=2)

        config_loader.reload()
        from app.utils import reset_doc_rec_context
        reset_doc_rec_context()

        doc_rec_context = get_doc_rec_context()
        engine = doc_rec_context.extract_framework.ocr_engine
        engine.get_status_manager().clear_disabled(provider)

        return jsonify({'success': True, 'message': f'已设为当前默认供应商: {provider}'})
    except Exception as e:
        logger.error("设为当前 OCR 供应商失败: %s", e, exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/settings/save', methods=['POST'])
@require_role_api('admin')
def settings_save():
    """保存系统设置"""
    try:
        from pathlib import Path
        import json
        from config.loader import get_config

        data = request.get_json()
        default_ocr = data.get('default_ocr_provider', '')
        default_llm = data.get('default_llm_provider', '')
        
        # 获取 API Keys
        ocr_keys = data.get('ocr_keys', {})
        llm_keys = data.get('llm_keys', {})

        root_path = Path(current_app.root_path).parent
        
        # 1. 更新 settings.json (默认供应商)
        config_loader = get_config()
        settings_path = config_loader.config_path
        
        if settings_path.exists():
            try:
                # 读取现有配置
                with open(settings_path, 'r', encoding='utf-8') as f:
                    # 使用 ConfigLoader 的去注释方法读取
                    content = f.read()
                    content = config_loader._strip_json_comments(content)
                    settings_config = json.loads(content)
                
                # 更新默认供应商
                if default_ocr and 'ocr' in settings_config:
                    settings_config['ocr']['default_provider'] = default_ocr
                if default_llm and 'llm' in settings_config:
                    settings_config['llm']['default_provider'] = default_llm
                
                # 保存 settings.json
                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump(settings_config, f, ensure_ascii=False, indent=2)
                # 使新默认供应商立即生效
                config_loader.reload()
                if default_ocr or default_llm:
                    from app.utils import reset_doc_rec_context
                    reset_doc_rec_context()
            except Exception as e:
                logger.error(f"保存 settings.json 失败: {e}")
                return jsonify({'success': False, 'message': f'保存 settings.json 失败: {str(e)}'}), 500
        else:
            return jsonify({'success': False, 'message': '配置文件 settings.json 不存在'}), 404

        # 2. 更新 apikey.json (API Keys)，仅更新非空 Key，避免空串覆盖已有配置
        apikey_dir = root_path / 'apikey'
        apikey_path = apikey_dir / 'apikey.json'
        
        # 确保目录存在
        if not apikey_dir.exists():
            apikey_dir.mkdir(parents=True, exist_ok=True)
            
        # 读取现有 Keys 或初始化
        user_keys = {"ocr": {}, "llm": {}, "pdf": {}}
        if apikey_path.exists():
            try:
                with open(apikey_path, 'r', encoding='utf-8') as f:
                    user_keys = json.load(f)
            except Exception:
                pass
        
        # 更新 Keys：仅写入非空值，避免未填写的输入框用空串覆盖已有 Key
        if 'ocr' not in user_keys:
            user_keys['ocr'] = {}
        if 'llm' not in user_keys:
            user_keys['llm'] = {}
        for k, v in (ocr_keys or {}).items():
            if v and isinstance(v, str) and v.strip():
                user_keys['ocr'][k] = v.strip()
        for k, v in (llm_keys or {}).items():
            if v and isinstance(v, str) and v.strip():
                user_keys['llm'][k] = v.strip()

        # 保存 apikey.json
        try:
            with open(apikey_path, 'w', encoding='utf-8') as f:
                json.dump(user_keys, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存 apikey.json 失败: {e}")
            return jsonify({'success': False, 'message': f'保存 API Keys 失败: {str(e)}'}), 500
            
        logger.info(f"系统设置已保存")
        return jsonify({'success': True, 'message': '设置保存成功'})

    except Exception as e:
        logger.error(f"保存设置失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500


@bp.route('/settings/auto-archive/update', methods=['POST'])
@require_role_api('admin')
def auto_archive_settings_update():
    """保存自动归档设置"""
    try:
        from pathlib import Path
        import json
        from config.loader import get_config

        data = request.get_json()

        # 获取配置文件路径
        config_loader = get_config()
        settings_path = config_loader.config_path

        if not settings_path.exists():
            return jsonify({'success': False, 'message': '配置文件 settings.json 不存在'}), 404

        # 读取现有配置
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
            content = config_loader._strip_json_comments(content)
            settings_config = json.loads(content)

        # 更新自动归档配置
        if 'auto_archive' not in settings_config:
            settings_config['auto_archive'] = {}

        settings_config['auto_archive']['award_valid'] = data.get('award_valid', False)
        settings_config['auto_archive']['award_invalid'] = data.get('award_invalid', False)
        settings_config['auto_archive']['patent_valid'] = data.get('patent_valid', False)
        settings_config['auto_archive']['patent_invalid'] = data.get('patent_invalid', False)
        settings_config['auto_archive']['software_valid'] = data.get('software_valid', False)
        settings_config['auto_archive']['software_invalid'] = data.get('software_invalid', False)
        settings_config['auto_archive']['innovation'] = data.get('innovation', False)
        settings_config['auto_archive']['other'] = data.get('other', False)

        # 保存配置
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings_config, f, ensure_ascii=False, indent=2)

        # 清除ConfigLoader缓存，确保后续读取到最新配置
        config_loader.reload()

        # 立即同步配置到数据库，确保配置立即生效
        from backend.models.auto_archive_config import AutoArchiveConfigManager
        db_path = config_loader.get_path("database", "competitions_db")
        auto_archive_config_manager = AutoArchiveConfigManager(db_path)
        _sync_auto_archive_config_from_settings(config_loader, auto_archive_config_manager)

        logger.info(f"自动归档设置已保存并同步到数据库")
        return jsonify({'success': True, 'message': '自动归档设置保存成功'})

    except Exception as e:
        logger.error(f"保存自动归档设置失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500

