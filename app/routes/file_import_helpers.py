"""
文件导入与成果类型配置的辅助函数。
供 admin_achievement 等路由在 file-import、results、review 流程中使用。
"""
import json
import logging
import time
from pathlib import Path

from flask import request, url_for, flash

logger = logging.getLogger(__name__)

# 供外部引用：file_import_file 所在蓝图名，用于生成 URL
FILE_IMPORT_FILE_ENDPOINT = "admin_achievement.file_import_file"


def get_achievement_types_config():
    """从配置文件获取成果类型全局配置"""
    from app.utils import get_config
    config = get_config()

    achievement_types_config = config.get('achievement_types')
    if not achievement_types_config:
        raise ValueError(
            "配置文件缺少 'achievement_types' 配置节。"
            "请在 config/settings.json 中添加 'achievement_types' 配置。"
        )

    return achievement_types_config


def get_achievement_types():
    """获取所有支持的成果类型列表"""
    config = get_achievement_types_config()
    types = config.get('types')
    if not types:
        raise ValueError(
            "配置文件缺少 'achievement_types.types' 配置。"
            "请在 config/settings.json 的 'achievement_types' 配置节中添加 'types' 列表。"
        )
    return types


def get_data_import_types():
    """获取数据导入支持的类型列表（不包含 other）"""
    config = get_achievement_types_config()
    types = config.get('data_import_types')
    if not types:
        raise ValueError(
            "配置文件缺少 'achievement_types.data_import_types' 配置。"
            "请在 config/settings.json 的 'achievement_types' 配置节中添加 'data_import_types' 列表。"
        )
    return types


def get_type_names():
    """从配置文件获取成果类型名称映射"""
    config = get_achievement_types_config()
    type_names = config.get('type_names')
    if not type_names:
        raise ValueError(
            "配置文件缺少 'achievement_types.type_names' 配置。"
            "请在 config/settings.json 的 'achievement_types' 配置节中添加 'type_names' 映射。"
        )
    return type_names


def get_file_import_params():
    """获取文件导入结果页面的参数（从 request 读取）"""
    session_id = request.args.get('session_id', '')
    tab_type = request.args.get('tab', 'award')
    status = request.args.get('sub_tab', 'valid')
    try:
        index = int(request.args.get('index', 0))
    except (ValueError, TypeError):
        index = 0

    if tab_type == 'other' and status not in ('image', 'file'):
        status = 'image'

    if not session_id:
        logger.error("session_id 为空，无法查询数据")
        flash('缺少会话ID，请重新上传文件', 'error')
        return None, None, None, None

    return session_id, tab_type, status, index


def calculate_type_stats(session_id, pending_manager):
    """计算本次导入中各类型的数量统计"""
    from backend.models.pending_achievement import PendingAchievementFilter
    from backend.services.review_service import IMAGE_EXTENSIONS

    type_stats = {}
    achievement_types = get_achievement_types()
    for t in achievement_types:
        if t == 'other':
            filter_all = PendingAchievementFilter(
                achievement_type='other',
                import_session_id=session_id,
                limit=1000
            )
            other_items = pending_manager.query_pending(filter_all)
            image_count = 0
            file_count = 0
            for item in other_items:
                fp = item.file_path if hasattr(item, 'file_path') else None
                if fp:
                    ext = Path(fp).suffix.lower()
                    if ext in IMAGE_EXTENSIONS:
                        image_count += 1
                    else:
                        file_count += 1
            type_stats['other'] = {
                'total': len(other_items),
                'image': image_count,
                'file': file_count
            }
        else:
            filter_pending = PendingAchievementFilter(
                achievement_type=t,
                status='pending',
                import_session_id=session_id,
                limit=1000
            )
            all_items = pending_manager.query_pending(filter_pending)
            valid_items = [item for item in all_items if item.is_valid()]
            invalid_items = [item for item in all_items if not item.is_valid()]
            valid_count = len(valid_items)
            invalid_count = len(invalid_items)
            type_stats[t] = {
                'total': valid_count + invalid_count,
                'valid': valid_count,
                'invalid': invalid_count
            }

    return type_stats


