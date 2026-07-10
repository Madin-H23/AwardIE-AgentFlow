"""
Innovation Project Management Module

Handles innovation project (大创) data operations.
Note: Only admin can submit innovation projects.
"""
import sqlite3
import logging
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Forward declaration for type hints
if False:
    from backend.models.student import Student
    from backend.models.student import StudentManager


@dataclass
class InnovationProject:
    """Innovation Project data model"""
    # Core fields
    project_no: Optional[str] = None
    project_name: str = ""
    project_type: Optional[str] = None  # 国家级, 省级, 校级
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    # People
    student_leader_name: Optional[str] = None
    student_leader_id: Optional[str] = None
    other_members: Optional[str] = None  # JSON string or comma-separated
    supervisors: Optional[str] = None  # Comma-separated teacher names

    # Funding and status
    funding_amount: Optional[float] = None
    status: str = "进行中"  # 进行中, 已结题, 终止

    # Submitter info (admin only)
    submitter_type: str = "admin"
    submitter_id: Optional[int] = None
    submit_time: Optional[str] = None
    laboratory_id: Optional[int] = None

    # System fields
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # 对象关联（不存入主表，存入关联表）
    student_leader_obj: Optional['Student'] = field(default=None, init=False, repr=False)
    student_members: List['Student'] = field(default_factory=list, init=False, repr=False)
    _match_status: Dict[str, str] = field(default_factory=dict, init=False, repr=False)  # 匹配状态记录

    def __str__(self):
        parts = [self.project_name]
        if self.project_no:
            parts.append(f"编号:{self.project_no}")
        if self.project_type:
            parts.append(f"类型:{self.project_type}")
        if self.student_leader_name:
            parts.append(f"负责人:{self.student_leader_name}")
        if self.status:
            parts.append(f"状态:{self.status}")
        return " | ".join(parts)

    def _parse_other_members(self) -> List[Dict[str, str]]:
        """
        解析 other_members，兼容多种格式
        返回: [{"姓名": "...", "学号": "..."}, ...]
        """
        if not self.other_members:
            return []
        
        # 尝试解析JSON
        try:
            data = json.loads(self.other_members)
            if isinstance(data, list):
                # 检查元素格式
                if data and isinstance(data[0], dict):
                    # 新格式：[{"姓名":"...","学号":"..."}]
                    return data
                elif data and isinstance(data[0], str):
                    # 旧格式：["张三(2022001)", "李四(2022002)"]
                    return self._parse_legacy_format(data)
        except (json.JSONDecodeError, TypeError, IndexError):
            pass
        
        # 尝试逗号分隔
        if "," in self.other_members:
            names = [n.strip() for n in self.other_members.split(",") if n.strip()]
            return [{"姓名": name, "学号": None} for name in names]
        
        return []

    def _parse_legacy_format(self, data: List[str]) -> List[Dict[str, str]]:
        """解析旧格式：["张三(2022001)", "李四(2022002)"]"""
        result = []
        for item in data:
            if isinstance(item, str):
                # 尝试解析 "姓名(学号)" 格式
                if "(" in item and ")" in item:
                    name = item[:item.index("(")].strip()
                    student_id = item[item.index("(")+1:item.index(")")].strip()
                    result.append({"姓名": name, "学号": student_id})
                else:
                    result.append({"姓名": item.strip(), "学号": None})
        return result

    def get_members_list(self) -> List[Dict[str, str]]:
        """
        Get other members as structured list
        返回: [{"姓名": "...", "学号": "..."}, ...]
        """
        return self._parse_other_members()

    def get_other_members_display(self) -> str:
        """用于列表展示：其他成员格式化为「姓名(学号), ...」"""
        members = self._parse_other_members()
        if not members:
            return ""
        parts = []
        for m in members:
            name = (m.get("姓名") or "").strip()
            sid = (m.get("学号") or "").strip()
            parts.append(f"{name}({sid})" if sid else name)
        return ", ".join(parts)

    def get_supervisors_list(self) -> List[str]:
        """Get supervisors as list"""
        if not self.supervisors:
            return []
        return [s.strip() for s in self.supervisors.split(",") if s.strip()]

    def get_year(self) -> Optional[int]:
        """
        从 start_date 中提取年份
        支持格式：YYYY.MM、YYYY-MM、YYYY-MM-DD、YYYY年等
        """
        if not self.start_date:
            return None
        
        import re
        date_str = str(self.start_date).strip()
        
        # 模式1: YYYY.MM 或 YYYY-MM 或 YYYY-MM-DD
        pattern1 = r'^(\d{4})[-.]'
        match = re.match(pattern1, date_str)
        if match:
            try:
                year = int(match.group(1))
                if 1900 <= year <= 2100:
                    return year
            except (ValueError, IndexError):
                pass
        
        # 模式2: YYYY年
        pattern2 = r'(\d{4})年'
        match = re.search(pattern2, date_str)
        if match:
            try:
                year = int(match.group(1))
                if 1900 <= year <= 2100:
                    return year
            except (ValueError, IndexError):
                pass
        
        # 模式3: 纯数字YYYY
        pattern3 = r'^(\d{4})'
        match = re.match(pattern3, date_str)
        if match:
            try:
                year = int(match.group(1))
                if 1900 <= year <= 2100:
                    return year
            except (ValueError, IndexError):
                pass
        
        return None

    def refresh_student_associations(self, student_manager: 'StudentManager') -> bool:
        """
        刷新学生关联：匹配负责人和成员
        返回 True 表示所有关联都成功，False 表示存在未匹配项
        
        Args:
            student_manager: StudentManager 实例
            
        Returns:
            bool: 是否所有学生都匹配成功
        """
        all_matched = True
        self._match_status = {}
        
        # 1. 匹配负责人（优先使用学号）
        if self.student_leader_id:
            student = student_manager.get_student_by_student_id(self.student_leader_id)
            if student:
                # 验证姓名是否匹配
                if student.name == self.student_leader_name:
                    self.student_leader_obj = student
                    self._match_status['leader'] = "student_id_exact"
                else:
                    # 学号存在但姓名不匹配
                    all_matched = False
                    self._match_status['leader'] = "id_name_mismatch"
                    # 仍然建立关联，但标记为异常
                    self.student_leader_obj = student
            else:
                # 学号不存在，尝试用姓名匹配
                found = student_manager.find_students_by_name(self.student_leader_name)
                if len(found) == 1:
                    self.student_leader_obj = found[0]
                    self._match_status['leader'] = "name_only"
                elif len(found) > 1:
                    all_matched = False
                    self._match_status['leader'] = "name_ambiguous"
                    # 重名时，选择第一个（或由管理员手动选择）
                    self.student_leader_obj = found[0]
                else:
                    all_matched = False
                    self._match_status['leader'] = "unmatched"
        elif self.student_leader_name:
            # 只有姓名，没有学号
            found = student_manager.find_students_by_name(self.student_leader_name)
            if len(found) == 1:
                self.student_leader_obj = found[0]
                self._match_status['leader'] = "name_only"
            elif len(found) > 1:
                all_matched = False
                self._match_status['leader'] = "name_ambiguous"
                # 重名时，选择第一个
                self.student_leader_obj = found[0]
            else:
                all_matched = False
                self._match_status['leader'] = "unmatched"
        
        # 2. 匹配成员（从 other_members 解析）
        self.student_members = []
        members_data = self._parse_other_members()
        
        for i, member in enumerate(members_data):
            member_name = member.get("姓名")
            member_id = member.get("学号")
            
            if member_id:
                student = student_manager.get_student_by_student_id(member_id)
                if student:
                    if student.name == member_name:
                        self.student_members.append(student)
                        self._match_status[f'member_{i}'] = "student_id_exact"
                    else:
                        # 学号存在但姓名不匹配
                        all_matched = False
                        self._match_status[f'member_{i}'] = "id_name_mismatch"
                        # 仍然建立关联，但标记为异常
                        self.student_members.append(student)
                else:
                    # 学号不存在，尝试姓名匹配
                    found = student_manager.find_students_by_name(member_name)
                    if len(found) == 1:
                        self.student_members.append(found[0])
                        self._match_status[f'member_{i}'] = "name_only"
                    elif len(found) > 1:
                        all_matched = False
                        self._match_status[f'member_{i}'] = "name_ambiguous"
                        # 重名时，选择第一个
                        self.student_members.append(found[0])
                    else:
                        all_matched = False
                        self._match_status[f'member_{i}'] = "unmatched"
            elif member_name:
                # 只有姓名
                found = student_manager.find_students_by_name(member_name)
                if len(found) == 1:
                    self.student_members.append(found[0])
                    self._match_status[f'member_{i}'] = "name_only"
                elif len(found) > 1:
                    all_matched = False
                    self._match_status[f'member_{i}'] = "name_ambiguous"
                    # 重名时，选择第一个
                    self.student_members.append(found[0])
                else:
                    all_matched = False
                    self._match_status[f'member_{i}'] = "unmatched"
        
        return all_matched

    def _normalize_other_members(self, members_data: List[Dict[str, str]]) -> Optional[str]:
        """
        将成员数据标准化为JSON字符串
        如果输入为空，返回None
        """
        if not members_data:
            return None
        return json.dumps(members_data, ensure_ascii=False)


