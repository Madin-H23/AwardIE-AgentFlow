"""
管理员 - 实验室管理路由
"""
import logging
import os
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, session

from app.auth import require_role, require_role_api, require_login, require_can_edit_laboratory, require_can_edit_laboratory_api
from backend.utils.users_sync import to_users_id
from config.loader import get_config
from app.utils import get_app_context_instance

logger = logging.getLogger(__name__)
bp = Blueprint('admin_laboratory', __name__)

@bp.route('/laboratories')
@require_role('admin')
def laboratories_list():
    """实验室列表页面"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        # 获取所有实验室
        all_labs = laboratory_manager.get_all_laboratories()

        # 为每个实验室计算统计信息
        labs_data = []
        for lab in all_labs:
            # 获取指导教师姓名列表
            instructor_names = [teacher.name for teacher in lab.instructors]

            labs_data.append({
                'lab': lab,
                'instructor_count': len(lab.instructors),
                'instructor_names': instructor_names,
                'student_count': len(lab.students),
                'assistant_count': len(lab.assistants),
            })

        return render_template('admin/laboratories/list.html', labs_data=labs_data)
    except Exception as e:
        import traceback
        flash(f'加载实验室列表失败: {str(e)}', 'error')
        if current_app.config.get('DEBUG'):
            flash(f'错误详情: {traceback.format_exc()}', 'error')
        return render_template('admin/laboratories/list.html', labs_data=[])

@bp.route('/laboratories/add', methods=['GET', 'POST'])
@bp.route('/laboratories/<int:lab_id>/edit', methods=['GET', 'POST'])
@require_can_edit_laboratory
def laboratory_edit(lab_id=None):
    """添加/编辑实验室"""
    app_context = get_app_context_instance()
    laboratory_manager = app_context.get_laboratory_manager()
    student_manager = app_context.get_student_manager()
    teacher_manager = app_context.get_teacher_manager()

    lab = None
    if lab_id:
        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            flash('实验室不存在', 'error')
            return redirect(url_for('admin_laboratory.laboratories_list'))

    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip() or None

            if not name:
                flash('实验室名称不能为空', 'error')
                all_students = student_manager.students if hasattr(student_manager, 'students') else []
                all_teachers = teacher_manager.teachers if hasattr(teacher_manager, 'teachers') else []
                return render_template('admin/laboratories/edit.html',
                                     lab=lab,
                                     all_students=all_students,
                                     all_teachers=all_teachers)

            # 处理封面图片上传
            cover_image = None
            if 'cover_image' in request.files:
                file = request.files['cover_image']
                if file and file.filename:
                    # 生成唯一文件名
                    import os
                    from werkzeug.utils import secure_filename
                    from datetime import datetime

                    filename = secure_filename(file.filename)
                    ext = os.path.splitext(filename)[1]
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    new_filename = f"lab_{lab_id or 'new'}_{timestamp}{ext}"

                    # 保存到static/images/laboratory_covers目录
                    static_folder = Path(current_app.static_folder)
                    upload_dir = static_folder / 'images' / 'laboratory_covers'
                    upload_dir.mkdir(parents=True, exist_ok=True)
                    file_path = upload_dir / new_filename
                    file.save(str(file_path))

                    # 保存相对路径
                    cover_image = f"images/laboratory_covers/{new_filename}"

            if lab_id:
                # 更新现有实验室
                lab.name = name
                lab.description = description
                if cover_image:
                    # 删除旧图片（如果存在）
                    if lab.cover_image:
                        static_folder = Path(current_app.static_folder)
                        old_path = static_folder / lab.cover_image
                        if old_path.exists():
                            try:
                                old_path.unlink()
                            except:
                                pass
                    lab.cover_image = cover_image
                laboratory_manager.update_laboratory(lab)

                # 更新教师和学生关联
                instructor_ids = [int(x) for x in request.form.getlist('instructor_ids')]
                student_ids = [int(x) for x in request.form.getlist('student_ids')]

                # 清除现有关联（在内存中）
                lab.instructors.clear()
                lab.students.clear()

                # 添加新的教师关联
                for teacher_id in instructor_ids:
                    laboratory_manager.add_teacher_to_lab(lab.id, teacher_pk=teacher_id)

                # 添加新的学生关联
                for student_id in student_ids:
                    laboratory_manager.add_student_to_lab(lab.id, student_pk=student_id)

                # 保存到数据库
                laboratory_manager.save(lab)
                flash('实验室更新成功', 'success')
            else:
                # 创建新实验室
                instructor_ids = [int(x) for x in request.form.getlist('instructor_ids')]
                student_ids = [int(x) for x in request.form.getlist('student_ids')]

                new_lab = laboratory_manager.add_laboratory(
                    name=name,
                    description=description,
                    instructor_ids=instructor_ids,
                    student_ids=student_ids,
                    cover_image=cover_image
                )

                if new_lab:
                    laboratory_manager.save(new_lab)
                    flash('实验室创建成功', 'success')
                else:
                    flash('创建实验室失败', 'error')
                    all_students = student_manager.students if hasattr(student_manager, 'students') else []
                    all_teachers = teacher_manager.teachers if hasattr(teacher_manager, 'teachers') else []
                    return render_template('admin/laboratories/edit.html',
                                         lab=None,
                                         all_students=all_students,
                                         all_teachers=all_teachers)

            return redirect(url_for('admin_laboratory.laboratories_list'))
        except Exception as e:
            import traceback
            flash(f'保存实验室失败: {str(e)}', 'error')
            if current_app.config.get('DEBUG'):
                flash(f'错误详情: {traceback.format_exc()}', 'error')

    # GET请求，显示表单
    all_students = student_manager.students if hasattr(student_manager, 'students') else []
    all_teachers = teacher_manager.teachers if hasattr(teacher_manager, 'teachers') else []

    return render_template('admin/laboratories/edit.html',
                         lab=lab,
                         all_students=all_students,
                         all_teachers=all_teachers)


@bp.route('/api/laboratories/unclaimed/awards')
@require_role_api('admin', 'teacher')
def api_laboratories_unclaimed_awards():
    """API: 未关联实验室的奖状列表，供实验室编辑页「成果认领」使用。"""
    try:
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()

        awards = award_manager.query_awards(
            laboratory_id=None,
            filter_no_laboratory=True,
            with_associations=True,
            student_manager=student_manager,
            teacher_manager=teacher_manager,
            comp_mgr=competition_manager,
        )
        items = []
        for a in awards or []:
            comp_name = ''
            if a.competition_obj:
                comp_name = a.competition_obj.name or ''
            if not comp_name and getattr(a, 'competition_name_in_file', None):
                comp_name = a.competition_name_in_file or ''
            items.append({
                'title': a.title,
                'competition_name': comp_name,
                'year': a.year,
                'winner_name': a.winner_name or '',
                'award_level': a.award_level or '',
                'edit_url': url_for('admin_awards.award_edit', award_id=a.id),
            })
        return jsonify({'success': True, 'data': items})
    except Exception as e:
        logger.exception('未认领奖状列表失败')
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/laboratories/unclaimed/patents')
@require_role_api('admin', 'teacher')
def api_laboratories_unclaimed_patents():
    """API: 未关联实验室的专利列表，供实验室编辑页「成果认领」使用。"""
    try:
        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()
        all_patents = patent_manager.query_patents(None)
        unclaimed = [p for p in (all_patents or []) if p.laboratory_id is None]
        items = [
            {
                'patent_name': p.patent_name or '',
                'patent_type': p.patent_type or '专利',
                'inventor': p.inventor or '',
                'application_date': p.application_date or '',
                'edit_url': url_for('admin_patents.patent_edit', patent_id=p.id),
            }
            for p in unclaimed
        ]
        return jsonify({'success': True, 'data': items})
    except Exception as e:
        logger.exception('未认领专利列表失败')
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/laboratories/unclaimed/software')
@require_role_api('admin', 'teacher')
def api_laboratories_unclaimed_software():
    """API: 未关联实验室的软著列表，供实验室编辑页「成果认领」使用。"""
    try:
        app_context = get_app_context_instance()
        software_manager = app_context.get_software_copyright_manager()
        all_copyrights = software_manager.query_copyrights(None)
        unclaimed = [c for c in (all_copyrights or []) if c.laboratory_id is None]
        items = [
            {
                'software_name': c.software_name or '',
                'registration_number': c.registration_number or '',
                'copyright_owner': c.copyright_owner or '',
                'registration_date': c.registration_date or '',
                'edit_url': url_for('admin_software.software_edit', copyright_id=c.id),
            }
            for c in unclaimed
        ]
        return jsonify({'success': True, 'data': items})
    except Exception as e:
        logger.exception('未认领软著列表失败')
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/laboratories/<int:lab_id>')
def laboratory_detail(lab_id):
    """实验室详情页（TAB首页）- 所有人可访问，管理员和实验室指导教师可编辑"""
    try:
        from app.auth import get_current_user, can_edit_laboratory

        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()
        award_manager = app_context.get_award_manager()
        teacher_manager = app_context.get_teacher_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            flash('实验室不存在', 'error')
            # 如果用户是管理员，重定向到列表页；否则返回404或错误页
            user_info = get_current_user()
            if user_info and user_info.get('role') == 'admin':
                return redirect(url_for('admin_laboratory.laboratories_list'))
            from flask import abort
            abort(404)

        # 获取当前用户信息（可能为None）
        user_info = get_current_user()

        # 检查权限
        can_edit = can_edit_laboratory(user_info, lab_id, laboratory_manager, teacher_manager) if user_info else False
        is_admin = user_info and user_info.get('role') == 'admin'

        # 计算实验室统计数据
        statistics = {
            'competition_count': 0,
            'national_awards_3years': 0,
            'provincial_awards_3years': 0
        }

        # 获取实验室的所有成果数据（用于成果展示卡片）
        lab_achievements = {
            'awards': [],
            'patents': [],
            'software': [],
            'innovation': []
        }

        try:
            # 获取实验室的所有指导教师ID
            instructor_ids = [teacher.id for teacher in lab.instructors] if lab.instructors else []

            from datetime import datetime

            # ==================== 获取奖状 ====================
            all_awards = award_manager.query_awards(
                with_associations=True,
                student_manager=app_context.get_student_manager(),
                teacher_manager=teacher_manager,
                comp_mgr=app_context.get_competition_manager()
            )

            # 筛选属于该实验室的奖状
            lab_awards = []
            for award in all_awards:
                # 方式1：奖状直接关联到该实验室（优先）
                if hasattr(award, 'laboratory_id') and award.laboratory_id == lab_id:
                    lab_awards.append(award)
                    continue

                # 方式2：通过指导教师匹配（兼容旧数据，需要 instructor_ids 不为空）
                if instructor_ids and award.supervisors:
                    award_supervisor_ids = [s.id for s in award.supervisors if s and s.id]
                    if any(sid in instructor_ids for sid in award_supervisor_ids):
                        lab_awards.append(award)

            # 计算参与的竞赛数量（去重）
            competition_ids = set()
            whitelist_competition_ids = set()
            for lab_award in lab_awards:
                if lab_award.competition_id:
                    competition_ids.add(lab_award.competition_id)
                    # 检查是否是白名单赛事
                    if hasattr(lab_award, 'competition') and lab_award.competition:
                        if getattr(lab_award.competition, 'white_list', False):
                            whitelist_competition_ids.add(lab_award.competition_id)
            statistics['competition_count'] = len(competition_ids)
            statistics['whitelist_count'] = len(whitelist_competition_ids)

            # 计算近三年国赛和省赛奖项数量
            current_year = datetime.now().year
            three_years_ago_year = current_year - 2  # 包含当前年份，所以是近三年

            for lab_award in lab_awards:
                # 获取年份
                award_year = None
                if lab_award.year:
                    award_year = lab_award.year
                elif lab_award.date:
                    try:
                        if isinstance(lab_award.date, datetime):
                            award_year = lab_award.date.year
                        elif isinstance(lab_award.date, str):
                            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日', '%Y.%m.%d']:
                                try:
                                    parsed_date = datetime.strptime(lab_award.date, fmt)
                                    award_year = parsed_date.year
                                    break
                                except ValueError:
                                    continue
                    except Exception:
                        pass

                # 只统计近三年的奖项（包含当前年份）
                if award_year and award_year >= three_years_ago_year:
                    competition_level = lab_award.competition_level or ''
                    if competition_level == '国赛':
                        statistics['national_awards_3years'] += 1
                    elif competition_level == '省赛':
                        statistics['provincial_awards_3years'] += 1

            # 按提交时间倒序排列，取最近5项
            lab_awards_sorted = sorted(lab_awards, key=lambda x: x.submit_time or '', reverse=True)
            lab_achievements['awards'] = lab_awards_sorted[:5]

            # ==================== 获取专利 ====================
            patent_manager = app_context.get_patent_manager()
            if patent_manager:
                all_patents = patent_manager.patents if hasattr(patent_manager, 'patents') else []
                for patent in all_patents:
                    # 方式1：专利直接关联到该实验室
                    if hasattr(patent, 'laboratory_id') and patent.laboratory_id == lab_id:
                        lab_achievements['patents'].append(patent)
                        continue

                    # 方式2：通过指导教师匹配（兼容旧数据，需要 instructor_ids 不为空）
                    if instructor_ids and hasattr(patent, 'supervisors') and patent.supervisors:
                        supervisor_ids = [s.id for s in patent.supervisors if s and hasattr(s, 'id')]
                        if any(sid in instructor_ids for sid in supervisor_ids):
                            lab_achievements['patents'].append(patent)

                # 按提交时间倒序排列，取最近5项
                lab_achievements['patents'] = sorted(
                    lab_achievements['patents'],
                    key=lambda x: getattr(x, 'submit_time', None) or getattr(x, 'created_at', None) or '',
                    reverse=True
                )[:5]

            # ==================== 获取软著 ====================
            software_manager = app_context.get_software_copyright_manager()
            if software_manager:
                all_software = software_manager.software_copyrights if hasattr(software_manager, 'software_copyrights') else []
                for software in all_software:
                    # 方式1：软著直接关联到该实验室
                    if hasattr(software, 'laboratory_id') and software.laboratory_id == lab_id:
                        lab_achievements['software'].append(software)
                        continue

                    # 方式2：通过指导教师匹配（兼容旧数据，需要 instructor_ids 不为空）
                    if instructor_ids and hasattr(software, 'supervisors') and software.supervisors:
                        supervisor_ids = [s.id for s in software.supervisors if s and hasattr(s, 'id')]
                        if any(sid in instructor_ids for sid in supervisor_ids):
                            lab_achievements['software'].append(software)

                # 按提交时间倒序排列，取最近5项
                lab_achievements['software'] = sorted(
                    lab_achievements['software'],
                    key=lambda x: getattr(x, 'submit_time', None) or getattr(x, 'created_at', None) or '',
                    reverse=True
                )[:5]

            # ==================== 获取大创 ====================
            innovation_manager = app_context.get_innovation_project_manager()
            if innovation_manager:
                all_innovation = innovation_manager.innovation_projects if hasattr(innovation_manager, 'innovation_projects') else []
                for innovation in all_innovation:
                    # 方式1：大创直接关联到该实验室
                    if hasattr(innovation, 'laboratory_id') and innovation.laboratory_id == lab_id:
                        lab_achievements['innovation'].append(innovation)
                        continue

                    # 方式2：通过指导教师匹配（兼容旧数据，需要 instructor_ids 不为空）
                    if instructor_ids and hasattr(innovation, 'supervisors') and innovation.supervisors:
                        supervisor_ids = [s.id for s in innovation.supervisors if s and hasattr(s, 'id')]
                        if any(sid in instructor_ids for sid in supervisor_ids):
                            lab_achievements['innovation'].append(innovation)

                # 按提交时间倒序排列，取最近5项
                lab_achievements['innovation'] = sorted(
                    lab_achievements['innovation'],
                    key=lambda x: getattr(x, 'submit_time', None) or getattr(x, 'created_at', None) or '',
                    reverse=True
                )[:5]

        except Exception as e:
            logger.warning(f'计算实验室统计数据失败: {e}')
            # 统计数据保持默认值0

        return render_template('admin/laboratories/detail.html',
                             lab=lab,
                             can_edit=can_edit,
                             is_admin=is_admin,
                             statistics=statistics,
                             lab_achievements=lab_achievements)
    except Exception as e:
        import traceback
        flash(f'加载实验室详情失败: {str(e)}', 'error')
        if current_app.config.get('DEBUG'):
            flash(f'错误详情: {traceback.format_exc()}', 'error')
        # 检查用户是否是管理员，决定重定向位置
        from app.auth import get_current_user
        user_info = get_current_user()
        if user_info and user_info.get('role') == 'admin':
            return redirect(url_for('admin_laboratory.laboratories_list'))
        from flask import abort
        abort(404)

@bp.route('/laboratories/<int:lab_id>/achievements')
def laboratory_achievements(lab_id):
    """实验室成果展示页面：内容与管理员成果管理一致，仅显示该实验室数据，不显示学生实验室筛选。
    管理员和该实验室指导教师可编辑/删除，其他人（含游客）仅可查看。"""
    try:
        from app.auth import get_current_user, can_edit_laboratory
        from flask import abort

        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()
        teacher_manager = app_context.get_teacher_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            flash('实验室不存在', 'error')
            user_info = get_current_user()
            if user_info and user_info.get('role') == 'admin':
                return redirect(url_for('admin_laboratory.laboratories_list'))
            abort(404)

        user_info = get_current_user()
        can_edit = can_edit_laboratory(user_info, lab_id, laboratory_manager, teacher_manager) if user_info else False

        competition_manager = app_context.get_competition_manager()
        laboratories = laboratory_manager.get_all_laboratories() if hasattr(laboratory_manager, 'get_all_laboratories') else []
        competitions = list(competition_manager.competitions) if hasattr(competition_manager, 'competitions') else []

        tab = request.args.get('tab', 'award')
        return render_template('admin/achievements.html',
                             tab=tab,
                             laboratory_id=lab_id,
                             laboratory_name=lab.name,
                             is_readonly=not can_edit,
                             competitions=competitions,
                             laboratories=laboratories)
    except Exception as e:
        if hasattr(e, 'code') and e.code == 404:
            raise
        import traceback
        flash(f'加载成果页面失败: {str(e)}', 'error')
        if current_app.config.get('DEBUG'):
            flash(f'错误详情: {traceback.format_exc()}', 'error')
        return redirect(url_for('admin_laboratory.laboratory_detail', lab_id=lab_id))


@bp.route('/laboratories/<int:lab_id>/competitions')
def laboratory_competitions(lab_id):
    """实验室参与的竞赛列表页面"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            flash('实验室不存在', 'error')
            return redirect(url_for('admin_laboratory.laboratories_list'))

        # 获取实验室的所有指导教师ID
        instructor_ids = [teacher.id for teacher in lab.instructors] if lab.instructors else []

        # 获取属于该实验室的所有奖状
        all_awards = award_manager.query_awards(
            with_associations=True,
            student_manager=app_context.get_student_manager(),
            teacher_manager=app_context.get_teacher_manager(),
            comp_mgr=competition_manager
        )

        # 筛选属于该实验室的奖状
        lab_awards = []
        for award in all_awards:
            # 方式1：奖状直接关联到该实验室（优先）
            if hasattr(award, 'laboratory_id') and award.laboratory_id == lab_id:
                lab_awards.append(award)
                continue

            # 方式2：通过指导教师匹配（兼容旧数据）
            if instructor_ids and award.supervisors:
                award_supervisor_ids = [s.id for s in award.supervisors if s and s.id]
                if any(sid in instructor_ids for sid in award_supervisor_ids):
                    lab_awards.append(award)

        # 统计每个竞赛的获奖情况
        competition_stats = {}  # {competition_id: {'total': 0, 'national': 0, 'provincial': 0}}
        
        for award in lab_awards:
            if not award.competition_id:
                continue
            
            comp_id = award.competition_id
            if comp_id not in competition_stats:
                competition_stats[comp_id] = {
                    'total': 0,
                    'national': 0,
                    'provincial': 0
                }
            
            competition_stats[comp_id]['total'] += 1
            competition_level = award.competition_level or ''
            if competition_level == '国赛':
                competition_stats[comp_id]['national'] += 1
            elif competition_level == '省赛':
                competition_stats[comp_id]['provincial'] += 1

        # 获取竞赛详细信息（包括官网和名单状态）
        competitions_data = []
        for comp_id, stats in competition_stats.items():
            comp = competition_manager.get_competition_by_id(comp_id)
            if comp:
                # 从数据库获取 official_website 字段
                official_website = None
                try:
                    conn = competition_manager._get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT official_website FROM competitions WHERE id = ?", (comp_id,))
                    row = cursor.fetchone()
                    if row:
                        official_website = row['official_website']
                    conn.close()
                except Exception as e:
                    logger.warning(f"获取竞赛官网失败: {e}")

                competitions_data.append({
                    'id': comp.id,
                    'name': comp.name,
                    'official_website': official_website,
                    'is_white_list': comp.is_white_list,
                    'is_watch_list': comp.is_watch_list,
                    'grade_category': comp.grade_category,
                    'total_awards': stats['total'],
                    'national_awards': stats['national'],
                    'provincial_awards': stats['provincial']
                })

        # 按总获奖数倒序排列
        competitions_data.sort(key=lambda x: x['total_awards'], reverse=True)

        return render_template('admin/laboratories/competitions.html',
                             lab=lab,
                             competitions=competitions_data)
    except Exception as e:
        import traceback
        logger.error(f'加载竞赛列表失败: {e}', exc_info=True)
        flash(f'加载竞赛列表失败: {str(e)}', 'error')
        if current_app.config.get('DEBUG'):
            flash(f'错误详情: {traceback.format_exc()}', 'error')
        return redirect(url_for('admin_laboratory.laboratory_detail', lab_id=lab_id))


