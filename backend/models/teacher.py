"""
教师模型和管理器
"""
import sqlite3
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Teacher:
    """教师实体类"""
    id: int
    teacher_id: str
    name: str
    department: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    id_number: Optional[str] = None
    qq: Optional[str] = None
    skills: Optional[str] = None  # JSON格式存储技能标签列表
    user_activated: bool = True
    password_hash: Optional[str] = None
    role: str = 'teacher'


class TeacherManager:
    """教师管理器"""
    
    def __init__(self, db_path: str):
        """
        初始化教师管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.teachers: List[Teacher] = []
        self._load_all_from_db()
    
    def _get_db_connection(self):
        """获取数据库连接（统一工厂：外键/WAL/busy_timeout 强制契约，P0-4/5/7）"""
        from backend.utils.db_connection import get_connection
        return get_connection(self.db_path)
    
    def _load_all_from_db(self):
        """从数据库加载所有教师"""
        self.teachers = []
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, teacher_id, name, department, title, phone, id_number, qq, skills,
                       user_activated, password_hash, role
                FROM teachers
            ''')
            
            for row in cursor.fetchall():
                teacher = Teacher(
                    id=row[0],
                    teacher_id=row[1],
                    name=row[2],
                    department=row[3] or '未设置',
                    title=row[4],
                    phone=row[5],
                    id_number=row[6],
                    qq=row[7] if len(row) > 7 else None,
                    skills=row[8] if len(row) > 8 else None,
                    user_activated=bool(row[9]) if len(row) > 9 and row[9] is not None else True,
                    password_hash=row[10] if len(row) > 10 else None,
                    role=row[11] if len(row) > 11 and row[11] else 'teacher'
                )
                self.teachers.append(teacher)
            
            conn.close()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                self._init_db()
                self._load_all_from_db()
            else:
                raise
    
    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                department TEXT NOT NULL DEFAULT '未设置',
                title TEXT,
                phone TEXT,
                id_number TEXT,
                qq TEXT,
                skills TEXT,
                user_activated INTEGER DEFAULT 1,
                password_hash TEXT,
                role TEXT DEFAULT 'teacher',
                needs_password_change INTEGER NOT NULL DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_teacher_by_id(self, teacher_id: int) -> Optional[Teacher]:
        """根据ID获取教师（P0-6：miss 回源 DB）"""
        for teacher in self.teachers:
            if teacher.id == teacher_id:
                return teacher
        return self._fetch_one_from_db('id', teacher_id)

    def get_teacher_by_pk(self, pk: int) -> Optional[Teacher]:
        """根据主键ID获取教师（别名方法）"""
        return self.get_teacher_by_id(pk)

    def get_teacher_by_teacher_id(self, teacher_id: str) -> Optional[Teacher]:
        """根据工号获取教师（P0-6：miss 回源）"""
        for teacher in self.teachers:
            if teacher.teacher_id == teacher_id:
                return teacher
        return self._fetch_one_from_db('teacher_id', teacher_id)

    def _fetch_one_from_db(self, column: str, value) -> Optional[Teacher]:
        """单行回源（P0-6：读路径伙伴，命中回填缓存）。"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                f'''SELECT id, teacher_id, name, department, title, phone, id_number, qq, skills,
                           user_activated, password_hash, role FROM teachers WHERE {column} = ?''',
                (value,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            teacher = Teacher(
                id=row[0], teacher_id=row[1], name=row[2],
                department=row[3] or '未设置', title=row[4], phone=row[5], id_number=row[6],
                qq=row[7] if len(row) > 7 else None, skills=row[8] if len(row) > 8 else None,
                user_activated=bool(row[9]) if len(row) > 9 and row[9] is not None else True,
                password_hash=row[10] if len(row) > 10 else None,
                role=row[11] if len(row) > 11 and row[11] else 'teacher')
            self.teachers.append(teacher)
            return teacher
        except sqlite3.Error:
            return None
    
    def find_teachers_by_name(self, name: str) -> List[Teacher]:
        """根据姓名查找教师（支持重名，使用精确匹配）"""
        name_lower = name.lower().strip()
        results = []
        for teacher in self.teachers:
            if name_lower == teacher.name.lower().strip():
                results.append(teacher)
        return results
    
    # M1 后半②：写路径已迁 users（UserRepository），视图化后旧表不可写——add/update/delete 已删除
