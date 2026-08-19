"""M1 后半①：admin 写路径切 users 真源后的登录闭环回归。

路由层验证采用轻量闭环：写 users（ORM 仓储）→ verify_user（users 优先）走通；
旧表镜像写仍由 Manager 负责（视图化前保留），此处不重复测。
"""
import sqlite3
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.schemas import USERS_DDL


@pytest.fixture()
def migrated_db(tmp_path):
    """旧三表 + users 的已迁移库，s1 为存量学生（登录回退路径安全）。"""
    db = tmp_path / "u.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE admins(username TEXT PRIMARY KEY, name TEXT, password_hash TEXT, user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE students(student_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT DEFAULT 'student', user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE teachers(teacher_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT DEFAULT 'teacher', user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
    conn.execute(USERS_DDL)
    conn.execute("INSERT INTO students VALUES ('s1','张三',?,'student',1,0)",
                 (generate_password_hash('OldPass123'),))
    conn.execute("INSERT INTO users(login_code,name,role,password_hash) VALUES ('s1','张三','student',?)",
                 (generate_password_hash('OldPass123'),))
    conn.commit()
    conn.close()
    return str(db)


@pytest.fixture(autouse=True)
def _reset_engine():
    import backend.orm.base as b
    b.reset_engine()
    yield
    if b._engine is not None:
        b._engine.dispose()
    b.reset_engine()


def _inject_engine(db):
    """verify_user 的 ORM 分支走进程级 engine——测试须指向测试库。"""
    import backend.orm.base as b
    b._engine = b.build_engine(db)
    b._SessionLocal = None


class TestAdminWriteUsersLoop:
    def test_reset_password_writes_users_then_login(self, migrated_db):
        """admin 重置密码（等价调用）→ users 新密码生效，登录走 users 优先。"""
        _inject_engine(migrated_db)
        from backend.orm.repositories import UserRepository
        from app.auth import verify_user

        new_hash = generate_password_hash('NewPass456!')
        assert UserRepository.update_password('s1', new_hash, needs_password_change=1) == 1
        # 路由同时镜像旧表（视图化前保留），与 users 保持一致
        conn = sqlite3.connect(migrated_db)
        conn.execute("UPDATE students SET password_hash=? WHERE student_id='s1'", (new_hash,))
        conn.commit()
        conn.close()

        info = verify_user('s1', 'NewPass456!', migrated_db)
        assert info is not None
        assert info['user_type'] == 'student'
        assert info['needs_password_change'] is True
        # 旧密码已失效（users 优先分支，非旧表回退）
        assert verify_user('s1', 'OldPass123', migrated_db) is None

    def test_create_student_writes_users_then_login(self, migrated_db):
        """admin 创建学生（等价调用）→ users 落库；旧表无此行，仅 users 能登录。"""
        _inject_engine(migrated_db)
        from backend.orm.repositories import UserRepository
        from app.auth import verify_user

        pwd_hash = generate_password_hash('InitPass789!')
        UserRepository.create_user(
            's9', '新学生', 'student', pwd_hash, needs_password_change=1, major='计算机')

        info = verify_user('s9', 'InitPass789!', migrated_db)
        assert info is not None
        assert info['user_type'] == 'student' and info['name'] == '新学生'
        assert info['needs_password_change'] is True

    def test_create_teacher_writes_users_then_login(self, migrated_db):
        """admin 创建教师（等价调用）→ users 落库并可登录。"""
        _inject_engine(migrated_db)
        from backend.orm.repositories import UserRepository
        from app.auth import verify_user

        pwd_hash = generate_password_hash('InitPass789!')
        UserRepository.create_user(
            't9', '新教师', 'teacher', pwd_hash, needs_password_change=1,
            department='信息学院', title='讲师')

        info = verify_user('t9', 'InitPass789!', migrated_db)
        assert info is not None
        assert info['user_type'] == 'teacher'


class TestRouteNoSyncBridge:
    """守卫：写路径切 users 后，路由层不得再出现 users_sync 写桥调用。"""

    @pytest.mark.parametrize("route_file", [
        "app/routes/admin.py",
        "app/routes/user_common.py",
    ])
    def test_no_sync_bridge_in_routes(self, route_file):
        text = (PROJECT_ROOT / route_file).read_text(encoding="utf-8")
        assert "insert_user_row" not in text
        assert "sync_user_row" not in text