def adjust_tab_and_status(tab_type, status, type_stats):
    """调整 tab_type 和 status，确保指向有数据的类型和状态"""
    achievement_types = get_achievement_types()
    available_types = [t for t in achievement_types
                      if type_stats.get(t, {}).get('total', 0) > 0]

    if tab_type not in available_types and available_types:
        tab_type = available_types[0]
        if tab_type == 'other':
            status = 'image' if type_stats['other'].get('image', 0) > 0 else 'file'
        else:
            status = 'valid' if type_stats[tab_type].get('valid', 0) > 0 else 'invalid'

    if tab_type in available_types:
        current_type_stats = type_stats.get(tab_type, {})
        if tab_type == 'other':
            if status == 'image' and current_type_stats.get('image', 0) == 0:
                status = 'file' if current_type_stats.get('file', 0) > 0 else 'image'
            elif status == 'file' and current_type_stats.get('file', 0) == 0:
                status = 'image' if current_type_stats.get('image', 0) > 0 else 'file'
        else:
            if status == 'valid' and current_type_stats.get('valid', 0) == 0:
                status = 'invalid' if current_type_stats.get('invalid', 0) > 0 else 'valid'
            elif status == 'invalid' and current_type_stats.get('invalid', 0) == 0:
                status = 'valid' if current_type_stats.get('valid', 0) > 0 else 'invalid'

    return tab_type, status, available_types


def query_pending_items(tab_type, status, session_id, pending_manager):
    """根据 tab_type 和 status 查询 pending items"""
    from backend.models.pending_achievement import PendingAchievementFilter
    from backend.services.review_service import IMAGE_EXTENSIONS

    if tab_type == 'other':
        filter_obj = PendingAchievementFilter(
            achievement_type='other',
            import_session_id=session_id,
            limit=1000
        )
        all_other_items = pending_manager.query_pending(filter_obj)
        items = []
        for item in all_other_items:
            file_path = item.file_path if hasattr(item, 'file_path') else None
            if file_path:
                ext = Path(file_path).suffix.lower()
                is_image = ext in IMAGE_EXTENSIONS
                if status == 'image' and is_image:
                    items.append(item)
                elif status == 'file' and not is_image:
                    items.append(item)
        count = len(items)
        
    else:
        query_status = 'pending'
        filter_obj = PendingAchievementFilter(
            achievement_type=tab_type,
            status=query_status,
            import_session_id=session_id,
            limit=1000
        )
        all_items = pending_manager.query_pending(filter_obj)
        if status == 'valid':
            items = [item for item in all_items if item.is_valid()]
        else:
            items = [item for item in all_items if not item.is_valid()]
        count = len(items)

    return items, count


def get_current_item(items, count, index, tab_type, status, session_id):
    """获取当前项，处理索引边界"""
    current_item = None
    if items and 0 <= index < count:
        current_item = items[index]
    else:
        if items:
            index = 0
            current_item = items[0]
            logger.warning(f"索引 {index} 超出范围(0-{count-1})，重置为第一项")
        else:
            index = 0
            logger.warning(f"没有找到任何 {tab_type} 类型的 {status} 记录 (session_id={session_id})")

    return current_item, index


def get_all_reference_data(competition_manager, teacher_manager, student_manager, laboratory_manager):
    """获取所有竞赛、学生、教师、实验室数据"""
    all_competitions = []
    if hasattr(competition_manager, 'competitions'):
        all_competitions = competition_manager.competitions
    elif hasattr(competition_manager, '_competitions'):
        all_competitions = competition_manager._competitions

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

    all_laboratories = []
    if laboratory_manager:
        all_laboratories = (
            laboratory_manager.get_all_laboratories()
            if hasattr(laboratory_manager, 'get_all_laboratories')
            else (laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else [])
        )

    return all_competitions, all_teachers, all_students, all_laboratories