@bp.route('/laboratories/<int:lab_id>', methods=['DELETE'])
@require_role('admin')
def laboratory_delete(lab_id):
    """删除实验室"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            return jsonify({'success': False, 'message': '实验室不存在'}), 404

        laboratory_manager.delete_laboratory(lab_id)
        laboratory_manager.save()

        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500

@bp.route('/laboratories/<int:lab_id>/assistants/add', methods=['POST'])
@require_can_edit_laboratory_api
def laboratory_assistant_add(lab_id):
    """添加学生助教"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        data = request.get_json()
        student_id = data.get('student_id')
        
        # 转换为整数
        if student_id is not None:
            try:
                student_id = int(student_id)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': '学生ID格式无效'}), 400

        if not student_id:
            return jsonify({'success': False, 'message': '学生ID不能为空'}), 400

        success = laboratory_manager.add_assistant_to_lab(lab_id, student_id)
        if success:
            return jsonify({'success': True, 'message': '添加助教成功'})
        else:
            return jsonify({'success': False, 'message': '添加助教失败（学生必须是实验室成员，且未在其他实验室担任助教）'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加助教失败: {str(e)}'}), 500

@bp.route('/laboratories/<int:lab_id>/assistants/<int:student_id>/remove', methods=['DELETE'])
@require_can_edit_laboratory_api
def laboratory_assistant_remove(lab_id, student_id):
    """移除学生助教"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        success = laboratory_manager.remove_assistant_from_lab(lab_id, student_id)
        if success:
            return jsonify({'success': True, 'message': '移除助教成功'})
        else:
            return jsonify({'success': False, 'message': '移除助教失败'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'移除助教失败: {str(e)}'}), 500

@bp.route('/laboratories/<int:lab_id>/images/upload', methods=['POST'])
@require_can_edit_laboratory_api
def laboratory_image_upload(lab_id):
    """上传实验室图片"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            return jsonify({'success': False, 'message': '实验室不存在'}), 404

        if 'image' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'}), 400

        file = request.files['image']
        if not file or not file.filename:
            return jsonify({'success': False, 'message': '文件名为空'}), 400

        # 生成唯一文件名
        import os
        import io
        from werkzeug.utils import secure_filename
        from datetime import datetime

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        # 检查文件扩展名和MIME类型
        allowed_extensions = ['.jpg', '.jpeg', '.png']
        file_mime = file.content_type or ''
        allowed_mimes = ['image/jpeg', 'image/jpg', 'image/png']

        # 如果扩展名不在允许列表中，检查MIME类型
        ext_valid = ext in allowed_extensions
        mime_valid = file_mime.lower() in [m.lower() for m in allowed_mimes]

        if not ext_valid and not mime_valid:
            return jsonify({
                'success': False,
                'message': f'不支持的图片格式（扩展名: {ext or "无"}, MIME: {file_mime or "无"}），仅支持 JPG、PNG'
            }), 400

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        new_filename = f"lab_{lab_id}_{timestamp}.jpg"  # 统一保存为jpg

        # 保存到 files/laboratories/{lab_id}/photos/ 目录（迁移后的新目录结构）
        from config.loader import get_config
        config_loader = get_config()
        files_base = config_loader.get_path("files")  # files 目录
        files_dir = files_base / "laboratories" / str(lab_id) / "photos"
        files_dir.mkdir(parents=True, exist_ok=True)
        file_path = files_dir / new_filename

        # 使用PIL处理图片：压缩和缩放
        try:
            from PIL import Image

            # 读取图片
            image_data = file.read()
            img = Image.open(io.BytesIO(image_data))

            # 如果是RGBA模式（PNG透明图），转换为RGB
            if img.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # 图片尺寸限制：最大宽度或高度2000px
            max_size = 2000
            original_width, original_height = img.size

            # 如果图片太大，按比例缩放
            if original_width > max_size or original_height > max_size:
                if original_width > original_height:
                    new_width = max_size
                    new_height = int(original_height * (max_size / original_width))
                else:
                    new_height = max_size
                    new_width = int(original_width * (max_size / original_height))

                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"图片已缩放: {original_width}x{original_height} -> {new_width}x{new_height}")

            # 保存图片，使用高质量JPEG压缩
            # quality=85 是质量和文件大小的良好平衡
            img.save(str(file_path), 'JPEG', quality=85, optimize=True)

            # 检查文件大小，如果仍然太大（>2MB），进一步压缩
            file_size = file_path.stat().st_size
            max_file_size = 2 * 1024 * 1024  # 2MB
            if file_size > max_file_size:
                # 进一步降低质量
                quality = 75
                while file_size > max_file_size and quality > 50:
                    img.save(str(file_path), 'JPEG', quality=quality, optimize=True)
                    file_size = file_path.stat().st_size
                    quality -= 5
                logger.info(f"图片已进一步压缩，最终大小: {file_size / 1024 / 1024:.2f}MB")

        except ImportError:
            # 如果没有PIL，直接保存（可能失败）
            logger.warning("PIL/Pillow未安装，无法压缩图片，直接保存")
            file.seek(0)  # 重置文件指针
            file.save(str(file_path))
        except Exception as e:
            logger.error(f"图片处理失败: {e}")
            # 如果处理失败，尝试直接保存
            file.seek(0)
            file.save(str(file_path))

        # 保存相对路径（相对于files目录，使用迁移后的新格式）
        image_path = f"laboratories/{lab_id}/photos/{new_filename}"

        # 添加到数据库
        success = laboratory_manager.add_laboratory_image(lab_id, image_path)
        if success:
            return jsonify({'success': True, 'message': '上传成功', 'image_path': image_path})
        else:
            # 如果数据库保存失败，删除文件
            if file_path.exists():
                file_path.unlink()
            return jsonify({'success': False, 'message': '保存到数据库失败'}), 500
    except Exception as e:
        import traceback
        logger.error(f"上传实验室图片失败: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'}), 500

@bp.route('/laboratories/<int:lab_id>/images/delete', methods=['POST'])
@require_can_edit_laboratory_api
def laboratory_image_delete(lab_id):
    """删除实验室图片"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            return jsonify({'success': False, 'message': '实验室不存在'}), 404

        data = request.get_json()
        image_path = data.get('image_path', '').strip()

        if not image_path:
            return jsonify({'success': False, 'message': '图片路径不能为空'}), 400

        # 从数据库删除
        success = laboratory_manager.delete_laboratory_image(lab_id, image_path)
        if success:
            # 删除文件
            # 从配置文件获取files目录，不允许硬编码
            from config.loader import get_config
            config_loader = get_config()
            files_dir = config_loader.get_path("files")
            file_path = files_dir / image_path
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.warning(f"删除图片文件失败: {e}")

            return jsonify({'success': True, 'message': '删除成功'})
        else:
            return jsonify({'success': False, 'message': '删除失败'}), 400
    except Exception as e:
        import traceback
        logger.error(f"删除实验室图片失败: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500


# ============================================================
# 实验室下载专区管理
# ============================================================

@bp.route('/laboratories/<int:lab_id>/downloads/upload', methods=['POST'])
@require_can_edit_laboratory_api
def laboratory_downloads_upload(lab_id):
    """上传文件到实验室下载专区"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            return jsonify({'success': False, 'message': '实验室不存在'}), 404

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'}), 400

        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'success': False, 'message': '文件名为空'}), 400

        file_title = request.form.get('file_title', '').strip() or file.filename

        # 生成唯一文件名
        import os
        from werkzeug.utils import secure_filename
        from datetime import datetime

        original_filename = secure_filename(file.filename)
        ext = os.path.splitext(original_filename)[1].lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        new_filename = f"download_{lab_id}_{timestamp}{ext}"

        # 保存到 files/laboratories/{lab_id}/downloads/ 目录
        from config.loader import get_config
        config_loader = get_config()
        files_base = config_loader.get_path("files")
        files_dir = files_base / "laboratories" / str(lab_id) / "downloads"
        files_dir.mkdir(parents=True, exist_ok=True)
        file_path = files_dir / new_filename

        # 保存文件
        file.save(str(file_path))
        file_size = file_path.stat().st_size

        # 保存相对路径（相对于files目录）
        relative_path = f"laboratories/{lab_id}/downloads/{new_filename}"

        # 添加到数据库
        download_id = laboratory_manager.add_download_file(
            lab_id=lab_id,
            file_path=relative_path,
            file_title=file_title,
            file_name=original_filename,
            file_size=file_size,
            submitter_type='admin',
            submitter_id=to_users_id(str(get_config().get_path('database', 'competitions_db')), session.get('user_id'), 'admin'),
            is_public=True
        )

        if download_id:
            return jsonify({
                'success': True, 
                'message': '上传成功', 
                'download_id': download_id,
                'file_path': relative_path
            })
        else:
            # 如果数据库保存失败，删除文件
            if file_path.exists():
                file_path.unlink()
            return jsonify({'success': False, 'message': '保存到数据库失败'}), 500

    except Exception as e:
        import traceback
        logger.error(f"上传下载文件失败: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'}), 500


@bp.route('/laboratories/<int:lab_id>/downloads/<int:download_id>', methods=['DELETE'])
@require_can_edit_laboratory_api
def laboratory_downloads_delete(lab_id, download_id):
    """删除实验室下载专区文件"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            return jsonify({'success': False, 'message': '实验室不存在'}), 404

        # 获取文件路径（用于删除物理文件）
        download_info = None
        for d in lab.downloads:
            if d.get('id') == download_id:
                download_info = d
                break

        if not download_info:
            return jsonify({'success': False, 'message': '下载文件不存在'}), 404

        # 从数据库删除
        success = laboratory_manager.delete_download_file(lab_id, download_id)
        if success:
            # 删除物理文件
            from config.loader import get_config
            config_loader = get_config()
            files_dir = config_loader.get_path("files")
            file_path = files_dir / download_info.get('file_path', '')
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.warning(f"删除下载文件失败: {e}")

            return jsonify({'success': True, 'message': '删除成功'})
        else:
            return jsonify({'success': False, 'message': '删除失败'}), 400

    except Exception as e:
        import traceback
        logger.error(f"删除下载文件失败: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500


@bp.route('/laboratories/<int:lab_id>/downloads')
@require_can_edit_laboratory
def laboratory_downloads_list(lab_id):
    """实验室下载专区文件列表页面"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            flash('实验室不存在', 'error')
            return redirect(url_for('admin_laboratory.laboratories_list'))

        downloads = laboratory_manager.get_laboratory_downloads(lab_id)

        return render_template('admin/laboratories/downloads.html',
                             lab=lab,
                             downloads=downloads)

    except Exception as e:
        logger.error(f"加载下载列表失败: {e}", exc_info=True)
        flash(f'加载失败: {str(e)}', 'error')
        return redirect(url_for('admin_laboratory.laboratory_detail', lab_id=lab_id))


@bp.route('/laboratories/<int:lab_id>/downloads/<int:download_id>/file')
def laboratory_download_file(lab_id, download_id):
    """下载实验室下载专区的文件（公开访问）"""
    try:
        from flask import send_file, abort

        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            abort(404)

        # 查找下载文件
        download_info = None
        for d in lab.downloads:
            if d.get('id') == download_id:
                download_info = d
                break

        if not download_info:
            abort(404)

        # 检查是否公开
        if not download_info.get('is_public', True):
            # 非公开文件需要登录
            if 'user_id' not in session:
                abort(403)

        # 获取文件路径
        from config.loader import get_config
        config_loader = get_config()
        files_dir = config_loader.get_path("files")
        file_path = files_dir / download_info.get('file_path', '')

        if not file_path.exists():
            logger.warning(f"下载文件不存在: {file_path}")
            abort(404)

        # 发送文件
        return send_file(
            str(file_path),
            as_attachment=True,
            download_name=download_info.get('file_name') or file_path.name
        )

    except Exception as e:
        logger.error(f"下载文件失败: {e}", exc_info=True)
        from flask import abort
        abort(500)


@bp.route('/files/laboratory/<path:filename>')
@bp.route('/files/laboratory/<filename>')  # 添加一个更简单的路由作为备用
def laboratory_image_file(filename):
    """提供实验室图片文件访问（公开访问，游客也可查看）
    
    支持两种路径格式:
    1. 直接文件名格式: lab_{lab_id}_{timestamp}.{ext}
       - 文件存储在 files/laboratories/{lab_id}/photos/{filename}
    2. 完整相对路径格式: laboratories/{lab_id}/album/{filename} 或 laboratories/{lab_id}/photos/{filename}
       - 文件存储在 files/{相对路径}
    """
    # 允许游客访问实验室图片，与实验室详情页的访问权限保持一致
    try:
        import os
        import re
        from flask import abort, send_file
        from config.loader import get_config
        
        original_filename = filename
        # 统一将反斜杠转换为正斜杠（兼容 Windows 路径）
        filename = filename.replace('\\', '/')
        
        config_loader = get_config()
        files_base = config_loader.get_path("files")  # files 目录
        laboratories_base = files_base / "laboratories"
        
        # 判断是完整路径格式还是文件名格式
        if filename.startswith('laboratories/') or '/' in filename:
            # 完整相对路径格式: laboratories/{lab_id}/album/{filename}
            # 直接拼接路径
            file_path = files_base / filename
        else:
            # 直接文件名格式: lab_{lab_id}_{timestamp}.{ext}
            # 从文件名解析实验室ID
            match = re.match(r'lab_(\d+)_', filename)
            if not match:
                logger.warning(f"[实验室图片] 无法从文件名解析实验室ID: {filename}")
                abort(404)
            
            lab_id = match.group(1)
            # 构建文件路径: files/laboratories/{lab_id}/photos/{filename}
            file_path = files_base / "laboratories" / lab_id / "photos" / filename

        # 安全检查：确保文件在 files/laboratories 目录下
        try:
            resolved_file_path = file_path.resolve()
            resolved_base = laboratories_base.resolve()
            resolved_file_path.relative_to(resolved_base)
        except ValueError:
            logger.warning(f"[实验室图片] 路径安全检查失败: filename={filename}, file_path={file_path}")
            abort(403)  # 禁止访问

        if not file_path.exists():
            logger.warning(f"[实验室图片] 文件不存在: file_path={file_path}")
            abort(404)

        if not file_path.is_file():
            logger.warning(f"[实验室图片] 路径不是文件: {file_path}")
            abort(404)

        # 根据文件扩展名设置正确的MIME类型
        ext = file_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.jfif': 'image/jpeg',  # JFIF 是 JPEG 文件格式的一种变体
            '.png': 'image/png',
            '.gif': 'image/gif'
        }
        mimetype = mime_types.get(ext, 'image/jpeg')
        return send_file(str(file_path), mimetype=mimetype)
    except Exception as e:
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            raise
        import traceback
        logger.error(f"[实验室图片] 访问失败: {e}\n原始文件名: {filename}\n{traceback.format_exc()}")
        abort(404)


