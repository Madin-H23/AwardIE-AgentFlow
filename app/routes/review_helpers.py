"""
审核页面渲染辅助模块

提供统一的审核页面渲染逻辑，供以下入口共用：
1. 文件导入后的审核页面 (admin.file_import_results)
2. 成果审核入口的审核页面 (admin_review.review_single_global)

两者的区别仅在于：
- 文件导入审核：只显示本次导入的内容（需要 session_id）
- 成果审核：显示所有待审核内容（无 session_id）
"""
import logging
import json
import time
from pathlib import Path
from flask import render_template, url_for
from backend.models.pending_achievement import PendingAchievementFilter

logger = logging.getLogger(__name__)


def normalize_laboratory_id(value):
    """将 laboratory_id 规范为 int，便于存储与模板比较。"""
    if value is None or value == '':
        return None
    try:
        i = int(value)
        return i if i > 0 else None
    except (TypeError, ValueError):
        return None


def normalize_related_student_from_ids(data, student_manager):
    """
    将 modified_data 中的 related_student_ids / related_student_ids[] 转换为 related_student 和 related_student_name。
    原地修改 data，供归档/审核时正确传递关联学生。
    前端修复后发送 related_student_ids (数组)，旧版可能为 related_student_ids[] (单值)。
    """
    if not student_manager or not isinstance(data, dict):
        return
    ids_raw = data.get('related_student_ids') or data.get('related_student_ids[]')
    if not ids_raw:
        return
    ids = ids_raw if isinstance(ids_raw, list) else [ids_raw] if ids_raw else []
    names = []
    for sid in ids:
        if not sid:
            continue
        try:
            s = student_manager.get_student_by_id(int(sid))
            if s and s.name:
                names.append(s.name)
        except (ValueError, TypeError):
            pass
    if names:
        name_str = ', '.join(names)
        data['related_student'] = name_str
        data['related_student_name'] = name_str


class TempAward:
    """临时奖状对象，用于模板渲染"""

    def __init__(self, data, file_path, student_manager, teacher_manager, pending_item=None):
        _cid = data.get('competition_id')
        try:
            self.competition_id = int(_cid) if _cid not in (None, '') else None
        except (TypeError, ValueError):
            self.competition_id = None
        self.award_level = data.get('award_level')
        self.competition_level = data.get('competition_level')
        self.year = data.get('year')
        self.track = data.get('track')
        self.certificate_id = data.get('certificate_id')
        self.project_title = data.get('project_title')
        self.date = data.get('date')
        self.province = data.get('province')
        self.issuer = data.get('issuer')
        self.laboratory_id = data.get('laboratory_id')
        self.granted_role = data.get('granted_role', '学生')
        self.winner_name = data.get('winner_name', '')
        self.supervisor_name = data.get('supervisor_name', '')
        self.related_student = data.get('related_student', '')

        # OCR和LLM数据：优先从pending对象的直接属性读取，其次从achievement_data读取
        if pending_item and hasattr(pending_item, 'ocr_text') and pending_item.ocr_text:
            self.ocr_result = pending_item.ocr_text
        else:
            self.ocr_result = data.get('ocr_result', '')

        if pending_item and hasattr(pending_item, 'llm_response') and pending_item.llm_response:
            self.llm_response = pending_item.llm_response
        else:
            self.llm_response = data.get('llm_response', '')

        # 最终抽取结果
        extract_data = data.get('_extract_data', data)
        if isinstance(extract_data, dict):
            clean_extract_data = {k: v for k, v in extract_data.items()
                                if k not in ['ocr_result', 'llm_response', 'matched_template_name',
                                            'import_session_id', 'file_name', 'file_path', 'file_type', '_extract_data']}
            self.extract_data_formatted = json.dumps(clean_extract_data, ensure_ascii=False, indent=2)
        else:
            self.extract_data_formatted = json.dumps(extract_data, ensure_ascii=False, indent=2) if extract_data else '{}'

        self.image_hash = data.get('image_hash', '')
        self.file_path = file_path

        # 获取模板名称：优先从 data 中获取，其次从 pending_item.ext_info 中获取
        self.matched_template_name = data.get('matched_template_name')
        if not self.matched_template_name and pending_item and hasattr(pending_item, 'ext_info'):
            try:
                ext_info = json.loads(pending_item.ext_info) if isinstance(pending_item.ext_info, str) else pending_item.ext_info
                if ext_info and isinstance(ext_info, dict):
                    self.matched_template_name = ext_info.get('template_name')
            except Exception as e:
                logger.warning(f"解析 ext_info 失败: {e}")
        self.student_winners = []
        self.teacher_winners = []
        self.supervisors = []
        self.related_students = []

        # 解析获奖者（根据证书类型判断是学生还是教师）
        is_teacher_role = self.granted_role and "教师" in self.granted_role
        if self.winner_name:
            names = [n.strip() for n in self.winner_name.split(',') if n.strip()]
            for name in names:
                if is_teacher_role:
                    # 教师证书：在教师中查找
                    matched_teachers = teacher_manager.find_teachers_by_name(name)
                    exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
                    if exact_matches:
                        self.teacher_winners.extend(exact_matches)
                else:
                    # 学生证书：在学生中查找
                    matched_students = student_manager.find_students_by_name(name)
                    exact_matches = [s for s in matched_students if s.name.strip() == name.strip()]
                    if exact_matches:
                        self.student_winners.extend(exact_matches)

        # 解析指导教师
        if self.supervisor_name:
            names = [n.strip() for n in self.supervisor_name.split(',') if n.strip()]
            for name in names:
                matched_teachers = teacher_manager.find_teachers_by_name(name)
                exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
                if exact_matches:
                    self.supervisors.extend(exact_matches)

        # 解析关联学生（用于教师证书）
        if self.related_student:
            names = [n.strip() for n in self.related_student.split(',') if n.strip()]
            for name in names:
                matched_students = student_manager.find_students_by_name(name)
                exact_matches = [s for s in matched_students if s.name.strip() == name.strip()]
                if exact_matches:
                    self.related_students.extend(exact_matches)

    def set_images_dir(self, images_dir):
        self.images_dir = images_dir


