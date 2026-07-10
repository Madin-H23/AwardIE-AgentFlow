import sqlite3
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime

# Import other models for type hinting
from backend.models.competition import CompetitionManager, Competition
from backend.models.student import StudentManager, Student
from backend.models.teacher import TeacherManager, Teacher

logger = logging.getLogger(__name__)

def split_names(names: str) -> List[str]:
    """将名字字符串拆分成列表。支持逗号、顿号、分号"""
    if not names:
        return []
    return re.split(r'[,，、;；]', names)

class Award_info:
    """从奖状中抽取奖状信息。初始化时传入json字符串。"""
    def __init__(self, json_str: str):
        try:
            data = json.loads(json_str)
        except Exception as e:
            logger.error(f"解析Award_info json失败: {e}")
            data = {}
        self.competition_name: Optional[str] = data.get("competition_name")
        track_value = data.get("track")
        # 如果track的值是字符串"None"，转换为空字符串
        if track_value == "None" or (isinstance(track_value, str) and track_value.strip() == "None"):
            self.track: Optional[str] = ""
        else:
            self.track: Optional[str] = track_value
        self.issuer: Optional[str] = data.get("issuer")
        self.province: Optional[str] = data.get("province")
        self.group_name: Optional[str] = data.get("group_name")
        winner_name = data.get("winner_name")
        if winner_name:
            self.winner_name = split_names(winner_name)
        else:
            self.winner_name = []
        supervisor_name = data.get("supervisor_name")
        if supervisor_name:
            self.supervisor_name = split_names(supervisor_name)
        else:
            self.supervisor_name = []
        self.certificate_id: Optional[str] = data.get("certificate_id")
        self.award_level: Optional[str] = data.get("award_level")
        self.competition_level: Optional[str] = data.get("competition_level")
        self.date: Optional[str] = data.get("date")
        self.project_title: Optional[str] = data.get("project_title")
        self.granted_role: Optional[str] = data.get("granted_role")
        related_student: Optional[str] = data.get("related_student")
        if related_student:
            self.related_student = split_names(related_student)
        else:
            self.related_student = []
        self.edition: Optional[int] = data.get("edition")
        self.year: Optional[int] = data.get("year")

    def __str__(self):
        # 设置显示最大字符数，超长换行
        maxlen = 40

        def to_str(val, fieldname=None):
            # 修改winner_name：始终一行输出
            if fieldname == 'winner_name':
                return ', '.join([v for v in val if v]) if isinstance(val, list) else (val or "")
            if isinstance(val, list):
                s = ', '.join([v for v in val if v])
                if len(s) > maxlen:
                    # insert line breaks between names
                    return '\n'.join([x.strip() for x in s.split(',')])
                return s
            elif isinstance(val, str):
                if len(val) > maxlen:
                    # split long strings by Chinese comma or space/逗号
                    return '\n'.join(re.split(r'[，, ]', val))
                return val
            else:
                return str(val) if val is not None else ""
        
        result = []
        fields = [
            ('competition_name', self.competition_name),
            ('track', self.track),
            ('issuer', self.issuer),
            ('province', self.province),
            ('group_name', self.group_name),
            ('winner_name', self.winner_name),
            ('supervisor_name', self.supervisor_name),
            ('certificate_id', self.certificate_id),
            ('award_level', self.award_level),
            ('competition_level', self.competition_level),
            ('date', self.date),
            ('project_title', self.project_title),
            ('granted_role', self.granted_role),
            ('related_student', self.related_student),
            ('edition', self.edition),
            ('year', self.year),
        ]
        for name, value in fields:
            if value and (value != []): # 非空
                vstr = to_str(value, name)
                if vstr.strip():
                    if '\n' in vstr and name != 'winner_name':  # winner_name总在一行
                        result.append(f"{name}:\n  {vstr.replace(chr(10), chr(10)+'  ')}")
                    else:
                        result.append(f"{name}: {vstr}")
        return '\n'.join(result)

