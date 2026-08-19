"""
学生模型和管理器
"""
import sqlite3
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Student:
    """学生实体类"""
    id: int
    student_id: str
    name: str
    major: Optional[str] = None
    grade: Optional[str] = None
    phone: Optional[str] = None
    qq: Optional[str] = None
    skills: Optional[str] = None  # JSON格式存储技能标签列表
    user_activated: bool = True
    password_hash: Optional[str] = None
    role: str = 'student'

    def __str__(self):
        # 展示格式: "{姓名} ｛学号｝{年级} {专业}"
        # 年级和专业允许为None时显示为空
        grade = self.grade or ""
        major = self.major or ""
        return f"{self.name} {self.student_id} {grade} {major}"
    

    def get_brief_desc(self) -> str:
        """
        返回简要信息：如“李家鸿(22计科)”。
        22为年级后两位，专业简写规则：
        - 计算机科学与技术：计科
        - 软件工程：软工
        - 数字媒体与技术：数媒
        未匹配的专业显示原专业或空字符串。
        """
        # 处理年级
        grade_short = ""
        if self.grade and len(self.grade) >= 2:
            grade_short = self.grade[-2:]
        # 处理专业简写
        major_map = {
            "计算机科学与技术": "计科",
            "软件工程": "软工",
            "数字媒体与技术": "数媒",
        }
        major_short = ""
        if self.major:
            for key, val in major_map.items():
                if key in self.major:
                    major_short = val
                    break
            else:
                major_short = self.major  # 未知专业显示原专业
        desc = f"{self.name}"
        if grade_short or major_short:
            desc += "("
            if grade_short:
                desc += grade_short
            if major_short:
                desc += major_short
            desc += ")"
        return desc


class StudentManager:
    """学生管理器"""
    
    def __init__(self, db_path: str):
        """
        初始化学生管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.students: List[Student] = []
        self._load_all_from_db()
    
    def _get_db_connection(self):
        """获取数据库连接（统一工厂：外键/WAL/busy_timeout 强制契约，P0-4/5/7）"""
        from backend.utils.db_connection import get_connection
        return get_connection(self.db_path)
    
    def _load_all_from_db(self):
        """从数据库加载所有学生"""
        self.students = []
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, student_id, name, major, grade, phone, qq, skills,
                       user_activated, password_hash, role
                FROM students
            ''')
            
            for row in cursor.fetchall():
                student = Student(
                    id=row[0],
                    student_id=row[1],
                    name=row[2],
                    major=row[3],
                    grade=row[4],
                    phone=row[5],
                    qq=row[6] if len(row) > 6 else None,
                    skills=row[7] if len(row) > 7 else None,
                    user_activated=bool(row[8]) if len(row) > 8 and row[8] is not None else True,
                    password_hash=row[9] if len(row) > 9 else None,
                    role=row[10] if len(row) > 10 and row[10] else 'student'
                )
                self.students.append(student)
            
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
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                major TEXT,
                grade TEXT,
                phone TEXT,
                qq TEXT,
                skills TEXT,
                user_activated INTEGER DEFAULT 1,
                password_hash TEXT,
                role TEXT DEFAULT 'student',
                needs_password_change INTEGER NOT NULL DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_student_by_id(self, student_id: int) -> Optional[Student]:
        """根据ID获取学生（P0-6：内存 miss 时单行回源 DB，read-through 缓解多 worker 一致性）"""
        for student in self.students:
            if student.id == student_id:
                return student
        return self._fetch_one_from_db('id', student_id)

    def get_student_by_pk(self, pk: int) -> Optional[Student]:
        """根据主键ID获取学生（别名方法）"""
        return self.get_student_by_id(pk)

    def get_student_by_student_id(self, student_id: str) -> Optional[Student]:
        """根据学号获取学生（P0-6：miss 回源）"""
        for student in self.students:
            if student.student_id == student_id:
                return student
        return self._fetch_one_from_db('student_id', student_id)

    def _fetch_one_from_db(self, column: str, value) -> Optional[Student]:
        """单行回源查询（替代写后全表重载的读路径伙伴；命中即入内存缓存）。"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                f'''SELECT id, student_id, name, major, grade, phone, qq, skills,
                           user_activated, password_hash, role
                    FROM students WHERE {column} = ?''', (value,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            student = Student(
                id=row[0], student_id=row[1], name=row[2], major=row[3], grade=row[4],
                phone=row[5], qq=row[6] if len(row) > 6 else None,
                skills=row[7] if len(row) > 7 else None,
                user_activated=bool(row[8]) if len(row) > 8 and row[8] is not None else True,
                password_hash=row[9] if len(row) > 9 else None,
                role=row[10] if len(row) > 10 and row[10] else 'student')
            self.students.append(student)   # 回填缓存
            return student
        except sqlite3.Error:
            return None
    
    def find_students_by_name(self, name: str) -> List[Student]:
        """根据姓名查找学生（支持重名，使用精确匹配）。用于重名检测、按姓名解析等。"""
        name_lower = name.lower().strip()
        results = []
        for student in self.students:
            if name_lower == student.name.lower().strip():
                results.append(student)
        return results

    def search_students_by_name(self, query: str) -> List[Student]:
        """根据姓名模糊搜索学生（部分匹配），用于编辑页候选列表、自动完成等。"""
        q = query.lower().strip()
        if not q:
            return []
        results = []
        for student in self.students:
            if q in student.name.lower():
                results.append(student)
        return results
    
    # M1 后半②：写路径已迁 users（UserRepository），视图化后旧表不可写——add/update/delete 已删除