def process_validation_result(validation_result):
    """处理验证结果，构建字段错误映射"""
    field_errors = {}
    is_valid = True

    if validation_result:
        is_valid = validation_result.get('is_valid', True)
        all_issues = []
        all_issues.extend(validation_result.get('content_issues', []))
        all_issues.extend(validation_result.get('completeness_issues', []))

        for issue in all_issues:
            field_name = None
            if isinstance(issue, dict):
                field_name = issue.get('field') or issue.get('field_name') or ''
            elif isinstance(issue, str):
                if ':' in issue:
                    field_name = issue.split(':', 1)[0].strip()

            if field_name:
                if ',' in field_name:
                    fields = [f.strip() for f in field_name.split(',') if f.strip()]
                    for single_field in fields:
                        if single_field not in field_errors:
                            msg = issue.get('message', issue.get('error_message', str(issue))) if isinstance(issue, dict) else str(issue)
                            field_errors[single_field] = {
                                'message': msg,
                                'suggestion': issue.get('suggestion', '') if isinstance(issue, dict) else '',
                                'error_type': issue.get('error_type', 'invalid') if isinstance(issue, dict) else 'invalid'
                            }
                else:
                    if field_name not in field_errors:
                        msg = issue.get('message', issue.get('error_message', str(issue))) if isinstance(issue, dict) else str(issue)
                        field_errors[field_name] = {
                            'message': msg,
                            'suggestion': issue.get('suggestion', '') if isinstance(issue, dict) else '',
                            'error_type': issue.get('error_type', 'invalid') if isinstance(issue, dict) else 'invalid'
                        }
                    else:
                        existing_msg = field_errors[field_name]['message']
                        new_msg = issue.get('message', issue.get('error_message', str(issue))) if isinstance(issue, dict) else str(issue)
                        if new_msg and new_msg not in existing_msg:
                            field_errors[field_name]['message'] = f"{existing_msg}; {new_msg}"

    return field_errors, is_valid


