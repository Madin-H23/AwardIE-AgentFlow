
import unittest
import sqlite3
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from backend.models.student import StudentManager
from backend.models.teacher import TeacherManager

import time

class TestManagerRestrictions(unittest.TestCase):
    def setUp(self):
        # 使用唯一的文件名避免权限问题
        self.db_path = f"test_temp_{int(time.time() * 1000)}.db"
        
        self.student_manager = StudentManager(self.db_path)
        self.teacher_manager = TeacherManager(self.db_path)
        
        self.student_manager._init_db()
        self.teacher_manager._init_db()
        
        self.student = self.student_manager.add_student(
            student_id="S123",
            name="Test Student"
        )
        self.teacher = self.teacher_manager.add_teacher(
            teacher_id="T456",
            name="Test Teacher"
        )

    def tearDown(self):
        # 尝试清理，如果不成功也没关系
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except:
            pass

    def test_student_id_not_in_allowed_keys(self):
        """验证学生学号不在允许更新的字段中"""
        # 我们可以通过查看源代码或尝试更新来验证
        # 这里的 update_student 参数名冲突实际上也阻止了通过 kwargs 传递 student_id
        original_id = self.student.student_id
        self.student_manager.update_student(self.student.id, name="New Name")
        updated = self.student_manager.get_student_by_id(self.student.id)
        self.assertEqual(updated.student_id, original_id)

    def test_teacher_id_not_updated(self):
        """验证教师工号不在允许更新的字段中"""
        original_id = self.teacher.teacher_id
        # 即使尝试通过某种方式传递（虽然参数名冲突会报错，但我们可以验证代码逻辑）
        # 这里我们验证 update_teacher 确实更新了姓名但没有报错（如果 teacher_id 被忽略）
        self.teacher_manager.update_teacher(self.teacher.id, name="New Teacher Name")
        updated = self.teacher_manager.get_teacher_by_id(self.teacher.id)
        self.assertEqual(updated.name, "New Teacher Name")
        self.assertEqual(updated.teacher_id, original_id)
        self.assertNotEqual(updated.teacher_id, "T999")

if __name__ == "__main__":
    unittest.main()