# ==================== 实验室下载（按 file_id） ====================

@bp.route('/laboratory-downloads/<int:file_id>/download')
@require_role('admin')
def laboratory_download_download(file_id):
    """下载实验室文件"""
    try:
        import sqlite3
        from config.loader import get_config
        from flask import send_file
        from pathlib import Path

        config = get_config()
        db_path = config.get_path("database", "competitions_db")
        files_dir = config.get_path("files")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM laboratory_downloads WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            flash('文件不存在', 'error')
            return redirect(url_for('admin_achievement.achievements', tab='other'))

        file_path = files_dir / row['file_path']
        if not file_path.exists():
            flash('文件不存在', 'error')
            return redirect(url_for('admin_achievement.achievements', tab='other'))

        return send_file(file_path, as_attachment=True, download_name=row['file_name'] or row['file_title'])

    except Exception as e:
        logger.error(f"Error downloading laboratory file {file_id}: {e}")
        flash(f'下载文件失败: {e}', 'error')
        return redirect(url_for('admin_achievement.achievements', tab='other'))


@bp.route('/laboratory-downloads/<int:file_id>/delete', methods=['POST'])
@require_role('admin')
def laboratory_download_delete(file_id):
    """删除实验室文件"""
    try:
        import sqlite3
        from config.loader import get_config
        from pathlib import Path

        config = get_config()
        db_path = config.get_path("database", "competitions_db")
        files_dir = config.get_path("files")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 获取文件信息
        cursor.execute("SELECT * FROM laboratory_downloads WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            flash('文件不存在', 'error')
            return jsonify({'success': False, 'message': '文件不存在'})

        # 删除物理文件
        file_path = files_dir / row['file_path']
        if file_path.exists():
            file_path.unlink()

        # 删除数据库记录
        cursor.execute("DELETE FROM laboratory_downloads WHERE id = ?", (file_id,))
        conn.commit()
        conn.close()

        flash('文件删除成功', 'success')
        return jsonify({'success': True, 'message': '删除成功'})

    except Exception as e:
        logger.error(f"Error deleting laboratory file {file_id}: {e}")


@bp.route('/laboratories/<int:lab_id>/data-analysis')
@require_login
def laboratory_data_analysis(lab_id):
    """实验室数据分析页面（管理员视图）"""
    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            flash('实验室不存在', 'error')
            return redirect(url_for('admin_laboratory.laboratories_list'))

        return render_template('admin/laboratory_data_analysis.html', lab_id=lab_id)

    except Exception as e:
        logger.error(f"Error loading laboratory data analysis: {e}", exc_info=True)
        flash(f'加载数据分析页面失败: {str(e)}', 'error')
        return redirect(url_for('admin_laboratory.laboratory_detail', lab_id=lab_id))