def process_award_item(current_item, app_context, all_competitions, all_teachers, all_students, all_laboratories):
    """处理奖状类型的当前项"""
    award_manager = app_context.get_award_manager()
    competition_manager = app_context.get_competition_manager()
    student_manager = app_context.get_student_manager()
    teacher_manager = app_context.get_teacher_manager()
    laboratory_manager = app_context.get_laboratory_manager()

    class TempAward:
        def __init__(self, data, file_path):
            _cid = data.get('competition_id')
            try:
                self.competition_id = int(_cid) if _cid not in (None, '') else None
            except (TypeError, ValueError):
                self.competition_id = None
            self.award_level = data.get('award_level')
            self.competition_level = data.get('competition_level')
            self.year = data.get('year')
            self.track = data.get('track')
            self.edition = data.get('edition')
            self.certificate_id = data.get('certificate_id')
            self.project_title = data.get('project_title')
            self.date = data.get('date')
            self.province = data.get('province')
            self.issuer = data.get('issuer')
            self.laboratory_id = data.get('laboratory_id')
            self.granted_role = data.get('granted_role', '学生')
            self.winner_name = data.get('winner_name', '')
            self.supervisor_name = data.get('supervisor_name', '')
            self.related_student_name = data.get('related_student') or data.get('related_student_name', '')

            self.ocr_result = data.get('ocr_result', '')
            self.llm_response = data.get('llm_response', '')

            extract_data = data.get('_extract_data', data)
            if isinstance(extract_data, dict):
                clean_extract_data = {k: v for k, v in extract_data.items()
                                      if k not in ['ocr_result', 'llm_response', 'matched_template_name', 'import_session_id', 'file_name', 'file_path', 'file_type', '_extract_data']}
                self.extract_data_formatted = json.dumps(clean_extract_data, ensure_ascii=False, indent=2)
            else:
                self.extract_data_formatted = json.dumps(extract_data, ensure_ascii=False, indent=2) if extract_data else '{}'

            self.image_hash = data.get('image_hash', '')
            self.file_path = file_path
            self.matched_template_name = data.get('matched_template_name')
            extract_data = data.get('_extract_data', {})
            _comp_name = data.get('competition_name')
            if not _comp_name and isinstance(extract_data, dict):
                _comp_name = extract_data.get('competition_name')
            self.competition_name_in_file = (_comp_name or '').strip() or ''
            self.student_winners = []
            self.teacher_winners = []
            self.supervisors = []
            self.related_students = []

        def set_images_dir(self, images_dir):
            self.images_dir = images_dir

    data = current_item.get_achievement_data()
    file_path = current_item.get_file_path()
    temp_award = TempAward(data, file_path)

    if hasattr(current_item, 'get_ext_info'):
        ext_info = current_item.get_ext_info()
        if isinstance(ext_info, dict):
            if not temp_award.matched_template_name and ext_info.get('template_name'):
                temp_award.matched_template_name = ext_info.get('template_name')
            if ext_info.get('template_id') is not None:
                setattr(temp_award, 'template_id', ext_info.get('template_id'))

    if award_manager.images_dir:
        temp_award.set_images_dir(award_manager.images_dir)

    if current_item.ocr_text:
        temp_award.ocr_result = current_item.ocr_text
    if current_item.llm_response:
        temp_award.llm_response = current_item.llm_response

    if not temp_award.competition_id:
        matched_competition = None
        template_id = data.get('template_id') or getattr(temp_award, 'template_id', None)

        if template_id:
            try:
                from app.utils import get_doc_rec_context
                doc_rec_context = get_doc_rec_context()
                template_manager = doc_rec_context.template_manager
                template = template_manager.get_template(template_id)

                if template and template.default_fields:
                    template_competition_name = template.default_fields.get('competition_name')
                    if template_competition_name:
                        matched_competition = competition_manager.match_competition(template_competition_name)
                        
            except Exception as e:
                logger.warning(f"从模板获取竞赛失败: {e}", exc_info=True)

        if not matched_competition:
            competition_name = data.get('competition_name')
            if not competition_name:
                extract_data = data.get('_extract_data', {})
                if isinstance(extract_data, dict):
                    competition_name = extract_data.get('competition_name')

            if competition_name:
                matched_competition = competition_manager.match_competition(competition_name)
                if matched_competition:
                    logger.info(f"通过 competition_name 关联竞赛: competition_name={competition_name}, competition_id={matched_competition.id}")
                else:
                    # 审核阶段即创建竞赛，审核页显示新建竞赛而非「未关联」
                    try:
                        new_comp_id = competition_manager.get_competition_id_by_name(competition_name.strip())
                        temp_award.competition_id = new_comp_id
                        logger.info(f"审核阶段自动创建竞赛: competition_name={competition_name}, competition_id={new_comp_id}")
                    except Exception as e:
                        logger.warning(f"审核阶段自动创建竞赛失败: {e}", exc_info=True)

        if matched_competition:
            temp_award.competition_id = matched_competition.id

    missing_competition_name = None
    if not temp_award.competition_id and temp_award.competition_name_in_file:
        missing_competition_name = temp_award.competition_name_in_file
        logger.info(f"竞赛未找到: competition_name={missing_competition_name}，提交时将自动创建")

    winner_status_list = []
    supervisor_status_list = []
    matched_teacher_ids = set()

    is_teacher_certificate = temp_award.granted_role and "教师" in temp_award.granted_role

    if temp_award.winner_name:
        # 归一化：去掉括号及括号内内容得到纯姓名，用于查库和去重
        # 例如 "林俊杰(23计科),林俊杰(23软工)" -> 纯姓名均为 "林俊杰"，只保留一条并正确识别重名
        def base_name(segment: str) -> str:
            s = segment.strip()
            if "(" in s:
                return s.split("(")[0].strip()
            return s

        raw_names = [n.strip() for n in temp_award.winner_name.split(',') if n.strip()]
        # 按纯姓名去重（保留顺序），避免同一人因 brief_desc 格式出现多条
        seen_base = {}
        for n in raw_names:
            b = base_name(n)
            if b not in seen_base:
                seen_base[b] = b
        names = list(seen_base.values())
        for name in names:
            if is_teacher_certificate:
                matched_teachers = teacher_manager.find_teachers_by_name(name)
                exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
                if len(exact_matches) == 1:
                    winner_status_list.append({
                        'name': name, 'matched': True, 'obj': exact_matches[0],
                        'ambiguous': False, 'not_found': False, 'type': 'teacher'
                    })
                elif len(exact_matches) > 1:
                    winner_status_list.append({
                        'name': name, 'matched': False, 'obj': None,
                        'ambiguous': True, 'not_found': False, 'type': 'teacher'
                    })
                else:
                    winner_status_list.append({
                        'name': name, 'matched': False, 'obj': None,
                        'ambiguous': False, 'not_found': True, 'type': 'teacher'
                    })
            else:
                matched_students = student_manager.find_students_by_name(name)
                exact_matches = [s for s in matched_students if s.name.strip() == name.strip()]
                if len(exact_matches) == 1:
                    winner_status_list.append({
                        'name': name, 'matched': True, 'obj': exact_matches[0],
                        'ambiguous': False, 'not_found': False, 'type': 'student'
                    })
                elif len(exact_matches) > 1:
                    winner_status_list.append({
                        'name': name, 'matched': False, 'obj': None,
                        'ambiguous': True, 'not_found': False, 'type': 'student'
                    })
                else:
                    winner_status_list.append({
                        'name': name, 'matched': False, 'obj': None,
                        'ambiguous': False, 'not_found': True, 'type': 'student'
                    })

    if temp_award.supervisor_name:
        names = [n.strip() for n in temp_award.supervisor_name.split(',') if n.strip()]
        for name in names:
            matched_teachers = teacher_manager.find_teachers_by_name(name)
            exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
            if len(exact_matches) == 1:
                supervisor_status_list.append({
                    'name': name, 'matched': True, 'obj': exact_matches[0],
                    'ambiguous': False, 'not_found': False
                })
            elif len(exact_matches) > 1:
                supervisor_status_list.append({
                    'name': name, 'matched': False, 'obj': None,
                    'ambiguous': True, 'not_found': False
                })
            else:
                supervisor_status_list.append({
                    'name': name, 'matched': False, 'obj': None,
                    'ambiguous': False, 'not_found': True
                })

    related_student_status_list = []
    if temp_award.related_student_name:
        def base_name_related(segment: str) -> str:
            s = segment.strip()
            if "(" in s:
                return s.split("(")[0].strip()
            return s
        raw_related = [n.strip() for n in temp_award.related_student_name.split(',') if n.strip()]
        seen_related = {}
        for n in raw_related:
            b = base_name_related(n)
            if b not in seen_related:
                seen_related[b] = b
        names_related = list(seen_related.values())
        for name in names_related:
            matched_students = student_manager.find_students_by_name(name)
            exact_matches = [s for s in matched_students if s.name.strip() == name.strip()]
            if len(exact_matches) == 1:
                related_student_status_list.append({
                    'name': name, 'matched': True, 'obj': exact_matches[0],
                    'ambiguous': False, 'not_found': False
                })
                temp_award.related_students.append(exact_matches[0])
            elif len(exact_matches) > 1:
                related_student_status_list.append({
                    'name': name, 'matched': False, 'obj': None,
                    'ambiguous': True, 'not_found': False
                })
            else:
                related_student_status_list.append({
                    'name': name, 'matched': False, 'obj': None,
                    'ambiguous': False, 'not_found': True
                })

    if temp_award.teacher_winners:
        matched_teacher_ids = set(w.id for w in temp_award.teacher_winners)

    if not temp_award.laboratory_id:
        if supervisor_status_list and len(supervisor_status_list) > 0:
            first_supervisor = supervisor_status_list[0]
            if first_supervisor.get('matched') and first_supervisor.get('obj'):
                teacher_id = first_supervisor['obj'].id
                if laboratory_manager:
                    lab = laboratory_manager.get_laboratory_by_teacher_id(teacher_id)
                    if lab:
                        temp_award.laboratory_id = lab.id
                        logger.info(f"根据第一指导教师（教师ID: {teacher_id}）自动设置实验室ID: {temp_award.laboratory_id}")

        if not temp_award.laboratory_id and is_teacher_certificate and winner_status_list and len(winner_status_list) > 0:
            first_winner = winner_status_list[0]
            if first_winner.get('matched') and first_winner.get('obj') and first_winner.get('type') == 'teacher':
                teacher_id = first_winner['obj'].id
                if laboratory_manager:
                    lab = laboratory_manager.get_laboratory_by_teacher_id(teacher_id)
                    if lab:
                        temp_award.laboratory_id = lab.id
                        logger.info(f"根据第一教师获奖者（教师ID: {teacher_id}）自动设置实验室ID: {temp_award.laboratory_id}")

    file_url = None
    if temp_award.file_path:
        try:
            file_url = url_for(FILE_IMPORT_FILE_ENDPOINT, file_path=temp_award.file_path.replace('\\', '/'))
        except Exception:
            pass

    # PDF 第一页预览图路径（相对 files_root），供各端生成 preview_image_url
    preview_image_path = data.get('preview_image_path') if isinstance(data, dict) else None

    return {
        'temp_award': temp_award,
        'competitions': all_competitions,
        'winner_status_list': winner_status_list,
        'supervisor_status_list': supervisor_status_list,
        'related_student_status_list': related_student_status_list,
        'matched_teacher_ids': list(matched_teacher_ids),
        'file_path': file_path,
        'file_url': file_url,
        'preview_image_path': preview_image_path,
        'missing_competition_name': missing_competition_name
    }


