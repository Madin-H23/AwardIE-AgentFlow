"""
管理员 - 成果相关路由（成果汇总页、文件导入等）
奖状相关路由在 app/routes/admin_awards.py。
"""
import logging
import json
import shutil
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, session
from pathlib import Path
from app.auth import require_role, require_role_api, require_admin_or_lab_view_api
from app.utils import get_app_context_instance
from app.routes.review_helpers import normalize_related_student_from_ids
from app.routes.file_import_helpers import (
    get_achievement_types_config,
    get_achievement_types,
    get_data_import_types,
    get_type_names,
    get_file_import_params,
    calculate_type_stats,
    adjust_tab_and_status,
    query_pending_items,
    get_current_item,
    get_all_reference_data,
    process_validation_result,
    process_award_item,
    process_non_award_item,
)
logger = logging.getLogger(__name__)
bp = Blueprint('admin_achievement', __name__)


def _resolve_laboratory_by_first_supervisor(achievement_data, achievement_type, teacher_manager, laboratory_manager):
    """
    根据成果数据中的第一导师（指导教师）解析所属实验室。
    用于导入/抽取时自动关联实验室。
    返回 (laboratory_id: int|None, reason: str)。
    """
    if not achievement_data or not isinstance(achievement_data, dict):
        return None, ""
    if not teacher_manager or not laboratory_manager:
        return None, ""
    first_name = None
    if achievement_type == "award":
        raw = achievement_data.get("supervisor_name") or achievement_data.get("supervisor")
        if raw and isinstance(raw, str):
            first_name = raw.split(",")[0].split("，")[0].split("、")[0].strip()
    elif achievement_type == "innovation":
        teachers_raw = achievement_data.get("指导教师") or achievement_data.get("supervisors") or achievement_data.get("teachers")
        if isinstance(teachers_raw, list) and teachers_raw:
            first_name = (teachers_raw[0] or "").strip() if isinstance(teachers_raw[0], str) else None
        elif isinstance(teachers_raw, str) and teachers_raw.strip():
            first_name = teachers_raw.split(",")[0].split("，")[0].split("、")[0].strip()
        if not first_name and achievement_data.get("projects"):
            first_proj = achievement_data["projects"][0] if achievement_data["projects"] else None
            if isinstance(first_proj, dict):
                teachers_raw = first_proj.get("指导教师") or first_proj.get("supervisors") or first_proj.get("teachers")
                if isinstance(teachers_raw, list) and teachers_raw:
                    first_name = (teachers_raw[0] or "").strip() if isinstance(teachers_raw[0], str) else None
                elif isinstance(teachers_raw, str) and teachers_raw.strip():
                    first_name = teachers_raw.split(",")[0].split("，")[0].split("、")[0].strip()
    else:
        raw = achievement_data.get("指导教师") or achievement_data.get("supervisor_name") or achievement_data.get("supervisors")
        if raw and isinstance(raw, str):
            first_name = raw.split(",")[0].split("，")[0].split("、")[0].strip()
        elif isinstance(raw, list) and raw and isinstance(raw[0], str):
            first_name = raw[0].strip()
    if not first_name:
        return None, ""
    found = teacher_manager.find_teachers_by_name(first_name)
    if not found:
        return None, ""
    teacher = found[0]
    lab = laboratory_manager.get_laboratory_by_teacher_id(teacher.id)
    if not lab:
        return None, ""
    return lab.id, f"根据第一导师 {first_name} 关联"


def _resolve_laboratory_id_for_innovation_project(project_dict, teacher_manager, laboratory_manager):
    """
    根据单个大创项目的指导教师解析所属实验室。
    用于导入时为每个项目独立关联实验室。
    返回 laboratory_id (int|None)。
    """
    if not project_dict or not isinstance(project_dict, dict):
        return None
    if not teacher_manager or not laboratory_manager:
        return None
    teachers_raw = project_dict.get("指导教师") or project_dict.get("supervisors") or project_dict.get("teachers")
    first_name = None
    if isinstance(teachers_raw, list) and teachers_raw:
        first_name = (teachers_raw[0] or "").strip() if isinstance(teachers_raw[0], str) else None
    elif isinstance(teachers_raw, str) and teachers_raw.strip():
        first_name = teachers_raw.split(",")[0].split("，")[0].split("、")[0].strip()
    if not first_name:
        return None
    found = teacher_manager.find_teachers_by_name(first_name)
    if not found:
        return None
    lab = laboratory_manager.get_laboratory_by_teacher_id(found[0].id)
    return lab.id if lab else None


def _ensure_innovation_laboratory_resolved(session_id, pending_manager, teacher_manager, laboratory_manager):
    """
    对当前 session 下所有大创 pending 的每个项目补齐 laboratory_id 并持久化。
    进入文件导入结果页（大创 tab）时调用，保证「关联学生实验室」列有值（含历史导入）。
    """
    if not session_id or not pending_manager or not teacher_manager or not laboratory_manager:
        return
    from backend.models.pending_achievement import PendingAchievementFilter
    filter_obj = PendingAchievementFilter(
        achievement_type='innovation',
        status='pending',
        import_session_id=session_id,
        limit=1000
    )
    items = pending_manager.query_pending(filter_obj)
    for pending in items:
        achievement_data = pending.get_achievement_data()
        if not isinstance(achievement_data, dict):
            continue
        projects = achievement_data.get('projects') or []
        if not projects:
            continue
        modified = False
        for p in projects:
            if not isinstance(p, dict):
                continue
            if p.get('laboratory_id') is not None:
                continue
            lab_id = _resolve_laboratory_id_for_innovation_project(p, teacher_manager, laboratory_manager)
            if lab_id is not None:
                p['laboratory_id'] = lab_id
                modified = True
        if modified:
            pending_manager.update(pending_item=pending, achievement_data=achievement_data)
            logger.info(
                "[导入结果页] 已为大创 session %s pending_id=%s 补齐 %d 个项目的 laboratory_id",
                session_id, pending.id, len(projects)
            )


@bp.route('/achievements')
@require_role('admin')
def achievements():
    """成果管理统一页面 - 包含5个tab: 奖状/专利/软著/大创/其他文件"""
    tab = request.args.get('tab', 'award')

    app_context = get_app_context_instance()
    competition_manager = app_context.get_competition_manager()
    laboratory_manager = app_context.get_laboratory_manager()

    competitions = competition_manager.competitions if hasattr(competition_manager, 'competitions') else []
    laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []

    return render_template('admin/achievements.html',
                         tab=tab,
                         competitions=competitions,
                         laboratories=laboratories)


@bp.route('/api/achievements/counts')
@require_admin_or_lab_view_api
def api_achievements_counts():
    """API: 实验室成果展示页各 tab 总数（仅当 laboratory_id 在 query 时返回各类型数量）。"""
    laboratory_id = request.args.get('laboratory_id', type=int)
    if laboratory_id is None:
        return jsonify({'success': True, 'award': 0, 'patent': 0, 'software': 0, 'innovation': 0, 'other': 0})

    try:
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()

        count_params = {
            'with_associations': False,
            'laboratory_id': laboratory_id,
            'exclude_teacher_certificates': True,
            'granted_role': '学生',
            'limit': None,
            'offset': None,
            'student_manager': student_manager,
            'teacher_manager': teacher_manager,
        }
        total_awards = award_manager.query_awards(**count_params)
        award_count = len(total_awards) if total_awards else 0

        patent_count = 0
        patent_manager = app_context.get_patent_manager()
        if patent_manager:
            from backend.models.patent import PatentFilter
            filter_obj = PatentFilter(laboratory_id=laboratory_id)
            patents = patent_manager.query_patents(filter_obj)
            patent_count = len(patents)

        software_count = 0
        software_manager = app_context.get_software_copyright_manager()
        if software_manager:
            from backend.models.software_copyright import SoftwareCopyrightFilter
            filter_obj = SoftwareCopyrightFilter(laboratory_id=laboratory_id)
            software_list = software_manager.query_copyrights(filter_obj)
            software_count = len(software_list)

        innovation_count = 0
        innovation_manager = app_context.get_innovation_project_manager()
        if innovation_manager:
            from backend.models.innovation_project import InnovationProjectFilter
            filter_obj = InnovationProjectFilter(laboratory_id=laboratory_id)
            projects = innovation_manager.query_projects(filter_obj)
            innovation_count = len(projects)

        other_count = 0
        from config.loader import get_config
        import sqlite3
        config = get_config()
        db_path = config.get_path("database", "competitions_db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM laboratory_downloads WHERE laboratory_id = ?", (laboratory_id,))
        other_count = cursor.fetchone()[0]
        conn.close()

        return jsonify({
            'success': True,
            'award': award_count,
            'patent': patent_count,
            'software': software_count,
            'innovation': innovation_count,
            'other': other_count,
        })
    except Exception as e:
        logger.exception("api_achievements_counts 失败")
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== 成果/文件导入功能 ====================

@bp.route('/file-import')
@require_role('admin')
def file_import():
    """文件上传页面"""
    return render_template('admin/file_import/upload.html')