def get_type_names():
    """获取类型名称映射"""
    return {
        'award': '奖状',
        'patent': '专利',
        'software': '软著',
        'innovation': '大创',
        'other': '其他文件'
    }


def query_pending_items(pending_manager, tab_type, status, session_id=None):
    """
    查询待审核记录
    
    Args:
        pending_manager: PendingAchievementManager 实例
        tab_type: 成果类型 (award, patent, software, innovation, other)
        status: 状态 (valid 或 invalid)
        session_id: 可选的导入会话ID，如果提供则只查询该会话的记录
        
    Returns:
        items: 匹配的记录列表
    """
    # 新流程：只使用 pending 和 submit 状态
    if session_id:
        # 文件导入审核：只查询特定session的记录
        # valid 表示识别成功，invalid 表示待修订，但都使用 pending 状态
        query_status = 'pending'  # 新流程：识别成功和待修订都使用 pending 状态
        filter_obj = PendingAchievementFilter(
            achievement_type=tab_type,
            status=query_status,
            import_session_id=session_id,
            limit=1000
        )
        items = pending_manager.query_pending(filter_obj)
        
        # 根据 status 参数过滤验证结果
        if status == 'valid':
            # 只返回验证通过的记录
            return [item for item in items if item.is_valid()]
        else:
            # 只返回验证失败的记录
            return [item for item in items if not item.is_valid()]
    else:
        # 全局审核：查询 submit 状态的记录（已提交等待审核）
        # 同样需要区分识别成功和待修订
        filter_obj = PendingAchievementFilter(
            achievement_type=tab_type,
            status='submit',
            limit=1000
        )
        items = pending_manager.query_pending(filter_obj)

        # 根据验证结果分类
        if status == 'valid':
            # 只返回验证通过的记录
            return [item for item in items if item.is_valid()]
        elif status == 'invalid':
            # 只返回验证失败的记录
            return [item for item in items if not item.is_valid()]
        else:
            # 返回所有记录
            return items