@dataclass
class Award:
    # 核心字段
    image_hash: str
    ocr_result: str
    
    # LLM 调试字段
    llm_prompt: Optional[str] = None  # LLM 提示词（用于调试）
    llm_response: Optional[str] = None  # LLM 响应（用于调试）
    
    # 抽取出的详细字段
    competition_name_in_file: Optional[str] = None
    competition_id: Optional[int] = None
    track: Optional[str] = None
    issuer: Optional[str] = None
    province: Optional[str] = None
    group_name: Optional[str] = None
    winner_name: Optional[str] = None
    supervisor_name: Optional[str] = None
    certificate_id: Optional[str] = None
    award_level: Optional[str] = None
    competition_level: Optional[str] = None
    date: Optional[str] = None
    project_title: Optional[str] = None
    granted_role: Optional[str] = None
    related_student_name: Optional[str] = None # corresponds to 'related_student' in JSON (database field name)
    edition: Optional[int] = None
    year: Optional[int] = None
    
    # 系统字段
    id: Optional[int] = None
    match_status: bool = False
    is_abnormal: bool = False  # 异常标记：True表示存在异常，False表示正常
    validation_result: Optional[str] = None  # 检测结果（JSON格式）
    # 注意：title 是动态计算的属性（@property），不是数据字段
    submitter_type: Optional[str] = None  # 新增：提交者类型（student/teacher/admin）
    submitter_id: Optional[int] = None  # 新增：提交者ID
    submit_time: Optional[str] = None  # 新增：提交时间
    laboratory_id: Optional[int] = None  # 新增：关联实验室ID
    
    # 图片文件路径（不存储在数据库，通过 image_hash 计算）
    _images_dir: Optional[Path] = field(default=None, init=False, repr=False)
    
    # 对象关联 (不存入 awards 表，存入关联表)
    competition_obj: Optional[Competition] = field(default=None, init=False)
    # 改名: winners -> student_winners
    student_winners: List[Student] = field(default_factory=list, init=False)
    # 新增: teacher_winners
    teacher_winners: List[Teacher] = field(default_factory=list, init=False)
    
    supervisors: List[Teacher] = field(default_factory=list, init=False)
    related_students: List[Student] = field(default_factory=list, init=False)
    
    def set_images_dir(self, images_dir: Path):
        """设置图片目录路径"""
        self._images_dir = images_dir
    
    @property
    def title(self) -> str:
        """
        动态生成标题：{年份}年{竞赛名称}_{赛道}_{竞赛等级}{获奖等级}{第一位获奖者}
        例如：2024年全国大学生数学建模竞赛_本科组_国家级一等奖张三
        如果赛道为空，则不显示"_{赛道}"部分
        """
        parts = []
        
        # 年份
        if self.year:
            parts.append(f"{self.year}年")
        
        # 竞赛名称
        competition_name = self.competition_name_in_file or ''
        if self.competition_obj:
            competition_name = self.competition_obj.name
        if competition_name:
            parts.append(competition_name)
        
        # 赛道（如果有）
        if self.track:
            parts.append(f"_{self.track}")
        
        # 竞赛等级 + 获奖等级
        level_parts = []
        if parts:  # 如果前面有内容，加下划线分隔
            level_parts.append("_")
        if self.competition_level:
            level_parts.append(self.competition_level)
        if self.award_level:
            level_parts.append(self.award_level)
        if level_parts:
            parts.append(''.join(level_parts))
        
        # 第一位获奖者
        if self.winner_name:
            # 获取第一个获奖者名字（可能有多个，用逗号分隔）
            first_winner = self.winner_name.split(',')[0].split('，')[0].strip()
            if first_winner:
                parts.append(first_winner)
        
        return ''.join(parts) if parts else '获奖'
    
    @property
    def subtitle(self) -> str:
        """
        动态生成副标题：{year}年{竞赛名称}
        """
        subtitle_parts = []
        if self.year:
            subtitle_parts.append(f"{self.year}年")
        
        competition_name = self.competition_name_in_file or ''
        if self.competition_obj:
            competition_name = self.competition_obj.name
        subtitle_parts.append(competition_name)
        
        return ''.join(subtitle_parts) if subtitle_parts else competition_name
    
    def get_image_path(self) -> Optional[Path]:
        """
        获取图片文件路径
        :return: 图片文件路径，如果不存在返回 None
        """
        if not self._images_dir or not self.image_hash:
            return None
        
        # 尝试常见的图片扩展名及 PDF（PDF 时由 award_image 路由返回第一页预览图）
        for ext in [".jpg", ".jpeg", ".png", ".gif", ".pdf"]:
            image_path = self._images_dir / f"{self.image_hash}{ext}"
            if image_path.exists():
                return image_path
        
        return None
    
    def get_image_bytes(self) -> Optional[bytes]:
        """
        读取图片文件内容
        :return: 图片二进制数据，如果文件不存在返回 None
        """
        image_path = self.get_image_path()
        if image_path and image_path.exists():
            try:
                with open(image_path, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"读取图片文件失败 {image_path}: {e}")
        return None
    
    def get_competition_name(self, comp_mgr: CompetitionManager) -> Optional[str]:
        """
        获取竞赛名称（动态查询，不缓存）
        
        Args:
            comp_mgr: 竞赛管理对象
        
        Returns:
            竞赛名称，如果 competition_id 为空或找不到竞赛返回 None
        """
        if not self.competition_id:
            return None
        
        # 从 CompetitionManager 查询（不缓存，每次查询最新值）
        return comp_mgr.get_competition_name_by_id(self.competition_id)

    def __post_init__(self):
        # 处理可能的 JSON 字符串转对象? 不，这里假设传入的是基础类型
        pass

    def _parse_names(self, source: str) -> List[str]:
        """辅助函数：拆分名字字符串"""
        if not source:
            return []
        # 支持逗号、顿号、分号
        parts = re.split(r'[,，、;；]', source)
        return [p.strip() for p in parts if p.strip()]

    def _normalize_name_for_compare(self, s: Optional[str]) -> str:
        """姓名比较前规范化：去除首尾空白、全角空格转半角、合并连续空白"""
        if not s:
            return ''
        s = (s or '').strip()
        s = s.replace('\u3000', ' ')  # 全角空格
        s = re.sub(r'\s+', ' ', s)   # 合并连续空白
        return s.strip()

    def set_teacher_winners_from_ids(self, teacher_ids: List[int], teacher_manager: TeacherManager) -> None:
        """
        从教师ID列表设置 teacher_winners
        
        Args:
            teacher_ids: 教师ID列表
            teacher_manager: 教师管理器
        """
        self.teacher_winners = []
        added_teacher_ids = set()  # 去重
        for teacher_id in teacher_ids:
            if teacher_id:
                try:
                    teacher = teacher_manager.get_teacher_by_id(int(teacher_id))
                    if teacher and teacher.id and teacher.id not in added_teacher_ids:
                        # 确保使用Manager缓存中的对象
                        cached_teacher = teacher_manager.get_teacher_by_id(teacher.id)
                        if cached_teacher:
                            self.teacher_winners.append(cached_teacher)
                            added_teacher_ids.add(cached_teacher.id)
                except (ValueError, TypeError) as e:
                    logger.warning(f"设置教师获奖者失败，无效的教师ID {teacher_id}: {e}")

    def set_teacher_winners_from_names(self, teacher_names: str, teacher_manager: TeacherManager) -> None:
        """
        从教师姓名字符串设置 teacher_winners（通过姓名匹配）
        
        Args:
            teacher_names: 教师姓名字符串，支持逗号、顿号、分号分隔
            teacher_manager: 教师管理器
        """
        self.teacher_winners = []
        if not teacher_names:
            return
        
        names = self._parse_names(teacher_names)
        added_teacher_ids = set()  # 去重
        for name in names:
            matched_teachers = teacher_manager.find_teachers_by_name(name)
            exact_matches = [t for t in matched_teachers if t.name.strip() == name.strip()]
            if len(exact_matches) == 1:
                teacher = exact_matches[0]
                if teacher.id and teacher.id not in added_teacher_ids:
                    # 确保使用Manager缓存中的对象
                    cached_teacher = teacher_manager.get_teacher_by_id(teacher.id)
                    if cached_teacher:
                        self.teacher_winners.append(cached_teacher)
                        added_teacher_ids.add(cached_teacher.id)
            elif len(exact_matches) > 1:
                logger.warning(f"教师姓名 '{name}' 匹配到多个教师，跳过")
            else:
                logger.debug(f"教师姓名 '{name}' 未匹配到教师")

    def set_supervisors_from_ids(self, teacher_ids: List[int], teacher_manager: TeacherManager) -> None:
        """
        从教师ID列表设置 supervisors，并同步 supervisor_name（便于存储与展示）。
        传入空列表时会清空指导教师与导师姓名。
        
        Args:
            teacher_ids: 教师ID列表
            teacher_manager: 教师管理器
        """
        self.supervisors = []
        added_teacher_ids = set()  # 去重
        for teacher_id in teacher_ids:
            if teacher_id:
                try:
                    teacher = teacher_manager.get_teacher_by_id(int(teacher_id))
                    if teacher and teacher.id and teacher.id not in added_teacher_ids:
                        # 确保使用Manager缓存中的对象
                        cached_teacher = teacher_manager.get_teacher_by_id(teacher.id)
                        if cached_teacher:
                            self.supervisors.append(cached_teacher)
                            added_teacher_ids.add(cached_teacher.id)
                except (ValueError, TypeError) as e:
                    logger.warning(f"设置指导教师失败，无效的教师ID {teacher_id}: {e}")
        if self.supervisors:
            self.supervisor_name = ", ".join(t.name for t in self.supervisors if t and t.name)
        else:
            self.supervisor_name = None

    def get_teacher_winner_ids(self) -> List[int]:
        """
        从 teacher_winners 对象列表获取教师ID列表
        
        Returns:
            教师ID列表，如果 teacher_winners 为空则返回空列表
        """
        if not self.teacher_winners:
            return []
        return [t.id for t in self.teacher_winners if t and t.id]

    def get_supervisor_ids(self) -> List[int]:
        """
        从 supervisors 对象列表获取教师ID列表
        
        Returns:
            教师ID列表，如果 supervisors 为空则返回空列表
        """
        if not self.supervisors:
            return []
        return [t.id for t in self.supervisors if t and t.id]

    def is_user_related(self, user_id: int) -> bool:
        """
        判断用户是否与奖状有关联
        
        关联的定义：用户是否出现在以下位置之一：
        - student_winners（学生获奖者）
        - teacher_winners（教师获奖者）
        - supervisors（指导教师）
        
        Args:
            user_id: 用户ID（可能是学生ID或教师ID）
        
        Returns:
            bool: 如果用户与奖状有关联返回 True，否则返回 False
        """
        if not user_id:
            return False
        
        # 检查是否在学生获奖者中
        if self.student_winners:
            for student in self.student_winners:
                if student and student.id == user_id:
                    return True
        
        # 检查是否在教师获奖者中
        if self.teacher_winners:
            for teacher in self.teacher_winners:
                if teacher and teacher.id == user_id:
                    return True
        
        # 检查是否在指导教师中
        if self.supervisors:
            for supervisor in self.supervisors:
                if supervisor and supervisor.id == user_id:
                    return True
        
        return False

    @staticmethod
    def in_name_list(name_string: Optional[str], target_name: Optional[str]) -> bool:
        """
        判断目标名字是否在名字字符串列表中
        :param name_string: 名字字符串，可能包含多个名字，用逗号、顿号、分号分隔
        :param target_name: 要查找的目标名字
        :return: 如果找到返回True，否则返回False
        """
        if not name_string or not target_name:
            return False
        
        name_string = str(name_string).strip()
        target_name = str(target_name).strip()
        
        if not name_string or not target_name:
            return False
        
        # 支持逗号、顿号、分号分隔
        parts = re.split(r'[,，、;；]', name_string)
        for part in parts:
            if part.strip() == target_name:
                return True
        return False

    def refresh_associations(self, 
                             comp_manager: CompetitionManager, 
                             student_manager: StudentManager, 
                             teacher_manager: TeacherManager) -> bool:
        """
        刷新关联：匹配竞赛、教师、学生。
        返回 True 表示所有关联都成功（非空且无歧义），False 表示存在未匹配项。
        """
        all_matched = True
        
        # 1. 匹配竞赛（必须关联一个竞赛）
        if self.competition_name_in_file and self.competition_name_in_file.strip():
            # 先尝试匹配现有竞赛
            self.competition_obj = comp_manager.match_competition(self.competition_name_in_file)
            if self.competition_obj:
                self.competition_id = self.competition_obj.id
            else:
                # 如果找不到，使用 get_competition_id_by_name 自动创建
                try:
                    self.competition_id = comp_manager.get_competition_id_by_name(self.competition_name_in_file)
                    self.competition_obj = comp_manager.get_competition_by_id(self.competition_id)
                    if not self.competition_obj:
                        raise ValueError(f"无法获取竞赛对象，competition_id={self.competition_id}")
                except Exception as e:
                    logger.error(f"无法确定竞赛 '{self.competition_name_in_file}': {e}")
                    raise ValueError(f"无法确定竞赛：{self.competition_name_in_file}")
        else:
            # 如果没有竞赛名称，尝试使用现有的 competition_id
            if self.competition_id:
                self.competition_obj = comp_manager.get_competition_by_id(self.competition_id)
                if not self.competition_obj:
                    raise ValueError(f"无法找到竞赛，competition_id={self.competition_id}")
            else:
                # 既没有竞赛名称，也没有 competition_id，抛出异常
                raise ValueError("无法确定竞赛：competition_name_in_file 和 competition_id 都为空")

        # 2. 匹配获奖者 (winner_name)
        # 注意：如果已经有 teacher_winners 或 student_winners，应该保留，不要清空
        old_teacher_winners = list(self.teacher_winners) if self.teacher_winners else []
        old_student_winners = list(self.student_winners) if self.student_winners else []
        
        winner_names = self._parse_names(self.winner_name)
        
        # 判断角色：如果是教师组，winner_name 匹配教师表
        is_teacher_role = self.granted_role and "教师" in self.granted_role
        
        logger.debug(f"[refresh_associations] 奖状 ID={self.id}: "
                    f"is_teacher_role={is_teacher_role}, "
                    f"winner_name={self.winner_name}, "
                    f"原有teacher_winners数量={len(old_teacher_winners)}, "
                    f"原有student_winners数量={len(old_student_winners)}")
        
        if is_teacher_role:
            # 对于教师奖状，只有在 teacher_winners 为空时才重新匹配
            if not old_teacher_winners:
                logger.info(f"[refresh_associations] ⚠️ 奖状 ID={self.id} 是教师奖状但 teacher_winners 为空，从 winner_name 重新匹配")
                self.teacher_winners = []
                # --- 教师获奖 ---
                # 使用Manager的内存缓存方法，确保返回同一个对象实例
                added_teacher_ids = set()  # 去重
                for name in winner_names:
                    found = teacher_manager.find_teachers_by_name(name)
                    if len(found) == 1:
                        teacher = found[0]
                        # 确保使用Manager缓存中的对象（通过ID重新获取）
                        if teacher.id:
                            cached_teacher = teacher_manager.get_teacher_by_id(teacher.id)
                            if cached_teacher and cached_teacher.id not in added_teacher_ids:
                                self.teacher_winners.append(cached_teacher)
                                added_teacher_ids.add(cached_teacher.id)
                        elif teacher.id not in added_teacher_ids:
                            self.teacher_winners.append(teacher)
                            added_teacher_ids.add(teacher.id)
                    elif len(found) > 1:
                        logger.warning(f"Ambiguous teacher winner '{name}', found {len(found)} matches. Skipping.")
                        all_matched = False
                    else:
                        all_matched = False
            else:
                logger.debug(f"[refresh_associations] ⚠️ 奖状 ID={self.id} 已有 teacher_winners ({len(old_teacher_winners)}个)，保留现有数据，跳过重新匹配")
                # 保留现有的 teacher_winners，不重新匹配
                self.teacher_winners = old_teacher_winners
        else:
            # 对于学生奖状，只有在 student_winners 为空时才重新匹配
            if not old_student_winners:
                self.student_winners = []
                # --- 学生获奖 ---
                # 使用Manager的内存缓存方法，确保返回同一个对象实例
                added_student_ids = set()  # 去重
                for name in winner_names:
                    found = student_manager.find_students_by_name(name)
                    if len(found) == 1:
                        student = found[0]
                        # 确保使用Manager缓存中的对象（通过ID重新获取）
                        if student.id:
                            cached_student = student_manager.get_student_by_id(student.id)
                            if cached_student and cached_student.id not in added_student_ids:
                                self.student_winners.append(cached_student)
                                added_student_ids.add(cached_student.id)
                        elif student.id not in added_student_ids:
                            self.student_winners.append(student)
                            added_student_ids.add(student.id)
                    elif len(found) > 1:
                        logger.warning(f"Ambiguous student winner '{name}', found {len(found)} matches. Skipping.")
                        all_matched = False
                    else:
                        all_matched = False
            else:
                logger.debug(f"[refresh_associations] ⚠️ 奖状 ID={self.id} 已有 student_winners ({len(old_student_winners)}个)，保留现有数据，跳过重新匹配")
                # 保留现有的 student_winners，不重新匹配
                self.student_winners = old_student_winners

        # 3. 匹配指导教师 (supervisor_name)
        # 使用Manager的内存缓存方法，确保返回同一个对象实例
        self.supervisors = []
        supervisor_names = self._parse_names(self.supervisor_name)
        
        # 用于去重，避免同一个教师被添加多次
        added_teacher_ids = set()
        
        for name in supervisor_names:
            found = teacher_manager.find_teachers_by_name(name)
            if len(found) == 1:
                teacher = found[0]
                # 确保使用Manager缓存中的对象（通过ID重新获取）
                if teacher.id:
                    cached_teacher = teacher_manager.get_teacher_by_id(teacher.id)
                    if cached_teacher and cached_teacher.id not in added_teacher_ids:
                        self.supervisors.append(cached_teacher)
                        added_teacher_ids.add(cached_teacher.id)
                elif teacher.id not in added_teacher_ids:
                    self.supervisors.append(teacher)
                    added_teacher_ids.add(teacher.id)
            elif len(found) > 1:
                logger.warning(f"Ambiguous supervisor name '{name}', found {len(found)} matches. Skipping.")
                all_matched = False
            else:
                all_matched = False

        # 4. 匹配相关学生 (related_student)
        # 使用Manager的内存缓存方法，确保返回同一个对象实例
        self.related_students = []
        related_names = self._parse_names(self.related_student_name)
        added_related_student_ids = set()  # 去重
        for name in related_names:
            found = student_manager.find_students_by_name(name)
            if len(found) == 1:
                student = found[0]
                # 确保使用Manager缓存中的对象（通过ID重新获取）
                if student.id:
                    cached_student = student_manager.get_student_by_id(student.id)
                    if cached_student and cached_student.id not in added_related_student_ids:
                        self.related_students.append(cached_student)
                        added_related_student_ids.add(cached_student.id)
                elif student.id not in added_related_student_ids:
                    self.related_students.append(student)
                    added_related_student_ids.add(student.id)
            elif len(found) > 1:
                all_matched = False
            else:
                all_matched = False

        self.match_status = all_matched
        return all_matched

    def update_from_json(self, json_data: Dict[str, Any], 
                         comp_mgr: CompetitionManager, 
                         stu_mgr: StudentManager, 
                         tea_mgr: TeacherManager):
        """更新字段并刷新关联"""
        # 映射 JSON key 到对象属性
        field_map = {
            "competition_name": "competition_name_in_file",
            "track": "track",
            "issuer": "issuer",
            "province": "province",
            "group_name": "group_name",
            "winner_name": "winner_name",
            "supervisor_name": "supervisor_name",
            "certificate_id": "certificate_id",
            "award_level": "award_level",
            "competition_level": "competition_level",
            "date": "date",
            "project_title": "project_title",
            "granted_role": "granted_role",
            "related_student": "related_student_name",
            "edition": "edition",
            "year": "year"
        }
        
        # 检查 competition_name_in_file 是否变化
        competition_name_changed = False
        old_competition_name_in_file = self.competition_name_in_file
        
        changed = False
        for json_key, attr_name in field_map.items():
            if json_key in json_data:
                val = json_data[json_key]
                
                # 特殊处理：year 和 edition 字段需要转换为 int
                if attr_name in ["year", "edition"]:
                    if val is None or val == "":
                        val = None
                    else:
                        try:
                            val = int(val)
                        except (ValueError, TypeError):
                            # 无法转换为 int，设为 None
                            val = None
                else:
                    # 处理列表转逗号分隔字符串
                    if isinstance(val, list):
                        val = ",".join([str(v) for v in val])
                    # 处理字符串：统一分隔符为逗号（仅在 val 是字符串时）
                    if isinstance(val, str):
                        val = val.replace("、", ",").replace("，", ",").replace(";", ",").replace("；", ",").replace("|", ",")
                        # 特殊处理：如果track字段的值是字符串"None"，转换为空字符串
                        if attr_name == "track" and val.strip() == "None":
                            val = ""
                    # 特殊处理：related_student_name 字段，如果新值为空但原值不为空，保留原值
                    # 这样可以避免在提交时因为找不到匹配学生而丢失原始名字
                    if attr_name == "related_student_name":
                        old_val = getattr(self, attr_name, None)
                        if (val == "" or val is None) and old_val and old_val.strip():
                            # 新值为空但原值不为空，保留原值，不更新
                            continue
                    # 如果 val 是 None 或空字符串，转换为 None
                    if val == "" or val is None:
                        val = None
                
                if getattr(self, attr_name) != val:
                    setattr(self, attr_name, val)
                    changed = True
                    
                    # 检查 competition_name_in_file 是否变化
                    if attr_name == "competition_name_in_file":
                        competition_name_changed = True
        
        # 如果 competition_name_in_file 变化，重新查询竞赛信息
        if competition_name_changed and self.competition_name_in_file and self.competition_name_in_file.strip():
            try:
                competition_id = comp_mgr.get_competition_id_by_name(self.competition_name_in_file)
                competition_obj = comp_mgr.get_competition_by_id(competition_id)
                if competition_obj:
                    self.competition_id = competition_id
                else:
                    logger.warning(f"无法获取竞赛对象，competition_id={competition_id}")
            except Exception as e:
                logger.error(f"更新竞赛信息失败: {e}")
                # 如果无法确定竞赛，抛出异常
                raise ValueError(f"无法确定竞赛：{self.competition_name_in_file}")
        
        if changed:
            self.refresh_associations(comp_mgr, stu_mgr, tea_mgr)
            
            # 验证 competition_id 不为 NULL
            if not self.competition_id:
                raise ValueError("更新奖状失败：competition_id 不能为 NULL")
    
    def get_first_winner_info(self):
        """
        获取第一个获奖者的信息
        
        Returns:
            dict: {
                'name': str,  # 姓名（从关联对象或原始字符串获取）
                'obj': Optional[Student|Teacher],  # 关联对象，如果没有则为None
                'obj_type': Optional[str]  # 'student' 或 'teacher'，如果没有则为None
            }
        """
        # 优先从winner_name获取第一个名字（保持原始顺序，即使不在数据库中）
        if self.winner_name:
            winner_names = self._parse_names(self.winner_name)
            if winner_names:
                first_name = winner_names[0].strip()
                if first_name:
                    first_name_norm = self._normalize_name_for_compare(first_name)
                    # 尝试在关联对象中查找匹配的学生或教师（使用规范化比较，避免全角/空格差异）
                    matched_obj = None
                    obj_type = None

                    # 在学生获奖者中查找
                    if self.student_winners:
                        for student in self.student_winners:
                            if student.name and self._normalize_name_for_compare(student.name) == first_name_norm:
                                matched_obj = student
                                obj_type = 'student'
                                break
                    
                    # 如果没找到学生，在教师获奖者中查找
                    if not matched_obj and self.teacher_winners:
                        for teacher in self.teacher_winners:
                            if teacher.name and self._normalize_name_for_compare(teacher.name) == first_name_norm:
                                matched_obj = teacher
                                obj_type = 'teacher'
                                break

                    return {
                        'name': first_name,
                        'obj': matched_obj,
                        'obj_type': obj_type
                    }
        
        # 如果没有winner_name，回退到关联对象（向后兼容）
        if self.student_winners and len(self.student_winners) > 0:
            first_student = self.student_winners[0]
            return {
                'name': first_student.name,
                'obj': first_student,
                'obj_type': 'student'
            }
        elif self.teacher_winners and len(self.teacher_winners) > 0:
            first_teacher = self.teacher_winners[0]
            return {
                'name': first_teacher.name,
                'obj': first_teacher,
                'obj_type': 'teacher'
            }
        
        return {'name': None, 'obj': None, 'obj_type': None}
    
    def get_first_supervisor_info(self):
        """
        获取第一指导教师的信息
        
        Returns:
            dict: {
                'name': str,  # 姓名（从关联对象或原始字符串获取）
                'obj': Optional[Teacher],  # 关联对象，如果没有则为None
                'obj_type': Optional[str]  # 'teacher'，如果没有则为None
            }
        """
        # 优先从关联对象获取（如果已加载）
        if self.supervisors and len(self.supervisors) > 0:
            first_supervisor = self.supervisors[0]
            return {
                'name': first_supervisor.name,
                'obj': first_supervisor,
                'obj_type': 'teacher'
            }
        
        # 如果没有关联对象，从原始字符串获取第一个名字
        if self.supervisor_name:
            supervisor_names = self._parse_names(self.supervisor_name)
            if supervisor_names:
                return {
                    'name': supervisor_names[0],
                    'obj': None,
                    'obj_type': None
                }
        
        return {'name': None, 'obj': None, 'obj_type': None}
    
    def get_team_members_desc(self) -> str:
        """
        获取参赛队伍描述
        
        格式：吴凌森(24机械)、李家鸿(22计科)、陈黎龙(22计科)、许耀辉(23计科)
        对于找不到或因为重名匹配不到的学生，不显示括号和里面的内容
        
        Returns:
            格式化的参赛队伍字符串
        """
        if not self.winner_name:
            return ""
        
        # 解析winner_name字符串，获取姓名列表
        winner_names = self._parse_names(self.winner_name)
        if not winner_names:
            return ""
        
        # 构建结果列表
        result_parts = []
        
        # 按顺序匹配student_winners列表
        # 假设student_winners的顺序与winner_name中的顺序一致
        student_index = 0
        
        for name in winner_names:
            name = name.strip()
            if not name:
                continue
            
            # 尝试在student_winners中找到匹配的学生
            matched_student = None
            
            # 如果还有未匹配的学生，尝试匹配
            if student_index < len(self.student_winners):
                student = self.student_winners[student_index]
                # 检查姓名是否匹配（精确匹配）
                if student.name == name:
                    matched_student = student
                    student_index += 1
            
            # 如果当前索引没有匹配，尝试在整个列表中查找（处理顺序不一致的情况）
            if not matched_student:
                for student in self.student_winners:
                    if student.name == name:
                        # 检查是否已经使用过（避免重复匹配）
                        if student not in [s for s in self.student_winners[:student_index]]:
                            matched_student = student
                            # 更新索引到该学生的位置之后
                            try:
                                student_index = self.student_winners.index(student) + 1
                            except ValueError:
                                student_index += 1
                            break
            
            # 如果找到匹配的学生，使用get_brief_desc()格式化
            if matched_student:
                result_parts.append(matched_student.get_brief_desc())
            else:
                # 找不到或重名匹配不到，只显示姓名
                result_parts.append(name)
        
        return "、".join(result_parts)
    
    def get_team_count(self) -> int:
        """
        获取队伍人数
        
        Returns:
            队伍人数（winner_name中的人数）
        """
        if not self.winner_name:
            return 0
        
        winner_names = self._parse_names(self.winner_name)
        return len(winner_names)
    
    def __str__(self):
        """将奖状的主要内容组合成一行，略去空的域"""
        fields = [
            getattr(self, "competition_name_in_file", None),
            getattr(self, "granted_role", None),
            getattr(self, "competition_level", None),
            getattr(self, "award_level", None),
            getattr(self, "track", None),
            getattr(self, "province", None),
            getattr(self, "group_name", None),
            getattr(self, "winner_name", None),
            getattr(self, "supervisor_name", None),
            getattr(self, "date", None),
            getattr(self, "project_title", None),
            getattr(self, "related_student_name", None),
            getattr(self, "edition", None),
            getattr(self, "year", None),
            getattr(self, "certificate_id", None),
            getattr(self, "issuer", None),
        ]
        # 只包含非空的且转为字符串后不是空字符串的字段
        parts = [str(f) for f in fields if f is not None and str(f).strip() != ""]
        return " | ".join(parts)


