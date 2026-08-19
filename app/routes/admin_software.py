"""
Software Copyright Management Routes (管理员 - 软著管理)
"""
import logging
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from pathlib import Path
from app.auth import require_role, require_role_api, require_admin_or_lab_view_api
from app.utils import get_app_context_instance
from backend.models.software_copyright import SoftwareCopyrightManager, SoftwareCopyright, SoftwareCopyrightFilter

logger = logging.getLogger(__name__)
bp = Blueprint('admin_software', __name__)


@bp.route('/software')
@require_role('admin')
def software_list():
    """软著列表页面"""
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    registration_number = request.args.get('registration_number', '').strip()
    copyright_owner = request.args.get('copyright_owner', '').strip()
    laboratory_id = request.args.get('laboratory_id', type=int)

    try:
        # Get managers
        app_context = get_app_context_instance()
        copyright_manager = app_context.get_software_copyright_manager()

        # Build filter
        filter_obj = SoftwareCopyrightFilter(
            registration_number=registration_number if registration_number else None,
            copyright_owner=copyright_owner if copyright_owner else None,
            laboratory_id=laboratory_id,
            limit=per_page,
            offset=(page - 1) * per_page
        )

        # Query software copyrights
        copyrights = copyright_manager.query_copyrights(filter_obj)

        # Get all laboratories for filter dropdown
        laboratory_manager = app_context.get_laboratory_manager()
        laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

        return render_template('admin/software/list.html',
                             copyrights=copyrights,
                             page=page,
                             per_page=per_page,
                             filter_obj=filter_obj,
                             laboratories=laboratories)

    except Exception as e:
        logger.error(f"Error loading software list: {e}")
        flash(f'加载软著列表失败: {e}', 'error')
        return render_template('admin/software/list.html',
                             copyrights=[],
                             page=page,
                             per_page=per_page)