def prepare_award_context(current_item, app_context, pending_item=None):
    """
    准备奖状类型的模板上下文

    Args:
        current_item: 当前 pending 记录
        app_context: 应用上下文
        pending_item: PendingAchievement 对象（用于获取 OCR/LLM 数据）

    Returns:
        dict: 包含奖状相关的模板变量
    """
    student_manager = app_context.get_student_manager()
    teacher_manager = app_context.get_teacher_manager()
    competition_manager = app_context.get_competition_manager()
    award_manager = app_context.get_award_manager()
    laboratory_manager = app_context.get_laboratory_manager()

    data = current_item.get_achievement_data()
    file_path = current_item.get_file_path()

    # 修复：laboratory_id 可能保存在两个地方
    # 1. achievement_data JSON 中
    # 2. pending_item.laboratory_id 直接字段
    # 优先使用 achievement_data 中的值，如果没有则使用直接字段；并规范为 int 便于模板比较
    laboratory_id = data.get('laboratory_id')
    if laboratory_id is None and hasattr(current_item, 'laboratory_id'):
        laboratory_id = current_item.laboratory_id
        if laboratory_id is not None:
            logger.info(f"从 pending_item.laboratory_id 字段读取到 laboratory_id: {laboratory_id}")
    laboratory_id = normalize_laboratory_id(laboratory_id)
    data['laboratory_id'] = laboratory_id

    # 创建临时奖状对象
    temp_award = TempAward(data, file_path, student_manager, teacher_manager, pending_item=pending_item or current_item)
    
    # 设置图片目录
    if award_manager.images_dir:
        temp_award.set_images_dir(award_manager.images_dir)
    
    # 尝试关联竞赛
    if not temp_award.competition_id:
        matched_competition = None
        template_id = data.get('template_id')
        
        # 优先级1: 从模板获取竞赛
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
                logger.warning(f"从模板获取竞赛失败: {e}")
        
        # 优先级2: 从数据中获取竞赛名称
        if not matched_competition:
            competition_name = data.get('competition_name')
            if not competition_name:
                extract_data = data.get('_extract_data', {})
                if isinstance(extract_data, dict):
                    competition_name = extract_data.get('competition_name')
            
            if competition_name:
                matched_competition = competition_manager.match_competition(competition_name)
        
        if matched_competition:
            temp_award.competition_id = matched_competition.id

    missing_competition_name = None
    if not temp_award.competition_id:
        comp_name = data.get('competition_name')
        if not comp_name:
            extract_data = data.get('_extract_data', {})
            if isinstance(extract_data, dict):
                comp_name = extract_data.get('competition_name')
        if comp_name and str(comp_name).strip():
            missing_competition_name = str(comp_name).strip()
            logger.info(f"竞赛未找到: competition_name={missing_competition_name}，提交时将自动创建")
    
    # 处理 winner_status_list
    # 根据证书类型判断是学生还是教师
    is_teacher_role = temp_award.granted_role and "教师" in temp_award.granted_role
    winner_status_list = []
    if temp_award.winner_name:
        def _base_name(segment: str) -> str:
            s = segment.strip()
            if "(" in s:
                return s.split("(")[0].strip()
            return s
        raw_names = [n.strip() for n in temp_award.winner_name.split(',') if n.strip()]
        seen_base = {}
        for n in raw_names:
            b = _base_name(n)
            if b not in seen_base:
                seen_base[b] = b
        names = list(seen_base.values())
        for name in names:
            if is_teacher_role:
                # 教师证书：在教师中查找
                matched_teachers = teacher_manager.find_teachers_by_name(name)
                exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
                if len(exact_matches) == 1:
                    winner_status_list.append({
                        'name': name, 'matched': True, 'obj': exact_matches[0],
                        'ambiguous': False, 'not_found': False
                    })
                elif len(exact_matches) > 1:
                    winner_status_list.append({
                        'name': name, 'matched': False, 'obj': None,
                        'ambiguous': True, 'not_found': False
                    })
                else:
                    winner_status_list.append({
                        'name': name, 'matched': False, 'obj': None,
                        'ambiguous': False, 'not_found': True
                    })
            else:
                # 学生证书：在学生中查找
                matched_students = student_manager.find_students_by_name(name)
                exact_matches = [s for s in matched_students if s.name.strip() == name.strip()]
                if len(exact_matches) == 1:
                    winner_status_list.append({
                        'name': name, 'matched': True, 'obj': exact_matches[0],
                        'ambiguous': False, 'not_found': False
                    })
                elif len(exact_matches) > 1:
                    winner_status_list.append({
                        'name': name, 'matched': False, 'obj': None,
                        'ambiguous': True, 'not_found': False
                    })
                else:
                    winner_status_list.append({
                        'name': name, 'matched': False, 'obj': None,
                        'ambiguous': False, 'not_found': True
                    })

    # 处理 supervisor_status_list
    supervisor_status_list = []
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
    
    # 关联学生：按纯姓名去重，重名显示为「林俊杰(重名)」
    related_student_status_list = []
    related_raw = getattr(temp_award, 'related_student', '') or getattr(temp_award, 'related_student_name', '')
    if related_raw:
        def _base_name_rel(seg: str) -> str:
            s = seg.strip()
            if "(" in s:
                return s.split("(")[0].strip()
            return s
        raw_rel = [n.strip() for n in str(related_raw).split(',') if n.strip()]
        seen_rel = {}
        for n in raw_rel:
            b = _base_name_rel(n)
            if b not in seen_rel:
                seen_rel[b] = b
        names_rel = list(seen_rel.values())
        for name in names_rel:
            matched_students = student_manager.find_students_by_name(name)
            exact_matches = [s for s in matched_students if s.name.strip() == name.strip()]
            if len(exact_matches) == 1:
                related_student_status_list.append({'name': name, 'matched': True, 'obj': exact_matches[0], 'ambiguous': False, 'not_found': False})
            elif len(exact_matches) > 1:
                related_student_status_list.append({'name': name, 'matched': False, 'obj': None, 'ambiguous': True, 'not_found': False})
            else:
                related_student_status_list.append({'name': name, 'matched': False, 'obj': None, 'ambiguous': False, 'not_found': True})

    # matched_teacher_ids
    matched_teacher_ids = set()
    if temp_award.teacher_winners:
        matched_teacher_ids = set(w.id for w in temp_award.teacher_winners)

    # 生成文件URL和预览图片URL
    file_url = None
    preview_image_url = None
    
    # 检查是否有预览图片路径（PDF文件）
    data = current_item.get_achievement_data() if current_item else {}
    preview_image_path = data.get('preview_image_path') if isinstance(data, dict) else None
    
    if preview_image_path:
        # 如果有预览图片路径，生成预览图片URL
        try:
            preview_image_url = url_for('admin_achievement.file_import_file', file_path=preview_image_path.replace('\\', '/'))
        except:
            pass
    
    # 生成原始文件URL
    if temp_award.file_path:
        try:
            file_url = url_for('admin_achievement.file_import_file', file_path=temp_award.file_path.replace('\\', '/'))
        except:
            pass

    # 获取所有竞赛
    all_competitions = []
    if hasattr(competition_manager, 'competitions'):
        all_competitions = competition_manager.competitions
    elif hasattr(competition_manager, '_competitions'):
        all_competitions = competition_manager._competitions

    # ==================== 新增：获取验证信息 ====================
    validation_result = current_item.get_validation_result()
    field_errors = {}  # {field_name: {message, suggestion}}

    if validation_result:
        # 合并 content_issues 和 completeness_issues
        all_issues = []
        all_issues.extend(validation_result.get('content_issues', []))
        all_issues.extend(validation_result.get('completeness_issues', []))

        # 构建字段错误映射
        for issue in all_issues:
            field_name = issue.get('field', '')
            if field_name:
                if field_name not in field_errors:
                    field_errors[field_name] = {
                        'message': issue.get('message', ''),
                        'suggestion': issue.get('suggestion', ''),
                        'error_type': issue.get('error_type', 'invalid')
                    }
                # 如果有多个错误，合并消息
                else:
                    existing_msg = field_errors[field_name]['message']
                    new_msg = issue.get('message', '')
                    if new_msg and new_msg not in existing_msg:
                        field_errors[field_name]['message'] = f"{existing_msg}; {new_msg}"

    # ==================== 新增：实验室默认选择 ====================
    # 如果第一导师匹配成功，查找其所属的实验室作为默认选择
    default_laboratory_id = None
    if supervisor_status_list and len(supervisor_status_list) > 0:
        first_supervisor = supervisor_status_list[0]
        if first_supervisor.get('matched') and first_supervisor.get('obj'):
            teacher_id = first_supervisor['obj'].id
            # 查询该教师所属的实验室
            if laboratory_manager:
                lab = laboratory_manager.get_laboratory_by_teacher_id(teacher_id)
                if lab:
                    default_laboratory_id = lab.id
                    logger.info(f"根据第一导师（教师ID: {teacher_id}）设置默认实验室ID: {default_laboratory_id}")

    # 设置 temp_award 的 laboratory_id
    if default_laboratory_id and not temp_award.laboratory_id:
        temp_award.laboratory_id = default_laboratory_id

    return {
        'award': temp_award,
        'competitions': all_competitions,
        'winner_status_list': winner_status_list,
        'supervisor_status_list': supervisor_status_list,
        'related_student_status_list': related_student_status_list,
        'matched_teacher_ids': list(matched_teacher_ids),
        'file_path': file_path,
        'file_url': file_url,
        'preview_image_url': preview_image_url,  # 新增：PDF预览图片URL
        'field_errors': field_errors,  # 新增：字段错误信息
        'is_valid': validation_result.get('is_valid', True) if validation_result else True,  # 新增：是否通过验证
        'missing_competition_name': missing_competition_name
    }


