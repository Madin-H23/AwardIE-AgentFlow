"""
Other Files Management Routes (管理员 - 其他类型文件管理)
"""
import logging
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, send_file
from pathlib import Path
from app.auth import require_role, require_role_api, require_admin_or_lab_view_api
from app.utils import get_app_context_instance
from backend.models.other_file import OtherFileManager, OtherFile, OtherFileFilter

logger = logging.getLogger(__name__)
bp = Blueprint('admin_other_files', __name__)


@bp.route('/other-files')
@require_role('admin')
def other_files_list():
    """其他类型文件列表"""
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    file_type = request.args.get('file_type', '').strip()
    is_image = request.args.get('is_image', type=bool)
    submitter_type = request.args.get('submitter_type', '').strip()
    laboratory_id = request.args.get('laboratory_id', type=int)

    try:
        # Get managers
        app_context = get_app_context_instance()
        file_manager = app_context.get_other_file_manager()

        # Build filter
        filter_obj = OtherFileFilter(
            file_type=file_type if file_type else None,
            is_image=is_image if request.args.get('is_image') else None,
            submitter_type=submitter_type if submitter_type else None,
            laboratory_id=laboratory_id,
            limit=per_page,
            offset=(page - 1) * per_page
        )

        # Query files
        files = file_manager.query_files(filter_obj)

        # Get all laboratories for filter dropdown
        laboratory_manager = app_context.get_laboratory_manager()
        laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

        return render_template('admin/other_files/list.html',
                             files=files,
                             page=page,
                             per_page=per_page,
                             filter_obj=filter_obj,
                             laboratories=laboratories)

    except Exception as e:
        logger.error(f"Error loading other files list: {e}")
        flash(f'加载文件列表失败: {e}', 'error')
        return render_template('admin/other_files/list.html',
                             files=[],
                             page=page,
                             per_page=per_page)


@bp.route('/other-files/<int:file_id>')
@require_role('admin')
def other_files_view(file_id):
    """查看文件详情"""
    try:
        app_context = get_app_context_instance()
        file_manager = app_context.get_other_file_manager()
        file = file_manager.get_file_by_id(file_id)

        if not file:
            flash('文件不存在', 'error')
            return redirect(url_for('admin_other_files.other_files_list'))

        # Get related laboratory info
        laboratory = None
        if file.laboratory_id:
            laboratory_manager = app_context.get_laboratory_manager()
            laboratory = laboratory_manager.get_laboratory_by_id(file.laboratory_id)

        # Get submitter info
        submitter = None
        if file.submitter_type and file.submitter_id:
            if file.submitter_type == 'student':
                student_manager = app_context.get_student_manager()
                submitter = student_manager.get_student_by_id(file.submitter_id)
            elif file.submitter_type == 'teacher':
                teacher_manager = app_context.get_teacher_manager()
                submitter = teacher_manager.get_teacher_by_id(file.submitter_id)

        return render_template('admin/other_files/view.html',
                             file=file,
                             laboratory=laboratory,
                             submitter=submitter)

    except Exception as e:
        logger.error(f"Error viewing file {file_id}: {e}")
        flash(f'加载文件详情失败: {e}', 'error')
        return redirect(url_for('admin_other_files.other_files_list'))


@bp.route('/other-files/upload', methods=['GET', 'POST'])
@require_role('admin')
def other_files_upload():
    """上传其他类型文件"""
    if request.method == 'GET':
        # Get laboratories for dropdown
        try:
            app_context = get_app_context_instance()
            laboratory_manager = app_context.get_laboratory_manager()
            laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

            return render_template('admin/other_files/upload.html',
                                 laboratories=laboratories)
        except Exception as e:
            logger.error(f"Error loading upload form: {e}")
            flash(f'加载上传表单失败: {e}', 'error')
            return redirect(url_for('admin_other_files.other_files_list'))

    # POST - Upload file
    try:
        app_context = get_app_context_instance()
        file_manager = app_context.get_other_file_manager()

        # Check for file
        if 'file' not in request.files:
            flash('请选择文件', 'error')
            return redirect(url_for('admin_other_files.other_files_upload'))

        uploaded_file = request.files['file']
        if not uploaded_file or not uploaded_file.filename:
            flash('请选择文件', 'error')
            return redirect(url_for('admin_other_files.other_files_upload'))

        # Get form data
        file_data = {
            'description': request.form.get('description', '').strip() or None,
            'submitter_type': 'admin',
            'submitter_id': session.get('user_id'),
            'laboratory_id': request.form.get('laboratory_id', type=int) or None,
        }

        # Upload file - 直接传递文件对象给OtherFileManager
        file = file_manager.add_file(uploaded_file, file_data)

        flash(f'文件 "{file.file_name}" 上传成功', 'success')
        return redirect(url_for('admin_other_files.other_files_view', file_id=file.id))

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        flash(f'上传文件失败: {e}', 'error')
        return redirect(url_for('admin_other_files.other_files_upload'))


@bp.route('/other-files/<int:file_id>/download')
@require_role('admin')
def other_files_download(file_id):
    """下载文件"""
    try:
        app_context = get_app_context_instance()
        file_manager = app_context.get_other_file_manager()
        file = file_manager.get_file_by_id(file_id)

        if not file:
            flash('文件不存在', 'error')
            return redirect(url_for('admin_other_files.other_files_list'))

        # Get full path using unified file manager
        from backend.services.unified_file_manager import get_unified_file_manager
        file_manager = get_unified_file_manager()
        try:
            full_path = file_manager.find_file_by_path(file.file_path)
        except FileNotFoundError:
            flash('文件不存在', 'error')
            return redirect(url_for('admin_other_files.other_files_list'))

        return send_file(full_path, as_attachment=True, download_name=file.file_name)

    except Exception as e:
        logger.error(f"Error downloading file {file_id}: {e}")
        flash(f'下载文件失败: {e}', 'error')
        return redirect(url_for('admin_other_files.other_files_view', file_id=file_id))


