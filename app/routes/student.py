"""
学生路由
"""
import json
import logging
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for, Response
from app.auth import require_user_type
from app.utils import get_app_context_instance
from app.routes.user_common import register_common_routes, get_profile_data_common, _parse_skills
from app.routes.file_import_helpers import get_data_import_types
from app.routes.admin_achievement import _get_review_service

logger = logging.getLogger(__name__)
bp = Blueprint('student', __name__)

# 注册共同路由（跳过 dashboard 和 achievements，使用自定义路由）
register_common_routes(bp, 'student', skip_routes=['dashboard', 'achievements'])

# 自定义仪表板路由，传递技能标签数据
@bp.route('/')
@bp.route('/dashboard')
@require_user_type('student')
def dashboard():
    """学生仪表板页面"""
    # 检查是否需要强制修改密码
    if session.get('needs_password_change'):
        return redirect(url_for('student.profile', tab='password'))

    try:
        import sqlite3
        user_id = session.get('user_id')
        if not user_id:
            return render_template('student/dashboard_ref.html', skills=[], laboratories=[], award_count=0, innovation_count=0,
                                 patents=[], software_list=[])

        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        teacher_manager = app_context.get_teacher_manager()
        innovation_manager = app_context.get_innovation_project_manager()
        laboratory_manager = app_context.get_laboratory_manager()
        patent_manager = app_context.get_patent_manager()
        software_manager = app_context.get_software_copyright_manager()

        # 获取学生信息
        student = student_manager.get_student_by_student_id(user_id)
        if not student:
            return render_template('student/dashboard_ref.html', skills=[], laboratories=[], award_count=0, innovation_count=0,
                                 patents=[], software_list=[])

        # 解析技能标签
        skills = _parse_skills(student.skills)

        # 获取学生参加的实验室
        laboratories = []
        conn = sqlite3.connect(laboratory_manager.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT laboratory_id FROM laboratory_students WHERE student_id = ?", (student.id,))
        lab_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        for lab_id in lab_ids:
            lab = laboratory_manager.get_laboratory_by_id(lab_id)
            if lab:
                laboratories.append(lab)

        # 获取奖状（学生作为获奖者的奖状）
        awards = []
        conn = sqlite3.connect(award_manager.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT award_id FROM award_student_winners WHERE student_id = ?", (student.id,))
        award_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        for award_id in award_ids:
            award = award_manager.get_award_by_id(award_id)
            if award:
                # 刷新关联数据
                award.refresh_associations(competition_manager, student_manager, teacher_manager)
                awards.append(award)
        award_count = len(awards)

        # 获取大创项目（学生作为负责人或成员）
        innovation_projects = []
        innovation_count = 0
        if innovation_manager:
            from backend.models.innovation_project import InnovationProjectFilter
            all_innovation = innovation_manager.query_projects(InnovationProjectFilter()) or []
            for p in all_innovation:
                is_member = False
                if (p.student_leader_id and p.student_leader_id == student.student_id) or (p.student_leader_name and p.student_leader_name.strip() == (student.name or '').strip()):
                    is_member = True
                elif p.other_members and (student.name or '') in p.other_members:
                    is_member = True

                if is_member:
                    innovation_projects.append(p)
                    innovation_count += 1

        # 学生作为提交者的专利
        patents = []
        if patent_manager:
            from backend.models.patent import PatentFilter
            pf = PatentFilter(submitter_type='student', submitter_id=student.id)
            patents = patent_manager.query_patents(pf) or []

        # 学生作为提交者的软著
        software_list = []
        if software_manager:
            from backend.models.software_copyright import SoftwareCopyrightFilter
            sf = SoftwareCopyrightFilter(submitter_type='student', submitter_id=student.id)
            software_list = software_manager.query_copyrights(sf) or []

        return render_template('student/dashboard_ref.html',
                             skills=skills,
                             laboratories=laboratories,
                             award_count=award_count,
                             innovation_count=innovation_count,
                             skills_count=len(skills) if skills else 0,
                             student=student,
                             awards=awards,
                             innovation_projects=innovation_projects,
                             patents=patents,
                             software_list=software_list,
                             competitions=competition_manager.competitions if hasattr(competition_manager, 'competitions') else [])
    except Exception as e:
        import traceback
        logger.error(f"获取学生仪表板数据失败: {traceback.format_exc()}")
        return render_template('student/dashboard_ref.html',
                             skills=[],
                             laboratories=[],
                             award_count=0,
                             innovation_count=0,
                             skills_count=0,
                             student=None,
                             awards=[],
                             innovation_projects=[],
                             patents=[],
                             software_list=[],
                             competitions=[])


def _get_student_export_data():
    """获取当前登录学生的全部个人成果数据，用于仪表盘与导出。返回 (student, awards, patents, software_list, innovation_projects) 或 None。"""
    import sqlite3
    user_id = session.get('user_id')
    if not user_id:
        return None
    app_context = get_app_context_instance()
    student_manager = app_context.get_student_manager()
    award_manager = app_context.get_award_manager()
    competition_manager = app_context.get_competition_manager()
    teacher_manager = app_context.get_teacher_manager()
    student = student_manager.get_student_by_student_id(user_id)
    if not student:
        return None
    conn = sqlite3.connect(award_manager.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT award_id FROM award_student_winners WHERE student_id = ?", (student.id,))
    award_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    awards = []
    if award_ids:
        for award in award_manager.awards:
            if award.id in award_ids:
                award.refresh_associations(competition_manager, student_manager, teacher_manager)
                awards.append(award)
    patents = []
    patent_manager = app_context.get_patent_manager()
    if patent_manager:
        from backend.models.patent import PatentFilter
        patents = patent_manager.query_patents(PatentFilter(submitter_type='student', submitter_id=student.id)) or []
    software_list = []
    software_manager = app_context.get_software_copyright_manager()
    if software_manager:
        from backend.models.software_copyright import SoftwareCopyrightFilter
        software_list = software_manager.query_copyrights(SoftwareCopyrightFilter(submitter_type='student', submitter_id=student.id)) or []
    innovation_projects = []
    innovation_manager = app_context.get_innovation_project_manager()
    if innovation_manager:
        from backend.models.innovation_project import InnovationProjectFilter
        all_innovation = innovation_manager.query_projects(InnovationProjectFilter()) or []
        for p in all_innovation:
            if (p.student_leader_id and p.student_leader_id == student.student_id) or (p.student_leader_name and p.student_leader_name.strip() == (student.name or '').strip()):
                innovation_projects.append(p)
                continue
            if p.other_members and (student.name or '') in p.other_members:
                innovation_projects.append(p)
    return (student, awards, patents, software_list, innovation_projects)


@bp.route('/export_all')
@require_user_type('student')
def export_all():
    """导出全部个人成果为 zip（HTML + 佐证材料）。"""
    if session.get('needs_password_change'):
        return redirect(url_for('student.profile', tab='password'))
    data = _get_student_export_data()
    if not data:
        flash('无法获取个人成果数据', 'error')
        return redirect(url_for('student.dashboard'))
    student, awards, patents, software_list, innovation_projects = data
    try:
        from backend.utils.report import generate_personal_export_student
        from datetime import datetime
        from urllib.parse import quote
        zip_bytes = generate_personal_export_student(
            student=student,
            awards=awards,
            patents=patents,
            software_list=software_list,
            innovation_projects=innovation_projects,
        )
        name_safe = (student.name or student.student_id or 'student').replace('/', '_').replace('\\', '_')
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"个人成果_{name_safe}_{date_str}.zip"
        try:
            encoded = quote(filename, safe='')
            content_disp = f"attachment; filename*=UTF-8''{encoded}"
        except Exception:
            content_disp = f'attachment; filename="{filename}"'
        return Response(
            zip_bytes,
            mimetype='application/zip',
            headers={'Content-Disposition': content_disp},
        )
    except Exception as e:
        import traceback
        logger.error(f"学生导出全部失败: {traceback.format_exc()}")
        flash(f'导出失败: {str(e)}', 'error')
        return redirect(url_for('student.dashboard'))


@bp.route('/achievements')
@require_user_type('student')
def achievements():
    """学生成果页面：仅显示有关联数据的类型（奖状、专利、大创、软著）。"""
    if session.get('needs_password_change'):
        return redirect(url_for('student.profile', tab='password'))
    try:
        import sqlite3
        from datetime import datetime

        user_id = session.get('user_id')
        if not user_id:
            return render_template('student/achievements_ref.html', error='用户未登录',
                                 total_awards=0, awards=[], patents=[], software_list=[], innovation_projects=[])

        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        teacher_manager = app_context.get_teacher_manager()

        student = student_manager.get_student_by_student_id(user_id)
        if not student:
            return render_template('student/achievements_ref.html', error='学生信息不存在',
                                 total_awards=0, awards=[], patents=[], software_list=[], innovation_projects=[])

        # 学生作为获奖者的奖状
        conn = sqlite3.connect(award_manager.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT award_id FROM award_student_winners WHERE student_id = ?", (student.id,))
        award_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        awards = []
        if award_ids:
            for award in award_manager.awards:
                if award.id in award_ids:
                    award.refresh_associations(competition_manager, student_manager, teacher_manager)
                    awards.append(award)

        total_awards = len(awards)

        # 学生作为提交者的专利
        patents = []
        patent_manager = app_context.get_patent_manager()
        if patent_manager:
            from backend.models.patent import PatentFilter
            pf = PatentFilter(submitter_type='student', submitter_id=student.id)
            patents = patent_manager.query_patents(pf) or []

        # 学生作为提交者的软著
        software_list = []
        software_manager = app_context.get_software_copyright_manager()
        if software_manager:
            from backend.models.software_copyright import SoftwareCopyrightFilter
            sf = SoftwareCopyrightFilter(submitter_type='student', submitter_id=student.id)
            software_list = software_manager.query_copyrights(sf) or []

        # 学生作为负责人或成员的大创
        innovation_projects = []
        innovation_manager = app_context.get_innovation_project_manager()
        if innovation_manager:
            from backend.models.innovation_project import InnovationProjectFilter
            all_innovation = innovation_manager.query_projects(InnovationProjectFilter()) or []
            for p in all_innovation:
                if (p.student_leader_id and p.student_leader_id == student.student_id) or (p.student_leader_name and p.student_leader_name.strip() == (student.name or '').strip()):
                    innovation_projects.append(p)
                    continue
                if p.other_members and (student.name or '') in p.other_members:
                    innovation_projects.append(p)

        return render_template('student/achievements_ref.html',
                             total_awards=total_awards,
                             awards=awards[:20],
                             competitions=competition_manager.competitions if hasattr(competition_manager, 'competitions') else [],
                             patents=patents,
                             software_list=software_list,
                             innovation_projects=innovation_projects)
    except Exception as e:
        import traceback
        logger.error(f"获取学生成果数据失败: {traceback.format_exc()}")
        return render_template('student/achievements_ref.html', error=f'获取数据失败: {str(e)}',
                             total_awards=0, awards=[], patents=[], software_list=[], innovation_projects=[])


@bp.route('/award/<int:award_id>')
@require_user_type('student')
def award_detail(award_id):
    """学生查看自己某条获奖的完整详情（只读）。"""
    import sqlite3
    user_id = session.get('user_id')
    app_context = get_app_context_instance()
    award_manager = app_context.get_award_manager()
    competition_manager = app_context.get_competition_manager()
    student_manager = app_context.get_student_manager()
    teacher_manager = app_context.get_teacher_manager()

    student = student_manager.get_student_by_student_id(user_id) if user_id else None
    if not student:
        flash('学生信息不存在', 'error')
        return redirect(url_for('student.achievements'))

    # 权限：该获奖必须属于当前学生（通过 award_student_winners 关联表）
    conn = sqlite3.connect(award_manager.db_path)
    belongs = conn.execute(
        "SELECT 1 FROM award_student_winners WHERE award_id=? AND student_id=? LIMIT 1",
        (award_id, student.id)
    ).fetchone()
    conn.close()
    if not belongs:
        flash('无权查看该获奖记录', 'error')
        return redirect(url_for('student.achievements'))

    award = award_manager.get_award_by_id(award_id)
    if not award:
        flash('获奖记录不存在', 'error')
        return redirect(url_for('student.achievements'))

    award.refresh_associations(competition_manager, student_manager, teacher_manager)
    return render_template('student/award_detail.html', award=award)


@bp.route('/profile/data')
@require_user_type('student')
def get_profile_data():
    """获取学生个人信息数据"""
    return get_profile_data_common('student')

@bp.route('/profile/update', methods=['POST'])
@require_user_type('student')
def update_profile():
    """更新学生个人信息"""
    try:
        user_id = session.get('user_id')
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()

        # 根据学号获取学生信息
        student = student_manager.get_student_by_student_id(user_id)
        if not student:
            return jsonify({'success': False, 'message': '学生信息不存在'}), 404

        # 获取请求数据
        data = request.get_json()

        # 更新可修改字段（学生只能修改QQ、手机号和技能标签）
        update_data = {}
        
        logger.info(f"正在通过个人中心更新学生信息: ID={student.id}, 学号={student.student_id}")

        if 'qq' in data:
            update_data['qq'] = data['qq']
        if 'phone' in data:
            update_data['phone'] = data['phone']
        if 'skills' in data:
            # 将技能标签列表转换为JSON字符串
            skills = data['skills']
            if isinstance(skills, list):
                update_data['skills'] = json.dumps(skills, ensure_ascii=False)
            else:
                update_data['skills'] = skills

        # 执行更新（M1 后半②：视图化后旧表不可写，直写 users 真源）
        if update_data:
            from backend.orm.repositories import UserRepository
            UserRepository.update_profile(student.student_id, **update_data)
            logger.info(f"学生信息更新成功: ID={student.id}")

        return jsonify({
            'success': True,
            'message': '个人信息更新成功'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


# ==================== 成果提交相关路由 ====================

@bp.route('/achievement-submit')
@require_user_type('student')
def achievement_submit():
    """成果提交页面（包含文件导入和提交记录）"""
    # 检查是否需要强制修改密码
    if session.get('needs_password_change'):
        return redirect(url_for('student.profile', tab='password'))

    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        pending_manager = app_context.get_pending_achievement_manager()

        # 获取当前学生信息
        user_id = session.get('user_id')
        student = student_manager.get_student_by_student_id(user_id)
        if not student:
            flash('学生信息不存在', 'error')
            return render_template('student/submissions.html', submissions=[], all_submissions=[], total_count=0)

        # 全部提交记录（用于统计）；最近 10 条用于首页列表展示
        all_submissions = pending_manager.get_pending_by_submitter('student', student.id)
        recent_submissions = all_submissions[:10]

        return render_template('student/submissions.html',
                             submissions=recent_submissions,
                             all_submissions=all_submissions,
                             total_count=len(all_submissions))

    except Exception as e:
        flash(f'加载提交记录失败: {e}', 'error')
        return render_template('student/submissions.html', submissions=[], all_submissions=[], total_count=0)


@bp.route('/achievement-submit/list')
@require_user_type('student')
def achievement_submit_list():
    """提交记录列表页面（显示所有记录）"""
    # 检查是否需要强制修改密码
    if session.get('needs_password_change'):
        return redirect(url_for('student.profile', tab='password'))

    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        pending_manager = app_context.get_pending_achievement_manager()

        # 获取当前学生信息
        user_id = session.get('user_id')
        student = student_manager.get_student_by_student_id(user_id)
        if not student:
            flash('学生信息不存在', 'error')
            return render_template('student/submissions_list.html', submissions=[])

        # 获取所有提交记录
        submissions = pending_manager.get_pending_by_submitter('student', student.id)

        return render_template('student/submissions_list.html', submissions=submissions)

    except Exception as e:
        flash(f'加载提交记录失败: {e}', 'error')
        return render_template('student/submissions_list.html', submissions=[])


# 保持向后兼容
@bp.route('/submissions')
@require_user_type('student')
def my_submissions():
    """向后兼容：重定向到成果提交页面"""
    return redirect(url_for('student.achievement_submit'))


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


# ==================== 文件上传相关路由 ====================
# 注意：由于代码较长，文件上传逻辑与教师路由相同，但submitter_type为'student'
# 具体实现请参考 app/routes/teacher.py 中的对应路由
# 这里先添加基本路由，完整实现需要从教师路由复制并修改submitter_type

@bp.route('/achievement-submit/progress')
@require_user_type('student')
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
@require_user_type('student')
def achievement_submit_upload():
    """处理文件上传（学生版薄壳——共享逻辑在 user_common.shared_achievement_submit_upload，M2）"""
    from app.routes.user_common import shared_achievement_submit_upload
    from app.utils import get_app_context_instance
    app_context = get_app_context_instance()
    student_manager = app_context.get_student_manager()
    user_id = session.get('user_id')
    student = student_manager.get_student_by_student_id(user_id)
    return shared_achievement_submit_upload(student, 'student', 'student')
@bp.route('/achievement-submit/manual/upload', methods=['POST'])
@require_user_type('student')
def achievement_submit_manual_upload():
    """手动导入：上传单个文件到临时目录，返回 file_path（与学生自动导入共用 results 流程）"""
    from app.routes.manual_import_helpers import handle_manual_upload
    ok, file_path, err = handle_manual_upload()
    if not ok:
        return jsonify({'success': False, 'message': err or '上传失败'}), 400 if err else 500
    return jsonify({'success': True, 'file_path': file_path})


@bp.route('/achievement-submit/manual/parse', methods=['POST'])
@require_user_type('student')
def achievement_submit_manual_parse():
    """手动导入：按指定类型解析文件，写入 pending 并返回完整解析结果（与教师端结构一致，供内联表单与奖状图片展示）"""
    try:
        from app.routes.manual_import_helpers import handle_manual_parse, build_winner_supervisor_status
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        user_id = session.get('user_id')
        student = student_manager.get_student_by_student_id(user_id) if user_id else None
        if not student:
            return jsonify({'success': False, 'message': '学生信息不存在'}), 403
        ok, session_id, achievement_type, err, path_for_db, achievement_data, ocr_text, template_type = handle_manual_parse(
            submitter_type='student',
            submitter_id=student.id,
        )
        if not ok:
            return jsonify({'success': False, 'message': err or '解析失败'}), 400
        redirect_url = url_for(
            'student.achievement_submit_results',
            session_id=session_id,
            tab=achievement_type,
            sub_tab='valid',
        )
        winner_status_list, supervisor_status_list = build_winner_supervisor_status(
            achievement_type, achievement_data or {}, app_context
        )
        return jsonify({
            'success': True,
            'redirect_url': redirect_url,
            'data': achievement_data or {},
            'template_type': template_type,
            'session_id': session_id,
            'ocr_text': ocr_text or '',
            'file_path': path_for_db,
            'winner_status_list': winner_status_list,
            'supervisor_status_list': supervisor_status_list,
        })
    except Exception as e:
        logger.exception("student manual parse failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/achievement-submit/manual/submit', methods=['POST'])
@require_user_type('student')
def achievement_submit_manual_submit():
    """手动导入：更新 pending 记录并提交（学生提交审核）"""
    try:
        data = request.get_json() or {}
        achievement_type = (data.get('achievement_type') or '').strip().lower()
        achievement_data = data.get('achievement_data')
        submitter_type = data.get('submitter_type', 'student')
        session_id = data.get('session_id')

        if not achievement_type:
            return jsonify({'success': False, 'message': '缺少 achievement_type'}), 400
        if achievement_data is None:
            return jsonify({'success': False, 'message': '缺少 achievement_data'}), 400
        if not session_id:
            return jsonify({'success': False, 'message': '缺少 session_id'}), 400

        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()

        from backend.models.pending_achievement import PendingAchievementFilter
        filter_obj = PendingAchievementFilter(session_id=session_id)
        pending_list = pending_manager.query_pending(filter_obj)

        if not pending_list:
            return jsonify({'success': False, 'message': '未找到对应的记录'}), 404

        pending_item = pending_list[0]

        if pending_item.status == 'submit':
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

        success = pending_manager.update(
            pending_item=pending_item,
            achievement_type=achievement_type,
            achievement_data=achievement_data
        )
        if not success:
            return jsonify({'success': False, 'message': '更新 pending 记录失败'}), 500

        from backend.services.review_service import ReviewService
        student_manager = app_context.get_student_manager()
        user_id = session.get('user_id')
        student = student_manager.get_student_by_student_id(user_id) if user_id else None
        student_id = student.id if student else 0

        review_service = ReviewService(
            pending_manager=pending_manager,
            review_log_manager=app_context.get_review_log_manager(),
            award_manager=app_context.get_award_manager(),
            patent_manager=app_context.get_patent_manager(),
            software_manager=app_context.get_software_copyright_manager(),
            innovation_manager=app_context.get_innovation_project_manager(),
            other_file_manager=app_context.get_other_file_manager(),
            laboratory_manager=app_context.get_laboratory_manager(),
            student_manager=student_manager,
            teacher_manager=app_context.get_teacher_manager(),
            competition_manager=app_context.get_competition_manager(),
            auto_archive_config_manager=app_context.get_auto_archive_config_manager()
        )
        result = review_service.submit_achievement(pending_item.id, submitter_type, student_id)

        if not result.success:
            return jsonify({'success': False, 'message': result.error or '提交失败'}), 500

        if result.action == 'approved':
            message = '已归档，数据已成功导入主数据库'
        elif result.action == 'auto_archive_started':
            message = '已提交，系统将自动归档'
        else:
            message = '提交成功，等待审核'

        logger.info(f"[学生手动导入提交] pending_id={pending_item.id}, session_id={session_id}, 类型={achievement_type}, action={result.action}")

        return jsonify({
            'success': True,
            'message': message,
            'pending_id': pending_item.id,
            'action': result.action
        })
    except Exception as e:
        logger.exception("student manual submit failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/achievement-submit/results')
@require_user_type('student')
def achievement_submit_results():
    """文件导入结果处理页面（学生版本，复用教师逻辑）"""
    from app.routes.file_import_helpers import (
        get_file_import_params,
        calculate_type_stats,
        adjust_tab_and_status,
        query_pending_items,
        get_current_item,
        get_all_reference_data,
        process_validation_result,
        process_award_item,
        process_non_award_item,
        get_type_names,
    )

    try:
        # 获取参数
        result = get_file_import_params()
        if result[0] is None:
            return redirect(url_for('student.achievement_submit'))
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

        # 处理当前项
        if current_item and tab_type == 'award':
            award_data = process_award_item(
                current_item, app_context, all_competitions,
                all_teachers, all_students, all_laboratories
            )

            validation_result = current_item.get_validation_result()
            field_errors, is_valid = process_validation_result(validation_result)
            
            data = current_item.get_achievement_data()
            file_path = data.get('file_path') if isinstance(data, dict) else None
            file_url = url_for('student.achievement_submit_file', file_path=file_path.replace('\\', '/')) if file_path else None
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
            preview_image_url = url_for('student.achievement_submit_file', file_path=preview_image_path.replace('\\', '/')) if preview_image_path else None

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
                                  route_prefix='student',
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
                file_url = url_for('student.achievement_submit_file', file_path=file_path.replace('\\', '/'))
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
                                  route_prefix='student',
                                  all_laboratories=all_laboratories,
                                  **non_award_data)

    except Exception as e:
        logger.error(f"加载文件导入结果失败: {e}", exc_info=True)
        flash(f'加载结果失败: {str(e)}', 'error')
        return redirect(url_for('student.achievement_submit'))


@bp.route('/achievement-submit/award-submit/<session_id>/<int:index>', methods=['POST'])
@require_user_type('student')
def file_import_award_submit(session_id, index):
    """学生端：提交奖状后跳转到下一项或返回成果提交页。与 admin 逻辑一致，但使用 student 身份并重定向到学生端。"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        student_manager = app_context.get_student_manager()

        user_id = session.get('user_id')
        student = student_manager.get_student_by_student_id(user_id) if user_id else None
        if not student:
            flash('学生信息不存在', 'error')
            return redirect(url_for('student.achievement_submit'))

        tab_type = request.form.get('tab_type', 'award')
        status = request.form.get('status', 'valid')
        pending_id_raw = request.form.get('pending_id')
        try:
            pending_id = int(pending_id_raw) if pending_id_raw else None
        except (ValueError, TypeError):
            pending_id = None

        def _redirect_results(**kwargs):
            return redirect(url_for('student.achievement_submit_results', session_id=session_id, **kwargs))

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
            logger.info(
                "[学生提交奖状] 准备写入数据库: pending_id=%s, session_id=%s, 表单字段=%s, achievement_data_keys=%s, competition_name=%s",
                item_id, session_id, list(form_data.keys()),
                list(data.keys()) if isinstance(data, dict) else None,
                data.get("competition_name") if isinstance(data, dict) else None,
            )
            pending_manager.update(
                pending_item=current_item,
                achievement_data=data,
                status=current_item.status
            )

        review_service = _get_review_service(app_context)
        result = review_service.submit_achievement(current_item.id, 'student', student.id)
        # 提交后从数据库重新读取，确认写入内容
        after_item = pending_manager.get_by_id(current_item.id)
        if after_item:
            after_data = after_item.get_achievement_data()
            logger.info(
                "[学生提交奖状] 提交后数据库状态: pending_id=%s, status=%s, achievement_data_keys=%s, competition_name=%s",
                after_item.id, after_item.status,
                list(after_data.keys()) if isinstance(after_data, dict) else None,
                after_data.get("competition_name") if isinstance(after_data, dict) else None,
            )
        else:
            logger.warning("[学生提交奖状] 提交后无法读取记录: pending_id=%s（可能已归档）", current_item.id)
        if result.action == 'auto_archive_started':
            flash('已提交，系统将自动归档', 'success')
        else:
            flash('已提交审核', 'success')

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
                flash('已提交审核', 'success')
                return redirect(url_for('student.achievement_submit'))
            else:
                return _redirect_results(tab=tab_type, sub_tab=status)

    except Exception as e:
        logger.error(f"提交奖状失败: {e}", exc_info=True)
        flash(f'提交失败: {str(e)}', 'error')
        _tab = request.form.get('tab_type', 'award')
        _sub = request.form.get('status', 'valid')
        return redirect(url_for('student.achievement_submit_results', session_id=session_id, tab=_tab, sub_tab=_sub, index=index))


@bp.route('/achievement-submit/withdraw/<int:pending_id>', methods=['POST'])
@require_user_type('student')
def withdraw_submission(pending_id):
    """学生撤回已提交待审核的记录（submit→pending），以便重新编辑后提交。"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        student_manager = app_context.get_student_manager()
        user_id = session.get('user_id')
        student = student_manager.get_student_by_student_id(user_id) if user_id else None
        pending = pending_manager.get_by_id(pending_id) if pending_id else None
        if not pending or not student:
            flash('记录不存在', 'error')
            return redirect(url_for('student.achievement_submit'))
        # 权限：仅本人已提交的记录可撤回
        if not (pending.submitter_type == 'student' and pending.submitter_id == student.id):
            flash('无权操作该记录', 'error')
            return redirect(url_for('student.achievement_submit'))
        if pending.status != 'submit':
            flash('仅"等待审核"的记录可撤回', 'error')
            return redirect(url_for('student.achievement_submit'))
        session_id = getattr(pending, 'session_id', None) or (pending.get_achievement_data() or {}).get('import_session_id')
        tab_type = pending.achievement_type or 'award'
        pending_manager.update(pending, status='pending')
        # P1-13 留痕：动作11=撤回
        try:
            from backend.utils.audit_logger import audit_log
            audit_log(11, pending_id, pending.achievement_type,
                      operator={"id": student.id, "code": str(student.student_id), "user_type": "student"})
        except Exception:
            pass
        flash('已撤回，可重新编辑并提交', 'success')
        return redirect(url_for('student.achievement_submit_results', session_id=session_id, tab=tab_type))
    except Exception as e:
        logger.error(f"撤回提交失败: {e}", exc_info=True)
        flash(f'撤回失败: {str(e)}', 'error')
        return redirect(url_for('student.achievement_submit'))


@bp.route('/api/competitions')
@require_user_type('student')
def api_competitions():
    """获取所有竞赛列表API（学生成果提交手动导入用）"""
    try:
        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()
        if hasattr(competition_manager, 'competitions'):
            competitions = competition_manager.competitions
        elif hasattr(competition_manager, '_competitions'):
            competitions = competition_manager._competitions
        else:
            competitions = []
        results = [{'id': c.id, 'name': c.name} for c in competitions]
        return jsonify({'success': True, 'competitions': results})
    except Exception as e:
        logger.error(f"获取竞赛列表失败: {e}")
        return jsonify({'success': False, 'competitions': [], 'error': str(e)}), 500


@bp.route('/api/teachers')
@require_user_type('student')
def api_teachers():
    """获取所有教师列表API（学生成果提交手动导入用）"""
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

        results = [
            {'id': t.id, 'teacher_id': t.teacher_id, 'name': t.name, 'laboratory_id': teacher_lab_map.get(t.id)}
            for t in teachers
        ]
        return jsonify({'success': True, 'teachers': results})
    except Exception as e:
        logger.error(f"获取教师列表失败: {e}")
        return jsonify({'success': False, 'teachers': [], 'error': str(e)}), 500


@bp.route('/api/laboratories')
@require_user_type('student')
def api_laboratories():
    """获取所有实验室列表API（学生成果提交手动导入与自动导入用）"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()
        if not laboratory_manager:
            return jsonify({'success': True, 'laboratories': []})
        if hasattr(laboratory_manager, 'get_all_laboratories'):
            laboratories = laboratory_manager.get_all_laboratories()
        elif hasattr(laboratory_manager, 'laboratories'):
            laboratories = laboratory_manager.laboratories
        elif hasattr(laboratory_manager, '_laboratories'):
            laboratories = laboratory_manager._laboratories
        else:
            laboratories = []
        results = [{'id': lab.id, 'name': lab.name} for lab in laboratories]
        return jsonify({'success': True, 'laboratories': results})
    except Exception as e:
        logger.error(f"获取实验室列表失败: {e}")
        return jsonify({'success': False, 'laboratories': [], 'error': str(e)}), 500


@bp.route('/api/students/search')
@require_user_type('student')
def api_students_search():
    """学生搜索API（成果表单填写获奖人用）。兼容 q 与 query 参数，与教师端一致。"""
    query = (request.args.get('q') or request.args.get('query') or '').strip()
    if not query:
        return jsonify({'success': True, 'students': []})
    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        students = student_manager.find_students_by_name(query)
        results = []
        for s in students[:10]:
            brief_parts = [s.student_id, s.major, s.grade]
            brief_desc = ' | '.join(p for p in brief_parts if p) or ''
            results.append({
                'id': s.id, 'student_id': s.student_id, 'name': s.name,
                'major': s.major, 'grade': s.grade, 'brief_desc': brief_desc,
                'display': f"({s.student_id})" if s.student_id else ''
            })
        return jsonify({'success': True, 'students': results})
    except Exception as e:
        logger.error(f"学生搜索失败: {e}")
        return jsonify({'success': False, 'students': [], 'error': str(e)}), 500


@bp.route('/achievement-submit/api/batch-discard', methods=['POST'])
@require_user_type('student')
def achievement_submit_api_batch_discard():
    """学生端批量放弃当前导入会话中指定类型/验证状态的记录，与管理员端逻辑一致但仅可放弃本人记录。"""
    try:
        app_context = get_app_context_instance()
        student_manager = app_context.get_student_manager()
        user_id = session.get('user_id')
        student = student_manager.get_student_by_student_id(user_id) if user_id else None
        if not student:
            return jsonify({'success': False, 'message': '学生信息不存在'}), 403

        submitter_type = 'student'
        submitter_id = student.id
        body = request.get_json() or {}
        achievement_type = body.get('type')
        session_id = body.get('session_id', '') or None
        validation_status = body.get('validation_status', 'all')
        pending_ids = body.get('pending_ids')
        if not achievement_type:
            return jsonify({'success': False, 'message': '缺少 type'}), 400

        pending_manager = app_context.get_pending_achievement_manager()
        from backend.models.pending_achievement import PendingAchievementFilter

        count = 0
        files_deleted = 0

        def _same_submitter(item, st: str, sid: int) -> bool:
            it = (getattr(item, 'submitter_type', None) or '').strip().lower()
            ii = getattr(item, 'submitter_id', None)
            try:
                ii = int(ii) if ii is not None else None
            except (TypeError, ValueError):
                pass
            return (it == (st or '').strip().lower()) and (ii == sid)

        if pending_ids and isinstance(pending_ids, list) and len(pending_ids) > 0:
            for pid in pending_ids:
                item = pending_manager.get_by_id(pid)
                if item and item.achievement_type == achievement_type:
                    if not _same_submitter(item, submitter_type, submitter_id):
                        continue
                    if achievement_type == 'innovation':
                        data = item.get_achievement_data() or {}
                        projects = data.get('projects') or []
                        project_count = len(projects) if isinstance(projects, list) else 1
                    else:
                        project_count = 1
                    result = pending_manager.safe_delete_with_file(item.id)
                    if result.get('success'):
                        count += project_count
                        if result.get('file_deleted'):
                            files_deleted += 1
                        # P1-13 留痕：动作10=放弃
                        try:
                            from backend.utils.audit_logger import audit_log
                            audit_log(10, item.id, item.achievement_type,
                                      operator={"id": submitter_id, "code": str(submitter_id), "user_type": submitter_type})
                        except Exception:
                            pass
            return jsonify({'success': True, 'count': count, 'files_deleted': files_deleted})

        query_status = 'pending' if session_id else 'submit'
        if achievement_type == 'other' and session_id:
            filter_obj = PendingAchievementFilter(
                achievement_type=achievement_type,
                status=None,
                import_session_id=session_id,
                limit=1000
            )
            filter_list = [filter_obj]
        else:
            filter_list = [
                PendingAchievementFilter(
                    achievement_type=achievement_type,
                    status=query_status,
                    import_session_id=session_id,
                    limit=1000
                )
            ]

        for filter_obj in filter_list:
            items = pending_manager.query_pending(filter_obj)
            items = [i for i in items if _same_submitter(i, submitter_type, submitter_id)]
            for item in items:
                if session_id:
                    if validation_status == 'valid' and not item.validation_passed():
                        continue
                    if validation_status == 'invalid' and item.validation_passed():
                        continue
                else:
                    if achievement_type not in ('other', 'innovation'):
                        if validation_status == 'valid' and not item.validation_passed():
                            continue
                        if validation_status == 'invalid' and item.validation_passed():
                            continue
                    elif achievement_type == 'other' and validation_status in ('image', 'file'):
                        from pathlib import Path
                        ext = (Path(getattr(item, 'file_path', None) or '').suffix or '').lower()
                        is_image = ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.jfif')
                        if validation_status == 'image' and not is_image:
                            continue
                        if validation_status == 'file' and is_image:
                            continue
                if achievement_type == 'innovation':
                    data = item.get_achievement_data() or {}
                    projects = data.get('projects') or []
                    project_count = len(projects) if isinstance(projects, list) else 1
                else:
                    project_count = 1
                result = pending_manager.safe_delete_with_file(item.id)
                if result.get('success'):
                    count += project_count
                    if result.get('file_deleted'):
                        files_deleted += 1

        return jsonify({'success': True, 'count': count, 'files_deleted': files_deleted})
    except Exception as e:
        logger.exception("student batch discard failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/achievement-submit/file/<path:file_path>')
@require_user_type('student')
def achievement_submit_file(file_path):
    """提供文件导入中的文件访问（学生版本）。路径为相对路径 temp_upload/... 或历史绝对路径，便于跨服务器部署。"""
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
        elif path_str.startswith('manual_import/') or path_str.startswith('manual_import\\'):
            # 手动导入文件：先试 unified temp_upload，再试 config temp_dir（与教师 file_preview 一致）
            full_path = (files_root / 'temp_upload' / path_str).resolve()
            if full_path.exists():
                allowed_prefix = temp_upload_prefix
            else:
                from config.loader import get_config
                base_temp_dir = get_config().get_path("temp_dir")
                if not base_temp_dir:
                    from flask import abort
                    abort(404)
                base_dir = Path(base_temp_dir).resolve()
                full_path = (base_dir / path_str).resolve()
                try:
                    full_path.relative_to(base_dir)
                except ValueError:
                    from flask import abort
                    abort(403)
                allowed_prefix = base_dir
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