def prepare_patent_context(current_item, app_context):
    """
    准备专利类型的模板上下文

    Args:
        current_item: 当前 pending 记录
        app_context: 应用上下文

    Returns:
        dict: 包含专利相关的模板变量
    """
    laboratory_manager = app_context.get_laboratory_manager()

    data = current_item.get_achievement_data()
    file_path = current_item.get_file_path()

    # 修复：laboratory_id 可能保存在两个地方
    laboratory_id = data.get('laboratory_id')
    if laboratory_id is None and hasattr(current_item, 'laboratory_id'):
        laboratory_id = current_item.laboratory_id
        if laboratory_id is not None:
            data['laboratory_id'] = laboratory_id
            logger.info(f"[专利] 从 pending_item.laboratory_id 字段读取到 laboratory_id: {laboratory_id}")

    # 创建专利数据对象
    patent_data = {
        'patent_name': data.get('patent_name', ''),
        'patent_type': data.get('patent_type', ''),
        'application_number': data.get('application_number', ''),
        'publication_number': data.get('publication_number', ''),
        'inventor': data.get('inventor', ''),
        'patentee': data.get('patentee', ''),
        'application_date': data.get('application_date', ''),
        'laboratory_id': normalize_laboratory_id(laboratory_id),
    }
    
    # 生成文件URL
    file_url = None
    if file_path:
        try:
            file_url = url_for('admin_achievement.file_import_file', file_path=file_path.replace('\\', '/'))
        except:
            pass
    
    # 获取所有实验室
    all_laboratories = []
    if laboratory_manager:
        all_laboratories = laboratory_manager.get_all_laboratories() if hasattr(laboratory_manager, 'get_all_laboratories') else []
    
    return {
        'patent': patent_data,
        'file_path': file_path,
        'file_url': file_url,
        'all_laboratories': all_laboratories,
    }


def prepare_software_context(current_item, app_context):
    """
    准备软著类型的模板上下文

    Args:
        current_item: 当前 pending 记录
        app_context: 应用上下文

    Returns:
        dict: 包含软著相关的模板变量
    """
    laboratory_manager = app_context.get_laboratory_manager()

    data = current_item.get_achievement_data()
    file_path = current_item.get_file_path()

    # 修复：laboratory_id 可能保存在两个地方
    laboratory_id = data.get('laboratory_id')
    if laboratory_id is None and hasattr(current_item, 'laboratory_id'):
        laboratory_id = current_item.laboratory_id
        if laboratory_id is not None:
            data['laboratory_id'] = laboratory_id
            logger.info(f"[软著] 从 pending_item.laboratory_id 字段读取到 laboratory_id: {laboratory_id}")

    # 创建软著数据对象（laboratory_id 规范为 int，便于模板 selected 比较）
    software_data = {
        'software_name': data.get('software_name', ''),
        'software_version': data.get('software_version', ''),
        'registration_number': data.get('registration_number', ''),
        'certificate_no': data.get('certificate_no', ''),
        'registration_date': data.get('registration_date', ''),
        'copyright_owner': data.get('copyright_owner', ''),
        'laboratory_id': normalize_laboratory_id(laboratory_id),
    }
    
    # 生成文件URL
    file_url = None
    if file_path:
        try:
            file_url = url_for('admin_achievement.file_import_file', file_path=file_path.replace('\\', '/'))
        except:
            pass
    
    # 获取所有实验室
    all_laboratories = []
    if laboratory_manager:
        all_laboratories = laboratory_manager.get_all_laboratories() if hasattr(laboratory_manager, 'get_all_laboratories') else []
    
    return {
        'software': software_data,
        'file_path': file_path,
        'file_url': file_url,
        'all_laboratories': all_laboratories,
    }