@bp.route('/other-files/<int:file_id>/edit', methods=['POST'])
@require_role('admin')
def other_files_edit(file_id):
    """编辑文件元数据"""
    try:
        app_context = get_app_context_instance()
        file_manager = app_context.get_other_file_manager()

        file_data = {
            'file_name': request.form.get('file_name', '').strip(),
            'description': request.form.get('description', '').strip() or None,
            'laboratory_id': request.form.get('laboratory_id', type=int) or None,
        }

        success = file_manager.update_file(file_id, file_data)

        if success:
            flash('文件信息更新成功', 'success')
        else:
            flash('文件信息更新失败', 'error')

        return redirect(url_for('admin_other_files.other_files_view', file_id=file_id))

    except Exception as e:
        logger.error(f"Error updating file {file_id}: {e}")
        flash(f'更新文件失败: {e}', 'error')
        return redirect(url_for('admin_other_files.other_files_view', file_id=file_id))


@bp.route('/other-files/<int:file_id>/delete', methods=['POST'])
@require_role('admin')
def other_files_delete(file_id):
    """删除文件"""
    try:
        delete_physical = request.form.get('delete_physical', '0') == '1'

        app_context = get_app_context_instance()
        file_manager = app_context.get_other_file_manager()

        success = file_manager.delete_file(file_id, delete_physical=delete_physical)

        if success:
            flash('文件删除成功', 'success')
        else:
            flash('文件删除失败', 'error')

    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        flash(f'删除文件失败: {e}', 'error')

    return redirect(url_for('admin_other_files.other_files_list'))


@bp.route('/api/other-files/<int:file_id>/preview', methods=['GET'])
@require_role('admin')
def api_file_preview(file_id):
    """获取文件预览信息（AJAX）"""
    try:
        app_context = get_app_context_instance()
        file_manager = app_context.get_other_file_manager()
        file = file_manager.get_file_by_id(file_id)

        if not file:
            return jsonify({'error': '文件不存在'}), 404

        # Get full path for preview using unified file manager
        from backend.services.unified_file_manager import get_unified_file_manager
        file_manager = get_unified_file_manager()
        try:
            full_path = file_manager.find_file_by_path(file.file_path)
        except FileNotFoundError:
            return jsonify({'error': '文件不存在'}), 404

        if not full_path.exists():
            return jsonify({'error': '文件不存在'}), 404

        # For images, return base64 data
        if file.is_image:
            import base64
            with open(full_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            return jsonify({
                'is_image': True,
                'data': image_data,
                'mime_type': f'image/{full_path.suffix[1:]}'
            })
        else:
            # For non-images, return file info
            return jsonify({
                'is_image': False,
                'file_name': file.file_name,
                'file_size': file.file_size,
                'file_type': file.file_type
            })

    except Exception as e:
        logger.error(f"Error previewing file {file_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ---------- 成果汇总页 Tab API（实验室下载文件） ----------

@bp.route('/api/achievements/other')
@require_admin_or_lab_view_api
def api_achievements_other():
    """API: 获取实验室下载文件管理内容。实验室视图（laboratory_id 在 query）时仅返回该实验室数据，可只读。"""
    try:
        import sqlite3
        from config.loader import get_config

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        lab_id = request.args.get('laboratory_id', type=int)

        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()
        teacher_manager = app_context.get_teacher_manager()
        from app.auth import get_current_user, can_edit_laboratory
        is_readonly = False
        if lab_id is not None:
            user_info = get_current_user()
            can_edit = can_edit_laboratory(user_info, lab_id, laboratory_manager, teacher_manager) if user_info else False
            is_readonly = not can_edit

        config = get_config()
        db_path = config.get_path("database", "competitions_db")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where_clause = ""
        params = []
        if lab_id:
            where_clause = "WHERE ld.laboratory_id = ?"
            params.append(lab_id)

        count_sql = f"SELECT COUNT(*) FROM laboratory_downloads ld {where_clause}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]

        offset = (page - 1) * per_page
        list_sql = f"""
            SELECT ld.*, l.name as laboratory_name
            FROM laboratory_downloads ld
            LEFT JOIN laboratories l ON ld.laboratory_id = l.id
            {where_clause}
            ORDER BY ld.display_order, ld.id DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(list_sql, params + [per_page, offset])
        rows = cursor.fetchall()
        conn.close()

        files = []
        for row in rows:
            files.append({
                'id': row['id'],
                'laboratory_id': row['laboratory_id'],
                'laboratory_name': row['laboratory_name'],
                'file_path': row['file_path'],
                'file_title': row['file_title'],
                'file_name': row['file_name'],
                'file_size': row['file_size'],
                'submitter_type': row['submitter_type'],
            })

        laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []
        laboratory_name = next((lab.name for lab in laboratories if lab.id == lab_id), None) if lab_id and laboratories else None
        html = render_template('admin/achievements/tabs/other.html',
                               files=files,
                               laboratories=laboratories,
                               page=page,
                               per_page=per_page,
                               laboratory_id=lab_id,
                               laboratory_name=laboratory_name,
                               is_readonly=is_readonly)
        return jsonify({'success': True, 'html': html, 'total_count': total_count})
    except Exception as e:
        logger.error(f"Error loading other tab: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
