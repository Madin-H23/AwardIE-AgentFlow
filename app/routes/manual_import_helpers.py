"""
手动导入共享逻辑：上传单文件到临时目录、按类型解析并写入 pending。
供 admin / student / teacher 的 manual upload、manual parse 路由复用。
"""
import hashlib
import logging
import shutil
import uuid
from pathlib import Path
from datetime import datetime

from flask import request

logger = logging.getLogger(__name__)


def handle_manual_upload():
    """
    处理手动导入文件上传：保存到 temp_dir/manual_import，返回相对路径。
    Returns:
        tuple: (success: bool, file_path: str | None, error_message: str | None)
    """
    from config.loader import get_config_loader
    try:
        files = request.files.getlist('files')
        if not files or not any(f and f.filename for f in files):
            return False, None, '请选择文件'
        file = next(f for f in files if f and f.filename)
        config_loader = get_config_loader()
        base_temp_dir = config_loader.get_path("temp_dir")
        manual_dir = base_temp_dir / "manual_import"
        manual_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}_{file.filename}"
        save_path = manual_dir / safe_name
        file.save(str(save_path))
        relative_path = (
            str(save_path.relative_to(base_temp_dir))
            if base_temp_dir in save_path.parents
            else str(save_path)
        )
        return True, relative_path, None
    except Exception as e:
        logger.exception("manual upload failed")
        return False, None, str(e)


def handle_manual_parse(submitter_type: str, submitter_id: int):
    """
    处理手动导入解析：按类型解析文件、写入 pending。不生成 redirect_url，由调用方在各自蓝图内用 url_for 生成。
    submitter_type: 'admin' | 'student' | 'teacher'
    submitter_id: 当前用户 id（与 create_from_extract_result 约定一致）
    Returns:
        tuple: (success, session_id, achievement_type, error_message, path_for_db, achievement_data, ocr_text, template_type)
        成功时后四项为 (path_for_db, achievement_data, ocr_text, template_type)，失败时后四项为 None。
    """
    from config.loader import get_config_loader
    from app.utils import get_app_context_instance, get_doc_rec_context, calculate_file_hash
    from backend.services.manual_import_service import ManualImportService
    from backend.services.unified_file_manager import get_unified_file_manager
    from backend.extract.types import ExtractStatus

    try:
        data = request.get_json() or {}
        achievement_type = (data.get('achievement_type') or '').strip().lower()
        file_path = data.get('file_path')
        use_ocr_cache = data.get('use_ocr_cache', True)
        use_llm_cache = data.get('use_llm_cache', True)
        if not file_path:
            return False, None, None, '缺少 file_path', None, None, None, None
        if achievement_type not in ('award', 'patent', 'software'):
            return False, None, None, f'不支持的成果类型: {achievement_type}', None, None, None, None

        config_loader = get_config_loader()
        base_temp_dir = config_loader.get_path("temp_dir")
        full_path = Path(base_temp_dir) / file_path if not Path(file_path).is_absolute() else Path(file_path)
        if not full_path.exists():
            return False, None, None, '文件不存在', None, None, None, None

        app_context = get_app_context_instance()
        framework = get_doc_rec_context().extract_framework
        service = ManualImportService(framework)
        result = service.parse_by_type(
            str(full_path),
            achievement_type,
            use_ocr_cache=use_ocr_cache,
            use_llm_cache=use_llm_cache,
        )
        if not result or result.status != ExtractStatus.SUCCESS:
            return False, None, None, getattr(result, 'error_message', None) or '解析失败', None, None, None, None

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
                submitter_type=submitter_type,
                submitter_id=submitter_id,
                file_path=path_for_db,
                file_hash=file_hash,
                status='pending',
            )

        achievement_data = result.data if hasattr(result, 'data') else {}
        ocr_text = getattr(result, 'ocr_text', None) or ''
        template_type = getattr(result, 'template_type', None) or achievement_type
        return True, session_id, achievement_type, None, path_for_db, achievement_data, ocr_text, template_type
    except Exception as e:
        logger.exception("manual parse failed")
        return False, None, None, str(e), None, None, None, None


def build_winner_supervisor_status(achievement_type: str, achievement_data: dict, app_context) -> tuple:
    """
    根据解析结果计算获奖者与指导教师匹配状态，供内联表单展示。
    Returns:
        (winner_status_list, supervisor_status_list)
    """
    winner_status_list = []
    supervisor_status_list = []
    if achievement_type != 'award':
        return winner_status_list, supervisor_status_list

    def _base_name(seg: str) -> str:
        s = seg.strip()
        if "(" in s:
            return s.split("(")[0].strip()
        return s

    winner_name = achievement_data.get('winner_name', '')
    if winner_name:
        student_manager = app_context.get_student_manager()
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

    return winner_status_list, supervisor_status_list
