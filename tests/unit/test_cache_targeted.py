"""读路径缓存维护回归（M1 后半②：视图化后旧三表为视图，Manager 只读）。

写路径已迁 users（UserRepository），add/update/delete 用例随写方法删除；
保留 read-through 读缓存语义验证（视图作为数据源的读一致性）。
"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.schemas import (USERS_DDL, STUDENTS_VIEW_DDL, TEACHERS_VIEW_DDL)


@pytest.fixture()
def db(tmp_path):
    """视图化库：users 实体表 + 旧三表视图（与迁移 0002 同源定义）。"""
    d = tmp_path / "m.db"
    conn = sqlite3.connect(str(d))
    conn.execute(USERS_DDL)
    conn.execute(STUDENTS_VIEW_DDL)
    conn.execute(TEACHERS_VIEW_DDL)
    conn.execute("INSERT INTO users (login_code, name, role) VALUES ('20230001', '张三', 'student')")
    conn.execute("INSERT INTO users (login_code, name, role) VALUES ('T001', '王老师', 'teacher')")
    conn.commit()
    conn.close()
    return d


@pytest.fixture()
def sm(db):
    from backend.models.student import StudentManager
    return StudentManager(str(db))


@pytest.fixture()
def tm(db):
    from backend.models.teacher import TeacherManager
    return TeacherManager(str(db))


class TestReadThrough:
    def test_miss_falls_back_to_db(self, sm):
        """视图化后：Manager 读视图（users 数据）；外部直写 users 后 miss 回源读到。"""
        # 模拟 worker B 直连写 users
        conn = sqlite3.connect(str(sm.db_path))
        conn.execute("INSERT INTO users (login_code, name, role) VALUES ('20230002', '外部写入', 'student')")
        conn.commit()
        conn.close()
        # worker A 内存无此人——read-through 回源（经视图）
        got = sm.get_student_by_student_id("20230002")
        assert got is not None and got.name == "外部写入"
        assert any(x.student_id == "20230002" for x in sm.students)   # 已回填缓存

    def test_teacher_miss_fallback(self, tm):
        conn = sqlite3.connect(str(tm.db_path))
        conn.execute("INSERT INTO users (login_code, name, role) VALUES ('T999', '外部教师', 'teacher')")
        conn.commit()
        conn.close()
        got = tm.get_teacher_by_teacher_id("T999")
        assert got is not None and got.name == "外部教师"

    def test_students_view_lists_users_role_student(self, sm):
        """视图读路径：students 视图 = users 中 role='student' 的行。"""
        assert sm.get_student_by_student_id("20230001").name == "张三"
        assert sm.get_student_by_student_id("T001") is None     # teacher 不在学生视图
