"""UserRepository 写路径单测（M1 后半①：users 真源写）。

覆盖：幂等创建（upsert）、改密、资料更新白名单。
"""
import sqlite3

import pytest


@pytest.fixture(autouse=True)
def _reset_engine():
    import backend.orm.base as b
    b.reset_engine()
    yield
    if b._engine is not None:
        b._engine.dispose()
    b.reset_engine()


def _build_db(tmp_path, name="users_write.db"):
    """建完整 users 表并注入 ORM engine（测试库与生产隔离）。"""
    from tests.fixtures.schemas import USERS_DDL
    db = tmp_path / name
    conn = sqlite3.connect(str(db))
    conn.execute(USERS_DDL)
    conn.commit()
    conn.close()

    import backend.orm.base as b
    b._engine = b.build_engine(str(db))
    b._SessionLocal = None
    return db


class TestCreateUser:
    def test_create_user_and_read_back(self, tmp_path):
        from backend.orm.repositories import UserRepository
        _build_db(tmp_path)

        uid = UserRepository.create_user(
            '20250001', '张三', 'student', 'hash1', needs_password_change=1,
            major='计算机', phone='13800000000')

        u = UserRepository.get_by_login_code('20250001')
        assert u is not None
        assert u.id == uid
        assert u.name == '张三'
        assert u.role == 'student'
        assert u.password_hash == 'hash1'
        assert u.needs_password_change == 1
        assert u.major == '计算机'
        assert u.phone == '13800000000'
        assert u.created_at is not None and u.updated_at is not None

    def test_create_user_idempotent_upsert(self, tmp_path):
        """同 login_code 重复创建不报错，返回同一 id，资料被更新。"""
        from backend.orm.repositories import UserRepository
        _build_db(tmp_path)

        uid1 = UserRepository.create_user('20250002', '李四', 'student', 'h1')
        uid2 = UserRepository.create_user(
            '20250002', '李四', 'student', 'h2', major='软件工程')

        assert uid1 == uid2
        u = UserRepository.get_by_login_code('20250002')
        assert u.password_hash == 'h2'
        assert u.major == '软件工程'

    def test_create_user_ignores_whitelist_violations(self, tmp_path):
        """白名单外字段（login_code/未知键）不写入，主键不可被改写。"""
        from backend.orm.repositories import UserRepository
        _build_db(tmp_path)

        uid = UserRepository.create_user(
            '20250003', '王五', 'student', 'h1', bogus_field='x')
        u = UserRepository.get_by_login_code('20250003')
        assert u.id == uid


class TestUpdatePassword:
    def test_update_password_success(self, tmp_path):
        from backend.orm.repositories import UserRepository
        _build_db(tmp_path)
        UserRepository.create_user('20250004', '赵六', 'teacher', 'old')

        assert UserRepository.update_password('20250004', 'newhash', needs_password_change=1) == 1
        u = UserRepository.get_by_login_code('20250004')
        assert u.password_hash == 'newhash'
        assert u.needs_password_change == 1

    def test_update_password_missing_user(self, tmp_path):
        from backend.orm.repositories import UserRepository
        _build_db(tmp_path)
        assert UserRepository.update_password('nobody', 'h') == 0


class TestUpdateProfile:
    def test_update_profile_whitelist(self, tmp_path):
        from backend.orm.repositories import UserRepository
        _build_db(tmp_path)
        UserRepository.create_user('20250005', '孙七', 'student', 'h1', major='数学')

        assert UserRepository.update_profile(
            '20250005', major='物理', phone='139', user_activated=0,
            bogus_field='x') == 1
        u = UserRepository.get_by_login_code('20250005')
        assert u.major == '物理'
        assert u.phone == '139'
        assert u.user_activated == 0

    def test_update_profile_missing_user(self, tmp_path):
        from backend.orm.repositories import UserRepository
        _build_db(tmp_path)
        assert UserRepository.update_profile('nobody', major='x') == 0
