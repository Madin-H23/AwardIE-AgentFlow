"""P0-6 回归测试：写后定向维护 + read-through 回源（student/teacher）。"""
import sqlite3
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

STUDENT_DDL = """CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    major TEXT, grade TEXT, phone TEXT, qq TEXT, skills TEXT,
    user_activated INTEGER DEFAULT 1, password_hash TEXT, role TEXT DEFAULT 'student',
    needs_password_change INTEGER NOT NULL DEFAULT 0)"""
TEACHER_DDL = """CREATE TABLE teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    department TEXT, title TEXT, phone TEXT, id_number TEXT, qq TEXT, skills TEXT,
    user_activated INTEGER DEFAULT 1, password_hash TEXT, role TEXT DEFAULT 'teacher',
    needs_password_change INTEGER NOT NULL DEFAULT 0)"""


@pytest.fixture()
def db(tmp_path):
    d = tmp_path / "m.db"
    conn = sqlite3.connect(str(d))
    conn.execute(STUDENT_DDL)
    conn.execute(TEACHER_DDL)
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


class TestTargetedMaintenance:
    def test_add_no_full_reload(self, sm, monkeypatch):
        """add 后不再触发全表重载（性能核心断言）。"""
        called = {"n": 0}
        orig = sm._load_all_from_db
        monkeypatch.setattr(sm, "_load_all_from_db", lambda: called.__setitem__("n", called["n"] + 1))
        sm.add_student("20230001", "张三", major="计科")
        assert called["n"] == 0                       # 全表重载零次
        assert sm.get_student_by_student_id("20230001").name == "张三"

    def test_update_refresh_single(self, sm, monkeypatch):
        sm.add_student("20230001", "张三")
        monkeypatch.setattr(sm, "_load_all_from_db", lambda: pytest.fail("update 不得全表重载"))
        sm.update_student(sm.students[0].id, name="李四")
        assert sm.get_student_by_id(sm.students[0].id).name == "李四"

    def test_update_needs_password_change_persists(self, sm):
        """暗雷修复：update 白名单含 needs_password_change（阶段二曾被静默忽略）。"""
        s = sm.add_student("20230001", "张三", password_hash=generate_password_hash("x"))
        sm.update_student(s.id, needs_password_change=1)
        conn = sqlite3.connect(str(sm.db_path))
        v = conn.execute("SELECT needs_password_change FROM students WHERE id=?", (s.id,)).fetchone()[0]
        conn.close()
        assert v == 1

    def test_delete_removes_from_cache(self, sm):
        s = sm.add_student("20230001", "张三")
        sm.delete_student(s.id)
        assert sm.get_student_by_id(s.id) is None
        assert all(x.student_id != "20230001" for x in sm.students)


class TestReadThrough:
    def test_miss_falls_back_to_db(self, sm):
        """另一进程写入（直连 DB）后，本 Manager 查询 miss 能回源读到（多 worker 一致性缓解）。"""
        sid = sm.add_student("20230001", "张三").id
        # 模拟 worker B 直连写库
        conn = sqlite3.connect(str(sm.db_path))
        conn.execute("INSERT INTO students (student_id, name) VALUES ('20230002', '外部写入')")
        conn.commit()
        conn.close()
        # worker A 内存无此人——read-through 回源
        got = sm.get_student_by_student_id("20230002")
        assert got is not None and got.name == "外部写入"
        assert any(x.student_id == "20230002" for x in sm.students)   # 已回填缓存

    def test_teacher_miss_fallback(self, tm):
        conn = sqlite3.connect(str(tm.db_path))
        conn.execute("INSERT INTO teachers (teacher_id, name) VALUES ('T999', '外部教师')")
        conn.commit()
        conn.close()
        got = tm.get_teacher_by_teacher_id("T999")
        assert got is not None and got.name == "外部教师"


class TestTeacherSame:
    def test_teacher_full_cycle_no_reload(self, tm, monkeypatch):
        monkeypatch.setattr(tm, "_load_all_from_db", lambda: pytest.fail("不得全表重载"))
        t = tm.add_teacher("T001", "王老师", department="计科系")
        tm.update_teacher(t.id, title="教授")
        tm.delete_teacher(t.id)
