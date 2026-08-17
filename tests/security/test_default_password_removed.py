"""P1-2 回归测试：默认密码兜底必须已移除（空 hash 拒绝登录）。"""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from werkzeug.security import generate_password_hash

from app.auth import verify_user


@pytest.fixture()
def tmp_users_db(tmp_path):
    """构造含（激活/未激活/空hash/正常hash）四类用户的临时库。"""
    db = tmp_path / "users.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE admins(username TEXT PRIMARY KEY, name TEXT, password_hash TEXT, user_activated INTEGER DEFAULT 1)")
    conn.execute("CREATE TABLE students(student_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT DEFAULT 'student', user_activated INTEGER DEFAULT 1)")
    conn.execute("CREATE TABLE teachers(teacher_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT DEFAULT 'teacher', user_activated INTEGER DEFAULT 1)")
    conn.execute("INSERT INTO students VALUES ('s1','正常学生',?, 'student', 1)", (generate_password_hash('GoodPass123'),))
    conn.execute("INSERT INTO students VALUES ('s2','空hash学生', NULL, 'student', 1)")
    conn.execute("INSERT INTO teachers VALUES ('t1','空hash教师', NULL, 'teacher', 1)")
    conn.execute("INSERT INTO teachers VALUES ('t2','未激活教师', ?, 'teacher', 0)", (generate_password_hash('GoodPass123'),))
    conn.commit()
    conn.close()
    return str(db)


DEFAULT_PWD_CANDIDATES = ['P@ss301', 'P@ss301\n', '123456', 'password']


@pytest.mark.parametrize("pwd", DEFAULT_PWD_CANDIDATES)
def test_empty_hash_rejects_default_password(tmp_users_db, pwd):
    """空 hash 用户用任何候选默认密码都不得登录（修复前 P@ss301 可进）。"""
    assert verify_user('s2', pwd, tmp_users_db) is None
    assert verify_user('t1', pwd, tmp_users_db) is None


def test_normal_login_still_works(tmp_users_db):
    assert verify_user('s1', 'GoodPass123', tmp_users_db) is not None


def test_wrong_password_rejected(tmp_users_db):
    assert verify_user('s1', 'wrong', tmp_users_db) is None


def test_inactive_user_rejected(tmp_users_db):
    assert verify_user('t2', 'GoodPass123', tmp_users_db) is None


def test_no_fallback_code_remains():
    """源码防回退：auth.py 不得再引用 get_default_password 兜底。"""
    src = (PROJECT_ROOT / 'app' / 'auth.py').read_text(encoding='utf-8')
    assert 'get_default_password' not in src, '默认密码兜底代码回退了'
