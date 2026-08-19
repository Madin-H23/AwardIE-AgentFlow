"""
Patent Management Routes (管理员 - 专利管理)
"""
import logging
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from pathlib import Path
from app.auth import require_role, require_role_api, require_admin_or_lab_view_api
from app.utils import get_app_context_instance
from backend.models.patent import PatentManager, Patent, PatentFilter

logger = logging.getLogger(__name__)
bp = Blueprint('admin_patents', __name__)


@bp.route('/patents')
@require_role('admin')
def patents_list():
    """专利列表页面"""
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    patent_type = request.args.get('patent_type', '').strip()
    inventor = request.args.get('inventor', '').strip()
    laboratory_id = request.args.get('laboratory_id', type=int)

    try:
        # Get managers
        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()

        # Build filter
        filter_obj = PatentFilter(
            patent_type=patent_type if patent_type else None,
            inventor=inventor if inventor else None,
            laboratory_id=laboratory_id,
            limit=per_page,
            offset=(page - 1) * per_page
        )

        # Query patents
        patents = patent_manager.query_patents(filter_obj)

        # Get all laboratories for filter dropdown and create lookup dict
        laboratory_manager = app_context.get_laboratory_manager()
        laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []
        lab_dict = {lab.id: lab.name for lab in laboratories}

        # Get submitter names
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()

        submitter_names = {}
        for patent in patents:
            if patent.submitter_type and patent.submitter_id:
                if patent.submitter_type == 'student':
                    student = student_manager.get_student_by_id(patent.submitter_id)
                    submitter_names[patent.id] = student.name if student else f"学生({patent.submitter_id})"
                elif patent.submitter_type == 'teacher':
                    teacher = teacher_manager.get_teacher_by_id(patent.submitter_id)
                    submitter_names[patent.id] = teacher.name if teacher else f"教师({patent.submitter_id})"
                elif patent.submitter_type == 'admin':
                    submitter_names[patent.id] = "管理员"

        return render_template('admin/patents/list.html',
                             patents=patents,
                             page=page,
                             per_page=per_page,
                             filter_obj=filter_obj,
                             laboratories=laboratories,
                             lab_dict=lab_dict,
                             submitter_names=submitter_names)

    except Exception as e:
        logger.error(f"Error loading patents list: {e}")
        flash(f'加载专利列表失败: {e}', 'error')
        return render_template('admin/patents/list.html',
                             patents=[],
                             page=page,
                             per_page=per_page,
                             filter_obj=PatentFilter(),
                             laboratories=[])


@bp.route('/patents/<int:patent_id>')
@require_role('admin')
def patent_view(patent_id):
    """查看专利详情"""
    try:
        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()
        patent = patent_manager.get_patent_by_id(patent_id)

        if not patent:
            flash('专利不存在', 'error')
            return redirect(url_for('admin_patents.patents_list'))

        # Get related laboratory info
        laboratory = None
        if patent.laboratory_id:
            laboratory_manager = app_context.get_laboratory_manager()
            laboratory = laboratory_manager.get_laboratory_by_id(patent.laboratory_id)

        return render_template('admin/patents/view.html',
                             patent=patent,
                             laboratory=laboratory)

    except Exception as e:
        logger.error(f"Error viewing patent {patent_id}: {e}")
        flash(f'加载专利详情失败: {e}', 'error')
        return redirect(url_for('admin_patents.patents_list'))