@bp.route('/file-import/manual/upload', methods=['POST'])
@require_role_api('admin')
def file_import_manual_upload():
    """手动导入：上传单个文件到临时目录，返回 file_path"""
    from pathlib import Path
    from config.loader import get_config
    import uuid
    try:
        files = request.files.getlist('files')
        if not files or not any(f and f.filename for f in files):
            return jsonify({'success': False, 'message': '请选择文件'}), 400
        file = next(f for f in files if f and f.filename)
        config_loader = get_config()
        base_temp_dir = config_loader.get_path("temp_dir")
        manual_dir = base_temp_dir / "manual_import"
        manual_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}_{file.filename}"
        save_path = manual_dir / safe_name
        file.save(str(save_path))
        # 返回相对路径供 parse 使用
        relative_path = str(save_path.relative_to(base_temp_dir)) if base_temp_dir in save_path.parents else str(save_path)
        return jsonify({'success': True, 'file_path': relative_path})
    except Exception as e:
        logger.exception("manual upload failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/file-import/manual/parse', methods=['POST'])
@require_role_api('admin')
def file_import_manual_parse():
    """手动导入：按指定类型解析文件，返回抽取结果与 redirect_url"""
    try:
        data = request.get_json() or {}
        achievement_type = (data.get('achievement_type') or '').strip().lower()
        file_path = data.get('file_path')
        use_ocr_cache = data.get('use_ocr_cache', True)
        use_llm_cache = data.get('use_llm_cache', True)
        if not file_path:
            return jsonify({'success': False, 'message': '缺少 file_path'}), 400
        if achievement_type not in ('award', 'patent', 'software'):
            return jsonify({'success': False, 'message': f'不支持的成果类型: {achievement_type}'}), 400
        from pathlib import Path
        from config.loader import get_config
        config_loader = get_config()
        base_temp_dir = config_loader.get_path("temp_dir")
        full_path = Path(base_temp_dir) / file_path if not Path(file_path).is_absolute() else Path(file_path)
        if not full_path.exists():
            return jsonify({'success': False, 'message': '文件不存在'}), 400
        from app.utils import get_app_context_instance
        app_context = get_app_context_instance()
        from app.utils import get_doc_rec_context
        framework = get_doc_rec_context().extract_framework
        from backend.services.manual_import_service import ManualImportService
        service = ManualImportService(framework)
        from backend.extract.types import ExtractStatus
        result = service.parse_by_type(str(full_path), achievement_type, use_ocr_cache=use_ocr_cache, use_llm_cache=use_llm_cache)
        if not result or result.status != ExtractStatus.SUCCESS:
            return jsonify({
                'success': False,
                'message': getattr(result, 'error_message', None) or '解析失败'
            }), 400
        # 写入 pending：将文件复制到 files_root/temp_upload/ 并存相对路径，便于跨服务器部署与 move_to_review
        pending_manager = app_context.get_pending_achievement_manager()
        import hashlib
        import shutil
        from datetime import datetime
        from app.utils import calculate_file_hash
        from backend.services.unified_file_manager import get_unified_file_manager
        session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()
        file_hash = calculate_file_hash(str(full_path)) or ''
        file_manager = get_unified_file_manager()
        target_dir = file_manager.files_root / 'temp_upload' / session_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / Path(full_path).name
        shutil.copy2(str(full_path), str(target_path))
        path_for_db = f"temp_upload/{session_id}/{target_path.name}"
        pending_item = None
        if hasattr(pending_manager, 'create_from_extract_result'):
            result.metadata = result.metadata or {}
            result.metadata['session_id'] = session_id
            result.template_type = getattr(result, 'template_type', None) or achievement_type
            pending_item = pending_manager.create_from_extract_result(
                result,
                submitter_type='admin',
                submitter_id=session.get('user_id') or 0,
                file_path=path_for_db,
                file_hash=file_hash,
                status='pending'
            )
        # PDF 时生成第一页预览图，供内联表单与 results 页显示
        preview_image_path = None
        if target_path.suffix.lower() == '.pdf':
            try:
                from backend.utils.pdf_to_image import get_or_create_pdf_preview
                preview_dir = target_dir / 'preview'
                preview_dir.mkdir(parents=True, exist_ok=True)
                preview_path = get_or_create_pdf_preview(str(target_path), preview_dir)
                if preview_path:
                    preview_path_obj = Path(preview_path)
                    try:
                        preview_relative = preview_path_obj.relative_to(file_manager.files_root)
                        preview_image_path = str(preview_relative).replace('\\', '/')
                    except ValueError:
                        logger.warning("[手动导入PDF预览] 预览图不在 files_root 下: %s", preview_path)
            except Exception as e:
                logger.warning("[手动导入PDF预览] 生成失败: %s", e, exc_info=True)
        if preview_image_path and pending_item:
            ad = pending_item.get_achievement_data() if hasattr(pending_item, 'get_achievement_data') else {}
            if isinstance(ad, dict):
                ad = dict(ad)
                ad['preview_image_path'] = preview_image_path
                pending_manager.update(pending_item, achievement_type, ad)
        redirect_url = url_for('admin_achievement.file_import_results', session_id=session_id, tab=achievement_type, sub_tab='valid')
        ocr_text = getattr(result, 'ocr_text', None) or ''

        # 计算学生和指导教师的状态列表（用于显示匹配状态和重名检测）
        winner_status_list = []
        supervisor_status_list = []
        achievement_data = result.data if hasattr(result, 'data') else {}

        if achievement_type == 'award':
            # 处理学生获奖者状态（winner_name 可能是字符串或列表，统一转为字符串）
            winner_name_raw = achievement_data.get('winner_name', '')
            winner_name = winner_name_raw
            if isinstance(winner_name_raw, list):
                winner_name = ','.join(str(n).strip() for n in winner_name_raw if n)
            elif winner_name_raw is not None and not isinstance(winner_name_raw, str):
                winner_name = str(winner_name_raw)
            else:
                winner_name = winner_name_raw or ''
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
                            'obj': exact_matches[0],
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

        # 返回解析后的数据用于内联表单显示
        achievement_data = result.data if hasattr(result, 'data') else {}
        logger.info(f"[手动导入解析] achievement_data keys: {list(achievement_data.keys()) if achievement_data else []}, competition_name={achievement_data.get('competition_name') if achievement_data else None}")

        return jsonify({
            'success': True,
            'redirect_url': redirect_url,
            'data': achievement_data,
            'template_type': result.template_type,
            'session_id': session_id,
            'ocr_text': ocr_text,
            'file_path': path_for_db,  # 添加文件路径用于显示图片
            'preview_image_path': preview_image_path,  # PDF 时第一页预览图路径，供 img 显示
            'winner_status_list': winner_status_list,  # 添加学生状态列表
            'supervisor_status_list': supervisor_status_list  # 添加指导教师状态列表
        })
    except Exception as e:
        logger.exception("manual parse failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/file-import/manual/submit', methods=['POST'])
@require_role_api('admin')
def file_import_manual_submit():
    """手动导入：更新 pending 记录并提交（管理员自动归档）"""
    try:
        data = request.get_json() or {}
        achievement_type = (data.get('achievement_type') or '').strip().lower()
        achievement_data = data.get('achievement_data')
        submitter_type = data.get('submitter_type', 'admin')
        session_id = data.get('session_id')

        if not achievement_type:
            return jsonify({'success': False, 'message': '缺少 achievement_type'}), 400
        if achievement_data is None:
            return jsonify({'success': False, 'message': '缺少 achievement_data'}), 400
        if not session_id:
            return jsonify({'success': False, 'message': '缺少 session_id'}), 400

        # 获取 app_context
        from app.utils import get_app_context_instance
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

        # 调用 review_service.submit_achievement 提交（管理员会自动归档）
        review_service = _get_review_service(app_context)
        result = review_service.submit_achievement(pending_item.id, submitter_type, session.get('user_id') or 0)

        if not result.success:
            return jsonify({'success': False, 'message': result.error or '提交失败'}), 500

        # 根据返回的 action 确定提示消息
        if result.action == 'approved':
            message = '已归档，数据已成功导入主数据库'
        elif result.action == 'auto_archive_started':
            message = '已提交，系统将自动归档'
        else:
            message = '提交成功，等待审核'

        logger.info(f"[手动导入提交] pending_id={pending_item.id}, session_id={session_id}, 类型={achievement_type}, action={result.action}")

        return jsonify({
            'success': True,
            'message': message,
            'pending_id': pending_item.id,
            'action': result.action
        })
    except Exception as e:
        logger.exception("manual submit failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/file-import/progress')
@require_role('admin')
def file_import_progress():
    """获取文件导入进度（从独立存储读取，支持解析阶段轮询）。"""
    from app.import_progress_store import get_progress_or_idle
    task_id = request.args.get('task_id', '').strip()
    progress = get_progress_or_idle(task_id)
    return jsonify(progress)

@bp.route('/file-import/upload', methods=['POST'])
@require_role_api('admin')
def file_import_upload():
    """处理文件上传（使用 FileUploadService，与测试文件保持一致）"""
    import hashlib
    from pathlib import Path
    from datetime import datetime
    from backend.services.file_upload_service import FileUploadService

    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()
        laboratory_manager = app_context.get_laboratory_manager()

        # 获取上传的文件
        files = request.files.getlist('files')
        if not files:
            return jsonify({'success': False, 'message': '请选择要上传的文件'}), 400

        # 获取缓存选项
        use_ocr_cache = request.form.get('use_ocr_cache', '1') == '1'
        use_llm_cache = request.form.get('use_llm_cache', '1') == '1'

        # 获取实验室关联模式和指定指导教师
        lab_association_mode = request.form.get('lab_association_mode', 'auto')
        default_supervisor_name = request.form.get('default_supervisor_name', '').strip()

        logger.info(f"[文件导入] lab_association_mode={lab_association_mode}, default_supervisor_name={default_supervisor_name}")

        # 从配置文件获取临时目录
        from config.loader import get_config
        config_loader = get_config()
        base_temp_dir = config_loader.get_path("temp_dir")

        # 导入会话ID：前端可传 task_id 以便轮询进度，否则服务端生成
        client_task_id = request.form.get('task_id', '').strip()
        if client_task_id:
            import_session_id = client_task_id
        else:
            import_session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()

        # 创建会话专用临时目录（FileUploadService 会在这个目录下管理文件）
        temp_dir = base_temp_dir / f"file_import_{import_session_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 FileUploadService
        upload_service = FileUploadService()

        # 统计结果
        results = {
            'award': {'valid': 0, 'invalid': 0},
            'patent': {'valid': 0, 'invalid': 0},
            'software': {'valid': 0, 'invalid': 0},
            'innovation': {'valid': 0, 'invalid': 0},
            'other': {'valid': 0, 'invalid': 0}
        }

        submitter_id = session.get('user_id')
        submitter_type = 'admin'

        from backend.services.unified_file_manager import get_unified_file_manager
        from backend.extract.types import ExtractStatus
        from app.utils import get_doc_rec_context
        file_manager = get_unified_file_manager()
        framework = get_doc_rec_context().extract_framework

        # 初始化进度（写入独立存储，供进度接口在解析阶段轮询）
        valid_files = [f for f in files if f and f.filename]
        from app.import_progress_store import set_progress, update_progress
        initial_progress = {
            'total': len(valid_files),
            'current': 0,
            'current_file': '',
            'current_step': '正在处理文件...',
            'status': 'processing',
            'uploaded_count': len(valid_files),
            'stats': {
                'award': {'valid': 0, 'invalid': 0},
                'patent': {'valid': 0, 'invalid': 0},
                'software': {'valid': 0, 'invalid': 0},
                'innovation': {'valid': 0, 'invalid': 0},
                'other': {'valid': 0, 'invalid': 0}
            },
            'errors': []
        }
        set_progress(import_session_id, initial_progress)

        # 使用 FileUploadService 处理每个文件（与测试文件保持一致）
        for idx, file in enumerate(valid_files):
            if not file or not file.filename:
                continue

            try:
                # 更新进度：正在处理/解析当前文件（写入存储供前端轮询）
                update_progress(import_session_id, current=idx + 1, current_file=file.filename,
                               current_step=f'正在识别: {file.filename}', stats=dict(results))

                # 1. 仅上传文件到临时目录（FileUploadService 只接受 uploaded_file）
                upload_result = upload_service.upload_file(file)

                if not upload_result.success:
                    logger.error(f"文件上传失败: {file.filename}, 错误: {upload_result.error}")
                    results['other']['invalid'] += 1
                    continue

                full_path = file_manager.files_root / upload_result.relative_path
                if not full_path.exists():
                    logger.error(f"上传文件不存在: {full_path}")
                    results['other']['invalid'] += 1
                    continue

                # 2. 按路径自动识别类型并抽取，再创建 pending
                result = framework.extract(str(full_path), use_ocr_cache, use_llm_cache)

                if result.status != ExtractStatus.SUCCESS:
                    # 识别失败：作为 other 类型提交审核，并写入异常说明供页面展示
                    try:
                        data = {
                            'import_session_id': import_session_id,
                            'file_name': file.filename,
                            'file_path': upload_result.relative_path,
                            'file_type': Path(file.filename).suffix.lower()
                        }
                        note = (result.data or {}).get('note') or (getattr(result, 'error_message', None) or '识别失败，已转为其他类型处理。')
                        data['note'] = note
                        validation = {'is_valid': True, 'completeness_issues': []}
                        ext_info = {'import_session_id': import_session_id}
                        pending_manager.submit_for_review(
                            achievement_type='other',
                            achievement_data=data,
                            validation_result=validation,
                            submitter_type=submitter_type,
                            submitter_id=submitter_id,
                            file_path=upload_result.relative_path,
                            status='pending',
                            file_hash=upload_result.file_hash,
                            ext_info=ext_info
                        )
                        results['other']['valid'] += 1
                    except Exception as e:
                        logger.error(f"创建其他文件记录失败: {e}", exc_info=True)
                        results['other']['invalid'] += 1
                    continue

                # 3. 抽取成功：从 ExtractResult 创建 pending（存相对路径便于跨服务器部署）
                result.metadata = result.metadata or {}
                result.metadata['session_id'] = import_session_id

                # 计算实验室ID（根据关联模式）
                laboratory_id = None
                if lab_association_mode and lab_association_mode != 'none':
                    if lab_association_mode.startswith('specific:'):
                        # 指定实验室模式：从 "specific:lab_id" 中提取 lab_id
                        try:
                            laboratory_id = int(lab_association_mode.split(':', 1)[1])
                        except (ValueError, IndexError) as e:
                            logger.warning(f"[文件导入] 解析指定实验室ID失败: {lab_association_mode}, {e}")
                    elif lab_association_mode == 'auto':
                        # 自动关联模式：在更新achievement_data后处理（需要指导教师信息）
                        pass

                pending = pending_manager.create_from_extract_result(
                    result,
                    submitter_type=submitter_type,
                    submitter_id=submitter_id,
                    file_path=upload_result.relative_path,
                    file_hash=upload_result.file_hash,
                    status='pending',
                    laboratory_id=laboratory_id
                )

                # 如果是PDF文件，生成首页预览图
                preview_image_path = None
                if upload_result.relative_path and upload_result.relative_path.lower().endswith('.pdf'):
                    try:
                        from backend.utils.pdf_to_image import get_or_create_pdf_preview
                        from backend.services.unified_file_manager import get_unified_file_manager

                        file_manager = get_unified_file_manager()
                        # 获取PDF文件的完整路径
                        full_pdf_path = file_manager.find_file_by_path(upload_result.relative_path)

                        if full_pdf_path and full_pdf_path.exists():
                            # 预览图保存在同一目录下的preview子目录
                            preview_dir = full_pdf_path.parent / 'preview'
                            preview_dir.mkdir(parents=True, exist_ok=True)

                            # 生成或获取预览图
                            preview_path = get_or_create_pdf_preview(str(full_pdf_path), preview_dir)

                            if preview_path:
                                # 计算相对路径（从files_root开始）
                                try:
                                    preview_path_obj = Path(preview_path)
                                    preview_relative = preview_path_obj.relative_to(file_manager.files_root)
                                    preview_image_path = str(preview_relative).replace('\\', '/')
                                except ValueError:
                                    logger.warning(f"[PDF预览] 预览图不在files_root目录下: {preview_path}")
                    except Exception as e:
                        logger.warning(f"[PDF预览] 生成预览图失败: {e}", exc_info=True)
                if not pending:
                    logger.error("create_from_extract_result 未返回 pending")
                    results['other']['invalid'] += 1
                    continue

                # 获取验证结果
                validation_result = pending.get_validation_result()
                is_valid = validation_result.get('is_valid', False) if validation_result else False
                
                # 严格判断验证结果：只有当 is_valid 明确为 True 时才认为是识别成功
                if not isinstance(is_valid, bool):
                    is_valid = False
                
                # 额外检查：如果有任何验证问题，也应该视为待修订
                if is_valid:
                    content_issues = validation_result.get('content_issues', []) if validation_result else []
                    completeness_issues = validation_result.get('completeness_issues', []) if validation_result else []
                    if content_issues or completeness_issues:
                        is_valid = False
                        logger.info(f"检测到验证问题，将状态设置为待修订: content_issues={len(content_issues)}, completeness_issues={len(completeness_issues)}")

                # 根据验证结果设置状态（新流程：识别成功和待修订都使用 pending 状态）
                status = 'pending'  # 新流程：统一使用 pending 状态

                # 更新 achievement_data 添加 import_session_id 和其他元数据
                # 确保与模板期望的字段一致（ocr_result, llm_response, matched_template_name, template_id）
                achievement_data = pending.get_achievement_data()
                if not isinstance(achievement_data, dict):
                    achievement_data = {}
                
                # 添加导入会话和文件信息（存相对路径便于跨服务器部署）
                achievement_data['import_session_id'] = import_session_id
                achievement_data['file_name'] = file.filename
                achievement_data['file_path'] = upload_result.relative_path
                achievement_data['file_type'] = Path(file.filename).suffix.lower()

                # 添加PDF预览图路径
                if preview_image_path:
                    achievement_data['preview_image_path'] = preview_image_path

                # 添加实验室ID到achievement_data（确保前端可以读取）
                if laboratory_id is not None:
                    achievement_data['laboratory_id'] = laboratory_id
                
                # 添加 OCR 和 LLM 数据（从 pending 对象的独立字段中获取，确保模板可以访问）
                if pending.ocr_text:
                    achievement_data['ocr_result'] = pending.ocr_text
                if pending.llm_response:
                    achievement_data['llm_response'] = pending.llm_response
                
                # 从 ext_info 中获取模板信息
                ext_info = pending.get_ext_info() if hasattr(pending, 'get_ext_info') else {}
                if isinstance(ext_info, dict):
                    template_id = ext_info.get('template_id')
                    template_name = ext_info.get('template_name')
                    
                    if template_id:
                        achievement_data['template_id'] = template_id
                    
                    # 优先使用 ext_info 中的 template_name，如果不存在则从模板管理器获取
                    if template_name:
                        achievement_data['matched_template_name'] = template_name
                    elif template_id:
                        # 尝试从模板管理器获取模板名称
                        try:
                            from app.utils import get_doc_rec_context
                            doc_rec_context = get_doc_rec_context()
                            template_manager = doc_rec_context.template_manager
                            template = template_manager.get_template(template_id)
                            if template:
                                achievement_data['matched_template_name'] = template.get_display_name()
                        except Exception as e:
                            logger.warning(f"获取模板名称失败: {e}")

                # 更新 pending 记录：状态和 import_session_id
                pending_manager.update(
                    pending_item=pending,
                    status=status,
                    achievement_data=achievement_data
                )

                # 未指定实验室时，根据第一导师（指导教师）自动关联实验室
                ach_type = pending.achievement_type or 'other'
                if ach_type == 'innovation' and achievement_data.get('projects'):
                    # 大创：每个项目独立根据其指导教师关联实验室，导入抽取后即完成
                    for p in achievement_data['projects']:
                        if not isinstance(p, dict):
                            continue
                        lab_id = _resolve_laboratory_id_for_innovation_project(
                            p, teacher_manager, laboratory_manager
                        )
                        if lab_id is not None:
                            p['laboratory_id'] = lab_id
                    pending_manager.update(
                        pending_item=pending,
                        achievement_data=achievement_data,
                        status=status
                    )
                elif laboratory_id is None:
                    lab_id, reason = _resolve_laboratory_by_first_supervisor(
                        achievement_data, ach_type, teacher_manager, laboratory_manager
                    )
                    if lab_id and reason:
                        laboratory_id = lab_id
                        achievement_data['laboratory_id'] = laboratory_id
                        logger.info(f"[文件导入] {reason}, laboratory_id={laboratory_id}")
                        pending_manager.update(
                            pending_item=pending,
                            achievement_data=achievement_data,
                            status=status
                        )

                # 处理指定指导教师（仅奖状等非大创）
                if default_supervisor_name and not achievement_data.get('supervisor_name') and ach_type != 'innovation':
                    achievement_data['supervisor_name'] = default_supervisor_name
                    pending_manager.update(
                        pending_item=pending,
                        achievement_data=achievement_data
                    )
                    if laboratory_id is None:
                        lab_id, reason = _resolve_laboratory_by_first_supervisor(
                            achievement_data, ach_type,
                            teacher_manager, laboratory_manager
                        )
                        if lab_id and reason:
                            laboratory_id = lab_id
                            achievement_data['laboratory_id'] = laboratory_id
                            pending_manager.update(
                                pending_item=pending,
                                achievement_data=achievement_data
                            )

                # 统计结果
                # 注意：对于大创 Excel 文件，FileUploadService 会创建一个包含所有项目的记录
                # achievement_data 格式为 {"projects": [...], "count": N}
                # 统计时应该统计为 1 个 innovation 记录，而不是多个
                achievement_type = pending.achievement_type or 'other'
                
                # 对于大创项目，检查是否有 projects 列表（Excel 文件）
                if achievement_type == 'innovation':
                    achievement_data_check = pending.get_achievement_data()
                    if isinstance(achievement_data_check, dict) and 'projects' in achievement_data_check:
                        # 这是包含多个项目的 Excel 文件
                        # 统计为 1 个 innovation 记录（整个文件）
                        if is_valid:
                            results['innovation']['valid'] += 1
                        else:
                            results['innovation']['invalid'] += 1
                    else:
                        # 单个大创项目
                        if is_valid:
                            results['innovation']['valid'] += 1
                        else:
                            results['innovation']['invalid'] += 1
                elif achievement_type in results:
                    if is_valid:
                        results[achievement_type]['valid'] += 1
                    else:
                        results[achievement_type]['invalid'] += 1
                else:
                    if is_valid:
                        results['other']['valid'] += 1
                    else:
                        results['other']['invalid'] += 1

            except Exception as e:
                logger.error(f"处理文件失败 {file.filename}: {e}", exc_info=True)
                results['other']['invalid'] += 1

        # 更新最终进度状态（写入存储，前端轮询可见）
        update_progress(import_session_id, status='completed', current_step='处理完成', stats=dict(results))

        # 统一跳转到文件导入结果页面（单张和多张使用相同的处理逻辑）
        redirect_url = url_for('admin_achievement.file_import_results', session_id=import_session_id)

        return jsonify({
            'success': True,
            'uploaded_count': len([f for f in files if f and f.filename]),
            'import_session_id': import_session_id,
            'redirect_url': redirect_url
        })

    except Exception as e:
        logger.error(f"文件上传失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'}), 500


@bp.route('/file-import/results')
@require_role('admin')
def file_import_results():
    """文件导入结果处理页面"""
    try:
        # 获取参数
        result = get_file_import_params()
        if result[0] is None:  # session_id验证失败
            return redirect(url_for('admin_achievement.achievements'))
        session_id, tab_type, status, index = result

        # 初始化管理器
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()
        laboratory_manager = app_context.get_laboratory_manager()

        # 类型名称映射（从配置文件读取）
        type_names = get_type_names()
        
        # 计算类型统计
        type_stats = calculate_type_stats(session_id, pending_manager)
        
        # 调整tab和status
        tab_type, status, available_types = adjust_tab_and_status(tab_type, status, type_stats)

        # 大创：进入结果页时先补齐每个项目的 laboratory_id（含历史导入），再渲染
        if tab_type == 'innovation':
            _ensure_innovation_laboratory_resolved(
                session_id, pending_manager, teacher_manager, laboratory_manager
            )
            from app.routes.review_helpers import render_review_page
            return render_review_page(
                session_id, tab_type, status, index, app_context,
                title_prefix='导入结果', route_prefix='admin'
            )
        
        # 查询pending items
        items, count = query_pending_items(tab_type, status, session_id, pending_manager)

        # 获取当前项
        current_item, index = get_current_item(items, count, index, tab_type, status, session_id)
        
        # 获取所有参考数据
        all_competitions, all_teachers, all_students, all_laboratories = get_all_reference_data(
            competition_manager, teacher_manager, student_manager, laboratory_manager)

        # 处理当前项
        if current_item and tab_type == 'award':
            # 处理奖状类型
            award_data = process_award_item(
                current_item, app_context, all_competitions, 
                all_teachers, all_students, all_laboratories
            )
            
            # 获取验证结果
            validation_result = current_item.get_validation_result()
            field_errors, is_valid = process_validation_result(validation_result)
            
            # 调试：返回前打印模板匹配情况
            data = current_item.get_achievement_data()
            _mn = data.get('matched_template_name')
            _tid = data.get('template_id')
            _tm = getattr(award_data['temp_award'], 'matched_template_name', None)
            _relevant_keys = [k for k in (data.keys() if isinstance(data, dict) else []) if 'template' in k.lower() or 'match' in k.lower()]
            # logger.info(
            #     "[file_import_results] 模板匹配 | session_id=%s index=%s | "
            #     "data.matched_template_name=%r data.template_id=%r | temp_award.matched_template_name=%r | "
            #     "achievement_data keys含template/match: %s",
            #     session_id, index,
            #     _mn, _tid, _tm, _relevant_keys
            # )

            preview_image_path = award_data.get('preview_image_path')
            preview_image_url = url_for('admin_achievement.file_import_file', file_path=preview_image_path.replace('\\', '/')) if preview_image_path else None

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
                                  related_student_status_list=award_data.get('related_student_status_list', []),
                                  matched_teacher_ids=award_data['matched_teacher_ids'],
                                  file_path=award_data['file_path'],
                                  file_url=award_data['file_url'],
                                  preview_image_url=preview_image_url,
                                  field_errors=field_errors,
                                  is_valid=is_valid,
                                  missing_competition_name=award_data.get('missing_competition_name'))
        else:
            # 处理非奖状类型
            non_award_data = process_non_award_item(current_item, tab_type, all_laboratories)
            
            # 获取验证结果
            validation_result = current_item.get_validation_result() if current_item else None
            field_errors, is_valid = process_validation_result(validation_result)
            
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
                                  file_path=non_award_data['file_path'],
                                  file_url=non_award_data['file_url'],
                                  innovation=non_award_data['innovation_data'],
                                  patent=non_award_data['patent_data'],
                                  software=non_award_data['software_data'],
                                  other_data=non_award_data['other_data'],
                                  is_image=non_award_data['is_image'],
                                  all_laboratories=all_laboratories,
                                  field_errors=field_errors,
                                  is_valid=is_valid)

    except Exception as e:
        logger.error(f"加载文件导入结果页面失败: {e}", exc_info=True)
        flash(f'加载页面失败: {str(e)}', 'error')
        return redirect(url_for('admin_achievement.achievements'))

@bp.route('/file-import/file/<path:file_path>')
@require_role('admin')
def file_import_file(file_path):
    """提供文件导入/成果审核中的文件访问。支持 temp_upload/、review/（提交审核后）及 config temp_dir。"""
    try:
        from flask import send_file
        from pathlib import Path
        from urllib.parse import unquote
        from backend.services.unified_file_manager import get_unified_file_manager

        path_str = unquote(file_path).strip().replace('\\', '/')
        file_manager = get_unified_file_manager()
        files_root = file_manager.files_root.resolve()
        temp_upload_prefix = (files_root / 'temp_upload').resolve()
        review_prefix = (files_root / 'review').resolve()

        full_path = None
        allowed_prefix = None
        is_absolute = path_str.startswith('/') or (len(path_str) > 1 and path_str[1] == ':')

        # 1) 绝对路径（仅允许在 temp_upload 或 review 下）
        if is_absolute:
            full_path = Path(path_str).resolve()
            try:
                full_path.relative_to(temp_upload_prefix)
                allowed_prefix = temp_upload_prefix
            except ValueError:
                try:
                    full_path.relative_to(review_prefix)
                    allowed_prefix = review_prefix
                except ValueError:
                    from flask import abort
                    logger.warning(f"绝对路径不在 temp_upload/review 下: {full_path}")
                    abort(403)

        # 2) 相对路径：temp_upload/... 或 review/... 在 files_root 下
        if full_path is None and (path_str.startswith('temp_upload/') or path_str.startswith('temp_upload')):
            full_path = (files_root / path_str).resolve()
            allowed_prefix = temp_upload_prefix
        if full_path is None and (path_str.startswith('review/') or path_str.startswith('review')):
            full_path = (files_root / path_str).resolve()
            allowed_prefix = review_prefix

        # 3) 其他相对路径：在 config temp_dir 下（如手动导入）
        if full_path is None:
            from config.loader import get_config
            config_loader = get_config()
            base_temp_dir = config_loader.get_path("temp_dir")
            base_dir = Path(base_temp_dir)
            full_path = (base_dir / path_str).resolve()
            allowed_prefix = base_dir.resolve()

        # 安全检查：必须在允许的目录下
        try:
            full_path.relative_to(allowed_prefix)
        except ValueError:
            from flask import abort
            logger.warning(f"文件路径越界: {full_path} 不在 {allowed_prefix} 下")
            abort(403)  # 禁止访问
        
        if not full_path.exists() or not full_path.is_file():
            from flask import abort
            abort(404)
        
        ext = full_path.suffix.lower()
        # PDF 请求时返回第一页预览图，供 <img> 显示
        if ext == '.pdf':
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
                logger.warning("[file_import_file] PDF 预览图生成失败: %s", e)
            # 生成失败时仍返回 PDF 流（img 会失败，但可下载）
            return send_file(str(full_path), mimetype='application/pdf')
        
        # 根据文件扩展名设置MIME类型
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.jfif': 'image/jpeg',  # JFIF 是 JPEG 文件格式的一种变体
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


@bp.route('/file-import/award-edit/<session_id>/<int:index>', methods=['GET', 'POST'])
@require_role('admin')
def file_import_award_edit(session_id, index):
    """从pending_achievement显示奖状编辑页面"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()
        laboratory_manager = app_context.get_laboratory_manager()
        
        from backend.models.pending_achievement import PendingAchievementFilter
        
        # 获取所有奖状类型的pending记录
        filter_obj = PendingAchievementFilter(
            achievement_type='award',
            import_session_id=session_id,
            limit=1000
        )
        items = pending_manager.query_pending(filter_obj)
        
        # 获取当前项
        current_item = None
        if items and 0 <= index < len(items):
            current_item = items[index]
        else:
            flash('记录不存在', 'error')
            return redirect(url_for('admin_achievement.file_import_results', session_id=session_id))
        
        # 获取数据
        data = current_item.get_achievement_data()
        
        # 如果是POST请求，保存奖状
        if request.method == 'POST':
            return _save_award_from_pending(current_item, data, app_context, session_id, index)
        
        # GET请求，显示编辑页面
        # 获取所有竞赛（用于下拉框）
        all_competitions = []
        if hasattr(competition_manager, 'competitions'):
            all_competitions = competition_manager.competitions
        elif hasattr(competition_manager, '_competitions'):
            all_competitions = competition_manager._competitions
        
        # 获取所有教师和学生（用于下拉框）
        all_teachers = []
        if hasattr(teacher_manager, 'teachers'):
            all_teachers = teacher_manager.teachers
        elif hasattr(teacher_manager, '_teachers'):
            all_teachers = teacher_manager._teachers
        
        all_students = []
        if hasattr(student_manager, 'students'):
            all_students = student_manager.students
        elif hasattr(student_manager, '_students'):
            all_students = student_manager._students
        
        # 获取所有实验室（用于下拉框）
        all_laboratories = []
        if hasattr(laboratory_manager, 'laboratories'):
            all_laboratories = laboratory_manager.laboratories
        elif hasattr(laboratory_manager, 'get_all_laboratories'):
            all_laboratories = laboratory_manager.get_all_laboratories()
        
        # 确定默认选中的实验室（优先使用 pending_achievements 表的 laboratory_id 列）
        default_laboratory_id = current_item.laboratory_id if current_item.laboratory_id else data.get('laboratory_id')
        
        # 构建一个临时的Award对象用于模板渲染
        # 我们需要创建一个类似Award的对象，包含所有需要的字段
        class TempAward:
            def __init__(self, data, file_path, pending_laboratory_id=None):
                self.id = None  # 还没有创建，所以是None
                self.competition_id = data.get('competition_id')
                self.award_level = data.get('award_level')
                self.competition_level = data.get('competition_level')
                self.year = data.get('year')
                self.track = data.get('track')
                self.certificate_id = data.get('certificate_id')
                self.project_title = data.get('project_title')
                self.date = data.get('date')
                self.province = data.get('province')
                self.issuer = data.get('issuer')
                # 优先使用 pending_achievements 表的 laboratory_id 列
                self.laboratory_id = pending_laboratory_id if pending_laboratory_id else data.get('laboratory_id')
                self.granted_role = data.get('granted_role', '学生')
                self.winner_name = data.get('winner_name', '')
                self.supervisor_name = data.get('supervisor_name', '')
                self.ocr_result = data.get('ocr_result', '')
                # 最终抽取结果：使用原始的extract_result.data（不包含ocr_result、llm_response等额外字段）
                extract_data = data.get('_extract_data', data)
                # 从extract_data中移除额外添加的字段，只保留原始抽取的数据
                if isinstance(extract_data, dict):
                    clean_extract_data = {k: v for k, v in extract_data.items() 
                                        if k not in ['ocr_result', 'llm_response', 'matched_template_name', 'import_session_id', 'file_name', 'file_path', 'file_type', '_extract_data']}
                    self.extract_data_formatted = json.dumps(clean_extract_data, ensure_ascii=False, indent=2)
                else:
                    self.extract_data_formatted = json.dumps(extract_data, ensure_ascii=False, indent=2) if extract_data else '{}'
                self.llm_response = data.get('llm_response', '')  # LLM原始返回
                self.image_hash = data.get('image_hash', '')
                self.file_path = file_path
                self.student_winners = []
                self.teacher_winners = []
                self.supervisors = []
                self.related_students = []
                
                # 解析学生获奖者
                # 注意：这里不填充 student_winners，因为重名检测在 winner_status_list 中处理
                # 如果直接填充 student_winners，重名时会显示多个学生而不是显示"重名"标记
                # student_winners 留空，由 winner_status_list 负责显示匹配状态
                
                # 解析指导教师
                if self.supervisor_name:
                    names = [n.strip() for n in self.supervisor_name.split(',') if n.strip()]
                    for name in names:
                        matched_teachers = teacher_manager.find_teachers_by_name(name)
                        exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
                        if exact_matches:
                            self.supervisors.extend(exact_matches)
            
            def set_images_dir(self, images_dir):
                self.images_dir = images_dir

        file_path = current_item.get_file_path()
        temp_award = TempAward(data, file_path, pending_laboratory_id=current_item.laboratory_id)

        # 设置图片目录
        if award_manager.images_dir:
            temp_award.set_images_dir(award_manager.images_dir)

        # 从 pending_achievements 表中获取 OCR 和 LLM 数据（优先于 achievement_data 中的）
        if current_item.ocr_text:
            temp_award.ocr_result = current_item.ocr_text
        if current_item.llm_response:
            temp_award.llm_response = current_item.llm_response

        # 处理winner_status_list和supervisor_status_list（用于显示匹配状态）
        # 归一化：按纯姓名去重，避免 "林俊杰(23计科),林俊杰(23软工)" 显示两个标签
        def _base_name(segment: str) -> str:
            s = segment.strip()
            if "(" in s:
                return s.split("(")[0].strip()
            return s
        winner_status_list = []
        if temp_award.winner_name:
            raw_names = [n.strip() for n in temp_award.winner_name.split(',') if n.strip()]
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
                        'obj': exact_matches[0],
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
        
        supervisor_status_list = []
        if temp_award.supervisor_name:
            names = [n.strip() for n in temp_award.supervisor_name.split(',') if n.strip()]
            for name in names:
                matched_teachers = teacher_manager.find_teachers_by_name(name)
                exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
                if len(exact_matches) == 1:
                    supervisor_status_list.append({
                        'name': name,
                        'matched': True,
                        'obj': exact_matches[0],
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
        
        matched_teacher_ids = set()
        for status in supervisor_status_list:
            if status.get('matched') and status.get('obj'):
                matched_teacher_ids.add(status['obj'].id)
        
        # 处理文件路径，构建文件URL
        file_url = None
        if file_path:
            relative_path = file_path.replace('\\', '/')
            path_parts = relative_path.split('/')
            # 查找file_import_开头的目录
            file_import_index = -1
            for i, part in enumerate(path_parts):
                if 'file_import_' in part:
                    file_import_index = i
                    break
            if file_import_index >= 0:
                relative_file_path = '/'.join(path_parts[file_import_index:])
                file_url = url_for('admin_achievement.file_import_file', file_path=relative_file_path)
            else:
                file_url = file_path
        
        return render_template('admin/file_import/award_edit.html',
                             award=temp_award,
                             competitions=all_competitions,
                             all_teachers=all_teachers,
                             all_students=all_students,
                             all_laboratories=all_laboratories,
                             default_laboratory_id=default_laboratory_id,
                             winner_status_list=winner_status_list,
                             supervisor_status_list=supervisor_status_list,
                             matched_teacher_ids=matched_teacher_ids,
                             session_id=session_id,
                             index=index,
                             pending_id=current_item.id,
                             file_path=file_path,
                             file_url=file_url)
    
    except Exception as e:
        logger.error(f"加载奖状编辑页面失败: {e}", exc_info=True)
        flash(f'加载编辑页面失败: {str(e)}', 'error')
        return redirect(url_for('admin_achievement.file_import_results', session_id=session_id))

def _save_award_from_pending(pending_item, original_data, app_context, session_id, index):
    """从pending_achievement保存奖状"""
    try:
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()
        pending_manager = app_context.get_pending_achievement_manager()
        
        # 获取表单数据
        competition_id = request.form.get('competition_id')
        if competition_id:
            competition_id = int(competition_id)
        else:
            competition_id = None
        
        year = request.form.get('year')
        if year:
            year = int(year)
        else:
            year = None
        
        # 文件导入场景（有 session_id）：仅「提交审核」，不入库、不删 pending。
        # 文件保持在临时目录，待成果审核中「审核通过」时再入库并移动文件。
        # 从competition_id获取competition_name
        competition_name = original_data.get('competition_name', '')
        if competition_id:
            competition = competition_manager.get_competition_by_id(competition_id)
            if competition:
                competition_name = competition.name
        
        # 处理laboratory_id
        laboratory_id = request.form.get('laboratory_id')
        if laboratory_id and laboratory_id != '':
            try:
                laboratory_id = int(laboratory_id)
            except (ValueError, TypeError):
                laboratory_id = original_data.get('laboratory_id')
        else:
            laboratory_id = original_data.get('laboratory_id')
        
        # 构建extract_result
        extract_result = {
            'competition_id': competition_id,
            'competition_name': competition_name,
            'award_level': request.form.get('award_level') or original_data.get('award_level'),
            'competition_level': request.form.get('competition_level') or original_data.get('competition_level'),
            'year': year or original_data.get('year'),
            'track': request.form.get('track') or original_data.get('track'),
            'certificate_id': request.form.get('certificate_id') or original_data.get('certificate_id'),
            'project_title': request.form.get('project_title') or original_data.get('project_title'),
            'date': request.form.get('date') or original_data.get('date'),
            'province': request.form.get('province') or original_data.get('province'),
            'issuer': request.form.get('issuer') or original_data.get('issuer'),
            'granted_role': request.form.get('certificate_type') == 'teacher' and '教师' or '学生',
            'laboratory_id': laboratory_id,
        }
        
        # 处理学生获奖者
        student_winner_names = request.form.get('student_winner_names', '').strip()
        if student_winner_names:
            extract_result['winner_name'] = student_winner_names
        else:
            extract_result['winner_name'] = original_data.get('winner_name', '')
        
        # 处理指导教师
        supervisor_ids = request.form.getlist('supervisor_ids[]')
        supervisor_names = []
        for teacher_id in supervisor_ids:
            if teacher_id:
                try:
                    teacher = teacher_manager.get_teacher_by_id(int(teacher_id))
                    if teacher:
                        supervisor_names.append(teacher.name)
                except (ValueError, TypeError):
                    pass
        if supervisor_names:
            extract_result['supervisor_name'] = ', '.join(supervisor_names)
        else:
            extract_result['supervisor_name'] = original_data.get('supervisor_name', '')

        # 处理关联学生（教师证书）
        related_student_ids = request.form.getlist('related_student_ids[]')
        related_student_names = []
        for student_id in related_student_ids:
            if student_id:
                try:
                    student = student_manager.get_student_by_id(int(student_id))
                    if student:
                        related_student_names.append(student.name)
                except (ValueError, TypeError):
                    pass
        if related_student_names:
            extract_result['related_student_name'] = ', '.join(related_student_names)
        else:
            # 如果没有选择关联学生，保留原值
            extract_result['related_student_name'] = original_data.get('related_student_name', '')

        # 合并表单修改到 achievement_data，保留 ocr_result、image_hash、file_path、import_session_id 等
        merged = dict(original_data) if isinstance(original_data, dict) else {}
        merged.update(extract_result)
        for k in ('ocr_result', 'image_hash', 'file_path', 'import_session_id', 'file_name', 'file_type'):
            if k in original_data and (k not in merged or not merged.get(k)):
                merged[k] = original_data[k]

        success = pending_manager.update(
            pending_item=pending_item,
            achievement_data=merged,
            status='pending'  # 新流程：统一使用 pending 状态
        )
        if not success:
            raise RuntimeError('更新待审核记录失败')
        pending_item.status = 'pending'  # 新流程：统一使用 pending 状态

        flash('已提交审核，请前往「成果审核」确认入库', 'success')
        return redirect(url_for('admin_achievement.file_import_results', session_id=session_id))
    
    except Exception as e:
        logger.error(f"保存奖状失败: {e}", exc_info=True)
        flash(f'保存失败: {str(e)}', 'error')
        return redirect(url_for('admin_achievement.file_import_award_edit', session_id=session_id, index=index))

@bp.route('/file-import/review/<session_id>/<type>/<sub_tab>/<int:index>')
@require_role('admin')
def file_import_review_single(session_id, type, sub_tab, index):
    """
    单页式审核页面 - 文件导入后的审核
    
    注意：此路由已废弃，建议使用 file_import_results 路由。
    保留此路由是为了向后兼容，实际上会重定向到 file_import_results。
    """
    # 重定向到统一的审核页面
    return redirect(url_for('admin_achievement.file_import_results', 
                           session_id=session_id, 
                           tab=type, 
                           sub_tab=sub_tab, 
                           index=index))

@bp.route('/file-import/api/list')
@require_role_api('admin')
def file_import_api_list():
    """获取待处理的成果列表"""
    try:
        session_id = request.args.get('session_id', '')
        achievement_type = request.args.get('type', 'award')
        status = request.args.get('status', 'valid')  # valid or invalid

        if not session_id:
            return jsonify({'success': False, 'message': '缺少 session_id 参数'}), 400

        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()

        from backend.models.pending_achievement import PendingAchievementFilter

        # 根据状态设置查询条件
        # 新流程：识别成功和待修订都使用 pending 状态，提交后改为 submit
        # 新流程：识别成功和待修订都使用 pending 状态，提交后改为 submit
        query_status = 'pending'  # 文件导入时统一使用 pending 状态

        filter_obj = PendingAchievementFilter(
            achievement_type=achievement_type,
            status=query_status,
            import_session_id=session_id,  # 按会话ID过滤
            limit=100
        )

        items = pending_manager.query_pending(filter_obj)

        # 格式化数据返回
        result_items = []
        for item in items:
            data = item.get_achievement_data()
            validation = item.get_validation_result()

            result_items.append({
                'id': item.id,
                'data': data,
                'validation': validation,
                'submit_time': item.submit_time
            })

        return jsonify({
            'success': True,
            'items': result_items,
            'count': len(result_items)
        })

    except Exception as e:
        logger.error(f"获取成果列表失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/file-import/api/stats')
@require_role_api('admin')
def file_import_api_stats():
    """获取导入统计信息"""
    try:
        session_id = request.args.get('session_id', '')

        if not session_id:
            return jsonify({'success': False, 'message': '缺少 session_id 参数'}), 400

        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()

        from backend.models.pending_achievement import PendingAchievementFilter

        stats = {}
        types = get_achievement_types()

        for achievement_type in types:
            # 新流程：识别成功和待修订都使用 pending 状态，然后根据验证结果分类
            filter_pending = PendingAchievementFilter(
                achievement_type=achievement_type,
                status='pending',
                import_session_id=session_id
            )
            all_items = pending_manager.query_pending(filter_pending)
            # 根据验证结果分类
            valid_items = [item for item in all_items if item.is_valid()]
            invalid_items = [item for item in all_items if not item.is_valid()]
            valid_count = len(valid_items)
            invalid_count = len(invalid_items)

            stats[achievement_type] = {
                'valid': valid_count,
                'invalid': invalid_count,
                'total': valid_count + invalid_count
            }

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/file-import/api/item/<int:item_id>')
@require_role_api('admin')
def file_import_api_item(item_id):
    """获取单个成果详情"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()

        item = pending_manager.get_by_id(item_id)
        if not item:
            return jsonify({'success': False, 'message': '记录不存在'}), 404

        result = {
            'success': True,
            'item': {
                'id': item.id,
                'achievement_type': item.achievement_type,
                'data': item.get_achievement_data(),
                'validation': item.get_validation_result(),
                'status': item.status
            }
        }
        
        # 如果是奖状类型，返回额外的编辑所需数据
        if item.achievement_type == 'award':
            competition_manager = app_context.get_competition_manager()
            student_manager = app_context.get_student_manager()
            teacher_manager = app_context.get_teacher_manager()
            laboratory_manager = app_context.get_laboratory_manager()
            
            # 获取所有竞赛
            all_competitions = []
            if hasattr(competition_manager, 'competitions'):
                all_competitions = [{'id': c.id, 'name': c.name} for c in competition_manager.competitions]
            elif hasattr(competition_manager, '_competitions'):
                all_competitions = [{'id': c.id, 'name': c.name} for c in competition_manager._competitions]
            
            # 获取所有教师
            all_teachers = []
            if hasattr(teacher_manager, 'teachers'):
                all_teachers = [{'id': t.id, 'name': t.name, 'teacher_id': getattr(t, 'teacher_id', None)} for t in teacher_manager.teachers]
            elif hasattr(teacher_manager, '_teachers'):
                all_teachers = [{'id': t.id, 'name': t.name, 'teacher_id': getattr(t, 'teacher_id', None)} for t in teacher_manager._teachers]
            
            # 获取所有学生
            all_students = []
            if hasattr(student_manager, 'students'):
                all_students = [{'id': s.id, 'name': s.name, 'brief_desc': s.get_brief_desc()} for s in student_manager.students]
            elif hasattr(student_manager, '_students'):
                all_students = [{'id': s.id, 'name': s.name, 'brief_desc': s.get_brief_desc()} for s in student_manager._students]
            
            # 获取所有实验室
            all_laboratories = []
            if hasattr(laboratory_manager, 'laboratories'):
                all_laboratories = [{'id': lab.id, 'name': lab.name} for lab in laboratory_manager.laboratories]
            elif hasattr(laboratory_manager, 'get_all_laboratories'):
                labs = laboratory_manager.get_all_laboratories()
                all_laboratories = [{'id': lab.id, 'name': lab.name} for lab in labs]
            
            # 处理学生获奖者和指导教师的状态列表（按纯姓名去重，避免重名显示多个标签）
            def _base_name_vi(seg: str) -> str:
                s = seg.strip()
                if "(" in s:
                    return s.split("(")[0].strip()
                return s
            data = item.get_achievement_data()
            winner_status_list = []
            winner_name = data.get('winner_name', '')
            if winner_name:
                raw_names = [n.strip() for n in winner_name.split(',') if n.strip()]
                seen_base_vi = {}
                for n in raw_names:
                    b = _base_name_vi(n)
                    if b not in seen_base_vi:
                        seen_base_vi[b] = b
                names = list(seen_base_vi.values())
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
            
            supervisor_status_list = []
            supervisor_name = data.get('supervisor_name', '')
            if supervisor_name:
                names = [n.strip() for n in supervisor_name.split(',') if n.strip()]
                for name in names:
                    matched_teachers = teacher_manager.find_teachers_by_name(name)
                    exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
                    if len(exact_matches) == 1:
                        supervisor_status_list.append({
                            'name': name,
                            'matched': True,
                            'obj': {'id': exact_matches[0].id, 'name': exact_matches[0].name, 'teacher_id': getattr(exact_matches[0], 'teacher_id', None)},
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
            
            # 处理文件URL
            file_path = item.get_file_path()
            file_url = None
            if file_path:
                relative_path = file_path.replace('\\', '/')
                path_parts = relative_path.split('/')
                file_import_index = -1
                for i, part in enumerate(path_parts):
                    if 'file_import_' in part:
                        file_import_index = i
                        break
                if file_import_index >= 0:
                    relative_file_path = '/'.join(path_parts[file_import_index:])
                    file_url = url_for('admin_achievement.file_import_file', file_path=relative_file_path)
                else:
                    file_url = file_path
            
            result['award_edit_data'] = {
                'competitions': all_competitions,
                'teachers': all_teachers,
                'students': all_students,
                'laboratories': all_laboratories,
                'winner_status_list': winner_status_list,
                'supervisor_status_list': supervisor_status_list,
                'file_url': file_url,
                'file_path': file_path
            }

        return jsonify(result)

    except Exception as e:
        logger.error(f"获取成果详情失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

def _innovation_form_to_project(modified_data):
    """将大创编辑表单字段映射为单条 project 字典"""
    project = {}
    project['项目编号'] = (modified_data.get('project_id') or '').strip()
    project['项目名称'] = (modified_data.get('project_name') or '').strip()
    project['项目级别'] = (modified_data.get('project_level') or '').strip()
    project['验收等级'] = (modified_data.get('acceptance_level') or '').strip()
    project['系别'] = (modified_data.get('department') or '').strip()
    year_val = modified_data.get('year')
    try:
        project['年份'] = int(year_val) if year_val not in (None, '') else None
    except (TypeError, ValueError):
        project['年份'] = None
    project['项目开始时间'] = (modified_data.get('start_date') or '').strip()
    project['项目结束时间'] = (modified_data.get('end_date') or '').strip()
    project['项目简介'] = (modified_data.get('project_intro') or '').strip()
    leader_str = (modified_data.get('student_leader') or '').strip()
    if leader_str:
        parts = leader_str.split('(', 1)
        name = parts[0].strip()
        sid = parts[1].rstrip(')').strip() if len(parts) > 1 else ''
        project['学生负责人'] = {'姓名': name, '学号': sid}
    else:
        project['学生负责人'] = {}
    teachers_str = (modified_data.get('teachers') or '').strip()
    project['指导教师'] = [t.strip() for t in teachers_str.split(',') if t.strip()]
    members_str = (modified_data.get('other_members') or '').strip()
    member_list = []
    for part in members_str.replace('，', ',').split(','):
        part = part.strip()
        if not part:
            continue
        if '(' in part and ')' in part:
            name, rest = part.split('(', 1)
            sid = rest.rstrip(')').strip()
            member_list.append({'姓名': name.strip(), '学号': sid})
        else:
            member_list.append({'姓名': part, '学号': ''})
    project['项目其他成员信息'] = member_list
    # 每个项目独立关联实验室（仅当前编辑项）
    raw_lab = modified_data.get('laboratory_id')
    project['laboratory_id'] = int(raw_lab) if raw_lab not in (None, '') else None
    return project


@bp.route('/file-import/api/submit', methods=['POST'])
@require_role_api('admin', 'student', 'teacher')
def file_import_api_submit():
    """提交单个成果到正式库；大创支持按 project_index 仅更新某一项目后提交。student/teacher 仅可提交本人 pending。"""
    try:
        app_context = get_app_context_instance()
        submitter_type, submitter_id = _resolve_submitter_for_file_import(app_context)
        if submitter_type is None or submitter_id is None:
            return jsonify({'success': False, 'message': '用户信息不存在'}), 403
        item_id = request.json.get('item_id')
        modified_data = request.json.get('data', {}) or {}
        force_submit = request.json.get('force_submit', False)
        save_only = request.json.get('save_only', False)
        project_index = request.json.get('project_index') or modified_data.get('project_index')

        pending_manager = app_context.get_pending_achievement_manager()
        item = pending_manager.get_by_id(item_id)
        if not item:
            logger.warning(f"提交失败: 记录不存在, item_id={item_id}")
            return jsonify({'success': False, 'message': '记录不存在'}), 404
        ok, err = _ensure_item_belongs_to_submitter(item, submitter_type, submitter_id)
        if not ok:
            return err

        achievement_type = item.achievement_type
        data = item.get_achievement_data()

        # 奖状：将 related_student_ids 转为 related_student/related_student_name
        if achievement_type == 'award' and modified_data:
            normalize_related_student_from_ids(modified_data, app_context.get_student_manager())

        # 大创：仅更新 achievement_data.projects[project_index] 后提交
        if achievement_type == 'innovation' and project_index is not None:
            try:
                pi = int(project_index)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': 'project_index 无效'}), 400
            projects = list(data.get('projects') or [])
            if pi < 0 or pi >= len(projects):
                return jsonify({'success': False, 'message': '项目索引超出范围'}), 400
            project_dict = _innovation_form_to_project(modified_data)
            if not force_submit:
                vr = _validate_achievement_data('innovation', project_dict, app_context)
                if not vr.get('is_valid', True):
                    issues = vr.get('completeness_issues') or vr.get('content_issues') or []
                    return jsonify({
                        'success': False,
                        'needs_confirmation': True,
                        'message': '数据验证未通过: ' + ('; '.join(issues) if issues else '未知')
                    })
            projects[pi] = project_dict
            data['projects'] = projects
            data['count'] = len(projects)
            # 大创按项目独立关联实验室，laboratory_id 已写入 project_dict，无需再写文件级
            full_validation_result = _get_full_validation_result(achievement_type, data, app_context)
            current_data_validation_json = json.dumps(full_validation_result, ensure_ascii=False)
            pending_manager.update(
                pending_item=item,
                achievement_data=data,
                validation_result=current_data_validation_json
            )
            if save_only:
                return jsonify({'success': True, 'message': '已保存'})
            review_service = _get_review_service(app_context)
            result = review_service.submit_achievement(item.id, submitter_type, submitter_id)
            msg = '已提交，系统将自动归档' if getattr(result, 'action', None) == 'auto_archive_started' else '提交成功，等待审核'
            return jsonify({'success': True, 'message': msg})
        # 合并修改后的数据（非大创单项目编辑）
        if modified_data:
            data.update(modified_data)

        # 如果不是强制提交，先验证数据
        if not force_submit:
            validation_result = _validate_achievement_data(achievement_type, data, app_context)
            if not validation_result.get('is_valid'):
                issues = validation_result.get('completeness_issues', [])
                return jsonify({
                    'success': False,
                    'needs_confirmation': True,
                    'message': '数据验证未通过: ' + '; '.join(issues)
                })

        # 更新 pending_item 的数据（如果用户修改了数据）
        if modified_data:
            # 更新 pending_item 的 achievement_data
            current_data = item.get_achievement_data()
            current_data.update(modified_data)

            # 重新计算完整的验证结果（包括日期格式等）
            full_validation_result = _get_full_validation_result(achievement_type, current_data, app_context)
            current_data_validation_json = json.dumps(full_validation_result, ensure_ascii=False)

            # 更新 achievement_data、validation_result（提交与策略由 submit_achievement 处理）
            pending_manager.update(
                pending_item=item,
                achievement_data=current_data,
                validation_result=current_data_validation_json
            )
        else:
            # 没有修改数据，但为了确保 validation_result 是最新的，也重新校验一次
            current_data = item.get_achievement_data()
            full_validation_result = _get_full_validation_result(achievement_type, current_data, app_context)
            current_data_validation_json = json.dumps(full_validation_result, ensure_ascii=False)

            # 更新 validation_result（提交与策略由 submit_achievement 处理）
            pending_manager.update(
                pending_item=item,
                achievement_data=current_data,
                validation_result=current_data_validation_json
            )
        review_service = _get_review_service(app_context)
        result = review_service.submit_achievement(item.id, submitter_type, submitter_id)
        if result.action == 'auto_archive_started':
            msg = '已提交，系统将自动归档'
        else:
            msg = '提交成功，等待审核'
        return jsonify({'success': True, 'message': msg})

    except Exception as e:
        logger.error(f"提交成果失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

def _validate_achievement_data(achievement_type, data, app_context):
    """验证成果数据"""
    issues = []
    
    if achievement_type == 'award':
        if not data.get('competition_name'):
            issues.append('缺少竞赛名称')
    elif achievement_type == 'patent':
        if not data.get('patent_name'):
            issues.append('缺少专利名称')
    elif achievement_type == 'software':
        if not data.get('software_name'):
            issues.append('缺少软件名称')
    elif achievement_type == 'innovation':
        if not (data.get('project_name') or data.get('项目名称')):
            issues.append('缺少项目名称')
    elif achievement_type == 'other':
        if not data.get('title') and not data.get('file_name'):
            issues.append('缺少文件标题')
    
    return {
        'is_valid': len(issues) == 0,
        'completeness_issues': issues
    }


def _get_full_validation_result(achievement_type, data, app_context):
    """
    获取完整的验证结果（包括日期格式等详细验证）

    Args:
        achievement_type: 成果类型 (award, patent, software, innovation, other)
        data: 成果数据
        app_context: 应用上下文

    Returns:
        dict: 验证结果，格式为 {'is_valid': bool, 'content_issues': [], 'completeness_issues': []}
    """
    import json

    if achievement_type == 'award':
        # 使用奖状验证器
        try:
            from backend.extract.extractors.award import AwardExtractor
            extractor = AwardExtractor()
            validation_result = extractor.validate(data, app_context)

            # 转换为统一格式
            content_issues = []
            completeness_issues = []

            for issue in validation_result.get('content', []):
                content_issues.append({
                    'field': issue.field_name,
                    'message': issue.error_message,
                    'error_type': issue.error_type
                })

            for issue in validation_result.get('completeness', []):
                completeness_issues.append({
                    'field': issue.field_name,
                    'message': issue.error_message,
                    'error_type': issue.error_type
                })

            return {
                'is_valid': len(content_issues) == 0 and len(completeness_issues) == 0,
                'content_issues': content_issues,
                'completeness_issues': completeness_issues
            }
        except Exception as e:
            logger.error(f"奖状验证失败: {e}")
            # 返回基本验证结果
            return {
                'is_valid': True,
                'content_issues': [],
                'completeness_issues': []
            }

    elif achievement_type == 'patent':
        # 使用专利验证器
        try:
            from app.routes.teacher import _validate_patent_data
            from backend.extract.types import ValidationResult

            validation = _validate_patent_data(data)
            return {
                'is_valid': validation.is_valid,
                'content_issues': [{'field': 'patent', 'message': issue} for issue in validation.content_issues],
                'completeness_issues': [{'field': 'patent', 'message': issue} for issue in validation.completeness_issues]
            }
        except Exception as e:
            logger.error(f"专利验证失败: {e}")
            return {'is_valid': True, 'content_issues': [], 'completeness_issues': []}

    elif achievement_type == 'software':
        # 使用软著验证器
        try:
            from app.routes.teacher import _validate_software_data
            from backend.extract.types import ValidationResult

            validation = _validate_software_data(data)
            return {
                'is_valid': validation.is_valid,
                'content_issues': [{'field': 'software', 'message': issue} for issue in validation.content_issues],
                'completeness_issues': [{'field': 'software', 'message': issue} for issue in validation.completeness_issues]
            }
        except Exception as e:
            logger.error(f"软著验证失败: {e}")
            return {'is_valid': True, 'content_issues': [], 'completeness_issues': []}

    else:
        # 其他类型返回基本验证结果
        return {
            'is_valid': True,
            'content_issues': [],
            'completeness_issues': []
        }


@bp.route('/file-import/api/delete', methods=['POST'])
@require_role_api('admin', 'student', 'teacher')
def file_import_api_delete():
    """删除单个待处理成果 - 支持通过item_id或session_id+index删除。student/teacher 仅可删除本人 pending。
    
    使用 safe_delete_with_file() 方法：
    - 删除 pending 记录
    - 检查文件引用计数，只有当没有其他记录引用该文件时才删除文件
    - 这对于大创等一对多场景非常重要（多条记录引用同一个 Excel 文件）
    """
    try:
        app_context = get_app_context_instance()
        submitter_type, submitter_id = _resolve_submitter_for_file_import(app_context)
        if submitter_type is None or submitter_id is None:
            return jsonify({'success': False, 'message': '用户信息不存在'}), 403
        pending_manager = app_context.get_pending_achievement_manager()

        # 支持两种方式：通过item_id或通过session_id+index
        item_id = request.json.get('item_id')
        session_id = request.json.get('session_id')
        index = request.json.get('index')
        tab_type = request.json.get('tab_type', 'award')
        project_index = request.json.get('project_index')

        # 大创：删除当前文件下某一项目（item_id + project_index）
        if item_id is not None and tab_type == 'innovation' and project_index is not None:
            try:
                pid = int(item_id)
                pi = int(project_index)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': 'item_id 或 project_index 无效'}), 400
            item = pending_manager.get_by_id(pid)
            if not item:
                return jsonify({'success': False, 'message': '记录不存在'}), 404
            ok, err = _ensure_can_delete_or_discard_item(item, submitter_type, submitter_id, app_context)
            if not ok:
                return err
            if item.achievement_type != 'innovation':
                return jsonify({'success': False, 'message': '该记录不是大创类型'}), 400
            data = item.get_achievement_data()
            projects = list(data.get('projects') or [])
            if pi < 0 or pi >= len(projects):
                return jsonify({'success': False, 'message': '项目索引超出范围'}), 400
            projects.pop(pi)
            data['projects'] = projects
            data['count'] = len(projects)
            if len(projects) == 0:
                result = pending_manager.safe_delete_with_file(pid)
                return jsonify({
                    'success': result['success'],
                    'message': result['message'],
                    'file_deleted': result.get('file_deleted', False)
                })
            success = pending_manager.update(item, achievement_data=data)
            if not success:
                return jsonify({'success': False, 'message': '更新失败'}), 500
            return jsonify({'success': True, 'message': '已删除该项目', 'file_deleted': False})

        if item_id:
            item = pending_manager.get_by_id(item_id)
            if not item:
                return jsonify({'success': False, 'message': '记录不存在'}), 404
            ok, err = _ensure_can_delete_or_discard_item(item, submitter_type, submitter_id, app_context)
            if not ok:
                return err
            result = pending_manager.safe_delete_with_file(item_id)
            return jsonify({
                'success': result['success'],
                'message': result['message'],
                'file_deleted': result['file_deleted']
            })
        elif session_id is not None and index is not None:
            # 新方式：通过session_id和index删除
            from backend.models.pending_achievement import PendingAchievementFilter

            # 获取当前类型和状态（从请求参数或默认值）
            tab_type = request.json.get('tab_type', 'award')
            status = request.json.get('status', 'valid')
            # 新流程：识别成功和待修订都使用 pending 状态，提交后改为 submit
            query_status = 'pending'  # 文件导入时统一使用 pending 状态

            # 获取对应类型的列表
            filter_obj = PendingAchievementFilter(
                achievement_type=tab_type,
                status=query_status,
                import_session_id=session_id,
                limit=1000
            )
            all_items = pending_manager.query_pending(filter_obj)
            # 根据 status 参数过滤验证结果
            if status == 'valid':
                items = [item for item in all_items if item.is_valid()]
            else:
                items = [item for item in all_items if not item.is_valid()]

            # 检查索引是否有效
            if items and 0 <= index < len(items):
                item = items[index]
                ok, err = _ensure_can_delete_or_discard_item(item, submitter_type, submitter_id, app_context)
                if not ok:
                    return err
                # 使用安全删除方法，处理文件引用计数
                result = pending_manager.safe_delete_with_file(item.id)
                return jsonify({
                    'success': result['success'],
                    'message': result['message'],
                    'file_deleted': result['file_deleted']
                })
            else:
                return jsonify({'success': False, 'message': '索引超出范围'}), 404
        else:
            return jsonify({'success': False, 'message': '缺少必要参数'}), 400

    except Exception as e:
        logger.error(f"删除成果失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/file-import/api/other/submit', methods=['POST'])
@require_role_api('admin', 'student', 'teacher')
def file_import_api_other_submit():
    """提交 other 类型文件到实验室（图库或下载专区）。student/teacher 仅可提交本人 pending。
    
    请求参数:
    - item_id: pending记录ID
    - lab_id: 实验室ID（必填）
    - target_type: 目标位置 'album'（图库） 或 'downloads'（下载专区）
    - file_title: 文件标题（用于下载专区显示）
    """
    try:
        item_id = request.json.get('item_id')
        lab_id = request.json.get('lab_id')
        target_type = request.json.get('target_type', 'downloads')  # 默认放入下载专区
        file_title = request.json.get('file_title', '')
        
        if not item_id:
            return jsonify({'success': False, 'message': '缺少 item_id'}), 400
        
        if not lab_id:
            return jsonify({'success': False, 'message': '必须选择关联的实验室'}), 400
        
        app_context = get_app_context_instance()
        submitter_type, submitter_id = _resolve_submitter_for_file_import(app_context)
        if submitter_type is None or submitter_id is None:
            return jsonify({'success': False, 'message': '用户信息不存在'}), 403
        pending_manager = app_context.get_pending_achievement_manager()
        laboratory_manager = app_context.get_laboratory_manager()
        
        # 获取 pending 记录
        item = pending_manager.get_by_id(item_id)
        if not item:
            return jsonify({'success': False, 'message': '记录不存在'}), 404
        ok, err = _ensure_item_belongs_to_submitter(item, submitter_type, submitter_id)
        if not ok:
            return err
        
        if item.achievement_type != 'other':
            return jsonify({'success': False, 'message': '此接口仅用于处理 other 类型文件'}), 400
        
        # 验证实验室存在
        lab = laboratory_manager.get_laboratory_by_id(lab_id)
        if not lab:
            return jsonify({'success': False, 'message': f'实验室不存在: {lab_id}'}), 404
        
        # 获取审核服务
        from backend.services.review_service import Reviewer
        review_service = _get_review_service(app_context)
        
        # 创建审核人信息（使用当前提交人）
        reviewer = Reviewer(
            reviewer_type=submitter_type,
            reviewer_id=submitter_id
        )
        
        # 调用处理方法
        result = review_service.handle_other_type(
            pending=item,
            lab_id=lab_id,
            reviewer=reviewer,
            target_type=target_type,
            file_title=file_title
        )
        
        if result.success:
            target_desc = '实验室图库' if target_type == 'album' else '实验室下载专区'
            return jsonify({
                'success': True,
                'message': f'文件已成功提交到{lab.name}的{target_desc}',
                'target_table': result.target_table,
                'file_path': result.file_moved_to
            })
        else:
            return jsonify({
                'success': False,
                'message': result.error or '提交失败'
            }), 500
        
    except Exception as e:
        logger.error(f"提交 other 类型文件失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/file-import/award-submit/<session_id>/<int:index>', methods=['POST'])
@require_role('admin')
def file_import_award_submit(session_id, index):
    """提交奖状后跳转到下一项。使用表单中的 pending_id 定位记录，避免与 sub_tab(valid/invalid) 列表下标混淆。"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()

        # 获取当前状态（从表单）
        tab_type = request.form.get('tab_type', 'award')
        status = request.form.get('status', 'valid')
        pending_id_raw = request.form.get('pending_id')
        try:
            pending_id = int(pending_id_raw) if pending_id_raw else None
        except (ValueError, TypeError):
            pending_id = None

        if pending_id is None:
            flash('缺少待提交记录标识', 'error')
            return redirect(url_for('admin_achievement.file_import_results', session_id=session_id, tab=tab_type, sub_tab=status))

        current_item = pending_manager.get_by_id(pending_id)
        if not current_item:
            flash('记录不存在', 'error')
            return redirect(url_for('admin_achievement.file_import_results', session_id=session_id, tab=tab_type, sub_tab=status))
        item_session_id = current_item.get_achievement_data().get('import_session_id')
        if item_session_id != session_id or current_item.achievement_type != tab_type:
            flash('记录与当前导入会话或类型不一致', 'error')
            return redirect(url_for('admin_achievement.file_import_results', session_id=session_id, tab=tab_type, sub_tab=status))
        if current_item.status != 'pending':
            flash('该记录已提交或已处理', 'error')
            return redirect(url_for('admin_achievement.file_import_results', session_id=session_id, tab=tab_type, sub_tab=status))
        item_id = current_item.id
        data = current_item.get_achievement_data()

        # 合并表单数据（用户可能修改了字段）
        form_data = {}
        for key in request.form:
            if key not in ('tab_type', 'status', 'pending_id'):
                form_data[key] = request.form.get(key)

        # 处理关联学生（教师证书）
        related_student_ids = request.form.getlist('related_student_ids[]')
        if related_student_ids:
            student_manager = app_context.get_student_manager()
            related_student_names = []
            for student_id in related_student_ids:
                if student_id:
                    try:
                        student = student_manager.get_student_by_id(int(student_id))
                        if student:
                            related_student_names.append(student.name)
                    except (ValueError, TypeError):
                        pass
            if related_student_names:
                name_str = ', '.join(related_student_names)
                form_data['related_student_name'] = name_str
                form_data['related_student'] = name_str  # 与 related_student_name 保持一致，供 review_service 读取
            else:
                form_data['related_student_name'] = ''
                form_data['related_student'] = ''
        else:
            form_data['related_student_name'] = ''
            form_data['related_student'] = ''

        if form_data:
            data.update(form_data)
            # 未选具体竞赛时用解析出的竞赛名，后端将自动创建竞赛
            if not (data.get('competition_name') or '').strip() and (data.get('original_competition_name') or '').strip():
                data['competition_name'] = (data.get('original_competition_name') or '').strip()
            # 更新 pending_item 的数据
            pending_manager.update(
                pending_item=current_item,
                achievement_data=data,
                status=current_item.status
            )

        # 通过 ReviewService 提交并应用审核策略（自动归档或进入待审核）
        review_service = _get_review_service(app_context)
        admin_id = session.get('user_id') or 0
        result = review_service.submit_achievement(current_item.id, 'admin', admin_id)
        if result.action == 'auto_archive_started':
            flash('已提交，系统将自动归档', 'success')
        else:
            flash('提交成功，等待审核', 'success')

        # 重新获取当前类型下未提交的记录，用于决定跳转
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
            # 还有剩余记录，跳转到第一项
            return redirect(url_for('admin_achievement.file_import_results', session_id=session_id, tab=tab_type, sub_tab=status, index=0))
        else:
            # 没有剩余记录了，检查是否还有其他类型的未提交记录
            all_empty = True
            data_import_types = get_data_import_types()
            for t in data_import_types:
                filter_check = PendingAchievementFilter(
                    achievement_type=t,
                    status='pending',  # 新流程：统一使用 pending 状态
                    import_session_id=session_id,
                    limit=1000
                )
                check_items = pending_manager.query_pending(filter_check)
                # 过滤掉已提交的记录（状态为 'submit' 的记录）
                check_items = [item for item in check_items if item.status != 'submit']
                if check_items:
                    all_empty = False
                    break

            if all_empty:
                # 所有记录都已提交，跳转到成果审核页面
                flash('所有记录已提交审核，请前往成果审核页面确认入库', 'success')
                return redirect(url_for('admin_review.review_single_global', type='award', sub_tab='valid', index=0))
            else:
                # 还有其他类型的记录，返回列表页
                return redirect(url_for('admin_achievement.file_import_results', session_id=session_id, tab=tab_type, sub_tab=status))

    except Exception as e:
        logger.error(f"提交奖状失败: {e}", exc_info=True)
        flash(f'提交失败: {str(e)}', 'error')
        _tab = request.form.get('tab_type', 'award')
        _sub = request.form.get('status', 'valid')
        return redirect(url_for('admin_achievement.file_import_results', session_id=session_id, tab=_tab, sub_tab=_sub, index=index))

@bp.route('/file-import/api/batch-import', methods=['POST'])
@require_role_api('admin', 'student', 'teacher')
def file_import_api_batch_import():
    """批量提交当前类型、当前子TAB 的 pending 记录为 submit 状态。student/teacher 仅可提交本人 pending。

    - 可选 pending_ids：若传入则仅处理这些 ID（大创按文件分页时仅提交当前文件）；
    - 有 session_id：仅该导入会话内、且符合当前 sub_tab（识别成功/待修订 或 image/file）的记录；
    - 无 session_id：该类型下全部 pending 记录（成果审核页无 pending，通常为 0）。
    """
    try:
        app_context = get_app_context_instance()
        submitter_type, submitter_id = _resolve_submitter_for_file_import(app_context)
        if submitter_type is None or submitter_id is None:
            return jsonify({'success': False, 'message': '用户信息不存在'}), 403
        achievement_type = request.json.get('type')
        session_id = request.json.get('session_id', '') or None
        sub_tab = request.json.get('sub_tab')  # 'valid'|'invalid' 或 'image'|'file'，innovation 不传
        pending_ids = request.json.get('pending_ids')  # 可选，大创时仅提交当前文件

        pending_manager = app_context.get_pending_achievement_manager()

        from backend.models.pending_achievement import PendingAchievementFilter

        if pending_ids is not None and isinstance(pending_ids, list) and len(pending_ids) > 0:
            items = []
            expected_type = (submitter_type or '').strip().lower() if submitter_type != 'admin' else None
            expected_id = _normalize_submitter_id(submitter_id) if submitter_type != 'admin' else None
            for pid in pending_ids:
                item = pending_manager.get_by_id(pid)
                if item and item.achievement_type == achievement_type:
                    if submitter_type == 'admin':
                        items.append(item)
                    elif (getattr(item, 'submitter_type', None) or '').strip().lower() == expected_type and _normalize_submitter_id(getattr(item, 'submitter_id', None)) == expected_id:
                        items.append(item)
        else:
            filter_obj = PendingAchievementFilter(
                achievement_type=achievement_type,
                status='pending',
                import_session_id=session_id,
                limit=1000
            )
            items = pending_manager.query_pending(filter_obj)

        # 仅针对当前类别：按 sub_tab 过滤（未使用 pending_ids 时）
        if pending_ids is None and session_id and sub_tab and achievement_type not in ('innovation',):
            if achievement_type == 'other':
                from pathlib import Path
                if sub_tab == 'image':
                    items = [i for i in items if (getattr(i, 'file_path', None) and Path(i.file_path or '').suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.jfif'))]
                else:  # file
                    items = [i for i in items if not (getattr(i, 'file_path', None) and Path(i.file_path or '').suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.jfif'))]
            else:
                # award/patent/software: valid / invalid
                if sub_tab == 'valid':
                    items = [i for i in items if i.is_valid()]
                elif sub_tab == 'invalid':
                    items = [i for i in items if not i.is_valid()]

        # 非 admin 仅处理本人提交的 pending（规范化类型比较，避免 DB 与 session 类型不一致）
        if submitter_type != 'admin':
            expected_type = (submitter_type or '').strip().lower()
            expected_id = _normalize_submitter_id(submitter_id)
            items = [
                i for i in items
                if (getattr(i, 'submitter_type', None) or '').strip().lower() == expected_type
                and _normalize_submitter_id(getattr(i, 'submitter_id', None)) == expected_id
            ]

        success_count = 0
        failed_count = 0
        failed_errors = []
        review_service = _get_review_service(app_context)

        for item in items:
            try:
                result = review_service.submit_achievement(item.id, submitter_type, submitter_id)
                if result.success:
                    sc = getattr(result, 'submitted_count', None)
                    if sc is not None:
                        success_count += sc
                    elif achievement_type == 'innovation':
                        # 异步归档或待审核：该条未返回 submitted_count，按 pending 内项目数统计
                        data = item.get_achievement_data() or {}
                        projects = data.get('projects') or []
                        success_count += len(projects) if isinstance(projects, list) else 1
                    else:
                        success_count += 1
                else:
                    failed_count += 1
                    failed_errors.append(result.error or '未知错误')
            except Exception as e:
                logger.error(f"提交记录 {item.id} 失败: {e}", exc_info=True)
                failed_count += 1
                failed_errors.append(str(e))

        return jsonify({
            'success': True,
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': failed_errors
        })

    except Exception as e:
        logger.error(f"批量导入失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/file-import/api/batch-discard', methods=['POST'])
@require_role_api('admin', 'student', 'teacher')
def file_import_api_batch_discard():
    """批量放弃当前类型中指定验证状态的记录。student/teacher 仅可放弃本人 pending。

    可选 pending_ids：若传入则仅放弃这些 ID（大创按文件分页时仅放弃当前文件）。

    支持按验证状态筛选：
    - valid: 只删除验证通过的记录
    - invalid: 只删除验证失败的记录
    - all: 删除所有记录

    使用 safe_delete_with_file() 方法：
    - 删除 pending 记录
    - 检查文件引用计数，只有当没有其他记录引用该文件时才删除文件
    """
    try:
        app_context = get_app_context_instance()
        submitter_type, submitter_id = _resolve_submitter_for_file_import(app_context)
        if submitter_type is None or submitter_id is None:
            return jsonify({'success': False, 'message': '用户信息不存在'}), 403
        achievement_type = request.json.get('type')
        session_id = request.json.get('session_id', '') or None
        validation_status = request.json.get('validation_status', 'all')  # 'valid', 'invalid', or 'all'
        pending_ids = request.json.get('pending_ids')  # 可选，大创时仅放弃当前文件

        pending_manager = app_context.get_pending_achievement_manager()

        count = 0
        files_deleted = 0

        if pending_ids is not None and isinstance(pending_ids, list) and len(pending_ids) > 0:
            for pid in pending_ids:
                item = pending_manager.get_by_id(pid)
                if item and item.achievement_type == achievement_type:
                    ok, err = _ensure_can_delete_or_discard_item(item, submitter_type, submitter_id, app_context)
                    if not ok:
                        continue  # 跳过无权限的记录
                    # 大创：按项目数累加；其他类型：按记录数累加
                    if achievement_type == 'innovation':
                        data = item.get_achievement_data() or {}
                        projects = data.get('projects') or []
                        project_count = len(projects) if isinstance(projects, list) else 1
                    else:
                        project_count = 1
                    
                    result = pending_manager.safe_delete_with_file(item.id)
                    if result['success']:
                        count += project_count
                        if result.get('file_deleted'):
                            files_deleted += 1
            return jsonify({
                'success': True,
                'count': count,
                'files_deleted': files_deleted
            })

        from backend.models.pending_achievement import PendingAchievementFilter

        # 根据是否有 session_id 决定查询的状态
        # - 有 session_id：文件导入审核，查询 status='pending'
        # - 无 session_id：全局审核，查询 status='submit'
        if session_id:
            # 文件导入审核：查询 pending 状态
            query_status = 'pending'
        else:
            # 全局审核：查询 submit 状态
            query_status = 'submit'

        # other 类型且为文件导入（有 session_id）：不按 status 过滤，与 query_pending_items 一致
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

        # 教师端全局审核（无 session_id）：使用“教师可审核”列表，与审核页一致
        if submitter_type == 'teacher' and not session_id:
            teacher_manager = app_context.get_teacher_manager()
            teacher = teacher_manager.get_teacher_by_id(submitter_id) if submitter_id else None
            teacher_name = teacher.name if teacher else None
            items = pending_manager.get_pending_for_teacher(
                submitter_id,
                teacher_manager=teacher_manager,
                teacher_name=teacher_name
            )
            items = [i for i in items if i.achievement_type == achievement_type]
        else:
            items = []
            expected_type = (submitter_type or '').strip().lower() if submitter_type != 'admin' else None
            expected_id = _normalize_submitter_id(submitter_id) if submitter_type != 'admin' else None
            for filter_obj in filter_list:
                chunk = pending_manager.query_pending(filter_obj)
                if submitter_type != 'admin':
                    chunk = [
                        i for i in chunk
                        if (getattr(i, 'submitter_type', None) or '').strip().lower() == expected_type
                        and _normalize_submitter_id(getattr(i, 'submitter_id', None)) == expected_id
                    ]
                items.extend(chunk)

        for item in items:
            # 全部放弃只针对当前类别（当前类型 + 当前子TAB）
            if session_id:
                # 文件导入审核：按验证状态筛选
                if validation_status == 'valid':
                    if not item.is_valid():
                        continue
                elif validation_status == 'invalid':
                    if item.is_valid():
                        continue
            else:
                # 成果审核（全局）：只放弃当前子TAB 下的记录
                if achievement_type not in ('other', 'innovation'):
                    if validation_status == 'valid':
                        if not item.is_valid():
                            continue
                    elif validation_status == 'invalid':
                        if item.is_valid():
                            continue
                elif achievement_type == 'other' and validation_status in ('image', 'file'):
                    from pathlib import Path
                    ext = (Path(getattr(item, 'file_path', None) or '').suffix or '').lower()
                    is_image = ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.jfif')
                    if validation_status == 'image' and not is_image:
                        continue
                    if validation_status == 'file' and is_image:
                        continue

            # 大创：按项目数累加；其他类型：按记录数累加
            if achievement_type == 'innovation':
                data = item.get_achievement_data() or {}
                projects = data.get('projects') or []
                project_count = len(projects) if isinstance(projects, list) else 1
            else:
                project_count = 1

            result = pending_manager.safe_delete_with_file(item.id)
            if result['success']:
                count += project_count
                if result['file_deleted']:
                    files_deleted += 1

        return jsonify({
            'success': True,
            'count': count,
            'files_deleted': files_deleted
        })

    except Exception as e:
        logger.error(f"批量放弃失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


def _resolve_submitter_for_file_import(app_context):
    """根据当前 session 解析 file-import API 的提交人 (submitter_type, submitter_id)。仅允许 admin/student/teacher。"""
    role = session.get('role')
    user_id = session.get('user_id')
    if role == 'admin':
        return 'admin', (user_id or 0)
    if role == 'student':
        sm = app_context.get_student_manager()
        s = sm.get_student_by_student_id(user_id) if user_id else None
        if not s:
            return None, None
        return 'student', s.id
    if role == 'teacher':
        tm = app_context.get_teacher_manager()
        t = tm.get_teacher_by_teacher_id(user_id) if user_id else None
        if not t:
            return None, None
        return 'teacher', t.id
    return None, None


def _normalize_submitter_id(value):
    """将 submitter_id 规范为 int 或 None，避免 DB 返回类型与 session 中 id 类型不一致导致比较失败。"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _ensure_item_belongs_to_submitter(item, submitter_type, submitter_id):
    """非 admin 时校验 item 属于当前提交人，否则返回 (False, 403_response)。"""
    if submitter_type == 'admin':
        return True, None
    st = (getattr(item, 'submitter_type', None) or '').strip().lower() or None
    si = _normalize_submitter_id(getattr(item, 'submitter_id', None))
    expected_type = (submitter_type or '').strip().lower() or None
    expected_id = _normalize_submitter_id(submitter_id)
    if st != expected_type or si != expected_id:
        return False, (jsonify({'success': False, 'message': '权限不足'}), 403)
    return True, None


def _ensure_can_delete_or_discard_item(item, submitter_type, submitter_id, app_context):
    """校验当前用户可删除/放弃该记录：admin 任意；提交人本人；教师可审核的也允许删除/放弃。"""
    ok, err = _ensure_item_belongs_to_submitter(item, submitter_type, submitter_id)
    if ok:
        return True, None
    if submitter_type == 'teacher' and submitter_id is not None:
        pending_manager = app_context.get_pending_achievement_manager()
        if pending_manager.can_teacher_review(submitter_id, item.id, None):
            return True, None
    return False, (jsonify({'success': False, 'message': '权限不足'}), 403)


def _get_review_service(app_context):
    """
    获取 ReviewService 实例

    ReviewService 提供了结构化的成果提交功能，每个类型有独立的提交方法。
    """
    from backend.services.review_service import ReviewService
    from config.loader import get_config

    config_loader = get_config()
    files_dir = config_loader.get_path("files")

    # 使用单例 AutoArchiveConfigManager，不重复创建实例
    auto_archive_config_manager = app_context.get_auto_archive_config_manager()

    return ReviewService(
        pending_manager=app_context.get_pending_achievement_manager(),
        review_log_manager=app_context.get_review_log_manager() if hasattr(app_context, 'get_review_log_manager') else None,
        laboratory_manager=app_context.get_laboratory_manager(),
        student_manager=app_context.get_student_manager(),
        teacher_manager=app_context.get_teacher_manager(),
        award_manager=app_context.get_award_manager(),
        patent_manager=app_context.get_patent_manager(),
        software_manager=app_context.get_software_copyright_manager(),
        innovation_manager=app_context.get_innovation_project_manager(),
        other_file_manager=app_context.get_other_file_manager() if hasattr(app_context, 'get_other_file_manager') else None,
        competition_manager=app_context.get_competition_manager(),
        auto_archive_config_manager=auto_archive_config_manager,
        files_dir=files_dir
    )