def process_non_award_item(current_item, tab_type, all_laboratories):
    """处理非奖状类型的当前项（大创、专利、软著、其他文件等）"""
    file_path = None
    file_url = None
    innovation_data = None
    patent_data = None
    software_data = None
    other_data = None
    is_image = False

    if current_item:
        file_path = current_item.get_file_path()
        if file_path:
            try:
                file_url = url_for(FILE_IMPORT_FILE_ENDPOINT, file_path=file_path.replace('\\', '/'))
            except Exception:
                pass

        if tab_type == 'innovation':
            innovation_data = current_item.get_achievement_data()

        elif tab_type == 'patent':
            data = current_item.get_achievement_data()
            patent_data = {
                'patent_name': data.get('patent_name', ''),
                'patent_type': data.get('patent_type', ''),
                'application_number': data.get('application_number', ''),
                'publication_number': data.get('publication_number', ''),
                'inventor': data.get('inventor', ''),
                'patentee': data.get('patentee', ''),
                'application_date': data.get('application_date', ''),
                'laboratory_id': data.get('laboratory_id'),
            }

        elif tab_type == 'software':
            data = current_item.get_achievement_data()
            software_data = {
                'software_name': data.get('software_name', ''),
                'software_version': data.get('software_version', ''),
                'registration_number': data.get('registration_number', ''),
                'certificate_no': data.get('certificate_no', ''),
                'registration_date': data.get('registration_date', ''),
                'copyright_owner': data.get('copyright_owner', ''),
                'laboratory_id': data.get('laboratory_id'),
            }

        elif tab_type == 'other':
            from backend.services.review_service import IMAGE_EXTENSIONS
            other_data = current_item.get_achievement_data()
            if file_path:
                ext = Path(file_path).suffix.lower()
                is_image = ext in IMAGE_EXTENSIONS
            if not other_data.get('file_name') and file_path:
                other_data['file_name'] = Path(file_path).name

    return {
        'file_path': file_path,
        'file_url': file_url,
        'innovation_data': innovation_data,
        'patent_data': patent_data,
        'software_data': software_data,
        'other_data': other_data,
        'is_image': is_image
    }