@bp.route('/patents/create', methods=['GET', 'POST'])
@require_role('admin')
def patent_create():
    """创建新专利"""
    from backend.utils.users_sync import to_users_id
    from config.loader import get_config
    if request.method == 'GET':
        # Get laboratories for dropdown
        try:
            app_context = get_app_context_instance()
            laboratory_manager = app_context.get_laboratory_manager()
            laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

            return render_template('admin/patents/edit.html',
                                 patent=None,
                                 laboratories=laboratories)
        except Exception as e:
            logger.error(f"Error loading create form: {e}")
            flash(f'加载创建表单失败: {e}', 'error')
            return redirect(url_for('admin_patents.patents_list'))

    # POST - Create patent
    try:
        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()

        # Get form data
        patent_data = {
            'patent_name': request.form.get('patent_name', '').strip(),
            'patent_type': request.form.get('patent_type', '').strip() or None,
            'application_number': request.form.get('application_number', '').strip() or None,
            'publication_number': request.form.get('publication_number', '').strip() or None,
            'inventor': request.form.get('inventor', '').strip() or None,
            'application_date': request.form.get('application_date', '').strip() or None,
            'patentee': request.form.get('patentee', '').strip() or None,
            'submitter_type': 'admin',
            'submitter_id': to_users_id(str(get_config().get_path('database', 'competitions_db')), session.get('user_id'), 'admin'),
            'laboratory_id': request.form.get('laboratory_id', type=int) or None,
        }

        # Handle file upload - 直接传递文件对象给PatentManager
        uploaded_file = None
        if 'certificate_file' in request.files:
            file = request.files['certificate_file']
            if file and file.filename:
                uploaded_file = file

        # Validate required fields
        if not patent_data['patent_name']:
            flash('专利名称不能为空', 'error')
            return redirect(url_for('admin_patents.patent_create'))

        # Create patent
        patent = patent_manager.add_patent(patent_data, uploaded_file)

        flash(f'专利 "{patent.patent_name}" 创建成功', 'success')
        return redirect(url_for('admin_patents.patent_view', patent_id=patent.id))

    except ValueError as e:
        flash(f'创建失败: {e}', 'error')
        return redirect(url_for('admin_patents.patent_create'))
    except Exception as e:
        logger.error(f"Error creating patent: {e}")
        flash(f'创建专利失败: {e}', 'error')
        return redirect(url_for('admin_patents.patent_create'))


def _teacher_can_edit_patent(patent, app_context, session) -> bool:
    """教师是否有权限编辑该专利（未认领可认领，已认领且为该实验室指导教师可编辑）"""
    if session.get('role') != 'teacher':
        return True
    teacher_manager = app_context.get_teacher_manager()
    laboratory_manager = app_context.get_laboratory_manager()
    teacher = teacher_manager.get_teacher_by_teacher_id(session.get('user_id'))
    if not teacher or not laboratory_manager:
        return False
    if patent.laboratory_id is None:
        return laboratory_manager.is_teacher_in_lab(teacher.id)
    lab = laboratory_manager.get_laboratory_by_id(patent.laboratory_id)
    return lab is not None and teacher in lab.instructors


