"""
Innovation Project Management Routes (管理员 - 大创管理)
Note: Only admins can submit innovation projects.
"""
import logging
import json
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from pathlib import Path
from app.auth import require_role, require_role_api, require_admin_or_lab_view_api
from app.utils import get_app_context_instance
from backend.models.innovation_project import InnovationProjectManager, InnovationProject, InnovationProjectFilter

logger = logging.getLogger(__name__)
bp = Blueprint('admin_innovation', __name__)


def _innovation_list_url():
    """大创列表唯一入口：成果管理页大创 tab"""
    return url_for('admin_achievement.achievements', tab='innovation')


@bp.route('/innovation')
@require_role('admin')
def innovation_redirect():
    """原 /admin/innovation 已合并到成果管理-大创 tab，重定向到成果管理"""
    return redirect(_innovation_list_url())


@bp.route('/innovation/batch-delete', methods=['POST'])
@require_role('admin')
def innovation_batch_delete():
    """批量删除大创项目"""
    try:
        data = request.get_json()
        project_ids = data.get('project_ids', [])

        if not project_ids:
            return jsonify({'success': False, 'message': '请选择要删除的项目'}), 400

        app_context = get_app_context_instance()
        project_manager = app_context.get_innovation_project_manager()

        success_count = 0
        failed_count = 0
        errors = []

        for pid in project_ids:
            try:
                if project_manager.delete_project(pid):
                    success_count += 1
                else:
                    failed_count += 1
                    errors.append(f'ID {pid}: 未找到或删除失败')
            except Exception as e:
                failed_count += 1
                errors.append(f'ID {pid}: {str(e)}')

        if failed_count == 0:
            return jsonify({'success': True, 'message': f'成功删除 {success_count} 条项目'})
        return jsonify({
            'success': True,
            'message': f'成功删除 {success_count} 条，失败 {failed_count} 条',
            'errors': errors[:10]
        })
    except Exception as e:
        logger.error(f"批量删除大创项目失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'批量删除失败: {str(e)}'}), 500


@bp.route('/innovation/<int:project_id>')
@require_role('admin')
def innovation_view(project_id):
    """查看大创项目详情"""
    try:
        app_context = get_app_context_instance()
        project_manager = app_context.get_innovation_project_manager()
        student_manager = app_context.get_student_manager()
        
        # 加载项目并恢复学生关联
        project = project_manager.load_project_with_associations(project_id, student_manager)

        if not project:
            flash('大创项目不存在', 'error')
            return redirect(_innovation_list_url())

        # Parse members and supervisors
        members_data = project.get_members_list()  # 返回 [{"姓名":"...","学号":"..."}]
        # 格式化为显示字符串
        members_display = []
        for m in members_data:
            if isinstance(m, dict):
                name = m.get("姓名", "")
                sid = m.get("学号", "")
                if sid:
                    members_display.append(f"{name}({sid})")
                else:
                    members_display.append(name)
            else:
                members_display.append(str(m))
        
        supervisors = project.get_supervisors_list()

        # Get related laboratory info
        laboratory = None
        if project.laboratory_id:
            laboratory_manager = app_context.get_laboratory_manager()
            laboratory = laboratory_manager.get_laboratory_by_id(project.laboratory_id)

        return render_template('admin/innovation/view.html',
                             project=project,
                             members=members_display,
                             supervisors=supervisors,
                             laboratory=laboratory)

    except Exception as e:
        logger.error(f"Error viewing innovation {project_id}: {e}")
        flash(f'加载大创详情失败: {e}', 'error')
        return redirect(_innovation_list_url())


@bp.route('/innovation/create', methods=['GET', 'POST'])
@require_role('admin')
def innovation_create():
    """创建新大创项目"""
    if request.method == 'GET':
        # Get laboratories for dropdown
        try:
            app_context = get_app_context_instance()
            laboratory_manager = app_context.get_laboratory_manager()
            laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

            return render_template('admin/innovation/edit.html',
                                 project=None,
                                 laboratories=laboratories)
        except Exception as e:
            logger.error(f"Error loading create form: {e}")
            flash(f'加载创建表单失败: {e}', 'error')
            return redirect(_innovation_list_url())

    # POST - Create innovation project
    try:
        app_context = get_app_context_instance()
        project_manager = app_context.get_innovation_project_manager()
        student_manager = app_context.get_student_manager()

        # Get form data
        # 处理 laboratory_id - 先获取字符串再转换为 int
        lab_id_str = request.form.get('laboratory_id', '').strip()
        laboratory_id = int(lab_id_str) if lab_id_str and lab_id_str != '' else None

        project_data = {
            'project_no': request.form.get('project_no', '').strip() or None,
            'project_name': request.form.get('project_name', '').strip(),
            'project_type': request.form.get('project_type', '').strip() or None,
            'start_date': request.form.get('start_date', '').strip() or None,
            'end_date': request.form.get('end_date', '').strip() or None,
            'student_leader_name': request.form.get('student_leader_name', '').strip() or None,
            'student_leader_id': request.form.get('student_leader_id', '').strip() or None,
            'other_members': request.form.get('other_members', '').strip() or None,
            'supervisors': request.form.get('supervisors', '').strip() or None,
            'funding_amount': request.form.get('funding_amount', type=float) or None,
            'status': request.form.get('status', '进行中'),
            'submitter_type': 'admin',
            'submitter_id': session.get('user_id'),
            'laboratory_id': laboratory_id,
        }

        # Validate required fields
        if not project_data['project_name']:
            flash('项目名称不能为空', 'error')
            return redirect(url_for('admin_innovation.innovation_create'))

        # Create innovation project
        project = project_manager.add_project(project_data, student_manager=student_manager)

        flash(f'大创项目 "{project.project_name}" 创建成功', 'success')
        return redirect(url_for('admin_innovation.innovation_view', project_id=project.id))

    except ValueError as e:
        flash(f'创建失败: {e}', 'error')
        return redirect(url_for('admin_innovation.innovation_create'))
    except Exception as e:
        logger.error(f"Error creating innovation: {e}")
        flash(f'创建大创项目失败: {e}', 'error')
        return redirect(url_for('admin_innovation.innovation_create'))


@bp.route('/innovation/<int:project_id>/edit', methods=['GET', 'POST'])
@require_role('admin')
def innovation_edit(project_id):
    """编辑大创项目"""
    if request.method == 'GET':
        try:
            app_context = get_app_context_instance()
            project_manager = app_context.get_innovation_project_manager()
            student_manager = app_context.get_student_manager()
            teacher_manager = app_context.get_teacher_manager()
            
            # 加载项目并恢复学生关联
            project = project_manager.load_project_with_associations(project_id, student_manager)

            if not project:
                flash('大创项目不存在', 'error')
                return redirect(_innovation_list_url())

            # Get laboratories for dropdown
            laboratory_manager = app_context.get_laboratory_manager()
            laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

            # 准备负责人状态列表
            leader_status = None
            if project.student_leader_name:
                # 优先使用学号匹配
                if project.student_leader_id:
                    student = student_manager.get_student_by_student_id(project.student_leader_id)
                    if student:
                        if student.name == project.student_leader_name:
                            leader_status = {
                                'name': project.student_leader_name,
                                'student_id': project.student_leader_id,
                                'matched': True,
                                'obj': student,
                                'ambiguous': False,
                                'not_found': False
                            }
                        else:
                            # 学号存在但姓名不匹配
                            leader_status = {
                                'name': project.student_leader_name,
                                'student_id': project.student_leader_id,
                                'matched': False,
                                'obj': student,  # 仍然显示，但标记为不匹配
                                'ambiguous': False,
                                'not_found': False
                            }
                    else:
                        # 学号不存在，尝试姓名匹配
                        found = student_manager.find_students_by_name(project.student_leader_name)
                        exact_matches = [s for s in found if s.name.strip() == project.student_leader_name.strip()]
                        if len(exact_matches) == 1:
                            leader_status = {
                                'name': project.student_leader_name,
                                'student_id': project.student_leader_id,
                                'matched': True,
                                'obj': exact_matches[0],
                                'ambiguous': False,
                                'not_found': False
                            }
                        elif len(exact_matches) > 1:
                            leader_status = {
                                'name': project.student_leader_name,
                                'student_id': project.student_leader_id,
                                'matched': False,
                                'obj': None,
                                'ambiguous': True,
                                'not_found': False
                            }
                        else:
                            leader_status = {
                                'name': project.student_leader_name,
                                'student_id': project.student_leader_id,
                                'matched': False,
                                'obj': None,
                                'ambiguous': False,
                                'not_found': True
                            }
                else:
                    # 只有姓名，没有学号
                    found = student_manager.find_students_by_name(project.student_leader_name)
                    exact_matches = [s for s in found if s.name.strip() == project.student_leader_name.strip()]
                    if len(exact_matches) == 1:
                        leader_status = {
                            'name': project.student_leader_name,
                            'student_id': None,
                            'matched': True,
                            'obj': exact_matches[0],
                            'ambiguous': False,
                            'not_found': False
                        }
                    elif len(exact_matches) > 1:
                        leader_status = {
                            'name': project.student_leader_name,
                            'student_id': None,
                            'matched': False,
                            'obj': None,
                            'ambiguous': True,
                            'not_found': False
                        }
                    else:
                        leader_status = {
                            'name': project.student_leader_name,
                            'student_id': None,
                            'matched': False,
                            'obj': None,
                            'ambiguous': False,
                            'not_found': True
                        }
            
            # 准备成员状态列表
            members_status_list = []
            members_data = project.get_members_list()  # 返回 [{"姓名":"...","学号":"..."}]
            seen_member_ids = set()  # 已匹配的学生ID集合（用于去重）
            
            # 先收集已关联的学生
            members_by_id = {}
            for student in project.student_members:
                if student and student.id:
                    members_by_id[student.id] = student
            
            for member in members_data:
                member_name = member.get("姓名", "")
                member_id = member.get("学号", "")
                
                if not member_name:
                    continue
                
                # 优先使用学号匹配
                if member_id:
                    student = student_manager.get_student_by_student_id(member_id)
                    if student:
                        if student.name == member_name:
                            if student.id not in seen_member_ids:
                                members_status_list.append({
                                    'name': member_name,
                                    'student_id': member_id,
                                    'matched': True,
                                    'obj': student,
                                    'ambiguous': False,
                                    'not_found': False
                                })
                                seen_member_ids.add(student.id)
                        else:
                            # 学号存在但姓名不匹配
                            if student.id not in seen_member_ids:
                                members_status_list.append({
                                    'name': member_name,
                                    'student_id': member_id,
                                    'matched': False,
                                    'obj': student,
                                    'ambiguous': False,
                                    'not_found': False
                                })
                                seen_member_ids.add(student.id)
                    else:
                        # 学号不存在，尝试姓名匹配
                        found = student_manager.find_students_by_name(member_name)
                        exact_matches = [s for s in found if s.name.strip() == member_name.strip()]
                        if len(exact_matches) == 1:
                            if exact_matches[0].id not in seen_member_ids:
                                members_status_list.append({
                                    'name': member_name,
                                    'student_id': member_id,
                                    'matched': True,
                                    'obj': exact_matches[0],
                                    'ambiguous': False,
                                    'not_found': False
                                })
                                seen_member_ids.add(exact_matches[0].id)
                        elif len(exact_matches) > 1:
                            members_status_list.append({
                                'name': member_name,
                                'student_id': member_id,
                                'matched': False,
                                'obj': None,
                                'ambiguous': True,
                                'not_found': False
                            })
                        else:
                            members_status_list.append({
                                'name': member_name,
                                'student_id': member_id,
                                'matched': False,
                                'obj': None,
                                'ambiguous': False,
                                'not_found': True
                            })
                else:
                    # 只有姓名
                    found = student_manager.find_students_by_name(member_name)
                    exact_matches = [s for s in found if s.name.strip() == member_name.strip()]
                    if len(exact_matches) == 1:
                        if exact_matches[0].id not in seen_member_ids:
                            members_status_list.append({
                                'name': member_name,
                                'student_id': None,
                                'matched': True,
                                'obj': exact_matches[0],
                                'ambiguous': False,
                                'not_found': False
                            })
                            seen_member_ids.add(exact_matches[0].id)
                    elif len(exact_matches) > 1:
                        members_status_list.append({
                            'name': member_name,
                            'student_id': None,
                            'matched': False,
                            'obj': None,
                            'ambiguous': True,
                            'not_found': False
                        })
                    else:
                        members_status_list.append({
                            'name': member_name,
                            'student_id': None,
                            'matched': False,
                            'obj': None,
                            'ambiguous': False,
                            'not_found': True
                        })
            
            # 准备指导教师状态列表
            supervisors_status_list = []
            supervisors_names = project.get_supervisors_list()
            seen_teacher_ids = set()
            
            # 先收集已关联的教师（如果有的话，当前没有教师关联表）
            for supervisor_name in supervisors_names:
                if not supervisor_name:
                    continue
                
                matched_teachers = teacher_manager.find_teachers_by_name(supervisor_name)
                exact_matches = [t for t in matched_teachers if t.name.strip() == supervisor_name.strip()]
                if len(exact_matches) == 1:
                    if exact_matches[0].id not in seen_teacher_ids:
                        supervisors_status_list.append({
                            'name': supervisor_name,
                            'matched': True,
                            'obj': exact_matches[0],
                            'ambiguous': False,
                            'not_found': False
                        })
                        seen_teacher_ids.add(exact_matches[0].id)
                elif len(exact_matches) > 1:
                    supervisors_status_list.append({
                        'name': supervisor_name,
                        'matched': False,
                        'obj': None,
                        'ambiguous': True,
                        'not_found': False
                    })
                else:
                    supervisors_status_list.append({
                        'name': supervisor_name,
                        'matched': False,
                        'obj': None,
                        'ambiguous': False,
                        'not_found': True
                    })
            
            # 获取所有学生和教师（用于下拉选择）
            all_students = student_manager.students
            all_teachers = teacher_manager.teachers

            return render_template('admin/innovation/edit.html',
                                 project=project,
                                 laboratories=laboratories,
                                 leader_status=leader_status,
                                 members_status_list=members_status_list,
                                 supervisors_status_list=supervisors_status_list,
                                 all_students=all_students,
                                 all_teachers=all_teachers)

        except Exception as e:
            logger.error(f"Error loading edit form: {e}")
            flash(f'加载编辑表单失败: {e}', 'error')
            return redirect(_innovation_list_url())

    # POST - Update innovation project
    try:
        app_context = get_app_context_instance()
        project_manager = app_context.get_innovation_project_manager()
        student_manager = app_context.get_student_manager()

        # Get form data
        # 处理 other_members：从JSON格式获取（由前端JavaScript生成）
        other_members_json = request.form.get('other_members', '').strip() or None
        if other_members_json:
            import json
            try:
                # 验证JSON格式
                parsed = json.loads(other_members_json)
                if not isinstance(parsed, list):
                    other_members_json = None
            except:
                other_members_json = None
        
        # 处理 laboratory_id - 先获取字符串再转换为 int
        lab_id_str = request.form.get('laboratory_id', '').strip()
        laboratory_id = int(lab_id_str) if lab_id_str and lab_id_str != '' else None

        project_data = {
            'project_no': request.form.get('project_no', '').strip() or None,
            'project_name': request.form.get('project_name', '').strip(),
            'project_type': request.form.get('project_type', '').strip() or None,
            'start_date': request.form.get('start_date', '').strip() or None,
            'end_date': request.form.get('end_date', '').strip() or None,
            'student_leader_name': request.form.get('student_leader_name', '').strip() or None,
            'student_leader_id': request.form.get('student_leader_id', '').strip() or None,
            'other_members': other_members_json,
            'supervisors': request.form.get('supervisors', '').strip() or None,
            'funding_amount': request.form.get('funding_amount', type=float) or None,
            'status': request.form.get('status', '进行中'),
            'laboratory_id': laboratory_id,
        }

        # Validate required fields
        if not project_data['project_name']:
            flash('项目名称不能为空', 'error')
            return redirect(url_for('admin_innovation.innovation_edit', project_id=project_id))

        # Update innovation project
        success = project_manager.update_project(project_id, project_data, student_manager=student_manager)

        if success:
            flash('大创项目更新成功', 'success')
            return redirect(url_for('admin_innovation.innovation_view', project_id=project_id))
        else:
            flash('大创项目更新失败', 'error')
            return redirect(url_for('admin_innovation.innovation_edit', project_id=project_id))

    except Exception as e:
        logger.error(f"Error updating innovation {project_id}: {e}")
        flash(f'更新大创项目失败: {e}', 'error')
        return redirect(url_for('admin_innovation.innovation_edit', project_id=project_id))


@bp.route('/innovation/<int:project_id>/delete', methods=['POST', 'DELETE'])
@require_role('admin')
def innovation_delete(project_id):
    """删除大创项目"""
    # 检测是否为 AJAX 请求（通过 Content-Type 或 Accept 头）
    is_ajax = (request.headers.get('Content-Type') == 'application/json' or
               request.accept_mimetypes.accept_json)

    try:
        app_context = get_app_context_instance()
        project_manager = app_context.get_innovation_project_manager()

        success = project_manager.delete_project(project_id)

        if is_ajax:
            if success:
                return jsonify({'success': True, 'message': '大创项目删除成功'})
            else:
                return jsonify({'success': False, 'message': '大创项目删除失败'}), 400
        else:
            if success:
                flash('大创项目删除成功', 'success')
            else:
                flash('大创项目删除失败', 'error')
            return redirect(_innovation_list_url())

    except Exception as e:
        logger.error(f"Error deleting innovation {project_id}: {e}")
        if is_ajax:
            return jsonify({'success': False, 'message': f'删除大创项目失败: {e}'}), 500
        else:
            flash(f'删除大创项目失败: {e}', 'error')
            return redirect(_innovation_list_url())


@bp.route('/api/innovation/check-duplicate', methods=['POST'])
@require_role('admin')
def api_check_duplicate():
    """检查大创项目重复（AJAX）"""
    try:
        data = request.get_json()
        app_context = get_app_context_instance()
        project_manager = app_context.get_innovation_project_manager()

        duplicate = project_manager.check_duplicate(data)

        return jsonify({
            'has_duplicate': duplicate is not None,
            'duplicate_id': duplicate.id if duplicate else None,
            'duplicate_name': duplicate.project_name if duplicate else None
        })

    except Exception as e:
        logger.error(f"Error checking duplicate: {e}")
        return jsonify({'error': str(e)}), 500


# ---------- 成果汇总页 Tab API ----------

@bp.route('/api/achievements/innovation')
@require_admin_or_lab_view_api
def api_achievements_innovation():
    """API: 成果管理-大创 tab 内容（与原 /admin/innovation 列表同源）。实验室视图（laboratory_id）时仅返回该实验室数据。"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        laboratory_id = request.args.get('laboratory_id', type=int)
        project_type = request.args.get('project_type', '').strip() or None
        status = request.args.get('status', '').strip() or None
        student_leader_name = request.args.get('student_leader_name', '').strip() or None
        project_name = request.args.get('project_name', '').strip() or None
        year = request.args.get('year', type=int)

        app_context = get_app_context_instance()
        innovation_manager = app_context.get_innovation_project_manager()
        laboratory_manager = app_context.get_laboratory_manager()

        filter_kwargs = {
            'limit': per_page,
            'offset': (page - 1) * per_page,
            'project_type': project_type,
            'status': status,
            'student_leader_name': student_leader_name,
            'project_name': project_name,
            'laboratory_id': laboratory_id,
            'year': year,
        }
        filter_obj = InnovationProjectFilter(**filter_kwargs)
        projects = innovation_manager.query_projects(filter_obj)

        # 为每个项目添加实验室名称
        laboratory_dict = {lab.id: lab.name for lab in laboratory_manager.get_all()} if hasattr(laboratory_manager, 'get_all') else {}
        for project in projects:
            if project.laboratory_id and project.laboratory_id in laboratory_dict:
                project.laboratory_name = laboratory_dict[project.laboratory_id]
            else:
                project.laboratory_name = None

        count_filter = InnovationProjectFilter(
            project_type=filter_obj.project_type,
            status=filter_obj.status,
            student_leader_name=filter_obj.student_leader_name,
            project_name=filter_obj.project_name,
            laboratory_id=filter_obj.laboratory_id,
            year=filter_obj.year,
            limit=None,
            offset=None,
        )
        all_matching = innovation_manager.query_projects(count_filter)
        total_count = len(all_matching) if all_matching else 0
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []
        all_projects = innovation_manager.query_projects(None)
        available_years = sorted(set([p.get_year() for p in all_projects if p.get_year()]), reverse=True)

        html = render_template('admin/innovation/_list_content.html',
                               projects=projects,
                               page=page,
                               per_page=per_page,
                               total_count=total_count,
                               total_pages=total_pages,
                               filter_obj=filter_obj,
                               laboratories=laboratories,
                               available_years=available_years)

        return jsonify({'success': True, 'html': html, 'total_count': total_count})
    except Exception as e:
        logger.error(f"Error loading innovation tab: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