def _get_stored_agent_review(item):
    """读取 pending.ext_info.agent_review（P1 提交时 Agent 把关存下的审核结论）。"""
    if not item:
        return None
    try:
        ext_info = item.get_ext_info()
        if isinstance(ext_info, dict):
            return ext_info.get('agent_review')
    except Exception:
        pass
    return None


def render_review_page(session_id, tab_type, status, index, app_context, title_prefix='审核', route_prefix='admin'):
    """
    渲染统一的审核页面

    Args:
        session_id: 导入会话ID（如果是全局审核则为None）
        tab_type: 成果类型
        status: 状态 (valid 或 invalid)
        index: 当前项索引
        app_context: 应用上下文
        title_prefix: 页面标题前缀
        route_prefix: 路由前缀 ('admin' 或 'admin_review')

    Returns:
        渲染后的模板响应
    """
    from pathlib import Path
    from backend.services.review_service import IMAGE_EXTENSIONS

    pending_manager = app_context.get_pending_achievement_manager()
    student_manager = app_context.get_student_manager()
    teacher_manager = app_context.get_teacher_manager()
    laboratory_manager = app_context.get_laboratory_manager()

    type_names = get_type_names()

    # ==================== 统计各类型数据 ====================
    type_stats = {}
    all_types = ['award', 'patent', 'software', 'innovation', 'other']

    for t in all_types:
        if t == 'other':
            # 对于 other 类型，统计图片和文件数量
            # 新流程：只使用 pending 和 submit 状态
            if session_id:
                # 文件导入审核：只统计本次导入的记录（pending 状态）
                filter_all = PendingAchievementFilter(
                    achievement_type=t,
                    status='pending',
                    import_session_id=session_id,
                    limit=1000
                )
                other_items = pending_manager.query_pending(filter_all)
            else:
                # 全局审核：只统计 submit 状态的记录（已提交等待审核）
                filter_submit = PendingAchievementFilter(
                    achievement_type=t,
                    status='submit',
                    limit=1000
                )
                other_items = pending_manager.query_pending(filter_submit)
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
        elif t == 'innovation':
            # innovation 类型：不区分 valid/invalid，只统计 total
            if session_id:
                # 文件导入审核：只查询 pending 状态
                filter_pending = PendingAchievementFilter(
                    achievement_type=t,
                    status='pending',
                    import_session_id=session_id,
                    limit=1000
                )
                all_items = pending_manager.query_pending(filter_pending)
            else:
                # 全局审核：只统计 submit 状态的记录（已提交等待审核）
                filter_submit = PendingAchievementFilter(
                    achievement_type=t,
                    status='submit',
                    limit=1000
                )
                all_items = pending_manager.query_pending(filter_submit)
            type_stats[t] = {
                'total': len(all_items)
            }
        else:
            # award/patent/software：统计识别成功和待修订
            # 新流程：识别成功和待修订都使用 pending 状态，提交后改为 submit 状态
            if session_id:
                # 文件导入审核：只查询 pending 状态，然后根据验证结果分类
                filter_pending = PendingAchievementFilter(
                    achievement_type=t,
                    status='pending',
                    import_session_id=session_id,
                    limit=1000
                )
                all_items = pending_manager.query_pending(filter_pending)
                # 根据验证结果分类
                valid_items = [item for item in all_items if item.is_valid()]
                invalid_items = [item for item in all_items if not item.is_valid()]
                valid_count = len(valid_items)
                invalid_count = len(invalid_items)
            else:
                # 全局审核：只统计 submit 状态的记录（已提交等待审核），识别成功与待修订均展示
                filter_submit = PendingAchievementFilter(
                    achievement_type=t,
                    status='submit',
                    limit=1000
                )
                submit_items = pending_manager.query_pending(filter_submit)
                valid_items = [item for item in submit_items if item.is_valid()]
                invalid_items = [item for item in submit_items if not item.is_valid()]
                valid_count = len(valid_items)
                invalid_count = len(invalid_items)

            type_stats[t] = {
                'total': valid_count + invalid_count,
                'valid': valid_count,
                'invalid': invalid_count
            }

    # 只保留有数据的类型
    available_types = [t for t in all_types if type_stats.get(t, {}).get('total', 0) > 0]

    # 如果当前tab_type不在可用类型中，自动切换到第一个可用类型
    if tab_type not in available_types and available_types:
        tab_type = available_types[0]
        # 重置status为该类型的默认值
        if tab_type == 'other':
            status = 'image' if type_stats['other'].get('image', 0) > 0 else 'file'
        elif tab_type == 'innovation':
            # innovation 不需要 status
            status = None
        else:
            status = 'valid' if type_stats[tab_type].get('valid', 0) > 0 else 'invalid'

    # 对于 other 类型，默认 sub_tab 为 'image'（而非 'valid'）
    if tab_type == 'other' and status not in ('image', 'file'):
        status = 'image' if type_stats['other'].get('image', 0) > 0 else 'file'

    # 即使 tab_type 正确，也检查当前子TAB是否有数据；若无则自动切换到有数据的子TAB
    # （如：奖状-识别成功 全部提交后 valid=0、invalid=3，须切到 待修订，否则会出现「第 1/ 0 项」）
    if tab_type in available_types and tab_type not in ('other', 'innovation'):
        curr = type_stats.get(tab_type, {})
        if status == 'valid' and curr.get('valid', 0) == 0:
            status = 'invalid' if curr.get('invalid', 0) > 0 else 'valid'
        elif status == 'invalid' and curr.get('invalid', 0) == 0:
            status = 'valid' if curr.get('valid', 0) > 0 else 'invalid'

    # ==================== 查询当前类型的记录 ====================
    # 对于 other 类型，子TAB 是 'image' 和 'file'，而不是 'valid' 和 'invalid'
    if tab_type == 'other':
        # other 类型：按图片/文件分类
        # 新流程：只使用 pending 和 submit 状态
        if session_id:
            # 文件导入审核：查询 pending 状态的记录
            filter_obj = PendingAchievementFilter(
                achievement_type='other',
                status='pending',
                import_session_id=session_id,
                limit=1000
            )
            all_other_items = pending_manager.query_pending(filter_obj)
        else:
            # 全局审核：只查询 submit 状态的记录（已提交等待审核）
            filter_submit = PendingAchievementFilter(
                achievement_type='other',
                status='submit',
                limit=1000
            )
            all_other_items = pending_manager.query_pending(filter_submit)

        # 根据 sub_tab 过滤图片或文件
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
    elif tab_type == 'innovation':
        # innovation 类型：不区分 valid/invalid，返回全部记录
        if session_id:
            filter_obj = PendingAchievementFilter(
                achievement_type='innovation',
                status='pending',
                import_session_id=session_id,
                limit=1000
            )
        else:
            filter_obj = PendingAchievementFilter(
                achievement_type='innovation',
                status='submit',
                limit=1000
            )
        items = pending_manager.query_pending(filter_obj)
        count = len(items)
    else:
        # award/patent/software：按识别成功/待修订分类
        items = query_pending_items(pending_manager, tab_type, status, session_id)
        count = len(items)

    # innovation 类型：按文件分页，当前页显示「当前文件」下的 projects 表格
    if tab_type == 'innovation':
        from flask import request

        # index = 当前文件下标（第几个 innovation pending 行）
        file_count = len(items)
        if file_count == 0:
            current_file_index = 0
            current_file_item = None
        else:
            current_file_index = max(0, min(index, file_count - 1))
            current_file_item = items[current_file_index]

        # 检查是否有 edit 参数（编辑当前文件下第 project_index 个项目）
        edit_pending_id = request.args.get('edit')
        project_index_param = request.args.get('project_index')
        edit_project_index = None
        if project_index_param is not None:
            try:
                edit_project_index = int(project_index_param)
            except (ValueError, TypeError):
                edit_project_index = None

        # 从当前文件的 achievement_data.projects 展开表格行
        innovation_items = []
        if current_file_item:
            achievement_data = current_file_item.get_achievement_data()
            projects = achievement_data.get('projects') or []
            file_pending_id = current_file_item.id

            validation_result = current_file_item.get_validation_result()
            validation_by_index = {}
            if isinstance(validation_result, dict):
                content_issues = validation_result.get('content_issues') or []
                for issue in content_issues:
                    idx = issue.get('index')
                    if idx is not None and isinstance(idx, int):
                        validation_by_index[idx] = issue

            for i, p in enumerate(projects):
                # 兼容抽取器英文键与设计文档中文键
                def _get(d, *keys):
                    for k in keys:
                        v = d.get(k)
                        if v is not None and v != '':
                            return v
                    return ''

                leader = p.get('学生负责人') or {}
                if isinstance(leader, dict) and (leader.get('姓名') or leader.get('name') or leader.get('学号') or leader.get('student_id')):
                    ln = leader.get('姓名', '') or leader.get('name', '')
                    lid = leader.get('学号', '') or leader.get('student_id', '')
                    leader_display = ln + ('\n' + str(lid) if lid else '')
                else:
                    # 抽取器格式: leader_name, leader_student_id
                    ln = _get(p, 'leader_name', '负责人')
                    lid = _get(p, 'leader_student_id', '负责人学号')
                    leader_display = (ln + ('\n' + str(lid) if lid else '')) if ln or lid else ''

                teachers = p.get('指导教师') or p.get('supervisors') or []
                if isinstance(teachers, list):
                    teacher_display = '、'.join(str(t) for t in teachers if t)
                else:
                    teacher_display = str(teachers) if teachers else ''

                members = p.get('项目其他成员信息') or p.get('members') or []
                if isinstance(members, list):
                    member_parts = []
                    for m in members:
                        if isinstance(m, dict):
                            name = m.get('姓名', '') or m.get('name', '')
                            sid = m.get('学号', '') or m.get('student_id', '')
                            member_parts.append(f"{name}({sid})" if sid else name)
                        else:
                            member_parts.append(str(m))
                    member_display = '\n'.join(member_parts)
                else:
                    member_display = str(members) if members else ''

                year_val = p.get('年份') or p.get('year')
                if year_val is None and (p.get('start_date') or p.get('项目开始时间')):
                    import re
                    sd = p.get('start_date') or p.get('项目开始时间') or ''
                    ym = re.match(r'^(\d{4})', str(sd))
                    year_val = int(ym.group(1)) if ym else None
                year_display = year_val if year_val is not None else ''

                issue = validation_by_index.get(i)
                if issue:
                    valid_display = '待修订'
                else:
                    valid_display = '通过'

                # 弹窗编辑用：扁平表单字段，与 _innovation_form_to_project 对应
                leader = p.get('学生负责人') or {}
                if isinstance(leader, dict) and (leader.get('姓名') or leader.get('name') or leader.get('学号') or leader.get('student_id')):
                    student_leader_val = (leader.get('姓名') or leader.get('name') or '') + (' (' + (leader.get('学号') or leader.get('student_id') or '') + ')' if (leader.get('学号') or leader.get('student_id')) else '')
                else:
                    student_leader_val = (ln + (' (' + str(lid) + ')' if lid else '')) if (ln or lid) else ''
                teachers_val = teacher_display
                members_val = member_display.replace('\n', ', ') if member_display else ''

                # 每个大创项目独立关联实验室（从该项目字典取）
                project_laboratory_id = p.get('laboratory_id')
                project_laboratory_name = ''
                if project_laboratory_id and laboratory_manager:
                    lab = laboratory_manager.get_laboratory_by_id(project_laboratory_id)
                    if lab:
                        project_laboratory_name = lab.name

                form_data = {
                    'project_id': _get(p, '项目编号', 'project_number'),
                    'project_name': _get(p, '项目名称', 'project_name'),
                    'project_level': _get(p, '项目级别', 'project_level'),
                    'acceptance_level': _get(p, '验收等级', 'acceptance_level'),
                    'department': _get(p, '系别', 'department'),
                    'year': year_display if year_display != '' else '',
                    'start_date': _get(p, '项目开始时间', 'start_date'),
                    'end_date': _get(p, '项目结束时间', 'end_date'),
                    'student_leader': student_leader_val,
                    'teachers': teachers_val,
                    'other_members': members_val,
                    'project_intro': _get(p, '项目简介', 'project_intro'),
                    'laboratory_id': str(project_laboratory_id) if project_laboratory_id is not None else '',
                }

                innovation_items.append({
                    'pending_id': file_pending_id,
                    'project_index': i,
                    'project_number': _get(p, '项目编号', 'project_number'),
                    'project_name': _get(p, '项目名称', 'project_name'),
                    'year': year_display,
                    'project_level': _get(p, '项目级别', 'project_level'),
                    'leader_name': leader_display,
                    'teacher_list': teacher_display,
                    'member_list': member_display,
                    'acceptance_status': _get(p, '验收等级', 'acceptance_level'),
                    'validation_display': valid_display,
                    'laboratory_id': project_laboratory_id,
                    'laboratory': project_laboratory_name,
                    'project_raw': p,
                    'form_data': form_data,
                })

        # 编辑态：edit=pending_id&project_index=i 表示编辑当前文件下第 i 个项目
        innovation = None
        file_path = None
        file_url = None
        current_item = None
        if current_file_item and edit_pending_id is not None and edit_project_index is not None:
            try:
                edit_pid = int(edit_pending_id)
                if current_file_item.id == edit_pid:
                    achievement_data = current_file_item.get_achievement_data()
                    projects_list = achievement_data.get('projects') or []
                    if 0 <= edit_project_index < len(projects_list):
                        current_item = current_file_item
                        raw = projects_list[edit_project_index]
                        innovation = dict(raw) if isinstance(raw, dict) else {}
                        innovation['_project_index'] = edit_project_index
            except (ValueError, TypeError):
                pass

        if current_file_item:
            fp = current_file_item.get_file_path()
            if fp:
                file_path = fp
                try:
                    file_url = url_for('admin_achievement.file_import_file', file_path=file_path.replace('\\', '/'))
                except Exception:
                    file_url = None

        # 获取所有教师和学生（编辑表单用）
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
            all_laboratories = laboratory_manager.get_all_laboratories() if hasattr(laboratory_manager, 'get_all_laboratories') else []

        # 全部提交/全部放弃仅针对当前文件（当前页）
        current_tab_pending_ids = [current_file_item.id] if current_file_item else []
        # 大创「全部提交」提示用项目数量：仅当前文件的 projects 数（与提交范围一致）
        if current_file_item:
            current_data = current_file_item.get_achievement_data() or {}
            submit_display_count = len(current_data.get('projects') or [])
        else:
            submit_display_count = 0

        template_context = {
            'session_id': session_id,
            'tab_type': tab_type,
            'status': status,
            'current_index': current_file_index,
            'count': file_count,
            'type_names': type_names,
            'type_stats': type_stats,
            'available_types': available_types,
            'innovation_items': innovation_items,
            'current_item': current_item,
            'innovation': innovation,
            'current_file_item': current_file_item,
            'file_path': file_path,
            'file_url': file_url,
            'all_laboratories': all_laboratories,
            'field_errors': {},
            'is_valid': True,
            'title_prefix': title_prefix,
            'route_prefix': route_prefix,
            'is_global_review': session_id is None,
            'current_tab_pending_ids': current_tab_pending_ids,
            'submit_display_count': submit_display_count,
            'agent_review': _get_stored_agent_review(current_item),
        }

        return render_template('admin/file_import/results.html', **template_context)
    
    # 获取当前项（非 innovation 类型）
    current_item = None
    # 确保 count 和 items 长度一致
    if count != len(items):
        logger.warning(f"count ({count}) 和 items 长度 ({len(items)}) 不一致，使用 items 长度")
        count = len(items)
    
    if items and 0 <= index < count:
        current_item = items[index]
    elif items and count > 0:
        # 如果 index 超出范围，重置为 0
        index = 0
        current_item = items[0]
    else:
        # 如果没有 items，确保 current_item 为 None，index 为 0
        current_item = None
        index = 0

    # 获取所有教师和学生
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
        all_laboratories = laboratory_manager.get_all_laboratories() if hasattr(laboratory_manager, 'get_all_laboratories') else []

    # 当前 Tab 的 pending ID 列表（成果审核页「全部提交」= 批量审核通过时使用）
    current_tab_pending_ids = [item.id for item in items]
    # 全部提交提示用数量：大创=项目数，其他=记录数
    if tab_type == 'innovation':
        # 大创：计算所有 items 中的项目总数
        submit_display_count = sum(
            len((item.get_achievement_data() or {}).get('projects') or [])
            for item in items
        )
    else:
        submit_display_count = count

    # 基础模板参数
    template_context = {
        'session_id': session_id,
        'tab_type': tab_type,
        'status': status,
        'current_index': index,
        'count': count,  # 确保 count 与 items 长度一致
        'type_names': type_names,
        'type_stats': type_stats,
        'available_types': available_types,
        'current_item': current_item,
        'all_teachers': all_teachers,
        'all_students': all_students,
        'all_laboratories': all_laboratories,
        'title_prefix': title_prefix,
        'route_prefix': route_prefix,
        'is_global_review': session_id is None,  # 标记是否为全局审核
        'current_tab_pending_ids': current_tab_pending_ids,
        'submit_display_count': submit_display_count,
        'agent_review': _get_stored_agent_review(current_item),
    }

    # 根据类型添加特定参数
    if current_item and tab_type == 'award':
        award_context = prepare_award_context(current_item, app_context)
        template_context.update(award_context)
    elif current_item and tab_type == 'patent':
        patent_context = prepare_patent_context(current_item, app_context)
        template_context.update(patent_context)
    elif current_item and tab_type == 'software':
        software_context = prepare_software_context(current_item, app_context)
        template_context.update(software_context)
    elif current_item and tab_type == 'innovation':
        innovation_data = current_item.get_achievement_data()
        # 大创按项目独立关联实验室，不再使用文件级 laboratory_id
        template_context['innovation'] = innovation_data
        file_path = current_item.get_file_path()
        template_context['file_path'] = file_path
        if file_path:
            try:
                template_context['file_url'] = url_for('admin_achievement.file_import_file', file_path=file_path.replace('\\', '/'))
            except:
                template_context['file_url'] = None
    elif current_item and tab_type == 'other':
        # other 类型：需要设置 other_data 和 is_image
        file_path = current_item.get_file_path()
        template_context['file_path'] = file_path

        other_data = current_item.get_achievement_data()
        # 修复：laboratory_id 可能保存在两个地方
        laboratory_id = other_data.get('laboratory_id')
        if laboratory_id is None and hasattr(current_item, 'laboratory_id'):
            laboratory_id = current_item.laboratory_id
            if laboratory_id is not None:
                other_data['laboratory_id'] = laboratory_id
                logger.info(f"[其他文件] 从 pending_item.laboratory_id 字段读取到 laboratory_id: {laboratory_id}")
        # 获取文件名
        if not other_data.get('file_name') and file_path:
            other_data['file_name'] = Path(file_path).name
        template_context['other_data'] = other_data
        
        # 判断是否为图片
        is_image = False
        if file_path:
            ext = Path(file_path).suffix.lower()
            is_image = ext in IMAGE_EXTENSIONS
        template_context['is_image'] = is_image
        
        if file_path:
            try:
                template_context['file_url'] = url_for('admin_achievement.file_import_file', file_path=file_path.replace('\\', '/'))
            except:
                template_context['file_url'] = None
    elif current_item:
        file_path = current_item.get_file_path()
        template_context['file_path'] = file_path
        if file_path:
            try:
                template_context['file_url'] = url_for('admin_achievement.file_import_file', file_path=file_path.replace('\\', '/'))
            except:
                template_context['file_url'] = None

    return render_template('admin/file_import/results.html', **template_context)