@dataclass
class AwardFilter:
    """
    奖状查询过滤器

    用于封装查询条件，支持更灵活的查询方式，并为将来更复杂的搜索需求提供扩展接口。
    """
    # 核心筛选条件（前端实际使用的）
    id: Optional[int] = None                    # 奖状ID（精确匹配）
    competition_id: Optional[int] = None        # 竞赛ID（精确匹配）
    year: Optional[int] = None                  # 年份（精确匹配）
    competition_level: Optional[str] = None     # 竞赛等级（精确匹配：国赛/省赛/校赛）
    award_level: Optional[str] = None           # 获奖等级（精确匹配）
    supervisor_name: Optional[str] = None       # 第一指导教师姓名（精确匹配第一个名字）
    winner_name: Optional[str] = None           # 第一获奖者姓名（精确匹配第一个名字）
    exclude_teacher_certificates: bool = False  # 是否排除教师证书（默认False）
    laboratory_id: Optional[int] = None         # 实验室ID（精确匹配）

    # 查询控制参数
    limit: Optional[int] = None                 # 分页大小
    offset: Optional[int] = None                # 分页偏移
    with_associations: bool = False             # 是否加载关联数据

    def is_empty(self) -> bool:
        """
        检查过滤器是否为空（没有任何筛选条件）

        Returns:
            bool: 如果所有筛选条件都为None或False，返回True
        """
        return (
            self.id is None and
            self.competition_id is None and
            self.year is None and
            self.competition_level is None and
            self.award_level is None and
            self.supervisor_name is None and
            self.winner_name is None and
            self.laboratory_id is None and
            not self.exclude_teacher_certificates
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AwardFilter':
        """
        从字典创建 AwardFilter 对象
        
        Args:
            data: 包含筛选条件的字典
        
        Returns:
            AwardFilter: 创建的过滤器对象
        """
        # 只提取 AwardFilter 支持的字段
        filter_data = {
            'id': data.get('id'),
            'competition_id': data.get('competition_id'),
            'year': data.get('year'),
            'competition_level': data.get('competition_level'),
            'award_level': data.get('award_level'),
            'supervisor_name': data.get('supervisor_name'),
            'winner_name': data.get('winner_name'),
            'exclude_teacher_certificates': data.get('exclude_teacher_certificates', False),
            'limit': data.get('limit'),
            'offset': data.get('offset'),
            'with_associations': data.get('with_associations', False)
        }
        return cls(**filter_data)


class AwardManager:
    def __init__(self, db_path: str, images_dir: Optional[Path] = None):
        self.db_path = db_path
        self.awards: List[Award] = []  # 内存中的奖状列表
        
        # 图片目录（从配置文件获取，不允许硬编码），使用 resolve() 确保绝对路径（部署时工作目录可能不同）
        if images_dir is None:
            from backend.services.unified_file_manager import get_unified_file_manager, FileType
            file_manager = get_unified_file_manager()
            images_dir = file_manager.files_root / FileType.AWARD.directory
        
        self.images_dir = Path(images_dir).resolve()
        # 确保目录存在
        if not self.images_dir.exists():
            self.images_dir.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        self._load_all_from_db()
        
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 主表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS awards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_hash TEXT,
            certificate_id TEXT,
            match_status BOOLEAN,
            ocr_result TEXT,
            llm_prompt TEXT,
            llm_response TEXT,
            
            competition_name_in_file TEXT,
            track TEXT,
            issuer TEXT,
            province TEXT,
            group_name TEXT,
            winner_name TEXT,
            supervisor_name TEXT,
            award_level TEXT,
            competition_level TEXT,
            date TEXT,
            project_title TEXT,
            granted_role TEXT,
            related_student_name TEXT,
            edition INTEGER,
            year INTEGER,
            
            competition_id INTEGER NOT NULL,
            is_abnormal BOOLEAN DEFAULT 0,
            submitter_type TEXT,
            submitter_id INTEGER,
            submit_time TEXT,
            laboratory_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 关联表
        # award_student_winners (原 award_winners，改名更清晰，这里我们新建表，兼容旧表的话需要migration)
        # 为简化，我们使用新表名 award_student_winners
        cursor.execute("CREATE TABLE IF NOT EXISTS award_student_winners (award_id INTEGER, student_id INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS award_teacher_winners (award_id INTEGER, teacher_id INTEGER)")
        
        cursor.execute("CREATE TABLE IF NOT EXISTS award_supervisors (award_id INTEGER, teacher_id INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS award_related_students (award_id INTEGER, student_id INTEGER)")
        
        # 添加索引以提升查询性能（小型系统，简单索引即可）
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_award_student_winners_student ON award_student_winners(student_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_award_teacher_winners_teacher ON award_teacher_winners(teacher_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_award_supervisors_teacher ON award_supervisors(teacher_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_award_related_students_student ON award_related_students(student_id)")
        except sqlite3.OperationalError:
            # 索引可能已存在，忽略错误
            pass
        
        conn.commit()
        conn.close()
    
    def _load_all_from_db(self):
        """从数据库加载所有奖状到内存列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM awards ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        
        # 转换为 Award 对象（关联对象通过 refresh_associations 或 with_associations 加载）
        self.awards = [self._row_to_award(row) for row in rows]
        # 设置图片目录
        for award in self.awards:
            award.set_images_dir(self.images_dir)

    def add_award(self,
                  image_path: str,
                  ocr_text: str,
                  extract_result: Dict[str, Any],
                  image_hash: str,
                  comp_mgr: CompetitionManager,
                  stu_mgr: StudentManager,
                  tea_mgr: TeacherManager,
                  # 新增可选参数：来自 PendingAchievement 的元信息
                  submitter_type: Optional[str] = None,
                  submitter_id: Optional[int] = None,
                  submit_time: Optional[str] = None,
                  laboratory_id: Optional[int] = None,
                  is_abnormal: bool = False,
                  validation_result: Optional[str] = None,
                  llm_prompt: Optional[str] = None,
                  llm_response: Optional[str] = None) -> Tuple[Award, bool]:
        """
        添加奖状。
        
        Args:
            image_path: 图片文件路径
            ocr_text: OCR 识别结果文本
            extract_result: LLM 抽取的结构化数据
            image_hash: 图片哈希值
            comp_mgr: 竞赛管理器
            stu_mgr: 学生管理器
            tea_mgr: 教师管理器
            submitter_type: 提交者类型（student/teacher/admin）
            submitter_id: 提交者ID
            submit_time: 提交时间
            laboratory_id: 关联实验室ID
            is_abnormal: 是否存在异常（验证不通过时为True）
            validation_result: 验证结果（JSON格式字符串）
            llm_prompt: LLM 提示词（用于调试）
            llm_response: LLM 响应（用于调试）
        
        Returns:
            Tuple[Award对象, is_new: bool]
        """
        cert_id = extract_result.get("certificate_id")
        
        # 1. 尝试在内存列表中查找现有奖状
        existing_award = self._find_existing_award_in_memory(image_hash, cert_id)
        
        # 保存图片文件到文件系统
        image_saved = False
        try:
            # 如果 image_hash 为空，从文件计算
            if not image_hash and image_path:
                import hashlib
                try:
                    md5_hash = hashlib.md5()
                    with open(image_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(8192), b''):
                            md5_hash.update(chunk)
                    image_hash = md5_hash.hexdigest()
                    logger.info(f"从文件计算 image_hash: {image_hash}")
                except Exception as e:
                    logger.error(f"计算文件hash失败: {e}")
                    raise ValueError(f"无法计算文件hash，image_hash 为空且计算失败: {e}")

            if not image_hash:
                raise ValueError("image_hash 不能为空")

            # 确定源文件路径 - 支持相对路径
            source_path = Path(image_path)
            # 如果路径不是绝对路径，使用统一文件管理器查找
            if not source_path.is_absolute():
                try:
                    from backend.services.unified_file_manager import get_unified_file_manager
                    file_manager = get_unified_file_manager()
                    # find_file_by_path 会处理相对路径，返回绝对路径
                    source_path = file_manager.find_file_by_path(image_path)
                except Exception as e:
                    logger.error(f"无法通过统一文件管理器查找文件 {image_path}: {e}")
                    raise ValueError(f"无法找到文件: {image_path}")

            # 检查文件是否已经在业务目录中
            if source_path.parent == self.images_dir:
                # 文件已经在业务目录中，跳过复制
                logger.debug(f"文件已在业务目录中，跳过复制: {source_path}")
            else:
                # 确定文件扩展名（含 PDF，award_image 对 PDF 会返回第一页预览图）
                file_ext = source_path.suffix.lower()
                if not file_ext or file_ext not in [".jpg", ".jpeg", ".png", ".gif", ".pdf"]:
                    file_ext = ".jpg"  # 默认使用 .jpg

                target_path = self.images_dir / f"{image_hash}{file_ext}"
                # 如果文件不存在，复制过去
                if not target_path.exists():
                    import shutil
                    shutil.copy2(source_path, target_path)
                    image_saved = True
        except Exception as e:
            logger.warning(f"保存图片文件失败: {e}")

        if existing_award:
            award = existing_award
            # 同一奖状不同照片：删旧文件，避免垃圾
            if existing_award.image_hash != image_hash:
                old_path = existing_award.get_image_path()
                if old_path and old_path.exists():
                    try:
                        old_path.unlink()
                    except Exception as e:
                        logger.warning("奖状删旧文件失败: %s", e)
                award.image_hash = image_hash
            # 更新基础字段
            award.ocr_result = ocr_text
            
            # 确保竞赛信息已设置（如果 competition_name_in_file 变化，需要重新查询）
            competition_name_in_file = extract_result.get("competition_name")
            if competition_name_in_file and competition_name_in_file.strip():
                if not award.competition_id or award.competition_name_in_file != competition_name_in_file:
                    # 重新查询竞赛信息
                    competition_id = comp_mgr.get_competition_id_by_name(competition_name_in_file)
                    competition_obj = comp_mgr.get_competition_by_id(competition_id)
                    if competition_obj:
                        award.competition_id = competition_id
            
            # 使用 update_from_json 更新详细字段并刷新关联
            award.update_from_json(extract_result, comp_mgr, stu_mgr, tea_mgr)

            # 更新元信息（如果提供）
            if validation_result is not None:
                award.validation_result = validation_result
            if is_abnormal is not None:
                award.is_abnormal = is_abnormal
            
            # 验证 competition_id 不为 NULL
            if not award.competition_id:
                raise ValueError(f"更新奖状 ID {award.id} 失败：competition_id 不能为 NULL")
            
            # 同步到数据库
            self._save_award(award)
            return award, False
        else:
            # 创建新奖状
            # 1. 从抽取结果中获取竞赛名称（别名）
            competition_name_in_file = extract_result.get("competition_name")
            if competition_name_in_file is not None and isinstance(competition_name_in_file, str):
                competition_name_in_file = competition_name_in_file.strip() or None
            if not competition_name_in_file:
                competition_name_in_file = None

            # 2. 有竞赛名则查询或创建竞赛；无则使用占位竞赛「待补充」
            if competition_name_in_file:
                competition_id = comp_mgr.get_competition_id_by_name(competition_name_in_file)
            else:
                competition_id = comp_mgr.get_or_create_placeholder_competition_id()
                competition_name_in_file = comp_mgr.PLACEHOLDER_COMPETITION_NAME
                logger.info("competition_name 为空，使用占位竞赛「待补充」入库，后续可在竞赛管理中补充")
            competition_obj = comp_mgr.get_competition_by_id(competition_id)
            
            if not competition_obj:
                raise RuntimeError(f"无法获取竞赛对象，competition_id={competition_id}")

            # 4. 创建 Award 对象，设置竞赛信息（不设置 competition_name，需要时动态查询）
            award = Award(
                image_hash=image_hash,
                ocr_result=ocr_text,
                competition_name_in_file=competition_name_in_file,
                competition_id=competition_id
            )
            # 设置图片目录
            award.set_images_dir(self.images_dir)
            # 填充字段
            award.update_from_json(extract_result, comp_mgr, stu_mgr, tea_mgr)
            
            # 设置来自 PendingAchievement 的元信息
            award.submitter_type = submitter_type
            award.submitter_id = submitter_id
            award.submit_time = submit_time
            award.laboratory_id = laboratory_id
            award.is_abnormal = is_abnormal
            award.validation_result = validation_result
            
            # 验证 competition_id 不为 NULL
            if not award.competition_id:
                raise ValueError("创建奖状失败：competition_id 不能为 NULL")
            
            # 添加到内存列表
            self.awards.append(award)
            
            # 保存到数据库 (Insert)
            self._save_award(award, llm_prompt=llm_prompt, llm_response=llm_response)
            return award, True

    def _find_existing_award_in_memory(self, image_hash: str, cert_id: Optional[str]) -> Optional[Award]:
        """在内存列表中查找现有奖状"""
        # 策略1: Hash 匹配
        for award in self.awards:
            if award.image_hash == image_hash:
                return award
        
        # 策略2: Certificate ID 匹配 (非空)
        if cert_id:
            for award in self.awards:
                if award.certificate_id == cert_id:
                    return award
        
        return None

    def _row_to_award(self, row: sqlite3.Row) -> Award:
        # 将数据库行转换为 Award 对象
        # 注意：这里没有自动加载关联对象，需要外部调用 load_associations 或者 refresh_associations
        
        # 动态构建参数
        data = dict(row)
        # 移除不在 __init__ 中的字段 (timestamps)
        data.pop('created_at', None)
        data.pop('updated_at', None)
        
        # 处理 Boolean
        if 'match_status' in data:
            data['match_status'] = bool(data['match_status']) if data['match_status'] is not None else False
        if 'is_abnormal' in data:
            # 确保正确处理 is_abnormal 字段（可能是 0/1 或 True/False）
            val = data['is_abnormal']
            original_val = val
            if val is None:
                data['is_abnormal'] = False
            elif isinstance(val, bool):
                data['is_abnormal'] = val
            elif isinstance(val, (int, str)):
                data['is_abnormal'] = bool(int(val)) if str(val).isdigit() else False
            else:
                data['is_abnormal'] = False
        else:
            # 如果数据库中没有 is_abnormal 字段，默认为 False
            data['is_abnormal'] = False
        
        # 确保 year、edition 和 laboratory_id 字段是 int 类型（或 None）
        for field in ['year', 'edition', 'laboratory_id', 'submitter_id']:
            if field in data:
                val = data[field]
                if val is None or val == "":
                    data[field] = None
                else:
                    try:
                        data[field] = int(val)
                    except (ValueError, TypeError):
                        # 无法转换为 int，设为 None
                        data[field] = None
        
        # competition_name 不存储在数据库中，也不作为字段（需要时通过 CompetitionManager 查询）
        # 如果数据库中有这个字段（旧数据），移除它
        data.pop('competition_name', None)
        
        # 移除 llm_prompt 和 llm_response 字段（仅用于调试，不加载到内存）
        data.pop('llm_prompt', None)
        data.pop('llm_response', None)

        # 移除 extract_json 字段（仅用于调试，不加载到内存）
        data.pop('extract_json', None)
        
        # 检查 competition_id 是否为 NULL（应该不会发生，但记录警告）
        if 'competition_id' in data and data['competition_id'] is None:
            logger.warning(f"从数据库加载的奖状 competition_id 为 NULL，row id: {data.get('id', 'unknown')}")
        
        award = Award(**data)
        
        # 设置图片目录（如果 AwardManager 已初始化）
        if hasattr(self, 'images_dir'):
            award.set_images_dir(self.images_dir)
        return award

    def _save_award(self, award: Award, llm_prompt: Optional[str] = None, llm_response: Optional[str] = None):
        """
        保存奖状到数据库
        
        Args:
            award: Award 对象
            llm_prompt: LLM 提示词（可选，用于调试）
            llm_response: LLM 响应（可选，用于调试）
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            try:
                # 验证 competition_id 不为 NULL
                if not award.competition_id:
                    raise ValueError(f"无法保存奖状 ID {award.id}：competition_id 不能为 NULL")
                
                # 字段映射（移除 image_blob，不保存 competition_name，因为它从 competitions 表动态查询）
                # 包含所有需要保存的字段：核心字段 + 抽取字段 + 元信息字段 + LLM 调试字段
                fields = [
                    # 核心字段
                    "image_hash", "certificate_id", "match_status", "is_abnormal", "validation_result", "ocr_result",
                    # 抽取出的详细字段
                    "competition_name_in_file", "track", "issuer", "province", "group_name",
                    "winner_name", "supervisor_name", "award_level", "competition_level",
                    "date", "project_title", "granted_role", "related_student_name", "edition", "year",
                    # 系统字段
                    "competition_id",
                    # 元信息字段（来自 PendingAchievement）
                    "submitter_type", "submitter_id", "submit_time", "laboratory_id",
                ]
                
                values = [getattr(award, f) for f in fields]
                
                # 添加 LLM 调试字段（这些不是 Award 对象的属性，而是直接传入的参数）
                fields.extend(["llm_prompt", "llm_response"])
                values.extend([llm_prompt, llm_response])
                
                if award.id:
                    # Update
                    set_clause = ", ".join([f"{f} = ?" for f in fields])
                    sql = f"UPDATE awards SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                    cursor.execute(sql, values + [award.id])
                else:
                    # Insert
                    placeholders = ", ".join(["?" for _ in fields])
                    cols = ", ".join(fields)
                    sql = f"INSERT INTO awards ({cols}) VALUES ({placeholders})"
                    cursor.execute(sql, values)
                    award.id = cursor.lastrowid
                    
                # 更新关联表
                # 先删除旧关联
                
                cursor.execute("DELETE FROM award_student_winners WHERE award_id = ?", (award.id,))
                cursor.execute("DELETE FROM award_teacher_winners WHERE award_id = ?", (award.id,))
                cursor.execute("DELETE FROM award_supervisors WHERE award_id = ?", (award.id,))
                cursor.execute("DELETE FROM award_related_students WHERE award_id = ?", (award.id,))
                
                # 插入新关联（去重处理）
                if award.student_winners:
                    unique_students = []
                    seen_student_ids = set()
                    for s in award.student_winners:
                        if s.id and s.id not in seen_student_ids:
                            unique_students.append(s)
                            seen_student_ids.add(s.id)
                    if unique_students:
                        cursor.executemany("INSERT INTO award_student_winners (award_id, student_id) VALUES (?, ?)", 
                                        [(award.id, s.id) for s in unique_students])
                                    
                if award.teacher_winners:
                    unique_teachers = []
                    seen_teacher_ids = set()
                    for t in award.teacher_winners:
                        if t.id and t.id not in seen_teacher_ids:
                            unique_teachers.append(t)
                            seen_teacher_ids.add(t.id)
                    if unique_teachers:
                        cursor.executemany("INSERT INTO award_teacher_winners (award_id, teacher_id) VALUES (?, ?)", 
                                        [(award.id, t.id) for t in unique_teachers])
                
                if award.supervisors:
                    # 去重：确保每个 teacher.id 只出现一次
                    unique_supervisors = []
                    seen_teacher_ids = set()
                    for t in award.supervisors:
                        if t.id and t.id not in seen_teacher_ids:
                            unique_supervisors.append(t)
                            seen_teacher_ids.add(t.id)

                   
                    if unique_supervisors:
                        cursor.executemany("INSERT INTO award_supervisors (award_id, teacher_id) VALUES (?, ?)",
                                        [(award.id, t.id) for t in unique_supervisors])
                                    
                if award.related_students:
                    unique_related_students = []
                    seen_student_ids = set()
                    for s in award.related_students:
                        if s.id and s.id not in seen_student_ids:
                            unique_related_students.append(s)
                            seen_student_ids.add(s.id)
                    if unique_related_students:
                        cursor.executemany("INSERT INTO award_related_students (award_id, student_id) VALUES (?, ?)", 
                                        [(award.id, s.id) for s in unique_related_students])
                
                # 更新内存缓存中对应奖状对象的字段（特别是is_abnormal字段）
                if award.id:
                    self._update_cache_award(award.id, {
                        'is_abnormal': award.is_abnormal,
                        'validation_result': award.validation_result,
                        'competition_id': award.competition_id,
                        'award_level': award.award_level,
                        'competition_level': award.competition_level,
                        'year': award.year,
                        'track': award.track,
                        'certificate_id': award.certificate_id,
                        'project_title': award.project_title,
                        'date': award.date,
                        'province': award.province,
                        'issuer': award.issuer,
                        'winner_name': award.winner_name,
                        'supervisor_name': award.supervisor_name,
                        'related_student_name': award.related_student_name,
                        'granted_role': award.granted_role,
                        'match_status': award.match_status,
                        'laboratory_id': award.laboratory_id,
                    })
            except Exception as e:
                logger.error(f"Failed to save award: {e}")
    
    def _update_cache_award(self, award_id: int, updates: dict):
        """
        更新内存缓存中指定奖状对象的字段
        
        Args:
            award_id: 奖状ID
            updates: 要更新的字段字典
        """
        found = False
        for cached_award in self.awards:
            if cached_award.id == award_id:
                found = True
                for key, value in updates.items():
                    if hasattr(cached_award, key):
                        setattr(cached_award, key, value)
                break

    def update_validation_status(self, award_id: int, is_abnormal: bool, validation_result: Optional[str] = None):
        """
        更新奖状的验证状态（is_abnormal 和 validation_result）。
        
        同时更新数据库和内存缓存，确保数据一致性。
        
        Args:
            award_id: 奖状ID
            is_abnormal: 是否异常
            validation_result: 验证结果（JSON字符串），如果为None则清空
        """
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE awards SET is_abnormal = ?, validation_result = ? WHERE id = ?',
                (1 if is_abnormal else 0, validation_result, award_id)
            )
            conn.commit()
        
        # 更新内存缓存中的所有相关实例
        self._update_cache_award(award_id, {
            'is_abnormal': is_abnormal,
            'validation_result': validation_result
        })

    def refresh_abnormal_awards_status(self,
                                       student_manager: StudentManager,
                                       teacher_manager: TeacherManager,
                                       comp_mgr: CompetitionManager) -> int:
        """
        对所有异常奖状重新验证，对通过验证的清除异常标记。

        Args:
            student_manager: 学生管理器（用于加载关联）
            teacher_manager: 教师管理器（用于加载关联）
            comp_mgr: 竞赛管理器（用于加载关联）

        Returns:
            清除异常标记的奖状数量
        """
        abnormal_awards = self.query_awards(
            is_abnormal=True,
            with_associations=True,
            student_manager=student_manager,
            teacher_manager=teacher_manager,
            comp_mgr=comp_mgr
        )
        if not abnormal_awards:
            return 0

        from backend.extract.validation import AwardValidator
        validator = AwardValidator()
        cleared_count = 0
        for award in abnormal_awards:
            try:
                validation_result = validator.validate_for_db_object(award)
                if validation_result.is_valid:
                    self.update_validation_status(
                        award.id,
                        is_abnormal=False,
                        validation_result=None
                    )
                    cleared_count += 1
            except Exception as e:
                logger.warning(f"奖状 {award.id} 重新检测失败: {e}")

        if abnormal_awards:
            logger.info(
                f"刷新异常奖状状态: 共 {len(abnormal_awards)} 个异常奖状，"
                f"其中 {cleared_count} 个已通过验证并清除异常标记"
            )
        return cleared_count

    def get_award_by_id(self, award_id: int) -> Optional[Award]:
        """从内存列表中获取奖状"""
        for award in self.awards:
            if award.id == award_id:
                return award
        return None

    def query_awards(self,
                     filter_obj: Optional[AwardFilter] = None,
                     # 直接参数方式（向后兼容，推荐使用 filter_obj）
                     id: Optional[int] = None,
                     competition_id: Optional[int] = None,
                     competition_level: Optional[str] = None,
                     supervisor_name: Optional[str] = None,
                     winner_name: Optional[str] = None,
                     award_level: Optional[str] = None,
                     year: Optional[int] = None,
                     exclude_teacher_certificates: bool = False,
                     is_abnormal: Optional[bool] = None,
                     track: Optional[str] = None,
                     laboratory_id: Optional[int] = None,
                     filter_no_laboratory: bool = False,
                     limit: Optional[int] = None,
                     offset: Optional[int] = None,
                     with_associations: bool = False,
                     student_manager: Optional[StudentManager] = None,
                     teacher_manager: Optional[TeacherManager] = None,
                     comp_mgr: Optional[CompetitionManager] = None,
                     # 兼容旧参数名（已废弃，保留以兼容旧代码）
                     competition_name: Optional[str] = None,
                     student_name: Optional[str] = None,
                     teacher_name: Optional[str] = None,
                     granted_role: Optional[str] = None,
                     search: Optional[str] = None,
                     stu_mgr: Optional[StudentManager] = None,
                     tea_mgr: Optional[TeacherManager] = None) -> List[Award]:
        """
        多条件查询奖状（从内存列表查询）。
        
        支持两种调用方式：
        1. 使用 AwardFilter 对象（推荐，更清晰，便于扩展）
        2. 使用直接参数（向后兼容）
        
        Args:
            filter_obj: AwardFilter 对象（推荐使用）
            
            # 直接参数方式（向后兼容）
            id: 奖状ID（精确匹配）
            competition_id: 竞赛ID（精确匹配）
            competition_level: 竞赛等级（精确匹配：国赛/省赛/校赛）
            supervisor_name: 第一指导教师姓名（精确匹配第一个名字）
            winner_name: 第一获奖者姓名（精确匹配第一个名字）
            award_level: 获奖等级（精确匹配）
            year: 年份（精确匹配）
            exclude_teacher_certificates: 是否排除教师证书（默认False）
            limit: 返回结果数量限制
            offset: 返回结果偏移量
            with_associations: 是否预加载关联数据
            student_manager: 学生管理器（当 with_associations=True 时需要）
            teacher_manager: 教师管理器（当 with_associations=True 时需要）
            comp_mgr: 竞赛管理器（当 with_associations=True 时需要）
            
            # 兼容旧参数名（已废弃，不再使用）
            competition_name: 已废弃，使用 competition_id
            student_name: 已废弃，使用 winner_name
            teacher_name: 已废弃，使用 supervisor_name
            granted_role: 已废弃，使用 exclude_teacher_certificates
            search: 已废弃
            stu_mgr, tea_mgr: 已废弃，使用 student_manager, teacher_manager
        
        Returns:
            List[Award]: 符合条件的奖状列表
        """
        # 如果提供了 filter_obj，从 filter_obj 获取参数
        if filter_obj is not None:
            id = filter_obj.id
            competition_id = filter_obj.competition_id
            competition_level = filter_obj.competition_level
            supervisor_name = filter_obj.supervisor_name
            winner_name = filter_obj.winner_name
            award_level = filter_obj.award_level
            year = filter_obj.year
            exclude_teacher_certificates = filter_obj.exclude_teacher_certificates
            laboratory_id = filter_obj.laboratory_id
            is_abnormal = getattr(filter_obj, 'is_abnormal', None)
            filter_no_laboratory = getattr(filter_obj, 'filter_no_laboratory', False)
            limit = filter_obj.limit
            offset = filter_obj.offset
            with_associations = filter_obj.with_associations
        
        # 兼容旧的参数名（已废弃，但保留兼容性）
        if student_manager is None:
            student_manager = stu_mgr
        if teacher_manager is None:
            teacher_manager = tea_mgr
        
        # 处理 granted_role 参数
        # granted_role 用于筛选特定角色的证书
        # - '学生': 只显示学生证书（排除教师证书）
        # - '教师': 只显示教师证书
        # - None 或其他值: 显示全部
        filter_by_granted_role = None
        if granted_role:
            if granted_role == '学生':
                exclude_teacher_certificates = True
                filter_by_granted_role = '学生'
            elif granted_role == '教师':
                filter_by_granted_role = '教师'
        
        # 从内存列表过滤
        results = list(self.awards)
        
        # ID匹配（最高优先级）
        if id is not None:
            results = [a for a in results if a.id == id]
            if not results:
                return []
        
        # 竞赛ID匹配（如果为None则不限制）
        if competition_id is not None:
            results = [a for a in results if a.competition_id == competition_id]
        
        # 竞赛等级匹配
        if competition_level:
            results = [a for a in results if a.competition_level == competition_level]
        
        # 兼容旧的 competition_name 参数（已废弃，但保留兼容性）
        if competition_name:
            results = [a for a in results if a.competition_name_in_file and competition_name in a.competition_name_in_file]
        
        # 兼容旧的 student_name 参数（已废弃，但保留兼容性）
        if student_name:
            results = [a for a in results if 
                      (a.winner_name and Award.in_name_list(a.winner_name, student_name)) or 
                      (a.related_student_name and Award.in_name_list(a.related_student_name, student_name))]
        
        # 兼容旧的 teacher_name 参数（已废弃，但保留兼容性）
        if teacher_name:
            results = [a for a in results if 
                      (a.supervisor_name and Award.in_name_list(a.supervisor_name, teacher_name)) or 
                      (a.winner_name and Award.in_name_list(a.winner_name, teacher_name) and a.granted_role and "教师" in a.granted_role)]
        
        # 第一指导教师筛选（精确匹配第一个名字）
        if supervisor_name:
            def match_first_supervisor(award):
                if not award.supervisor_name:
                    return False
                supervisor_names = award._parse_names(award.supervisor_name)
                return supervisor_names and supervisor_names[0] == supervisor_name
            results = [a for a in results if match_first_supervisor(a)]
        
        # 第一获奖者筛选（精确匹配第一个名字）
        if winner_name:
            def match_first_winner(award):
                if not award.winner_name:
                    return False
                winner_names = award._parse_names(award.winner_name)
                return winner_names and winner_names[0] == winner_name
            results = [a for a in results if match_first_winner(a)]
        
        if award_level:
            results = [a for a in results if a.award_level == award_level]
        
        if year:
            results = [a for a in results if a.year == year]

        # 赛道筛选（精确匹配）
        if track and str(track).strip():
            track_val = str(track).strip()
            results = [a for a in results if (a.track or '').strip() == track_val]

        # 实验室筛选
        if laboratory_id is not None:
            results = [a for a in results if a.laboratory_id == laboratory_id]

        # 筛选无实验室的奖状
        if filter_no_laboratory:
            results = [a for a in results if a.laboratory_id is None]

        # 排除教师证书
        if exclude_teacher_certificates:
            results = [a for a in results if not a.granted_role or "教师" not in a.granted_role]
        
        # 按角色筛选证书（只显示特定角色的证书）
        if filter_by_granted_role == '教师':
            results = [a for a in results if a.granted_role and "教师" in a.granted_role]
        elif filter_by_granted_role == '学生':
            # 学生证书：granted_role为空或包含"学生"
            results = [a for a in results if not a.granted_role or "学生" in a.granted_role or "教师" not in a.granted_role]
        
        # 异常标记筛选
        if is_abnormal is not None:
            # 确保正确比较布尔值
            filtered_results = []
            for a in results:
                # 确保 is_abnormal 是布尔值
                award_is_abnormal = bool(a.is_abnormal) if a.is_abnormal is not None else False
                if award_is_abnormal == bool(is_abnormal):
                    filtered_results.append(a)
            results = filtered_results
        
        # 兼容旧的 search 参数（已废弃，但保留兼容性）
        if search:
            search_lower = search.lower()
            def matches_search(award):
                searchable_fields = [
                    award.competition_name_in_file or "",
                    award.winner_name or "",
                    award.supervisor_name or "",
                    award.award_level or "",
                    award.competition_level or "",
                    award.track or "",
                    award.certificate_id or ""
                ]
                return any(search_lower in str(field).lower() for field in searchable_fields)
            results = [a for a in results if matches_search(a)]
        
        # 按 ID 降序排列
        results.sort(key=lambda x: x.id or 0, reverse=True)
        
        # 分页处理
        if offset is not None:
            results = results[offset:]
        if limit is not None:
            results = results[:limit]
        
        # 如果需要关联数据，加载关联
        if with_associations and results and student_manager and teacher_manager and comp_mgr:
            self._eager_load_associations(results, student_manager, teacher_manager, comp_mgr)
        
        return results
    
    def query_awards_with_filter(self,
                                 filter_obj: AwardFilter,
                                 student_manager: Optional[StudentManager] = None,
                                 teacher_manager: Optional[TeacherManager] = None,
                                 comp_mgr: Optional[CompetitionManager] = None) -> List[Award]:
        """
        使用 AwardFilter 对象查询奖状（推荐使用的新接口）
        
        这个方法是专门为使用 AwardFilter 对象设计的接口，代码更清晰，便于扩展。
        将来如果需要更复杂的查询逻辑（如范围查询、多值查询等），可以在 AwardFilter 中添加字段，
        而不需要修改方法签名。
        
        Args:
            filter_obj: AwardFilter 对象，包含所有筛选条件
            student_manager: 学生管理器（当 filter_obj.with_associations=True 时需要）
            teacher_manager: 教师管理器（当 filter_obj.with_associations=True 时需要）
            comp_mgr: 竞赛管理器（当 filter_obj.with_associations=True 时需要）
        
        Returns:
            List[Award]: 符合条件的奖状列表
        
        Example:
            ```python
            filter_obj = AwardFilter(
                competition_id=1,
                year=2023,
                exclude_teacher_certificates=True,
                limit=20,
                offset=0,
                with_associations=True
            )
            awards = award_manager.query_awards_with_filter(
                filter_obj,
                student_manager=student_manager,
                teacher_manager=teacher_manager,
                comp_mgr=competition_manager
            )
            ```
        """
        return self.query_awards(
            filter_obj=filter_obj,
            student_manager=student_manager,
            teacher_manager=teacher_manager,
            comp_mgr=comp_mgr
        )

    def _eager_load_associations(self, awards: List[Award], 
                                 student_manager: StudentManager, 
                                 teacher_manager: TeacherManager,
                                 comp_mgr: CompetitionManager):
        """
        批量预加载关联数据
        注意：使用Manager的内存缓存方法，确保返回的是同一个对象实例
        """
        award_ids = [a.id for a in awards if a.id]
        if not award_ids: return

        award_map = {a.id: a for a in awards}
        placeholders = ",".join("?" for _ in award_ids)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Competitions (不需要批量查中间表，直接查 CompetitionManager)
        # 这里优化点：收集所有 comp_id 一次性查询，或者 CompetitionManager 有缓存
        for award in awards:
            if award.competition_id:
                # 使用Manager的内存缓存方法
                award.competition_obj = comp_mgr.get_competition_by_id(award.competition_id)

        # 2. Student Winners - 使用Manager的内存缓存方法，按照 winner_name 的顺序加载
        cursor.execute(f"SELECT DISTINCT award_id, student_id FROM award_student_winners WHERE award_id IN ({placeholders})", award_ids)
        # 先收集所有关联关系：{award_id: [student_id, ...]}
        students_by_award = {}  # {award_id: [student_id, ...]}
        for aid, sid in cursor.fetchall():
            if aid not in students_by_award:
                students_by_award[aid] = []
            students_by_award[aid].append(sid)
        
        # 按照 winner_name 的顺序加载 student_winners
        students_added = {}

        for aid, student_ids in students_by_award.items():
            if aid not in award_map:
                continue
            award_obj = award_map[aid]
            award_obj.student_winners = []  # 清空列表
            if aid not in students_added:
                students_added[aid] = set()
            added_student_ids = set()  # 去重
            
            # 如果有 winner_name，按照其顺序匹配（使用规范化比较，避免全角/空格差异）
            if award_obj.winner_name:
                winner_names = award_obj._parse_names(award_obj.winner_name)
                for name in winner_names:
                    name = name.strip()
                    if not name:
                        continue
                    name_norm = award_obj._normalize_name_for_compare(name)
                    # 在 student_ids 中查找匹配的学生
                    for sid in student_ids:
                        if sid in added_student_ids:
                            continue
                        student = student_manager.get_student_by_id(sid)
                        if student and student.name and award_obj._normalize_name_for_compare(student.name) == name_norm:
                            award_obj.student_winners.append(student)
                            added_student_ids.add(sid)
                            students_added[aid].add(sid)
                            break
            
            # 添加剩余未匹配的学生（按 student_ids 顺序）
            for sid in student_ids:
                if sid not in added_student_ids:
                    student = student_manager.get_student_by_id(sid)
                    if student:
                        award_obj.student_winners.append(student)
                        added_student_ids.add(sid)
                        students_added[aid].add(sid)

        # 对于学生奖状，如果从数据库加载的 student_winners 为空，尝试从 winner_name 重新匹配
        for award in awards:
            if award.id and award.id in award_map:
                award_obj = award_map[award.id]
                # 检查是否是学生奖状（不是教师奖状）
                is_teacher_role = award_obj.granted_role and "教师" in award_obj.granted_role
                # 如果 student_winners 为空，但 winner_name 不为空，尝试重新匹配
                if not is_teacher_role and not award_obj.student_winners and award_obj.winner_name:
                    winner_names = award_obj._parse_names(award_obj.winner_name)
                    for name in winner_names:
                        name = name.strip()
                        if not name:
                            continue
                        found = student_manager.find_students_by_name(name)
                        if len(found) == 1:
                            student = found[0]
                            if student.id:
                                cached_student = student_manager.get_student_by_id(student.id)
                                if cached_student:
                                    if award_obj.id not in students_added:
                                        students_added[award_obj.id] = set()
                                    if cached_student.id not in students_added[award_obj.id]:
                                        award_obj.student_winners.append(cached_student)
                                        students_added[award_obj.id].add(cached_student.id)
                                        logger.info(f"[_eager_load_associations] ⚠️ 奖状 ID={award_obj.id} 从 winner_name 重新匹配到学生: student_id={cached_student.id}, name={cached_student.name}")
                                        # 保存到数据库
                                        try:
                                            with sqlite3.connect(self.db_path) as save_conn:
                                                save_cursor = save_conn.cursor()
                                                save_cursor.execute("INSERT OR IGNORE INTO award_student_winners (award_id, student_id) VALUES (?, ?)", 
                                                                  (award_obj.id, cached_student.id))
                                                save_conn.commit()
                                                logger.info(f"[_eager_load_associations] ⚠️ 奖状 ID={award_obj.id} 的学生关联已保存到数据库")
                                        except Exception as e:
                                            logger.error(f"[_eager_load_associations] ⚠️ 保存奖状 ID={award_obj.id} 的学生关联到数据库失败: {e}")
                                        break
                        elif len(found) > 1:
                            logger.warning(f"[_eager_load_associations] ⚠️ 奖状 ID={award_obj.id} 的 winner_name '{name}' 匹配到多个学生，跳过")
                        else:
                            logger.debug(f"[_eager_load_associations] ⚠️ 奖状 ID={award_obj.id} 的 winner_name '{name}' 未匹配到学生")

        # 3. Teacher Winners - 使用Manager的内存缓存方法
        cursor.execute(f"SELECT DISTINCT award_id, teacher_id FROM award_teacher_winners WHERE award_id IN ({placeholders})", award_ids)
        db_teacher_winners = cursor.fetchall()
        logger.debug(f"[_eager_load_associations] 从数据库加载 teacher_winners: 找到 {len(db_teacher_winners)} 条关联记录")
        
        # 特别关注 ID 129
        award_129_teachers = [(aid, tid) for aid, tid in db_teacher_winners if aid == 129]
        if award_129_teachers:
            logger.info(f"[_eager_load_associations] ⚠️ 奖状 ID=129 在数据库中有 {len(award_129_teachers)} 个教师关联: {award_129_teachers}")
        
        teachers_added = {}
        for aid, tid in db_teacher_winners:
            if aid in award_map:
                if aid not in teachers_added:
                    teachers_added[aid] = set()
                    award_map[aid].teacher_winners = []  # 清空列表避免重复
                if tid not in teachers_added[aid]:
                    # 使用Manager的内存缓存方法，确保返回同一个对象实例
                    teacher = teacher_manager.get_teacher_by_id(tid)
                    if teacher:
                        award_map[aid].teacher_winners.append(teacher)
                        teachers_added[aid].add(tid)
                        # 特别关注 ID 129
                        if aid == 129:
                            logger.info(f"[_eager_load_associations] ⚠️ 奖状 ID=129 成功加载教师: teacher_id={tid}, name={teacher.name}, employee_id={teacher.employee_id}")
                    else:
                        logger.warning(f"[_eager_load_associations] ⚠️ 奖状 ID={aid} 的教师ID {tid} 未找到教师对象！")
                        # 特别关注 ID 129
                        if aid == 129:
                            logger.error(f"[_eager_load_associations] ⚠️ 奖状 ID=129 的教师ID {tid} 未找到教师对象！这可能导致 teacher_winners 为空")
        
        # 对于教师奖状：按 winner_name 顺序重建 teacher_winners，并补齐缺失的教师关联
        # 这样可解决：1) DB 无关联时从 winner_name 匹配并保存 2) DB 有关联但顺序/错误时按姓名重排并补缺
        for award in awards:
            if award.id and award.id not in award_map:
                continue
            award_obj = award_map[award.id]
            is_teacher_role = award_obj.granted_role and "教师" in award_obj.granted_role
            if not is_teacher_role or not award_obj.winner_name:
                continue
            winner_names = award_obj._parse_names(award_obj.winner_name)
            if not winner_names:
                continue
            current_teachers = list(award_obj.teacher_winners) if award_obj.teacher_winners else []
            new_teacher_winners = []
            for name in winner_names:
                name = name.strip()
                if not name:
                    continue
                name_norm = award_obj._normalize_name_for_compare(name)
                matched = None
                for t in current_teachers:
                    if t and getattr(t, 'name', None) and award_obj._normalize_name_for_compare(t.name) == name_norm:
                        matched = t
                        break
                if matched:
                    new_teacher_winners.append(matched)
                    continue
                found = teacher_manager.find_teachers_by_name(name)
                if len(found) == 1 and found[0].id:
                    cached = teacher_manager.get_teacher_by_id(found[0].id)
                    if cached:
                        new_teacher_winners.append(cached)
                        try:
                            with sqlite3.connect(self.db_path) as save_conn:
                                save_cursor = save_conn.cursor()
                                save_cursor.execute(
                                    "INSERT OR IGNORE INTO award_teacher_winners (award_id, teacher_id) VALUES (?, ?)",
                                    (award_obj.id, cached.id)
                                )
                                save_conn.commit()
                                logger.info(f"[_eager_load_associations] 奖状 ID={award_obj.id} 从 winner_name 补齐教师关联: teacher_id={cached.id}, name={cached.name}")
                        except Exception as e:
                            logger.error(f"[_eager_load_associations] 保存奖状 ID={award_obj.id} 的教师关联失败: {e}")
                elif len(found) > 1:
                    logger.warning(f"[_eager_load_associations] 奖状 ID={award_obj.id} 的 winner_name '{name}' 匹配到多个教师，跳过")
            award_obj.teacher_winners = new_teacher_winners

        # 4. Supervisors - 使用Manager的内存缓存方法，按照 supervisor_name 的顺序加载
        cursor.execute(f"SELECT DISTINCT award_id, teacher_id FROM award_supervisors WHERE award_id IN ({placeholders})", award_ids)
        # 先收集所有关联关系：{award_id: [teacher_id, ...]}
        supervisors_by_award = {}  # {award_id: [teacher_id, ...]}
        for aid, tid in cursor.fetchall():
            if aid not in supervisors_by_award:
                supervisors_by_award[aid] = []
            supervisors_by_award[aid].append(tid)
        
        # 按照 supervisor_name 的顺序加载 supervisors
        for aid, teacher_ids in supervisors_by_award.items():
            if aid not in award_map:
                continue
            award_obj = award_map[aid]
            award_obj.supervisors = []  # 清空列表
            added_teacher_ids = set()  # 去重
            
            # 如果有 supervisor_name，按照其顺序匹配
            if award_obj.supervisor_name:
                supervisor_names = award_obj._parse_names(award_obj.supervisor_name)
                for name in supervisor_names:
                    name = name.strip()
                    if not name:
                        continue
                    # 在 teacher_ids 中查找匹配的教师
                    for tid in teacher_ids:
                        if tid in added_teacher_ids:
                            continue
                        teacher = teacher_manager.get_teacher_by_id(tid)
                        if teacher and teacher.name.strip() == name:
                            award_obj.supervisors.append(teacher)
                            added_teacher_ids.add(tid)
                            break
            
            # 添加剩余未匹配的教师（按 teacher_ids 顺序）
            for tid in teacher_ids:
                if tid not in added_teacher_ids:
                    teacher = teacher_manager.get_teacher_by_id(tid)
                    if teacher:
                        award_obj.supervisors.append(teacher)
                        added_teacher_ids.add(tid)

        # 5. Related Students - 使用Manager的内存缓存方法
        cursor.execute(f"SELECT DISTINCT award_id, student_id FROM award_related_students WHERE award_id IN ({placeholders})", award_ids)
        related_students_added = {}
        for aid, sid in cursor.fetchall():
            if aid in award_map:
                if aid not in related_students_added:
                    related_students_added[aid] = set()
                    award_map[aid].related_students = []  # 清空列表避免重复
                if sid not in related_students_added[aid]:
                    # 使用Manager的内存缓存方法，确保返回同一个对象实例
                    student = student_manager.get_student_by_id(sid)
                    if student:
                        award_map[aid].related_students.append(student)
                        related_students_added[aid].add(sid)
                
        conn.close()

    def delete_award(self, award_id: int) -> bool:
        """删除奖状及关联（先从内存列表删除，然后同步到数据库）"""
        # 确保 award_id 是整数类型
        award_id = int(award_id)
        
        # 从内存列表查找并删除
        award_to_delete = None
        for award in self.awards:
            if award.id == award_id:
                award_to_delete = award
                break
        
        if not award_to_delete:
            logger.warning(f"Award ID {award_id} not found in memory for deletion (内存中共有 {len(self.awards)} 个奖状)")
            # 即使内存中没有，也尝试从数据库删除（可能内存和数据库不同步）
            logger.info(f"内存中未找到，尝试直接从数据库删除 ID {award_id}")
        
        # 如果内存中有，先从内存列表移除
        if award_to_delete:
            self.awards.remove(award_to_delete)
        
        # 同步到数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 1. Delete associations
            cursor.execute("DELETE FROM award_student_winners WHERE award_id = ?", (award_id,))
            deleted_students = cursor.rowcount
            cursor.execute("DELETE FROM award_teacher_winners WHERE award_id = ?", (award_id,))
            deleted_teachers = cursor.rowcount
            cursor.execute("DELETE FROM award_supervisors WHERE award_id = ?", (award_id,))
            deleted_supervisors = cursor.rowcount
            cursor.execute("DELETE FROM award_related_students WHERE award_id = ?", (award_id,))
            deleted_related = cursor.rowcount
            
            # 2. Delete award（使用显式的类型转换确保ID正确）
            cursor.execute("DELETE FROM awards WHERE id = ?", (int(award_id),))
            deleted_award = cursor.rowcount
            
            # 验证删除是否成功
            if deleted_award > 0:
                # 再次查询确认记录已删除
                cursor.execute("SELECT id FROM awards WHERE id = ?", (int(award_id),))
                still_exists = cursor.fetchone() is not None
                if still_exists:
                    logger.error(f"删除操作执行后，奖状 ID {award_id} 仍然存在于数据库中！这可能表示事务未被提交。")
            
            # 3. 显式提交事务
            conn.commit()
            
            # 提交后再次验证
            cursor.execute("SELECT id FROM awards WHERE id = ?", (int(award_id),))
            still_exists_after_commit = cursor.fetchone() is not None
            
            if deleted_award == 0:
                logger.warning(f"删除奖状 ID {award_id} 时，数据库中未找到该记录（可能已被删除）")
                # 即使数据库中没有记录，也从内存中删除了，返回True表示操作完成
                return True
            elif still_exists_after_commit:
                logger.error(f"删除奖状 ID {award_id} 后提交事务，但记录仍然存在！可能存在其他连接持有锁。")
                return False
            else:
                logger.info(f"成功删除奖状 ID: {award_id} (关联: students={deleted_students}, teachers={deleted_teachers}, supervisors={deleted_supervisors}, related={deleted_related})")

                # 4. 删除图片文件（如果图片不再被其他奖状使用）
                if award_to_delete and award_to_delete.image_hash:
                    # 检查是否有其他奖状使用相同的图片
                    cursor.execute("SELECT COUNT(*) FROM awards WHERE image_hash = ? AND id != ?", (award_to_delete.image_hash, award_id))
                    other_count = cursor.fetchone()[0]

                    if other_count == 0:
                        # 没有其他奖状使用此图片，可以安全删除
                        if self.images_dir:
                            for ext in ['.jpg', '.jpeg', '.png', '.gif']:
                                image_path = self.images_dir / f"{award_to_delete.image_hash}{ext}"
                                if image_path.exists():
                                    try:
                                        image_path.unlink()
                                        logger.info(f"已删除奖状 ID {award_id} 的图片文件: {image_path.name}")
                                        break
                                    except Exception as e:
                                        logger.warning(f"删除图片文件失败 {image_path}: {e}")
                        else:
                            logger.warning(f"奖状 ID {award_id} 的图片未删除：images_dir 未配置")
                    else:
                        logger.info(f"奖状 ID {award_id} 的图片文件保留（仍有 {other_count} 个奖状使用）")

                return True
        except Exception as e:
            # 回滚事务
            conn.rollback()
            logger.error(f"Failed to delete award {award_id} from database: {e}", exc_info=True)
            # 如果数据库删除失败，且对象之前在内存中，需要将对象重新加回内存列表
            if award_to_delete:
                self.awards.append(award_to_delete)
            return False
        finally:
            conn.close()
    
    @staticmethod
    def cleanup_associations_for_student(db_path: str, student_id: int) -> bool:
        """
        清理指定学生的所有关联记录（静态方法，供StudentManager调用）
        
        Args:
            db_path: 数据库路径
            student_id: 学生ID
        
        Returns:
            bool: 是否成功
        """
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM award_student_winners WHERE student_id = ?", (student_id,))
                cursor.execute("DELETE FROM award_related_students WHERE student_id = ?", (student_id,))
                logger.info(f"已清理学生 ID {student_id} 的关联记录")
                return True
        except Exception as e:
            logger.error(f"清理学生关联记录失败: {e}")
            return False
    
    @staticmethod
    def cleanup_associations_for_teacher(db_path: str, teacher_id: int) -> bool:
        """
        清理指定教师的所有关联记录（静态方法，供TeacherManager调用）
        
        Args:
            db_path: 数据库路径
            teacher_id: 教师ID
        
        Returns:
            bool: 是否成功
        """
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM award_teacher_winners WHERE teacher_id = ?", (teacher_id,))
                cursor.execute("DELETE FROM award_supervisors WHERE teacher_id = ?", (teacher_id,))
                logger.info(f"已清理教师 ID {teacher_id} 的关联记录")
                return True
        except Exception as e:
            logger.error(f"清理教师关联记录失败: {e}")
            return False

    def save_image(self, file_bytes: bytes, file_ext: str, img_hash: str) -> str:
        """
        保存图片文件到磁盘，返回保存路径。
        :param file_bytes: 图片文件的字节数据
        :param file_ext: 文件扩展名（如 .jpg, .png）
        :param img_hash: 图片哈希值，用于文件名
        :return: 保存的文件路径
        """
        # 使用实例的 images_dir
        if not self.images_dir:
            raise ValueError("images_dir 未设置")
        
        # 确保目录存在
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用 hash 作为文件名（避免重复）
        filename = f"{img_hash}{file_ext}"
        file_path = self.images_dir / filename
        
        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        
        return str(file_path)

    def _find_associate_award(self, award: Award):
        """ 有部分学生证书上没有指导教师，所以只能找出同一个比赛的教师证书"""
        for a in self.awards:
            # 跳过没有相关学生的教师证书
            if not a.related_student_name or a.related_student_name.strip() == "":
                continue
            # 只处理蓝桥杯相关证书
            # if "蓝桥杯" not in (a.competition_name_in_file or ""):
            #     continue
            # 必须属于同一个竞赛
            if a.competition_id != award.competition_id:
                continue
            # 匹配赛道、年份（省份可以为空，允许省份不匹配的情况）
            if a.track == award.track and a.year == award.year:
                # 匹配奖项等级和比赛等级
                if a.award_level == award.award_level and a.competition_level == award.competition_level:
                    # 解析相关学生列表（教师证书的 related_student_name 包含学生姓名）
                    related_student_list = [s.strip() for s in a.related_student_name.split(",") if s.strip()]
                    # 解析学生证书的获奖者列表
                    winner_name_list = [w.strip() for w in (award.winner_name or "").split(",") if w.strip()]
                    # 如果学生证书的获奖者在教师证书的相关学生列表中，则匹配成功
                    if set(winner_name_list) & set(related_student_list):
                        return a
        return None

    def query_awards_supervisor(self,supervisor_name: str, year: Optional[int] = None) -> List[Award]:
        """
        查询匹配第一指导教师的奖状对象列表。
        :param supervisor_name: 要匹配的教师名称
        :param year: 要匹配的年份
        :return: 满足条件的奖状对象列表
        """
        # 从内存列表过滤
        results = []
        
        for award in self.awards:
            if award.supervisor_name:
                # 处理各种可能的分隔符
                supervisor_str = award.supervisor_name
                # 统一替换所有可能的分隔符为逗号
                for symbol in ['、', '，', ';', '；', ' ', '\t']:
                    supervisor_str = supervisor_str.replace(symbol, ',')
                # 分割指导教师名称，取第一个作为第一指导教师
                supervisors = supervisor_str.split(',')
                if supervisors:
                    first_supervisor = supervisors[0].strip()
                    # 使用模糊匹配，检查教师名称是否在第一指导教师中
                    if supervisor_name == first_supervisor and (not year or award.year == year):
                        results.append(award)
        
        return results

    def refresh_association_for_student_award(self,comp_mgr: CompetitionManager,
                  stu_mgr: StudentManager,
                  tea_mgr: TeacherManager):
        """有部分学生证书上没有指导教师，所以只能找出同一个比赛的教师证书，将指导老师更新到学生证书上"""
        """一般教师证书只颁发给第一指导老师，所以只匹配一个证书。同时刷新关联数据，确保关联数据正确"""
        todolist = []
        # 修改一些错误信息
        # 统一替换所有分隔符为逗号，更便于扩展
        replace_symbols = ['、', '，', ';', '；']
        updated_count = 0
        for award in self.awards:
            # 防止 None
            for attr in ['winner_name', 'supervisor_name', 'related_student_name']:
                val = getattr(award, attr, None)
                if val:
                    original_val = val
                    for symbol in replace_symbols:
                        if symbol in val:
                            val = val.replace(symbol, ',')
                    # 只有当值发生变化时才更新和保存
                    if val != original_val:
                        setattr(award, attr, val)
                        logger.info(f"更新奖状 ID {award.id} ({award.competition_name_in_file}) 的 {attr}: '{original_val}' -> '{val}'")
                        self._save_award(award)
                        updated_count += 1
        if updated_count > 0:
            logger.info(f"共更新了 {updated_count} 个奖状的分隔符")
            
        # 将所有还没有填充指导教师的学生证书加入到todolist中
        for award in self.awards:
            award.refresh_associations(comp_mgr, stu_mgr, tea_mgr)
            # 只处理学生证书，且指导教师为空或None的情况
            if award.granted_role and "学生" in award.granted_role:
                # 检查 supervisor_name 是否为空
                #if not award.supervisor_name or award.supervisor_name.strip() == "":
                todolist.append(award)
        
        matched_count = 0
        for award in todolist:
            ret = self._find_associate_award(award)
            if ret:
                award.supervisor_name = ret.winner_name
                self._save_award(award)
                award_title = award.competition_name_in_file + " " + award.winner_name + " " + award.competition_level
                matched_count += 1
        
        # 统计教师奖状总数
        teacher_award_count = 0
        for award in self.awards:
            if award.granted_role and "教师" in str(award.granted_role):
                teacher_award_count += 1
        
        # 返回统计信息
        return {
            'total_student_awards': len(todolist),
            'total_teacher_awards': teacher_award_count,
            'updated': matched_count
        }
    
    def refresh_all_associations(self,
                                 student_manager: Optional[StudentManager] = None,
                                 teacher_manager: Optional[TeacherManager] = None,
                                 competition_manager: Optional[CompetitionManager] = None) -> Dict[str, int]:
        """
        遍历所有奖状，重新匹配人名并更新关联关系
        
        Args:
            student_manager: 学生管理器
            teacher_manager: 教师管理器
            competition_manager: 竞赛管理器（如果提供，会确保竞赛关联正确）
        
        Returns:
            dict: {
                'total': int,  # 处理的奖状总数
                'matched': int,  # 成功匹配的人名总数
                'ambiguous': int,  # 重名的人名总数
                'not_found': int  # 未找到的人名总数
            }
        """
        if not student_manager or not teacher_manager:
            raise ValueError("student_manager 和 teacher_manager 必须提供")
        
        total = len(self.awards)
        total_matched = 0
        total_ambiguous = 0
        total_not_found = 0
        
        for award in self.awards:
            # 重新匹配人名
            try:
                # 解析winner_name
                winner_names = award._parse_names(award.winner_name) if award.winner_name else []
                
                # 判断角色：如果是教师组，winner_name 匹配教师表
                is_teacher_role = award.granted_role and "教师" in award.granted_role
                
                matched_count = 0
                ambiguous_count = 0
                not_found_count = 0
                
                # 匹配获奖者
                for name in winner_names:
                    if is_teacher_role:
                        found = teacher_manager.find_teachers_by_name(name)
                    else:
                        found = student_manager.find_students_by_name(name)
                    
                    if len(found) == 1:
                        matched_count += 1
                    elif len(found) > 1:
                        ambiguous_count += 1
                    else:
                        not_found_count += 1
                
                # 匹配指导教师
                supervisor_names = award._parse_names(award.supervisor_name) if award.supervisor_name else []
                for name in supervisor_names:
                    found = teacher_manager.find_teachers_by_name(name)
                    if len(found) == 1:
                        matched_count += 1
                    elif len(found) > 1:
                        ambiguous_count += 1
                    else:
                        not_found_count += 1
                
                # 匹配关联学生
                related_names = award._parse_names(award.related_student_name) if award.related_student_name else []
                for name in related_names:
                    found = student_manager.find_students_by_name(name)
                    if len(found) == 1:
                        matched_count += 1
                    elif len(found) > 1:
                        ambiguous_count += 1
                    else:
                        not_found_count += 1
                
                # 刷新关联（会自动更新关联表）
                if competition_manager:
                    award.refresh_associations(competition_manager, student_manager, teacher_manager)
                else:
                    # 如果没有提供 competition_manager，只刷新人名关联（需要实现一个只刷新人名的版本）
                    # 这里暂时使用 refresh_associations，但需要 competition_manager
                    # 如果 competition_manager 为 None，从 AppContext 获取
                    from backend.models.app_context import get_app_context
                    try:
                        app_context = get_app_context()
                        comp_mgr = app_context.get_competition_manager()
                        award.refresh_associations(comp_mgr, student_manager, teacher_manager)
                    except:
                        logger.warning(f"无法获取 CompetitionManager，跳过奖状 {award.id} 的关联刷新")
                        continue
                
                # 保存到数据库
                self._save_award(award)
                
                total_matched += matched_count
                total_ambiguous += ambiguous_count
                total_not_found += not_found_count
                
            except Exception as e:
                logger.error(f"刷新奖状 {award.id} 的关联失败: {e}")
                continue
        
        return {
            'total': total,
            'matched': total_matched,
            'ambiguous': total_ambiguous,
            'not_found': total_not_found
        }
        
        
