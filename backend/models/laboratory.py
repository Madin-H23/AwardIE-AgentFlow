"""
实验室管理模块
支持实验室的创建、查询、更新、删除，以及学生和教师的关联管理
"""
import sqlite3
import logging
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field
from pathlib import Path

# 导入类型提示（避免循环导入）
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.models.student import Student
    from backend.models.teacher import Teacher

logger = logging.getLogger(__name__)

@dataclass
class Laboratory:
    """实验室类"""
    id: int
    name: str
    description: Optional[str] = None
    cover_image: Optional[str] = None  # 封面图片路径
    
    # 引用列表（不存储ID，直接存储对象引用）
    instructors: List['Teacher'] = field(default_factory=list, init=False)
    students: List['Student'] = field(default_factory=list, init=False)
    assistants: List['Student'] = field(default_factory=list, init=False)  # 学生助教列表
    images: List[str] = field(default_factory=list, init=False)  # 实验室图片路径列表
    downloads: List[Dict] = field(default_factory=list, init=False)  # 实验室下载文件列表
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'Laboratory':
        """从数据库行创建Laboratory对象（不包含关联数据）"""
        row_keys = row.keys()
        return cls(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            cover_image=row['cover_image'] if 'cover_image' in row_keys else None
        )

class LaboratoryManager:
    """实验室管理器：内存缓存、CRUD操作、数据库同步"""
    
    def __init__(self, db_path: str, 
                 student_manager: Optional['StudentManager'] = None,
                 teacher_manager: Optional['TeacherManager'] = None):
        """
        初始化实验室管理器
        
        Args:
            db_path: 数据库路径
            student_manager: StudentManager实例（用于引用管理）
            teacher_manager: TeacherManager实例（用于引用管理）
        """
        self.db_path = Path(db_path)
        self.student_manager = student_manager
        self.teacher_manager = teacher_manager
        
        if not self.db_path.exists():
            logger.warning(f"Database not found: {self.db_path}")
        
        # 内存缓存
        self.laboratories: List[Laboratory] = []
        self._laboratories_by_id: Dict[int, Laboratory] = {}  # 按主键索引
        self._laboratories_by_name: Dict[str, List[Laboratory]] = {}  # 按名称索引（支持重名）
        
        # Dirty跟踪：需要同步到数据库的实验室ID集合
        self._dirty_laboratories: Set[int] = set()
        self._deleted_laboratories: Set[int] = set()  # 已删除的实验室ID（用于数据库同步）
        
        # 初始化数据库表
        self._init_db()
        # 初始化时加载所有数据
        self._load_all_from_db()
    
    def _get_db_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """初始化数据库表"""
        if not self.db_path.exists():
            return
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 主表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS laboratories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    cover_image TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 检查并添加cover_image字段（如果不存在）
            try:
                cursor.execute("ALTER TABLE laboratories ADD COLUMN cover_image TEXT")
            except sqlite3.OperationalError:
                # 字段已存在，忽略错误
                pass
            
            # 关联表：实验室-教师
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS laboratory_instructors (
                    laboratory_id INTEGER,
                    teacher_id INTEGER,
                    PRIMARY KEY (laboratory_id, teacher_id),
                    FOREIGN KEY (laboratory_id) REFERENCES laboratories(id) ON DELETE CASCADE,
                    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
                )
            """)
            
            # 关联表：实验室-学生
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS laboratory_students (
                    laboratory_id INTEGER,
                    student_id INTEGER,
                    PRIMARY KEY (laboratory_id, student_id),
                    FOREIGN KEY (laboratory_id) REFERENCES laboratories(id) ON DELETE CASCADE,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
                )
            """)
            
            # 关联表：实验室-学生助教
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS laboratory_assistants (
                    laboratory_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    PRIMARY KEY (laboratory_id, student_id),
                    FOREIGN KEY (laboratory_id) REFERENCES laboratories(id) ON DELETE CASCADE,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    UNIQUE (student_id)
                )
            """)
            
            # 关联表：实验室图片
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS laboratory_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    laboratory_id INTEGER NOT NULL,
                    image_path TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (laboratory_id) REFERENCES laboratories(id) ON DELETE CASCADE
                )
            """)
            
            # 关联表：实验室下载专区
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS laboratory_downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    laboratory_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    file_title TEXT,
                    file_name TEXT,
                    file_size INTEGER,
                    submitter_type TEXT,
                    submitter_id INTEGER,
                    is_public INTEGER DEFAULT 1,
                    display_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (laboratory_id) REFERENCES laboratories(id) ON DELETE CASCADE
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("实验室数据库表初始化完成")
        except sqlite3.Error as e:
            logger.error(f"初始化实验室数据库表失败: {e}")
    
    def _load_all_from_db(self):
        """从数据库加载所有实验室到内存（包括关联数据）"""
        if not self.db_path.exists():
            return
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 加载主表数据
            cursor.execute("SELECT * FROM laboratories ORDER BY id")
            rows = cursor.fetchall()
            
            self.laboratories = []
            self._laboratories_by_id.clear()
            self._laboratories_by_name.clear()
            
            for row in rows:
                lab = Laboratory.from_db_row(row)
                self.laboratories.append(lab)
                self._laboratories_by_id[lab.id] = lab
                
                # 按名称索引（支持重名）
                if lab.name not in self._laboratories_by_name:
                    self._laboratories_by_name[lab.name] = []
                self._laboratories_by_name[lab.name].append(lab)
            
            # 加载关联数据
            if self.student_manager and self.teacher_manager:
                self._load_associations(conn)
            
            # 加载图片数据
            self._load_images(conn)
            
            # 加载下载文件数据
            self._load_downloads(conn)
            
            conn.close()
            logger.info(f"已加载 {len(self.laboratories)} 个实验室到内存")
        except sqlite3.Error as e:
            logger.error(f"加载实验室数据失败: {e}")
    
    def _load_associations(self, conn: sqlite3.Connection):
        """加载实验室的关联数据（教师和学生）"""
        cursor = conn.cursor()
        
        # 加载教师关联
        cursor.execute("SELECT laboratory_id, teacher_id FROM laboratory_instructors")
        for lab_id, teacher_id in cursor.fetchall():
            lab = self._laboratories_by_id.get(lab_id)
            if lab and self.teacher_manager:
                teacher = self.teacher_manager.get_teacher_by_pk(teacher_id)
                if teacher and teacher not in lab.instructors:
                    lab.instructors.append(teacher)
        
        # 加载学生关联
        cursor.execute("SELECT laboratory_id, student_id FROM laboratory_students")
        for lab_id, student_id in cursor.fetchall():
            lab = self._laboratories_by_id.get(lab_id)
            if lab and self.student_manager:
                student = self.student_manager.get_student_by_pk(student_id)
                if student and student not in lab.students:
                    lab.students.append(student)
        
        # 加载助教关联
        cursor.execute("SELECT laboratory_id, student_id FROM laboratory_assistants")
        for lab_id, student_id in cursor.fetchall():
            lab = self._laboratories_by_id.get(lab_id)
            if lab and self.student_manager:
                student = self.student_manager.get_student_by_pk(student_id)
                if student and student not in lab.assistants:
                    lab.assistants.append(student)
    
    def _load_images(self, conn: sqlite3.Connection):
        """加载实验室图片"""
        cursor = conn.cursor()
        cursor.execute("SELECT laboratory_id, image_path FROM laboratory_images ORDER BY display_order, id")
        for lab_id, image_path in cursor.fetchall():
            lab = self._laboratories_by_id.get(lab_id)
            if lab and image_path not in lab.images:
                lab.images.append(image_path)
    
    def _load_downloads(self, conn: sqlite3.Connection):
        """加载实验室下载文件"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, laboratory_id, file_path, file_title, file_name, file_size,
                   submitter_type, submitter_id, is_public, display_order, created_at
            FROM laboratory_downloads 
            ORDER BY display_order, id
        """)
        for row in cursor.fetchall():
            lab = self._laboratories_by_id.get(row[1])  # laboratory_id
            if lab:
                download_info = {
                    'id': row[0],
                    'file_path': row[2],
                    'file_title': row[3],
                    'file_name': row[4],
                    'file_size': row[5],
                    'submitter_type': row[6],
                    'submitter_id': row[7],
                    'is_public': bool(row[8]),
                    'display_order': row[9],
                    'created_at': row[10]
                }
                lab.downloads.append(download_info)
    
    def get_laboratory_by_id(self, lab_id: int) -> Optional[Laboratory]:
        """根据ID获取实验室 - 从内存查询"""
        return self._laboratories_by_id.get(lab_id)
    
    def find_laboratories_by_name(self, name: str) -> List[Laboratory]:
        """根据名称查找实验室 - 从内存查询（支持模糊匹配）"""
        results = []
        name_lower = name.lower()
        for lab_name, labs in self._laboratories_by_name.items():
            if name_lower in lab_name.lower():
                results.extend(labs)
        return results
    
    def get_all_laboratories(self) -> List[Laboratory]:
        """获取所有实验室"""
        return self.laboratories.copy()

    def get_all(self) -> List[Laboratory]:
        """获取所有实验室（别名方法，用于兼容）"""
        return self.get_all_laboratories()
    
    def add_laboratory(self, name: str, description: Optional[str] = None,
                      instructor_ids: Optional[List[int]] = None,
                      student_ids: Optional[List[int]] = None,
                      cover_image: Optional[str] = None) -> Optional[Laboratory]:
        """
        添加新实验室到内存（标记为dirty，需要调用save()同步到数据库）
        
        Args:
            name: 实验室名称
            description: 实验室描述
            instructor_ids: 指导教师ID列表（可选）
            student_ids: 学生ID列表（可选）
        
        Returns:
            Laboratory对象，如果名称已存在则返回None
        """
        # 检查名称是否已存在（可选，根据业务需求决定是否允许重名）
        # 这里暂时允许重名
        
        try:
            # 创建新实验室对象（id暂时为0，保存到数据库后会更新）
            new_lab = Laboratory(
                id=0,  # 临时ID，保存后会更新
                name=name,
                description=description,
                cover_image=cover_image
            )
            
            # 添加关联的教师和学生（通过Manager获取对象引用）
            if instructor_ids and self.teacher_manager:
                for teacher_id in instructor_ids:
                    teacher = self.teacher_manager.get_teacher_by_pk(teacher_id)
                    if teacher:
                        new_lab.instructors.append(teacher)
            
            if student_ids and self.student_manager:
                for student_id in student_ids:
                    student = self.student_manager.get_student_by_pk(student_id)
                    if student:
                        new_lab.students.append(student)
            
            # 添加到内存缓存
            self.laboratories.append(new_lab)
            if name not in self._laboratories_by_name:
                self._laboratories_by_name[name] = []
            self._laboratories_by_name[name].append(new_lab)
            
            # 标记为dirty（新对象，id=0表示需要INSERT）
            self._dirty_laboratories.add(0)  # 使用0作为新对象的标记
            
            logger.info(f"已添加实验室到内存: {name}")
            return new_lab
        except Exception as e:
            logger.error(f"添加实验室失败: {e}")
            return None
    
    def update_laboratory(self, lab: Laboratory) -> bool:
        """
        更新实验室信息（标记为dirty，需要调用save()同步到数据库）
        
        Args:
            lab: 要更新的Laboratory对象（必须是内存中的对象实例）
        
        Returns:
            bool: 是否成功
        """
        if not lab.id or lab.id not in self._laboratories_by_id:
            logger.warning(f"实验室对象不在内存缓存中，无法更新")
            return False
        
        # 更新索引（如果名称改变）
        old_lab = self._laboratories_by_id[lab.id]
        if old_lab.name != lab.name:
            # 名称改变，更新索引
            if old_lab.name in self._laboratories_by_name:
                try:
                    self._laboratories_by_name[old_lab.name].remove(old_lab)
                    if not self._laboratories_by_name[old_lab.name]:
                        del self._laboratories_by_name[old_lab.name]
                except ValueError:
                    pass
            
            if lab.name not in self._laboratories_by_name:
                self._laboratories_by_name[lab.name] = []
            if lab not in self._laboratories_by_name[lab.name]:
                self._laboratories_by_name[lab.name].append(lab)
        
        # 标记为dirty
        self._dirty_laboratories.add(lab.id)
        
        logger.info(f"已标记实验室为dirty: {lab.name} (ID: {lab.id})")
        return True
    
    def delete_laboratory(self, lab_id: int) -> bool:
        """
        从内存删除实验室（标记为deleted，需要调用save()同步到数据库）
        
        Args:
            lab_id: 实验室ID
        
        Returns:
            bool: 是否成功
        """
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到要删除的实验室 ID: {lab_id}")
            return False
        
        # 从内存缓存中删除
        try:
            self.laboratories.remove(lab)
            del self._laboratories_by_id[lab.id]
            
            if lab.name in self._laboratories_by_name:
                try:
                    self._laboratories_by_name[lab.name].remove(lab)
                    if not self._laboratories_by_name[lab.name]:
                        del self._laboratories_by_name[lab.name]
                except ValueError:
                    pass
            
            # 如果已存在于数据库，标记为deleted
            if lab.id > 0:
                self._deleted_laboratories.add(lab.id)
            # 如果是新对象（id=0），从dirty中移除
            elif 0 in self._dirty_laboratories:
                self._dirty_laboratories.remove(0)
            
            logger.info(f"已从内存删除实验室: {lab.name} (ID: {lab.id})")
            return True
        except Exception as e:
            logger.error(f"删除实验室失败: {e}")
            return False
    
    def save(self, lab: Optional[Laboratory] = None) -> bool:
        """
        将dirty对象同步到数据库
        
        Args:
            lab: 如果提供，只保存该实验室；否则保存所有dirty实验室
        
        Returns:
            bool: 是否成功
        """
        if not self.db_path.exists():
            logger.error(f"数据库文件不存在: {self.db_path}")
            return False
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 处理删除
            if self._deleted_laboratories:
                for lab_id in list(self._deleted_laboratories):
                    # 关联表会通过CASCADE自动删除
                    cursor.execute("DELETE FROM laboratories WHERE id = ?", (lab_id,))
                self._deleted_laboratories.clear()
                logger.info("已同步删除的实验室到数据库")
            
            # 处理新增和更新
            labs_to_save = []
            if lab:
                # 保存单个实验室
                if lab.id == 0 or lab.id in self._dirty_laboratories:
                    labs_to_save.append(lab)
            else:
                # 保存所有dirty实验室
                # 先处理新对象（id=0）
                new_labs = [l for l in self.laboratories if l.id == 0]
                labs_to_save.extend(new_labs)
                
                # 再处理更新的对象（排除id=0）
                for lab_id in list(self._dirty_laboratories):
                    if lab_id != 0:  # 跳过id=0，已在上面处理
                        lab_obj = self._laboratories_by_id.get(lab_id)
                        if lab_obj and lab_obj not in labs_to_save:
                            labs_to_save.append(lab_obj)
            
            for l in labs_to_save:
                if l.id == 0:
                    # INSERT
                    cursor.execute("""
                        INSERT INTO laboratories (name, description, cover_image)
                        VALUES (?, ?, ?)
                    """, (l.name, l.description, l.cover_image))
                    new_id = cursor.lastrowid
                    # 更新对象ID和索引
                    l.id = new_id
                    self._laboratories_by_id[new_id] = l
                    # 从dirty中移除（如果存在）
                    if 0 in self._dirty_laboratories:
                        self._dirty_laboratories.remove(0)
                    logger.info(f"已插入新实验室到数据库: {l.name} (新ID: {new_id})")
                else:
                    # UPDATE
                    cursor.execute("""
                        UPDATE laboratories 
                        SET name = ?, description = ?, cover_image = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (l.name, l.description, l.cover_image, l.id))
                    self._dirty_laboratories.discard(l.id)
                    logger.info(f"已更新实验室到数据库: {l.name} (ID: {l.id})")
                
                # 保存关联数据（先删除旧关联，再插入新关联）
                cursor.execute("DELETE FROM laboratory_instructors WHERE laboratory_id = ?", (l.id,))
                cursor.execute("DELETE FROM laboratory_students WHERE laboratory_id = ?", (l.id,))
                # 注意：助教关联单独管理，不在save中保存
                
                # 插入教师关联
                if l.instructors:
                    for teacher in l.instructors:
                        if teacher and teacher.id:
                            cursor.execute("""
                                INSERT INTO laboratory_instructors (laboratory_id, teacher_id)
                                VALUES (?, ?)
                            """, (l.id, teacher.id))
                
                # 插入学生关联
                if l.students:
                    for student in l.students:
                        if student and student.id:
                            cursor.execute("""
                                INSERT INTO laboratory_students (laboratory_id, student_id)
                                VALUES (?, ?)
                            """, (l.id, student.id))
            
            conn.commit()
            conn.close()
            
            if labs_to_save:
                logger.info(f"已同步 {len(labs_to_save)} 个实验室到数据库")
            return True
        except sqlite3.Error as e:
            logger.error(f"保存实验室到数据库失败: {e}")
            return False
    
    def add_student_to_lab(self, lab_id: int, student_id: Optional[str] = None, 
                           student_pk: Optional[int] = None) -> bool:
        """
        添加学生到实验室
        
        Args:
            lab_id: 实验室ID
            student_id: 学生学号（可选）
            student_pk: 学生主键ID（可选）
        
        Returns:
            bool: 是否成功
        """
        if not self.student_manager:
            logger.warning("StudentManager未初始化，无法添加学生")
            return False
        
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return False
        
        # 查找学生
        student = None
        if student_id:
            student = self.student_manager.get_student_by_id(student_id)
        elif student_pk:
            student = self.student_manager.get_student_by_pk(student_pk)
        
        if not student:
            logger.warning(f"找不到要添加的学生")
            return False
        
        # 检查是否已存在
        if student in lab.students:
            logger.info(f"学生 {student.name} 已在实验室 {lab.name} 中")
            return True
        
        # 添加到列表
        lab.students.append(student)
        
        # 标记实验室为dirty
        self._dirty_laboratories.add(lab.id)
        
        logger.info(f"已添加学生 {student.name} 到实验室 {lab.name}")
        return True
    
    def add_teacher_to_lab(self, lab_id: int, teacher_id: Optional[str] = None,
                           teacher_pk: Optional[int] = None) -> bool:
        """
        添加教师到实验室
        
        Args:
            lab_id: 实验室ID
            teacher_id: 教师工号（可选）
            teacher_pk: 教师主键ID（可选）
        
        Returns:
            bool: 是否成功
        """
        if not self.teacher_manager:
            logger.warning("TeacherManager未初始化，无法添加教师")
            return False
        
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return False
        
        # 查找教师
        teacher = None
        if teacher_id:
            teacher = self.teacher_manager.get_teacher_by_teacher_id(teacher_id)
        elif teacher_pk:
            teacher = self.teacher_manager.get_teacher_by_pk(teacher_pk)
        
        if not teacher:
            logger.warning(f"找不到要添加的教师")
            return False
        
        # 检查是否已存在
        if teacher in lab.instructors:
            logger.info(f"教师 {teacher.name} 已在实验室 {lab.name} 中")
            return True
        
        # 检查教师是否已属于其他实验室
        if self.is_teacher_in_lab(teacher.id):
            logger.warning(f"教师 {teacher.name} 已属于其他实验室，不能添加到 {lab.name}")
            return False
        
        # 添加到列表
        lab.instructors.append(teacher)
        
        # 标记实验室为dirty
        self._dirty_laboratories.add(lab.id)
        
        logger.info(f"已添加教师 {teacher.name} 到实验室 {lab.name}")
        return True
    
    def find_student_in_lab(self, lab_id: int, name: Optional[str] = None,
                            student_id: Optional[str] = None) -> List['Student']:
        """
        在实验室中搜索学生（根据姓名或学号）
        
        Args:
            lab_id: 实验室ID
            name: 学生姓名（可选，支持模糊匹配）
            student_id: 学生学号（可选，精确匹配）
        
        Returns:
            List[Student]: 匹配的学生列表
        """
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return []
        
        results = []
        
        # 按学号精确匹配
        if student_id:
            for student in lab.students:
                if student.student_id == student_id:
                    results.append(student)
            return results
        
        # 按姓名模糊匹配
        if name:
            name_lower = name.lower()
            for student in lab.students:
                if name_lower in student.name.lower():
                    results.append(student)
            return results
        
        # 如果都不提供，返回所有学生
        return lab.students.copy()
    
    def find_teacher_in_lab(self, lab_id: int, name: Optional[str] = None,
                            teacher_id: Optional[str] = None) -> List['Teacher']:
        """
        在实验室中搜索教师（根据姓名或工号）
        
        Args:
            lab_id: 实验室ID
            name: 教师姓名（可选，支持模糊匹配）
            teacher_id: 教师工号（可选，精确匹配）
        
        Returns:
            List[Teacher]: 匹配的教师列表
        """
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return []
        
        results = []
        
        # 按工号精确匹配
        if teacher_id:
            for teacher in lab.instructors:
                if teacher.teacher_id == teacher_id:
                    results.append(teacher)
            return results
        
        # 按姓名模糊匹配
        if name:
            name_lower = name.lower()
            for teacher in lab.instructors:
                if name_lower in teacher.name.lower():
                    results.append(teacher)
            return results
        
        # 如果都不提供，返回所有教师
        return lab.instructors.copy()
    
    def remove_student_from_lab(self, lab_id: int, name: Optional[str] = None,
                                 student_id: Optional[str] = None) -> bool:
        """
        从实验室移除学生（根据姓名或学号）
        
        Args:
            lab_id: 实验室ID
            name: 学生姓名（可选，精确匹配）
            student_id: 学生学号（可选，精确匹配）
        
        Returns:
            bool: 是否成功
        """
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return False
        
        # 查找要移除的学生
        student_to_remove = None
        
        if student_id:
            # 按学号查找
            for student in lab.students:
                if student.student_id == student_id:
                    student_to_remove = student
                    break
        elif name:
            # 按姓名精确匹配（如果有多人同名，只移除第一个）
            for student in lab.students:
                if student.name == name:
                    student_to_remove = student
                    break
        
        if not student_to_remove:
            logger.warning(f"在实验室 {lab.name} 中找不到要移除的学生")
            return False
        
        # 从列表中移除
        try:
            lab.students.remove(student_to_remove)
            
            # 标记实验室为dirty
            self._dirty_laboratories.add(lab.id)
            
            logger.info(f"已从实验室 {lab.name} 移除学生 {student_to_remove.name}")
            return True
        except ValueError:
            logger.warning(f"学生不在实验室列表中")
            return False
    
    def remove_teacher_from_lab(self, lab_id: int, name: Optional[str] = None,
                                 teacher_id: Optional[str] = None) -> bool:
        """
        从实验室移除教师（根据姓名或工号）
        
        Args:
            lab_id: 实验室ID
            name: 教师姓名（可选，精确匹配）
            teacher_id: 教师工号（可选，精确匹配）
        
        Returns:
            bool: 是否成功
        """
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return False
        
        # 查找要移除的教师
        teacher_to_remove = None
        
        if teacher_id:
            # 按工号查找
            for teacher in lab.instructors:
                if teacher.teacher_id == teacher_id:
                    teacher_to_remove = teacher
                    break
        elif name:
            # 按姓名精确匹配（如果有多人同名，只移除第一个）
            for teacher in lab.instructors:
                if teacher.name == name:
                    teacher_to_remove = teacher
                    break
        
        if not teacher_to_remove:
            logger.warning(f"在实验室 {lab.name} 中找不到要移除的教师")
            return False
        
        # 从列表中移除
        try:
            lab.instructors.remove(teacher_to_remove)
            
            # 标记实验室为dirty
            self._dirty_laboratories.add(lab.id)
            
            logger.info(f"已从实验室 {lab.name} 移除教师 {teacher_to_remove.name}")
            return True
        except ValueError:
            logger.warning(f"教师不在实验室列表中")
            return False
    
    @staticmethod
    def cleanup_associations_for_student(db_path: str, student_id: int) -> bool:
        """
        清理指定学生的所有实验室关联记录（静态方法，供StudentManager调用）
        
        Args:
            db_path: 数据库路径
            student_id: 学生ID（主键）
        
        Returns:
            bool: 是否成功
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM laboratory_students WHERE student_id = ?", (student_id,))
            conn.commit()
            conn.close()
            logger.info(f"已清理学生 ID {student_id} 的实验室关联记录")
            return True
        except Exception as e:
            logger.error(f"清理学生实验室关联记录失败: {e}")
            return False
    
    @staticmethod
    def cleanup_associations_for_teacher(db_path: str, teacher_id: int) -> bool:
        """
        清理指定教师的所有实验室关联记录（静态方法，供TeacherManager调用）
        
        Args:
            db_path: 数据库路径
            teacher_id: 教师ID（主键）
        
        Returns:
            bool: 是否成功
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM laboratory_instructors WHERE teacher_id = ?", (teacher_id,))
            conn.commit()
            conn.close()
            logger.info(f"已清理教师 ID {teacher_id} 的实验室关联记录")
            return True
        except Exception as e:
            logger.error(f"清理教师实验室关联记录失败: {e}")
            return False
    
    def get_laboratory_by_teacher_id(self, teacher_id: int) -> Optional[Laboratory]:
        """
        根据教师ID查找所属的实验室
        
        Args:
            teacher_id: 教师主键ID
        
        Returns:
            Laboratory对象，如果未找到则返回None
        """
        for lab in self.laboratories:
            for teacher in lab.instructors:
                if teacher.id == teacher_id:
                    return lab
        return None
    
    def is_teacher_in_lab(self, teacher_id: int) -> bool:
        """
        检查教师是否已属于任何实验室
        
        Args:
            teacher_id: 教师主键ID
        
        Returns:
            bool: 如果已属于某个实验室则返回True
        """
        return self.get_laboratory_by_teacher_id(teacher_id) is not None
    
    def is_student_assistant_in_lab(self, student_id: int) -> bool:
        """
        检查学生是否已在其他实验室担任助教
        
        Args:
            student_id: 学生主键ID
        
        Returns:
            bool: 如果已在其他实验室担任助教则返回True
        """
        if not self.db_path.exists():
            return False
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM laboratory_assistants WHERE student_id = ?", (student_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception as e:
            logger.error(f"检查学生助教状态失败: {e}")
            return False
    
    def add_assistant_to_lab(self, lab_id: int, student_id: int) -> bool:
        """
        添加学生助教到实验室
        
        Args:
            lab_id: 实验室ID
            student_id: 学生主键ID
        
        Returns:
            bool: 是否成功
        """
        if not self.student_manager:
            logger.warning("StudentManager未初始化，无法添加助教")
            return False
        
        if not self.db_path.exists():
            logger.error(f"数据库文件不存在: {self.db_path}")
            return False
        
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return False
        
        # 检查学生是否为实验室成员
        student = self.student_manager.get_student_by_pk(student_id)
        if not student:
            logger.warning(f"找不到学生 ID: {student_id}")
            return False
        
        if student not in lab.students:
            logger.warning(f"学生 {student.name} 不是实验室 {lab.name} 的成员，无法添加为助教")
            return False
        
        # 检查学生是否已在其他实验室担任助教
        if self.is_student_assistant_in_lab(student_id):
            logger.warning(f"学生 {student.name} 已在其他实验室担任助教")
            return False
        
        # 检查是否已经是助教
        if student in lab.assistants:
            logger.info(f"学生 {student.name} 已是实验室 {lab.name} 的助教")
            return True
        
        # 添加到内存
        lab.assistants.append(student)
        
        # 保存到数据库
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO laboratory_assistants (laboratory_id, student_id)
                VALUES (?, ?)
            """, (lab.id, student.id))
            conn.commit()
            conn.close()
            logger.info(f"已添加学生 {student.name} 为实验室 {lab.name} 的助教")
            return True
        except sqlite3.IntegrityError as e:
            logger.error(f"添加助教失败（可能违反唯一约束）: {e}")
            lab.assistants.remove(student)  # 回滚内存更改
            return False
        except Exception as e:
            logger.error(f"添加助教失败: {e}")
            lab.assistants.remove(student)  # 回滚内存更改
            return False
    
    def remove_assistant_from_lab(self, lab_id: int, student_id: int) -> bool:
        """
        从实验室移除学生助教
        
        Args:
            lab_id: 实验室ID
            student_id: 学生主键ID
        
        Returns:
            bool: 是否成功
        """
        if not self.student_manager:
            logger.warning("StudentManager未初始化，无法移除助教")
            return False
        
        if not self.db_path.exists():
            logger.error(f"数据库文件不存在: {self.db_path}")
            return False
        
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return False
        
        student = self.student_manager.get_student_by_pk(student_id)
        if not student:
            logger.warning(f"找不到学生 ID: {student_id}")
            return False
        
        # 从内存移除
        if student not in lab.assistants:
            logger.warning(f"学生 {student.name} 不是实验室 {lab.name} 的助教")
            return False
        
        try:
            lab.assistants.remove(student)
            
            # 从数据库删除
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM laboratory_assistants 
                WHERE laboratory_id = ? AND student_id = ?
            """, (lab.id, student.id))
            conn.commit()
            conn.close()
            logger.info(f"已从实验室 {lab.name} 移除学生助教 {student.name}")
            return True
        except ValueError:
            logger.warning(f"学生不在助教列表中")
            return False
        except Exception as e:
            logger.error(f"移除助教失败: {e}")
            return False

    def add_laboratory_image(self, lab_id: int, image_path: str) -> bool:
        """
        添加实验室图片
        
        Args:
            lab_id: 实验室ID
            image_path: 图片路径（相对于files目录）
        
        Returns:
            bool: 是否成功
        """
        if not self.db_path.exists():
            logger.error(f"数据库文件不存在: {self.db_path}")
            return False
        
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return False
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 获取当前最大排序值
            cursor.execute("SELECT MAX(display_order) FROM laboratory_images WHERE laboratory_id = ?", (lab_id,))
            max_order = cursor.fetchone()[0] or 0
            
            # 插入图片记录
            cursor.execute("""
                INSERT INTO laboratory_images (laboratory_id, image_path, display_order)
                VALUES (?, ?, ?)
            """, (lab_id, image_path, max_order + 1))
            
            conn.commit()
            conn.close()
            
            # 更新内存
            if image_path not in lab.images:
                lab.images.append(image_path)
            
            logger.info(f"已添加图片到实验室 {lab.name}: {image_path}")
            return True
        except sqlite3.Error as e:
            logger.error(f"添加实验室图片失败: {e}")
            return False
    
    def delete_laboratory_image(self, lab_id: int, image_path: str) -> bool:
        """
        删除实验室图片
        
        Args:
            lab_id: 实验室ID
            image_path: 图片路径
        
        Returns:
            bool: 是否成功
        """
        if not self.db_path.exists():
            logger.error(f"数据库文件不存在: {self.db_path}")
            return False
        
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return False
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 删除数据库记录
            cursor.execute("DELETE FROM laboratory_images WHERE laboratory_id = ? AND image_path = ?", 
                          (lab_id, image_path))
            
            conn.commit()
            conn.close()
            
            # 更新内存
            if image_path in lab.images:
                lab.images.remove(image_path)
            
            logger.info(f"已删除实验室 {lab.name} 的图片: {image_path}")
            return True
        except sqlite3.Error as e:
            logger.error(f"删除实验室图片失败: {e}")
            return False
    
    def get_laboratory_images(self, lab_id: int) -> List[str]:
        """
        获取实验室的所有图片路径
        
        Args:
            lab_id: 实验室ID
        
        Returns:
            List[str]: 图片路径列表
        """
        lab = self._laboratories_by_id.get(lab_id)
        if lab:
            return lab.images.copy()
        return []
    
    # ============================================================
    # 文件移动方法（用于成果审核流程）
    # ============================================================
    
    def move_file_to_album(
        self,
        lab_id: int,
        source_path: Path,
        files_base_dir: Path
    ) -> tuple:
        """
        移动文件到实验室相册目录
        
        Args:
            lab_id: 实验室ID
            source_path: 源文件路径
            files_base_dir: 文件存储根目录（已弃用，由统一文件管理器管理）
        
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (是否成功, 目标路径, 错误信息)
        """
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            return False, None, f"找不到实验室 ID: {lab_id}"
        
        source_path = Path(source_path)
        if not source_path.exists():
            return False, None, f"源文件不存在: {source_path}"
        
        try:
            from backend.services.unified_file_manager import get_unified_file_manager, LabFileType
            
            file_manager = get_unified_file_manager()
            
            # 使用统一文件管理器保存实验室图片（从路径直接保存，移动源文件）
            abs_path, relative_path = file_manager.save_lab_file_from_path(
                lab_id, LabFileType.PHOTOS, source_path, source_path.name, delete_source=True
            )
            
            # 记录到数据库
            self.add_laboratory_image(lab_id, relative_path)
            
            logger.info(f"文件已移动到实验室相册: {abs_path}")
            return True, abs_path, None
            
        except Exception as e:
            logger.error(f"移动文件到相册失败: {e}", exc_info=True)
            return False, None, str(e)
    
    def move_file_to_downloads(
        self,
        lab_id: int,
        source_path: Path,
        files_base_dir: Path,
        file_title: Optional[str] = None,
        submitter_type: Optional[str] = None,
        submitter_id: Optional[int] = None
    ) -> tuple:
        """
        移动文件到实验室下载专区
        
        Args:
            lab_id: 实验室ID
            source_path: 源文件路径
            files_base_dir: 文件存储根目录（已弃用，由统一文件管理器管理）
            file_title: 文件标题（可选，用于显示和重命名）
            submitter_type: 提交人类型
            submitter_id: 提交人ID
        
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (是否成功, 目标路径, 错误信息)
        """
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            return False, None, f"找不到实验室 ID: {lab_id}"
        
        source_path = Path(source_path)
        if not source_path.exists():
            return False, None, f"源文件不存在: {source_path}"
        
        try:
            from backend.services.unified_file_manager import get_unified_file_manager, LabFileType
            
            # 获取原始文件信息
            original_file_name = source_path.name
            file_size = source_path.stat().st_size
            
            # 确定目标文件名
            target_filename = original_file_name
            if file_title:
                # 使用提供的标题作为文件名（保留原扩展名）
                safe_title = "".join(c for c in file_title if c.isalnum() or c in '._- ')
                target_filename = f"{safe_title}{source_path.suffix}"
            
            file_manager = get_unified_file_manager()
            
            # 使用统一文件管理器保存实验室下载文件（从路径直接保存，移动源文件）
            abs_path, relative_path = file_manager.save_lab_file_from_path(
                lab_id, LabFileType.DOWNLOADS, source_path, target_filename, delete_source=True
            )
            
            display_title = file_title or original_file_name
            
            # 记录到数据库
            self.add_download_file(
                lab_id=lab_id,
                file_path=relative_path,
                file_title=display_title,
                file_name=original_file_name,
                file_size=file_size,
                submitter_type=submitter_type,
                submitter_id=submitter_id,
                is_public=True
            )
            
            logger.info(f"文件已移动到实验室下载区: {abs_path}")
            return True, abs_path, None
            
        except Exception as e:
            logger.error(f"移动文件到下载区失败: {e}", exc_info=True)
            return False, None, str(e)
    
    # ============================================================
    # 下载专区管理
    # ============================================================
    
    def add_download_file(
        self,
        lab_id: int,
        file_path: str,
        file_title: str,
        file_name: str,
        file_size: int,
        submitter_type: str = None,
        submitter_id: int = None,
        is_public: bool = True
    ) -> Optional[int]:
        """
        添加实验室下载文件记录
        
        Args:
            lab_id: 实验室ID
            file_path: 文件路径（相对于files目录）
            file_title: 文件标题（用于显示）
            file_name: 原始文件名
            file_size: 文件大小(字节)
            submitter_type: 提交人类型
            submitter_id: 提交人ID
            is_public: 是否公开
        
        Returns:
            新记录的ID，失败返回None
        """
        if not self.db_path.exists():
            logger.error(f"数据库文件不存在: {self.db_path}")
            return None
        
        lab = self._laboratories_by_id.get(lab_id)
        if not lab:
            logger.warning(f"找不到实验室 ID: {lab_id}")
            return None
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 获取当前最大排序值
            cursor.execute("SELECT MAX(display_order) FROM laboratory_downloads WHERE laboratory_id = ?", (lab_id,))
            max_order = cursor.fetchone()[0] or 0
            
            # 插入下载文件记录
            cursor.execute("""
                INSERT INTO laboratory_downloads 
                (laboratory_id, file_path, file_title, file_name, file_size, 
                 submitter_type, submitter_id, is_public, display_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (lab_id, file_path, file_title, file_name, file_size,
                  submitter_type, submitter_id, 1 if is_public else 0, max_order + 1))
            
            download_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # 更新内存
            download_info = {
                'id': download_id,
                'file_path': file_path,
                'file_title': file_title,
                'file_name': file_name,
                'file_size': file_size,
                'submitter_type': submitter_type,
                'submitter_id': submitter_id,
                'is_public': is_public,
                'display_order': max_order + 1,
                'created_at': None  # 由数据库自动生成
            }
            lab.downloads.append(download_info)
            
            logger.info(f"已添加下载文件到实验室 {lab.name}: {file_title}")
            return download_id
        except sqlite3.Error as e:
            logger.error(f"添加实验室下载文件失败: {e}")
            return None
    
    def delete_download_file(self, lab_id: int, download_id: int) -> bool:
        """
        删除实验室下载文件记录

        Args:
            lab_id: 实验室ID
            download_id: 下载文件记录ID

        Returns:
            bool: 是否成功
        """
        if not self.db_path.exists():
            logger.error(f"数据库文件不存在: {self.db_path}")
            return False

        lab = self._laboratories_by_id.get(lab_id)
        is_orphan = lab is None

        if is_orphan:
            logger.warning(f"找不到实验室 ID: {lab_id}，文件记录可能是孤立的，将尝试删除")

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # 获取文件路径（用于后续可能的文件删除）
            cursor.execute(
                "SELECT file_path FROM laboratory_downloads WHERE id = ? AND laboratory_id = ?",
                (download_id, lab_id)
            )
            row = cursor.fetchone()
            if not row:
                conn.close()
                logger.warning(f"找不到下载文件记录 ID: {download_id}")
                return False

            file_path = row[0]

            # 删除数据库记录
            cursor.execute(
                "DELETE FROM laboratory_downloads WHERE id = ? AND laboratory_id = ?",
                (download_id, lab_id)
            )

            conn.commit()
            conn.close()

            # 只有在实验室存在时才更新内存
            if lab:
                lab.downloads = [d for d in lab.downloads if d.get('id') != download_id]
                logger.info(f"已删除实验室 {lab.name} 的下载文件记录: {download_id}")
            else:
                logger.info(f"已删除孤立的下载文件记录: {download_id} (lab_id={lab_id})")

            return True
        except sqlite3.Error as e:
            logger.error(f"删除实验室下载文件失败: {e}")
            return False
    
    def get_download_by_id(self, download_id: int) -> Optional[Dict]:
        """
        按 id 查询单条实验室下载记录（用于路由层获取 laboratory_id、file_path 等）。

        Returns:
            含 laboratory_id、file_path、file_name、file_title 等键的字典，不存在则 None
        """
        if not self.db_path.exists():
            return None
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, laboratory_id, file_path, file_name, file_title FROM laboratory_downloads WHERE id = ?",
                (download_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "laboratory_id": row[1],
                "file_path": row[2],
                "file_name": row[3],
                "file_title": row[4],
            }
        except sqlite3.Error:
            return None
        finally:
            if conn:
                conn.close()

    def get_laboratory_downloads(self, lab_id: int) -> List[Dict]:
        """
        获取实验室下载文件列表
        
        Args:
            lab_id: 实验室ID
        
        Returns:
            下载文件列表
        """
        lab = self._laboratories_by_id.get(lab_id)
        if lab:
            return lab.downloads.copy()
        return []
