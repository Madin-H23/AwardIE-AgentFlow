"""
奖状处理服务

封装奖状处理相关的业务逻辑，提供可复用的方法供路由层调用。
包括：模板匹配信息获取、竞赛关联、姓名匹配状态列表生成、实验室自动匹配等。
"""
import logging
import re
from typing import Dict, List, Optional, Any
from backend.models.competition import CompetitionManager, Competition
from backend.models.student import StudentManager, Student
from backend.models.teacher import TeacherManager, Teacher

logger = logging.getLogger(__name__)


def _parse_names(names_str: Optional[str]) -> List[str]:
    """
    解析姓名字符串，支持逗号、顿号、分号分隔
    
    Args:
        names_str: 姓名字符串（可能包含多个姓名，用分隔符分隔）
        
    Returns:
        姓名列表
    """
    if not names_str:
        return []
    # 支持逗号、顿号、分号
    parts = re.split(r'[,，、;；]', names_str)
    return [p.strip() for p in parts if p.strip()]


class AwardProcessingService:
    """奖状处理服务类"""
    
    def get_template_match_info(self, pending_item) -> Dict[str, Any]:
        """
        从 pending_item 的 ext_info 中提取模板匹配信息
        
        Args:
            pending_item: PendingAchievement 对象或类似对象，需要有 get_ext_info 方法
            
        Returns:
            Dict 包含 template_id 和 template_name
        """
        template_info = {'template_id': None, 'template_name': None}
        
        if not pending_item:
            return template_info
        
        try:
            ext_info = pending_item.get_ext_info() if hasattr(pending_item, 'get_ext_info') else {}
            if isinstance(ext_info, dict):
                template_info['template_id'] = ext_info.get('template_id')
                template_info['template_name'] = ext_info.get('template_name')
                if template_info['template_name']:
                    logger.info(
                        f"[AwardProcessingService] 从 ext_info 获取模板名称: "
                        f"{template_info['template_name']}, template_id: {template_info['template_id']}"
                    )
        except Exception as e:
            logger.warning(f"获取模板匹配信息失败: {e}", exc_info=True)
        
        return template_info
    
    def associate_competition_by_template_or_name(
        self,
        template_id: Optional[int],
        competition_name: Optional[str],
        competition_manager: CompetitionManager,
        extract_data: Optional[Dict] = None
    ) -> Optional[Competition]:
        """
        通过模板或 competition_name 关联竞赛
        
        优先级：模板 > competition_name
        
        Args:
            template_id: 模板ID
            competition_name: 竞赛名称（从提取数据中获取）
            competition_manager: 竞赛管理器
            extract_data: 提取数据字典（可选，用于从 _extract_data 中获取 competition_name）
            
        Returns:
            匹配到的 Competition 对象，如果未匹配到则返回 None
        """
        matched_competition = None
        
        # 优先级1: 如果匹配到模板，从模板的 default_fields 中获取 competition_name
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
        
        # 优先级2: 如果没有模板或模板中没有 competition_name，从提取数据的 competition_name 字段匹配
        if not matched_competition:
            # 尝试从 extract_data 中获取 competition_name
            if not competition_name and extract_data:
                competition_name = extract_data.get('competition_name')
                if not competition_name:
                    extract_data_nested = extract_data.get('_extract_data', {})
                    if isinstance(extract_data_nested, dict):
                        competition_name = extract_data_nested.get('competition_name')
            
            if competition_name:
                matched_competition = competition_manager.match_competition(competition_name)
                if matched_competition:
                    logger.info(
                        f"通过 competition_name 关联竞赛: "
                        f"competition_name={competition_name}, "
                        f"competition_id={matched_competition.id}"
                    )
        
        return matched_competition
    
    def build_winner_status_list(
        self,
        winner_name: Optional[str],
        is_teacher_certificate: bool,
        student_manager: Optional[StudentManager],
        teacher_manager: Optional[TeacherManager],
        existing_winners: Optional[List] = None
    ) -> List[Dict[str, Any]]:
        """
        构建获奖者状态列表（统一处理学生/教师证书）
        
        Args:
            winner_name: 获奖者姓名（逗号分隔）
            is_teacher_certificate: 是否为教师证书
            student_manager: 学生管理器
            teacher_manager: 教师管理器
            existing_winners: 已存在的获奖者列表（可选，用于检查是否已匹配）
            
        Returns:
            状态列表，每个元素包含：
            - name: 姓名
            - matched: 是否匹配成功
            - obj: 匹配到的对象（Student 或 Teacher）
            - ambiguous: 是否重名（多个匹配）
            - not_found: 是否未找到
            - type: 'student' 或 'teacher'
        """
        winner_status_list = []
        
        if not winner_name:
            return winner_status_list
        
        names = _parse_names(winner_name)
        
        for name in names:
            if is_teacher_certificate:
                # 教师证书：使用 teacher_manager 查找教师
                if not teacher_manager:
                    winner_status_list.append({
                        'name': name,
                        'matched': False,
                        'obj': None,
                        'ambiguous': False,
                        'not_found': True,
                        'type': 'teacher'
                    })
                    continue
                
                matched_teachers = teacher_manager.find_teachers_by_name(name)
                exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
                
                # 如果提供了 existing_winners，先检查是否已经在列表中
                matched_obj = None
                if existing_winners:
                    for winner in existing_winners:
                        if hasattr(winner, 'name') and winner.name.strip() == name.strip():
                            matched_obj = winner
                            break
                
                if matched_obj:
                    winner_status_list.append({
                        'name': name,
                        'matched': True,
                        'obj': matched_obj,
                        'ambiguous': False,
                        'not_found': False,
                        'type': 'teacher'
                    })
                elif len(exact_matches) == 1:
                    winner_status_list.append({
                        'name': name,
                        'matched': True,
                        'obj': exact_matches[0],
                        'ambiguous': False,
                        'not_found': False,
                        'type': 'teacher'
                    })
                elif len(exact_matches) > 1:
                    winner_status_list.append({
                        'name': name,
                        'matched': False,
                        'obj': None,
                        'ambiguous': True,
                        'not_found': False,
                        'type': 'teacher'
                    })
                else:
                    winner_status_list.append({
                        'name': name,
                        'matched': False,
                        'obj': None,
                        'ambiguous': False,
                        'not_found': True,
                        'type': 'teacher'
                    })
            else:
                # 学生证书：使用 student_manager 查找学生
                if not student_manager:
                    winner_status_list.append({
                        'name': name,
                        'matched': False,
                        'obj': None,
                        'ambiguous': False,
                        'not_found': True,
                        'type': 'student'
                    })
                    continue
                
                matched_students = student_manager.find_students_by_name(name)
                exact_matches = [s for s in matched_students if s.name.strip() == name.strip()]
                
                # 如果提供了 existing_winners，先检查是否已经在列表中
                matched_obj = None
                if existing_winners:
                    for winner in existing_winners:
                        if hasattr(winner, 'name') and winner.name.strip() == name.strip():
                            matched_obj = winner
                            break
                
                if matched_obj:
                    winner_status_list.append({
                        'name': name,
                        'matched': True,
                        'obj': matched_obj,
                        'ambiguous': False,
                        'not_found': False,
                        'type': 'student'
                    })
                elif len(exact_matches) == 1:
                    winner_status_list.append({
                        'name': name,
                        'matched': True,
                        'obj': exact_matches[0],
                        'ambiguous': False,
                        'not_found': False,
                        'type': 'student'
                    })
                elif len(exact_matches) > 1:
                    winner_status_list.append({
                        'name': name,
                        'matched': False,
                        'obj': None,
                        'ambiguous': True,
                        'not_found': False,
                        'type': 'student'
                    })
                else:
                    winner_status_list.append({
                        'name': name,
                        'matched': False,
                        'obj': None,
                        'ambiguous': False,
                        'not_found': True,
                        'type': 'student'
                    })
        
        return winner_status_list
    
    def build_supervisor_status_list(
        self,
        supervisor_name: Optional[str],
        teacher_manager: Optional[TeacherManager],
        existing_supervisors: Optional[List] = None
    ) -> List[Dict[str, Any]]:
        """
        构建指导教师状态列表
        
        Args:
            supervisor_name: 指导教师姓名（逗号分隔）
            teacher_manager: 教师管理器
            existing_supervisors: 已存在的指导教师列表（可选，用于检查是否已匹配）
            
        Returns:
            状态列表，每个元素包含：
            - name: 姓名
            - matched: 是否匹配成功
            - obj: 匹配到的 Teacher 对象
            - ambiguous: 是否重名（多个匹配）
            - not_found: 是否未找到
        """
        supervisor_status_list = []
        
        if not supervisor_name:
            return supervisor_status_list
        
        names = _parse_names(supervisor_name)
        
        if not teacher_manager:
            # 如果没有 teacher_manager，返回未找到状态
            for name in names:
                supervisor_status_list.append({
                    'name': name,
                    'matched': False,
                    'obj': None,
                    'ambiguous': False,
                    'not_found': True
                })
            return supervisor_status_list
        
        for name in names:
            matched_teachers = teacher_manager.find_teachers_by_name(name)
            exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
            
            # 如果提供了 existing_supervisors，先检查是否已经在列表中
            matched_obj = None
            if existing_supervisors:
                for supervisor in existing_supervisors:
                    if hasattr(supervisor, 'name') and supervisor.name.strip() == name.strip():
                        matched_obj = supervisor
                        break
            
            if matched_obj:
                supervisor_status_list.append({
                    'name': name,
                    'matched': True,
                    'obj': matched_obj,
                    'ambiguous': False,
                    'not_found': False
                })
            elif len(exact_matches) == 1:
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
        
        return supervisor_status_list
    
    def auto_match_laboratory(
        self,
        supervisor_status_list: List[Dict],
        winner_status_list: List[Dict],
        is_teacher_certificate: bool,
        laboratory_manager: Any
    ) -> Optional[int]:
        """
        自动匹配实验室
        
        优先级：1. 第一指导教师 2. 第一教师获奖者（教师证书时）
        
        Args:
            supervisor_status_list: 指导教师状态列表
            winner_status_list: 获奖者状态列表
            is_teacher_certificate: 是否为教师证书
            laboratory_manager: 实验室管理器
            
        Returns:
            匹配到的实验室ID，如果未匹配到则返回 None
        """
        if not laboratory_manager:
            return None
        
        # 优先级1: 根据第一指导教师设置
        if supervisor_status_list and len(supervisor_status_list) > 0:
            first_supervisor = supervisor_status_list[0]
            if first_supervisor.get('matched') and first_supervisor.get('obj'):
                teacher_id = first_supervisor['obj'].id
                lab = laboratory_manager.get_laboratory_by_teacher_id(teacher_id)
                if lab:
                    logger.info(
                        f"根据第一指导教师（教师ID: {teacher_id}）自动设置实验室ID: {lab.id}"
                    )
                    return lab.id
        
        # 优先级2: 如果指导教师没有设置实验室，且是教师证书，尝试根据第一教师获奖者设置
        if is_teacher_certificate and winner_status_list and len(winner_status_list) > 0:
            first_winner = winner_status_list[0]
            if (first_winner.get('matched') and 
                first_winner.get('obj') and 
                first_winner.get('type') == 'teacher'):
                teacher_id = first_winner['obj'].id
                lab = laboratory_manager.get_laboratory_by_teacher_id(teacher_id)
                if lab:
                    logger.info(
                        f"根据第一教师获奖者（教师ID: {teacher_id}）自动设置实验室ID: {lab.id}"
                    )
                    return lab.id
        
        return None