@bp.route('/patents/<int:patent_id>/edit', methods=['GET', 'POST'])
@require_role('admin', 'teacher')
def patent_edit(patent_id):
    """编辑专利"""
    if request.method == 'GET':
        try:
            app_context = get_app_context_instance()
            patent_manager = app_context.get_patent_manager()
            patent = patent_manager.get_patent_by_id(patent_id)

            if not patent:
                flash('专利不存在', 'error')
                return redirect(url_for('admin_patents.patents_list'))

            if not _teacher_can_edit_patent(patent, app_context, session):
                flash('您没有权限编辑该专利', 'error')
                return redirect(url_for('teacher.dashboard'))

            # Get laboratories for dropdown
            laboratory_manager = app_context.get_laboratory_manager()
            laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

            return render_template('admin/patents/edit.html',
                                 patent=patent,
                                 laboratories=laboratories)

        except Exception as e:
            logger.error(f"Error loading edit form: {e}")
            flash(f'加载编辑表单失败: {e}', 'error')
            return redirect(url_for('admin_patents.patents_list'))

    # POST - Update patent
    try:
        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()
        patent = patent_manager.get_patent_by_id(patent_id)
        if not patent:
            flash('专利不存在', 'error')
            return redirect(url_for('admin_patents.patents_list'))
        if not _teacher_can_edit_patent(patent, app_context, session):
            flash('您没有权限编辑该专利', 'error')
            return redirect(url_for('teacher.dashboard'))

        # Get form data
        patent_data = {
            'patent_name': request.form.get('patent_name', '').strip(),
            'patent_type': request.form.get('patent_type', '').strip() or None,
            'application_number': request.form.get('application_number', '').strip() or None,
            'publication_number': request.form.get('publication_number', '').strip() or None,
            'inventor': request.form.get('inventor', '').strip() or None,
            'application_date': request.form.get('application_date', '').strip() or None,
            'patentee': request.form.get('patentee', '').strip() or None,
            'laboratory_id': request.form.get('laboratory_id', type=int) or None,
        }

        # Handle file upload - 直接传递文件对象给PatentManager
        uploaded_file = None
        if 'certificate_file' in request.files:
            file = request.files['certificate_file']
            if file and file.filename:
                uploaded_file = file

        # Validate required fields
        if not patent_data['patent_name']:
            flash('专利名称不能为空', 'error')
            return redirect(url_for('admin_patents.patent_edit', patent_id=patent_id))

        # Update patent
        success = patent_manager.update_patent(patent_id, patent_data, uploaded_file)

        # 保留来源参数
        from_page = request.args.get('from', '') or request.form.get('from', '')
        
        if success:
            flash('专利更新成功', 'success')
            if from_page:
                return redirect(url_for('admin_patents.patent_view', patent_id=patent_id, **{'from': from_page}))
            return redirect(url_for('admin_patents.patent_view', patent_id=patent_id))
        else:
            flash('专利更新失败', 'error')
            if from_page:
                return redirect(url_for('admin_patents.patent_edit', patent_id=patent_id, **{'from': from_page}))
            return redirect(url_for('admin_patents.patent_edit', patent_id=patent_id))

    except Exception as e:
        logger.error(f"Error updating patent {patent_id}: {e}")
        flash(f'更新专利失败: {e}', 'error')
        from_page = request.args.get('from', '') or request.form.get('from', '')
        if from_page:
            return redirect(url_for('admin_patents.patent_edit', patent_id=patent_id, **{'from': from_page}))
        return redirect(url_for('admin_patents.patent_edit', patent_id=patent_id))


@bp.route('/patents/<int:patent_id>/delete', methods=['POST'])
@require_role('admin')
def patent_delete(patent_id):
    """删除专利"""
    try:
        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()

        success = patent_manager.delete_patent(patent_id)

        if success:
            flash('专利删除成功', 'success')
        else:
            flash('专利删除失败', 'error')

    except Exception as e:
        logger.error(f"Error deleting patent {patent_id}: {e}")
        flash(f'删除专利失败: {e}', 'error')

    return redirect(url_for('admin_patents.patents_list'))


@bp.route('/patents/<int:patent_id>/file')
@require_role('admin')
def patent_file(patent_id):
    """获取专利证书文件"""
    from flask import send_file, abort
    try:
        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()
        patent = patent_manager.get_patent_by_id(patent_id)

        if not patent or not patent.certificate_file:
            abort(404)

        # 获取文件完整路径 - 使用统一文件管理器根目录
        from backend.services.file_upload_service import get_file_upload_service
        file_manager = get_file_upload_service().file_manager
        
        # 使用统一文件管理器查找文件路径
        try:
            file_path = file_manager.find_file_by_path(patent.certificate_file)
        except FileNotFoundError:
            logger.error(f"Patent certificate file not found: {patent.certificate_file}")
            abort(404)

        if not file_path.exists():
            logger.error(f"Patent file not found: {file_path}")
            abort(404)

        return send_file(file_path)

    except Exception as e:
        logger.error(f"Error serving patent file {patent_id}: {e}")
        abort(500)