@dataclass
class InnovationProjectFilter:
    """Innovation Project query filter"""
    id: Optional[int] = None
    project_no: Optional[str] = None
    project_name: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None
    student_leader_name: Optional[str] = None
    student_leader_id: Optional[str] = None
    laboratory_id: Optional[int] = None
    year: Optional[int] = None  # 年份过滤
    limit: Optional[int] = None
    offset: Optional[int] = None

    def is_empty(self) -> bool:
        return all([
            self.id is None,
            self.project_no is None,
            self.project_name is None,
            self.project_type is None,
            self.status is None,
            self.student_leader_name is None,
            self.student_leader_id is None,
            self.laboratory_id is None,
            self.year is None,
        ])


class InnovationProjectManager:
    """Manages innovation project data operations"""

    def __init__(self, db_path: str, files_dir: Optional[Path] = None):
        """
        Initialize InnovationProjectManager

        Args:
            db_path: Database file path
            files_dir: Directory for related files (Excel, etc.)
        """
        self.db_path = db_path

        if files_dir is None:
            from backend.services.unified_file_manager import get_unified_file_manager, FileType
            file_manager = get_unified_file_manager()
            files_dir = file_manager.files_root / FileType.OTHER.directory

        self.files_dir = Path(files_dir)

        self.projects: List[InnovationProject] = []
        self._init_db()
        self._load_all_from_db()

    def _init_db(self):
        """Initialize database tables (create if not exist)"""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 创建关联表（如果不存在）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS innovation_project_students (
                    project_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('leader', 'member')),
                    student_name TEXT,
                    student_id_str TEXT,
                    match_type TEXT,
                    PRIMARY KEY (project_id, student_id),
                    FOREIGN KEY (project_id) REFERENCES innovation_projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_innovation_project_students_student 
                ON innovation_project_students(student_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_innovation_project_students_project 
                ON innovation_project_students(project_id)
            """)
            
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize innovation_project_students table: {e}")
            conn.rollback()
        finally:
            conn.close()

    def _get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 启用外键约束
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _load_all_from_db(self):
        """Load all innovation projects from database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM innovation_projects ORDER BY id DESC")
            rows = cursor.fetchall()
            conn.close()

            self.projects = [self._row_to_project(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to load innovation projects: {e}")
            self.projects = []
    
    def load_project_with_associations(self, project_id: int, 
                                      student_manager: Optional['StudentManager'] = None) -> Optional[InnovationProject]:
        """
        加载项目并恢复学生关联
        
        Args:
            project_id: 项目ID
            student_manager: StudentManager 实例
            
        Returns:
            InnovationProject 对象（已加载关联）
        """
        project = self.get_project_by_id(project_id)
        if not project:
            return None
        
        if student_manager:
            # 恢复学生关联
            project.refresh_student_associations(student_manager)
            # 从数据库加载关联（如果关联表中有数据）
            self._load_associations_from_db([project], student_manager)
        
        return project
    
    def _load_associations_from_db(self, projects: List[InnovationProject],
                                   student_manager: Optional['StudentManager'] = None):
        """
        从数据库加载学生关联
        
        Args:
            projects: 项目列表
            student_manager: StudentManager 实例
        """
        if not student_manager or not projects:
            return
        
        project_ids = [p.id for p in projects if p.id]
        if not project_ids:
            return
        
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            placeholders = ",".join(["?" for _ in project_ids])
            cursor.execute(f"""
                SELECT project_id, student_id, role, student_name, student_id_str, match_type
                FROM innovation_project_students
                WHERE project_id IN ({placeholders})
            """, project_ids)
            
            rows = cursor.fetchall()
            
            # 按项目ID分组
            associations_by_project = {}
            for row in rows:
                project_id = row['project_id']
                if project_id not in associations_by_project:
                    associations_by_project[project_id] = []
                associations_by_project[project_id].append(row)
            
            # 加载到项目对象
            for project in projects:
                if project.id not in associations_by_project:
                    continue
                
                for assoc in associations_by_project[project.id]:
                    student = student_manager.get_student_by_id(assoc['student_id'])
                    if student:
                        if assoc['role'] == 'leader':
                            project.student_leader_obj = student
                        else:
                            if student not in project.student_members:
                                project.student_members.append(student)
                        project._match_status[assoc['role']] = assoc['match_type']
        
        except Exception as e:
            logger.error(f"Failed to load associations from DB: {e}")
        finally:
            conn.close()

    def _row_to_project(self, row: sqlite3.Row) -> InnovationProject:
        """Convert database row to InnovationProject object"""
        data = dict(row)
        data.pop('created_at', None)
        data.pop('updated_at', None)
        return InnovationProject(**data)

    def get_project_by_id(self, project_id: int) -> Optional[InnovationProject]:
        """Get innovation project by ID"""
        for project in self.projects:
            if project.id == project_id:
                return project
        return None

    def add_project(self, project_data: Dict[str, Any], 
                    student_manager: Optional['StudentManager'] = None) -> InnovationProject:
        """
        Add a new innovation project (admin only)

        Args:
            project_data: Project data dictionary
            student_manager: Optional StudentManager for association matching

        Returns:
            Created InnovationProject object
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # Check for duplicate by project_no
            if project_data.get('project_no'):
                existing = self._find_by_project_no(project_data['project_no'])
                if existing:
                    raise ValueError(f"Innovation project with project_no {project_data['project_no']} already exists")

            # 标准化 other_members 格式
            if 'other_members' in project_data and project_data['other_members']:
                if isinstance(project_data['other_members'], list):
                    # 如果是列表，转换为JSON字符串
                    project_data['other_members'] = json.dumps(project_data['other_members'], ensure_ascii=False)
                elif isinstance(project_data['other_members'], str):
                    # 如果是字符串，尝试解析并重新格式化
                    try:
                        parsed = json.loads(project_data['other_members'])
                        if isinstance(parsed, list):
                            project_data['other_members'] = json.dumps(parsed, ensure_ascii=False)
                    except:
                        pass  # 保持原样

            # Prepare fields
            fields = [
                "project_no", "project_name", "project_type",
                "start_date", "end_date", "student_leader_name",
                "student_leader_id", "other_members", "supervisors",
                "funding_amount", "status", "submitter_type",
                "submitter_id", "laboratory_id"
            ]

            values = [project_data.get(f) for f in fields]

            placeholders = ", ".join(["?" for _ in fields])
            cols = ", ".join(fields)

            cursor.execute(f"INSERT INTO innovation_projects ({cols}) VALUES ({placeholders})", values)
            project_id = cursor.lastrowid

            # 如果提供了 student_manager，建立学生关联
            if student_manager:
                project_obj = InnovationProject(**{f: project_data.get(f) for f in fields})
                project_obj.id = project_id
                project_obj.refresh_student_associations(student_manager)
                self._save_student_associations(cursor, project_obj)

            conn.commit()
            conn.close()

            # Reload and return
            self._load_all_from_db()
            return self.get_project_by_id(project_id)

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to add innovation project: {e}")
            raise

    def update_project(self, project_id: int, project_data: Dict[str, Any],
                       student_manager: Optional['StudentManager'] = None) -> bool:
        """
        Update existing innovation project

        Args:
            project_id: Project ID
            project_data: Updated data
            student_manager: Optional StudentManager for association matching

        Returns:
            True if successful
        """
        project = self.get_project_by_id(project_id)
        if not project:
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # 标准化 other_members 格式
            if 'other_members' in project_data and project_data['other_members']:
                if isinstance(project_data['other_members'], list):
                    project_data['other_members'] = json.dumps(project_data['other_members'], ensure_ascii=False)
                elif isinstance(project_data['other_members'], str):
                    try:
                        parsed = json.loads(project_data['other_members'])
                        if isinstance(parsed, list):
                            project_data['other_members'] = json.dumps(parsed, ensure_ascii=False)
                    except:
                        pass

            # Update fields
            fields = [
                "project_no", "project_name", "project_type",
                "start_date", "end_date", "student_leader_name",
                "student_leader_id", "other_members", "supervisors",
                "funding_amount", "status", "submitter_type",
                "submitter_id", "laboratory_id"
            ]

            set_clause = ", ".join([f"{f} = ?" for f in fields])
            values = [project_data.get(f, getattr(project, f)) for f in fields]

            cursor.execute(
                f"UPDATE innovation_projects SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values + [project_id]
            )

            # 如果提供了 student_manager，更新学生关联
            if student_manager:
                # 更新项目对象的数据
                for field in fields:
                    if field in project_data:
                        setattr(project, field, project_data[field])
                
                project.refresh_student_associations(student_manager)
                self._save_student_associations(cursor, project)

            conn.commit()
            conn.close()

            self._load_all_from_db()
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to update innovation project {project_id}: {e}")
            return False

    def delete_project(self, project_id: int) -> bool:
        """Delete innovation project"""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM innovation_projects WHERE id = ?", (project_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                self.projects = [p for p in self.projects if p.id != project_id]

            return deleted

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to delete innovation project {project_id}: {e}")
            return False

    def delete_all(self) -> int:
        """
        清空大创主表及关联表（innovation_projects、innovation_project_students）。
        用于一次性删除所有大创项目数据。

        Returns:
            删除的 innovation_projects 行数
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM innovation_project_students")
            cursor.execute("DELETE FROM innovation_projects")
            count = cursor.rowcount
            conn.commit()
            conn.close()
            self._load_all_from_db()
            logger.info(f"已清空大创数据，删除 innovation_projects 行数: {count}")
            return count
        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"清空大创数据失败: {e}")
            raise

    def query_projects(self, filter_obj: Optional[InnovationProjectFilter] = None) -> List[InnovationProject]:
        """
        Query innovation projects with optional filter

        Args:
            filter_obj: InnovationProjectFilter object

        Returns:
            List of matching innovation projects
        """
        results = list(self.projects)

        if not filter_obj or filter_obj.is_empty():
            return results

        # Apply filters
        if filter_obj.id is not None:
            results = [p for p in results if p.id == filter_obj.id]

        if filter_obj.project_no:
            results = [p for p in results if p.project_no == filter_obj.project_no]

        if filter_obj.project_type:
            results = [p for p in results if p.project_type == filter_obj.project_type]

        if filter_obj.status:
            results = [p for p in results if p.status == filter_obj.status]

        if filter_obj.student_leader_name:
            results = [p for p in results
                      if p.student_leader_name and filter_obj.student_leader_name in p.student_leader_name]

        if filter_obj.student_leader_id:
            results = [p for p in results if p.student_leader_id == filter_obj.student_leader_id]

        if filter_obj.project_name:
            results = [p for p in results
                      if p.project_name and filter_obj.project_name in p.project_name]

        if filter_obj.laboratory_id is not None:
            results = [p for p in results if p.laboratory_id == filter_obj.laboratory_id]

        if filter_obj.year is not None:
            # 按年份过滤（从 start_date 提取年份）
            filtered = []
            for p in results:
                year = p.get_year()
                if year == filter_obj.year:
                    filtered.append(p)
            results = filtered

        # Pagination
        if filter_obj.offset is not None:
            results = results[filter_obj.offset:]
        if filter_obj.limit is not None:
            results = results[:filter_obj.limit]

        return results

    def _find_by_project_no(self, project_no: str) -> Optional[InnovationProject]:
        """Find innovation project by project number"""
        for project in self.projects:
            if project.project_no == project_no:
                return project
        return None

    def check_duplicate(self, project_data: Dict[str, Any]) -> Optional[InnovationProject]:
        """
        Check for duplicate innovation project

        Strategy: student_leader_name + project_name (normalized)

        Args:
            project_data: Project data to check

        Returns:
            Existing project if duplicate found, None otherwise
        """
        if not project_data.get('student_leader_name') or not project_data.get('project_name'):
            return None

        leader_normalized = project_data['student_leader_name'].strip().lower()
        name_normalized = project_data['project_name'].strip().lower()

        for project in self.projects:
            if (project.student_leader_name and
                project.student_leader_name.strip().lower() == leader_normalized and
                project.project_name and
                project.project_name.strip().lower() == name_normalized):
                return project

        return None

    def _save_student_associations(self, cursor, project: InnovationProject):
        """
        保存学生关联到关联表
        
        Args:
            cursor: 数据库游标
            project: InnovationProject 对象
        """
        if not project.id:
            logger.warning("Cannot save associations: project.id is None")
            return
        
        # 删除旧关联
        cursor.execute(
            "DELETE FROM innovation_project_students WHERE project_id = ?",
            (project.id,)
        )
        
        # 保存负责人
        if project.student_leader_obj and project.student_leader_obj.id:
            match_type = project._match_status.get('leader', 'unmatched')
            cursor.execute("""
                INSERT INTO innovation_project_students 
                (project_id, student_id, role, student_name, student_id_str, match_type)
                VALUES (?, ?, 'leader', ?, ?, ?)
            """, (
                project.id,
                project.student_leader_obj.id,
                project.student_leader_name,
                project.student_leader_id,
                match_type
            ))
        
        # 保存成员
        members_data = project._parse_other_members()
        for i, member in enumerate(members_data):
            member_name = member.get("姓名")
            member_id = member.get("学号")
            
            # 找到对应的 Student 对象
            member_student = None
            for s in project.student_members:
                if member_id and s.student_id == member_id:
                    member_student = s
                    break
                elif member_name and s.name == member_name:
                    member_student = s
                    break
            
            if member_student and member_student.id:
                match_type = project._match_status.get(f'member_{i}', 'unmatched')
                cursor.execute("""
                    INSERT INTO innovation_project_students 
                    (project_id, student_id, role, student_name, student_id_str, match_type)
                    VALUES (?, ?, 'member', ?, ?, ?)
                """, (
                    project.id,
                    member_student.id,
                    member_name,
                    member_id,
                    match_type
                ))

    def _eager_load_associations(self, projects: List[InnovationProject],
                                 student_manager: Optional['StudentManager'] = None):
        """
        批量加载学生关联（延迟加载，按需调用）
        
        Args:
            projects: 项目列表
            student_manager: StudentManager 实例
        """
        if not student_manager or not projects:
            return
        
        project_ids = [p.id for p in projects if p.id]
        if not project_ids:
            return
        
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            placeholders = ",".join(["?" for _ in project_ids])
            cursor.execute(f"""
                SELECT project_id, student_id, role, student_name, student_id_str, match_type
                FROM innovation_project_students
                WHERE project_id IN ({placeholders})
            """, project_ids)
            
            rows = cursor.fetchall()
            
            # 按项目ID分组
            associations_by_project = {}
            for row in rows:
                project_id = row['project_id']
                if project_id not in associations_by_project:
                    associations_by_project[project_id] = []
                associations_by_project[project_id].append(row)
            
            # 加载到项目对象
            for project in projects:
                if project.id not in associations_by_project:
                    continue
                
                for assoc in associations_by_project[project.id]:
                    student = student_manager.get_student_by_id(assoc['student_id'])
                    if student:
                        if assoc['role'] == 'leader':
                            project.student_leader_obj = student
                        else:
                            if student not in project.student_members:
                                project.student_members.append(student)
                        project._match_status[assoc['role']] = assoc['match_type']
        
        except Exception as e:
            logger.error(f"Failed to eager load associations: {e}")
        finally:
            conn.close()