@bp.route('/api/achievements/software')
@require_admin_or_lab_view_api
def api_achievements_software():
    """API: 获取软著管理内容。实验室视图（laboratory_id 在 query）时仅返回该实验室数据，可只读、隐藏实验室列。"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        laboratory_id = request.args.get('laboratory_id', type=int)

        app_context = get_app_context_instance()
        software_manager = app_context.get_software_copyright_manager()
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

        filter_kwargs = {'limit': per_page, 'offset': (page - 1) * per_page}
        if laboratory_id is not None:
            filter_kwargs['laboratory_id'] = laboratory_id
        filter_obj = SoftwareCopyrightFilter(**filter_kwargs)
        software_list = software_manager.query_copyrights(filter_obj)
        laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

        html = render_template('admin/achievements/tabs/software.html',
                             software_list=software_list,
                             laboratories=laboratories,
                             page=page,
                             per_page=per_page,
                             filter_obj=filter_obj,
                             laboratory_id=laboratory_id,
                             is_readonly=is_readonly,
                             hide_laboratory_filter=hide_laboratory_filter)

        return jsonify({'success': True, 'html': html, 'total_count': len(software_list)})
    except Exception as e:
        logger.error(f"Error loading software tab: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/software/<int:copyright_id>')
@require_role('admin')
def software_view(copyright_id):
    """查看软著详情"""
    try:
        app_context = get_app_context_instance()
        copyright_manager = app_context.get_software_copyright_manager()
        copyright = copyright_manager.get_copyright_by_id(copyright_id)

        if not copyright:
            flash('软著不存在', 'error')
            return redirect(url_for('admin_software.software_list'))

        # Get related laboratory info
        laboratory = None
        if copyright.laboratory_id:
            laboratory_manager = app_context.get_laboratory_manager()
            laboratory = laboratory_manager.get_laboratory_by_id(copyright.laboratory_id)

        return render_template('admin/software/view.html',
                             copyright=copyright,
                             laboratory=laboratory)

    except Exception as e:
        logger.error(f"Error viewing software {copyright_id}: {e}")
        flash(f'加载软著详情失败: {e}', 'error')
        return redirect(url_for('admin_software.software_list'))


@bp.route('/software/create', methods=['GET', 'POST'])
@require_role('admin')
def software_create():
    """创建新软著"""
    from backend.utils.users_sync import to_users_id
    from config.loader import get_config
    if request.method == 'GET':
        # Get laboratories for dropdown
        try:
            app_context = get_app_context_instance()
            laboratory_manager = app_context.get_laboratory_manager()
            laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

            return render_template('admin/software/edit.html',
                                 copyright=None,
                                 laboratories=laboratories)
        except Exception as e:
            logger.error(f"Error loading create form: {e}")
            flash(f'加载创建表单失败: {e}', 'error')
            return redirect(url_for('admin_software.software_list'))

    # POST - Create software copyright
    try:
        app_context = get_app_context_instance()
        copyright_manager = app_context.get_software_copyright_manager()

        # Get form data
        copyright_data = {
            'software_name': request.form.get('software_name', '').strip(),
            'software_version': request.form.get('software_version', '').strip() or None,
            'registration_number': request.form.get('registration_number', '').strip() or None,
            'certificate_no': request.form.get('certificate_no', '').strip() or None,
            'registration_date': request.form.get('registration_date', '').strip() or None,
            'copyright_owner': request.form.get('copyright_owner', '').strip() or None,
            'submitter_type': 'admin',
            'submitter_id': to_users_id(str(get_config().get_path('database', 'competitions_db')), session.get('user_id'), 'admin'),
            'laboratory_id': request.form.get('laboratory_id', type=int) or None,
        }

        # Handle file upload - 直接传递文件对象给SoftwareCopyrightManager
        uploaded_file = None
        if 'certificate_file' in request.files:
            file = request.files['certificate_file']
            if file and file.filename:
                uploaded_file = file

        # Validate required fields
        if not copyright_data['software_name']:
            flash('软件名称不能为空', 'error')
            return redirect(url_for('admin_software.software_create'))

        # Create software copyright
        copyright = copyright_manager.add_copyright(copyright_data, uploaded_file)

        flash(f'软著 "{copyright.software_name}" 创建成功', 'success')
        return redirect(url_for('admin_software.software_view', copyright_id=copyright.id))

    except ValueError as e:
        flash(f'创建失败: {e}', 'error')
        return redirect(url_for('admin_software.software_create'))
    except Exception as e:
        logger.error(f"Error creating software: {e}")
        flash(f'创建软著失败: {e}', 'error')
        return redirect(url_for('admin_software.software_create'))


def _teacher_can_edit_software(copyright_obj, app_context, session) -> bool:
    """教师是否有权限编辑该软著（未认领可认领，已认领且为该实验室指导教师可编辑）"""
    if session.get('role') != 'teacher':
        return True
    teacher_manager = app_context.get_teacher_manager()
    laboratory_manager = app_context.get_laboratory_manager()
    teacher = teacher_manager.get_teacher_by_teacher_id(session.get('user_id'))
    if not teacher or not laboratory_manager:
        return False
    lab_id = getattr(copyright_obj, 'laboratory_id', None)
    if lab_id is None:
        return laboratory_manager.is_teacher_in_lab(teacher.id)
    lab = laboratory_manager.get_laboratory_by_id(lab_id)
    return lab is not None and teacher in lab.instructors


@bp.route('/software/<int:copyright_id>/edit', methods=['GET', 'POST'])
@require_role('admin', 'teacher')
def software_edit(copyright_id):
    """编辑软著"""
    if request.method == 'GET':
        try:
            app_context = get_app_context_instance()
            copyright_manager = app_context.get_software_copyright_manager()
            copyright = copyright_manager.get_copyright_by_id(copyright_id)

            if not copyright:
                flash('软著不存在', 'error')
                return redirect(url_for('admin_software.software_list'))

            if not _teacher_can_edit_software(copyright, app_context, session):
                flash('您没有权限编辑该软著', 'error')
                return redirect(url_for('teacher.dashboard'))

            # Get laboratories for dropdown
            laboratory_manager = app_context.get_laboratory_manager()
            laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

            return render_template('admin/software/edit.html',
                                 copyright=copyright,
                                 laboratories=laboratories)

        except Exception as e:
            logger.error(f"Error loading edit form: {e}")
            flash(f'加载编辑表单失败: {e}', 'error')
            return redirect(url_for('admin_software.software_list'))

    # POST - Update software copyright
    try:
        app_context = get_app_context_instance()
        copyright_manager = app_context.get_software_copyright_manager()
        copyright = copyright_manager.get_copyright_by_id(copyright_id)
        if not copyright:
            flash('软著不存在', 'error')
            return redirect(url_for('admin_software.software_list'))
        if not _teacher_can_edit_software(copyright, app_context, session):
            flash('您没有权限编辑该软著', 'error')
            return redirect(url_for('teacher.dashboard'))

        # Get form data
        copyright_data = {
            'software_name': request.form.get('software_name', '').strip(),
            'software_version': request.form.get('software_version', '').strip() or None,
            'registration_number': request.form.get('registration_number', '').strip() or None,
            'certificate_no': request.form.get('certificate_no', '').strip() or None,
            'registration_date': request.form.get('registration_date', '').strip() or None,
            'copyright_owner': request.form.get('copyright_owner', '').strip() or None,
            'laboratory_id': request.form.get('laboratory_id', type=int) or None,
        }

        # Handle file upload - 直接传递文件对象给SoftwareCopyrightManager
        uploaded_file = None
        if 'certificate_file' in request.files:
            file = request.files['certificate_file']
            if file and file.filename:
                uploaded_file = file

        # Validate required fields
        if not copyright_data['software_name']:
            flash('软件名称不能为空', 'error')
            return redirect(url_for('admin_software.software_edit', copyright_id=copyright_id))

        # Update software copyright
        success = copyright_manager.update_copyright(copyright_id, copyright_data, uploaded_file)

        if success:
            flash('软著更新成功', 'success')
            return redirect(url_for('admin_software.software_view', copyright_id=copyright_id))
        else:
            flash('软著更新失败', 'error')
            return redirect(url_for('admin_software.software_edit', copyright_id=copyright_id))

    except Exception as e:
        logger.error(f"Error updating software {copyright_id}: {e}")
        flash(f'更新软著失败: {e}', 'error')
        return redirect(url_for('admin_software.software_edit', copyright_id=copyright_id))


@bp.route('/software/<int:copyright_id>/delete', methods=['POST'])
@require_role('admin')
def software_delete(copyright_id):
    """删除软著"""
    try:
        app_context = get_app_context_instance()
        copyright_manager = app_context.get_software_copyright_manager()

        success = copyright_manager.delete_copyright(copyright_id)

        if success:
            flash('软著删除成功', 'success')
        else:
            flash('软著删除失败', 'error')

    except Exception as e:
        logger.error(f"Error deleting software {copyright_id}: {e}")
        flash(f'删除软著失败: {e}', 'error')

    return redirect(url_for('admin_software.software_list'))


def _mimetype_for_path(path) -> str:
    """根据文件扩展名返回 mimetype，用于 send_file。"""
    suf = (path.suffix or "").lower()
    if suf == ".pdf":
        return "application/pdf"
    if suf in (".png",):
        return "image/png"
    if suf in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suf in (".gif", ".webp"):
        return f"image/{suf[1:]}"
    return "application/octet-stream"


@bp.route('/software/<int:copyright_id>/file')
@require_role('admin')
def software_file(copyright_id):
    """获取软著证书文件

    支持回退机制：
    1. 使用 certificate_file 路径，经 find_file_by_path 解析（PDF 优先返回同目录 PNG）
    2. 若不存在且为 PDF，尝试 temp_upload/pdf_previews 下的同名 PNG
    """
    from flask import send_file, abort
    from pathlib import Path
    from werkzeug.exceptions import HTTPException

    try:
        app_context = get_app_context_instance()
        copyright_manager = app_context.get_software_copyright_manager()
        copyright = copyright_manager.get_copyright_by_id(copyright_id)

        if not copyright or not copyright.certificate_file:
            abort(404)

        from backend.services.file_upload_service import get_file_upload_service
        from backend.services.unified_file_manager import get_unified_file_manager, SessionStatus

        file_manager = get_file_upload_service().file_manager

        try:
            file_path = file_manager.find_file_by_path(copyright.certificate_file)
        except FileNotFoundError:
            logger.warning("Software certificate file not found: %s", copyright.certificate_file)
            # PDF 时尝试 pdf_previews 下的 PNG
            rel = Path(copyright.certificate_file)
            if rel.suffix.lower() != ".pdf":
                abort(404)
            fm = get_unified_file_manager()
            preview_dir = fm.files_root / SessionStatus.TEMP_UPLOAD.directory / "pdf_previews"
            preview_name = rel.name[:-4] + ".png"  # xxx.pdf -> xxx.png
            preview_path = preview_dir / preview_name
            if not preview_path.exists():
                abort(404)
            return send_file(
                str(preview_path),
                mimetype="image/png",
                download_name=preview_path.name,
            )

        if not file_path.exists():
            abort(404)

        return send_file(
            str(file_path),
            mimetype=_mimetype_for_path(file_path),
            download_name=file_path.name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error serving software file %s: %s", copyright_id, e)
        abort(500)


@bp.route('/api/software/check-duplicate', methods=['POST'])
@require_role('admin')
def api_check_duplicate():
    """检查软著重复（AJAX）"""
    try:
        data = request.get_json()
        app_context = get_app_context_instance()
        copyright_manager = app_context.get_software_copyright_manager()

        duplicate = copyright_manager.check_duplicate(data)

        return jsonify({
            'has_duplicate': duplicate is not None,
            'duplicate_id': duplicate.id if duplicate else None,
            'duplicate_name': duplicate.software_name if duplicate else None
        })

    except Exception as e:
        logger.error(f"Error checking duplicate: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/software/batch-delete', methods=['POST'])
@require_role('admin')
def software_batch_delete():
    """批量删除软著"""
    try:
        data = request.get_json()
        copyright_ids = data.get('copyright_ids', [])

        if not copyright_ids:
            return jsonify({'success': False, 'message': '请选择要删除的软著'}), 400

        app_context = get_app_context_instance()
        copyright_manager = app_context.get_software_copyright_manager()

        success_count = 0
        failed_count = 0
        errors = []

        for copyright_id in copyright_ids:
            try:
                copyright_manager.delete_copyright(copyright_id)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f'ID {copyright_id}: {str(e)}')

        if failed_count == 0:
            return jsonify({
                'success': True,
                'message': f'成功删除 {success_count} 条软著'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'删除完成：成功 {success_count} 条，失败 {failed_count} 条',
                'errors': errors
            }), 207  # 207 Multi-Status

    except Exception as e:
        logger.error(f"Error batch deleting software: {e}")
        return jsonify({'success': False, 'message': f'批量删除失败: {str(e)}'}), 500


@bp.route('/software/<int:copyright_id>', methods=['DELETE'])
@require_role_api('admin')
def delete_software(copyright_id):
    """删除单个软著（成果汇总页调用，DELETE 方法）"""
    try:
        app_context = get_app_context_instance()
        software_manager = app_context.get_software_copyright_manager()
        success = software_manager.delete_copyright(copyright_id)
        if success:
            return jsonify({'success': True, 'message': '软著删除成功'})
        return jsonify({'success': False, 'message': '软著删除失败'}), 400
    except Exception as e:
        logger.error(f"Error deleting software {copyright_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500
