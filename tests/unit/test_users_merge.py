"""8.5 渐进第一批回归：users 搬迁对账 / verify_user users 优先 / 双写同步。"""
import sqlite3
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash, check_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

def _require_real_db():
    """共享守卫（schemas.require_real_db）：文件存在且 users 表存在，否则 skip（R-028 升级）。"""
    from tests.fixtures.schemas import require_real_db
    require_real_db()

from tests.fixtures.schemas import USERS_DDL


@pytest.fixture()
def migrated_db(tmp_path):
    """构造已迁移的库：旧三表 + users + old_user_map 同步。"""
    db = tmp_path / "u.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE admins(username TEXT PRIMARY KEY, name TEXT, password_hash TEXT, user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE students(student_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT DEFAULT 'student', user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE teachers(teacher_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT DEFAULT 'teacher', user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
    conn.execute(USERS_DDL)   # 共享 schema（CI 无真实库文件，不得反射）
    conn.execute("INSERT INTO students VALUES ('s1','张三',?,'student',1,0)", (generate_password_hash('GoodPass123'),))
    conn.execute("INSERT INTO users(login_code,name,role,password_hash) VALUES ('s1','张三','student',?)",
                 (generate_password_hash('GoodPass123'),))
    conn.commit()
    conn.close()
    return str(db)


class TestVerifyUsersFirst:
    def test_login_via_users(self, migrated_db):
        from app.auth import verify_user
        info = verify_user('s1', 'GoodPass123', migrated_db)
        assert info and info['user_type'] == 'student' and info['needs_password_change'] is False

    def test_wrong_password_rejected(self, migrated_db):
        from app.auth import verify_user
        assert verify_user('s1', 'wrong', migrated_db) is None

    def test_fallback_when_users_absent(self, tmp_path):
        """未迁移库（无 users 表）回退旧三表仍可登录。"""
        db = tmp_path / "old.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE students(student_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT DEFAULT 'student', user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
        conn.execute("INSERT INTO students VALUES ('s1','张三',?,'student',1,0)", (generate_password_hash('GoodPass123'),))
        conn.commit(); conn.close()
        from app.auth import verify_user
        assert verify_user('s1', 'GoodPass123', str(db)) is not None

    def test_self_heal_on_old_path(self, migrated_db):
        """旧表改了新密码（users 未同步）→ 旧表登录成功且自愈回写 users。"""
        new_hash = generate_password_hash('NewPass456!')
        conn = sqlite3.connect(migrated_db)
        conn.execute("UPDATE students SET password_hash=? WHERE student_id='s1'", (new_hash,))
        conn.commit(); conn.close()
        from app.auth import verify_user
        info = verify_user('s1', 'NewPass456!', migrated_db)      # 走旧表路径 + 自愈
        assert info is not None
        conn = sqlite3.connect(migrated_db)
        u_hash = conn.execute("SELECT password_hash FROM users WHERE login_code='s1'").fetchone()[0]
        conn.close()
        assert check_password_hash(u_hash, 'NewPass456!')          # users 已同步新密码


class TestMigrationIntegrity:
    def test_real_db_counts(self):
        """真实库对账：users 总数 == 三表之和；映射无空（CI 无库则跳过）。"""
        _require_real_db()
        conn = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
        n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        n_old = sum(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("students", "teachers", "admins"))
        n_null = conn.execute("SELECT COUNT(*) FROM old_user_map WHERE new_user_id IS NULL").fetchone()[0]
        conn.close()
        assert n_users == n_old == 1832
        assert n_null == 0