@bp.route('/api/patents/check-duplicate', methods=['POST'])
@require_role('admin')
def api_check_duplicate():
    """检查专利重复（AJAX）"""
    try:
        data = request.get_json()
        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()

        duplicate = patent_manager.check_duplicate(data)

        return jsonify({
            'has_duplicate': duplicate is not None,
            'duplicate_id': duplicate.id if duplicate else None,
            'duplicate_name': duplicate.patent_name if duplicate else None
        })

    except Exception as e:
        logger.error(f"Error checking duplicate: {e}")
        return jsonify({'error': str(e)}), 500


# ---------- 成果汇总页 Tab API（与 admin_achievement 成果页共用 URL） ----------

@bp.route('/api/achievements/patents')
@require_admin_or_lab_view_api
def api_achievements_patents():
    """API: 获取专利管理内容。实验室视图（laboratory_id 在 query）时仅返回该实验室数据，可只读、隐藏实验室列。"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        patent_type = request.args.get('patent_type', '').strip()
        inventor = request.args.get('inventor', '').strip()
        application_number = request.args.get('application_number', '').strip()
        laboratory_id = request.args.get('laboratory_id', type=int)

        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()
        laboratory_manager = app_context.get_laboratory_manager()
        teacher_manager = app_context.get_teacher_manager()
        from app.auth import get_current_user, can_edit_laboratory
        is_readonly = False
        hide_laboratory_filter = False
        if laboratory_id is not None:
            hide_laboratory_filter = True
            user_info = get_current_user()
            can_edit = can_edit_laboratory(user_info, laboratory_id, laboratory_manager, teacher_manager) if user_info else False
            is_readonly = not can_edit

        filter_kwargs = {
            'limit': per_page,
            'offset': (page - 1) * per_page
        }
        if patent_type:
            filter_kwargs['patent_type'] = patent_type
        if inventor:
            filter_kwargs['inventor'] = inventor
        if application_number:
            filter_kwargs['application_number'] = application_number
        if laboratory_id is not None:
            filter_kwargs['laboratory_id'] = laboratory_id

        filter_obj = PatentFilter(**filter_kwargs)
        patents = patent_manager.query_patents(filter_obj)
        laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

        html = render_template('admin/achievements/tabs/patent.html',
                             patents=patents,
                             laboratories=laboratories,
                             page=page,
                             per_page=per_page,
                             laboratory_id=laboratory_id,
                             is_readonly=is_readonly,
                             hide_laboratory_filter=hide_laboratory_filter)

        return jsonify({'success': True, 'html': html, 'total_count': len(patents)})
    except Exception as e:
        logger.error(f"Error loading patents tab: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/patents/<int:patent_id>', methods=['DELETE'])
@require_role_api('admin')
def delete_patent(patent_id):
    """删除单个专利（成果汇总页调用）"""
    try:
        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()
        success = patent_manager.delete_patent(patent_id)
        if success:
            return jsonify({'success': True, 'message': '删除成功'})
        return jsonify({'success': False, 'message': '专利不存在或删除失败'}), 404
    except Exception as e:
        logger.error(f"Error deleting patent {patent_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500


@bp.route('/patents/batch-delete', methods=['POST'])
@require_role_api('admin')
def patents_batch_delete():
    """批量删除专利（成果汇总页调用）"""
    try:
        data = request.get_json()
        patent_ids = data.get('patent_ids', [])
        if not patent_ids:
            return jsonify({'success': False, 'message': '请选择要删除的专利'}), 400

        app_context = get_app_context_instance()
        patent_manager = app_context.get_patent_manager()
        success_count = 0
        failed_count = 0
        errors = []
        for patent_id in patent_ids:
            try:
                patent_manager.delete_patent(patent_id)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f'ID {patent_id}: {str(e)}')

        if failed_count == 0:
            return jsonify({'success': True, 'message': f'成功删除 {success_count} 条专利'})
        return jsonify({
            'success': True,
            'message': f'成功删除 {success_count} 条，失败 {failed_count} 条',
            'errors': errors[:5]
        })
    except Exception as e:
        logger.error(f"Error batch deleting patents: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'批量删除失败: {str(e)}'}), 500
