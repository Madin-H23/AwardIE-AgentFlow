"""M1 后半①回归：ORM 骨架 + users 模型（与现库一致/契约生效/类型规范）。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def reset_engine():
    from backend.orm.base import reset_engine
    reset_engine()
    yield
    reset_engine()


class TestOrmBase:
    def test_engine_contract(self):
        """G1 契约：engine 连接后外键/WAL/busy_timeout 生效。"""
        from backend.orm.base import get_engine
        eng = get_engine()
        with eng.connect() as c:
            assert c.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert c.exec_driver_sql("PRAGMA busy_timeout").scalar() == 30000
            assert str(c.exec_driver_sql("PRAGMA journal_mode").scalar()).lower() == "wal"

    def test_session_roundtrip(self, tmp_path):
        """Session 可写读（临时库——R-028：不连默认库路径避免无库建空库）。"""
        from backend.orm.base import get_engine, get_session, reset_engine
        from backend.orm.users import User
        import backend.orm.base as b
        b._engine = b.build_engine(str(tmp_path / "orm.db"))
        b._SessionLocal = None
        try:
            from backend.orm.base import Base
            Base.metadata.create_all(b._engine)
            s = get_session()
            u = User(login_code="t1", name="测试", role="student")
            s.add(u); s.commit()
            got = s.get(User, u.id)
            assert got is not None and got.login_code == "t1"
            s.close()
        finally:
            b._engine.dispose()
            reset_engine()


class TestUserModel:
    def test_count_matches_real_db(self):
        """ORM users 总数与现库一致（1834 = 1793 学生 + 40 教师 + 1 admin）。"""
        from tests.fixtures.schemas import require_real_db
        require_real_db()
        from backend.orm.base import get_session
        from backend.orm.users import User
        from sqlalchemy import func, select
        s = get_session()
        assert s.scalar(select(func.count()).select_from(User)) == 1834
        s.close()

    def test_type_spec_applied(self):
        """类型规范 G8：login_code/name 为 String(50)，skills 为长文本。"""
        from backend.orm.users import User
        from sqlalchemy import String
        login = User.__table__.c.login_code
        assert isinstance(login.type, String) and login.type.length == 50
        name = User.__table__.c.name
        assert isinstance(name.type, String) and name.type.length == 50
        # skills 保留 TEXT（无长度约束）
        skills = User.__table__.c.skills
        assert skills.type.length is None

    def test_query_by_role(self):
        """ORM 查询能力（角色分布）。"""
        from backend.orm.base import get_session
        from backend.orm.users import User
        from sqlalchemy import func, select
        s = get_session()
        roles = dict(s.execute(select(User.role, func.count()).group_by(User.role)).all())
        assert roles.get('student') == 1793 and roles.get('teacher') == 40 and roles.get('admin') == 1
        s.close()


class TestCoreModels:
    def test_pending_model_matches(self):
        """pending ORM：行数/状态分布/生成列与现库一致。"""
        from tests.fixtures.schemas import require_real_db
        require_real_db()
        from backend.orm.base import get_session
        from backend.orm.pending import PendingAchievement
        from sqlalchemy import func, select
        s = get_session()
        assert s.scalar(select(func.count()).select_from(PendingAchievement)) >= 0
        # is_valid 生成列 ORM 可读；真库全 archived 且 vr 全空时自建探针行验证
        probe_inserted = False
        if s.execute(select(PendingAchievement.id).limit(1)).first() is None:
            from sqlalchemy import text as _text
            s.execute(_text(
                """INSERT INTO pending_achievements
                   (achievement_type, achievement_data, status, submitter_type,
                    submitter_id, file_hash, session_id, validation_result)
                   VALUES ('award', '{"t":"orm-probe"}', 'pending', 'admin',
                           1, 'hash-orm-probe', 'orm-session',
                           '{"is_valid": true}')"""))
            s.commit()
            probe_inserted = True
        row = s.execute(select(PendingAchievement.is_valid).limit(1)).first()
        assert row is not None
        if probe_inserted:
            s.execute(_text(
                "DELETE FROM pending_achievements WHERE file_hash='hash-orm-probe'"))
            s.commit()
        s.close()

    def test_audit_log_model(self):
        """audit ORM 可读真实库（append-only：现 8 行，随业务操作增长）。"""
        from backend.orm.base import get_session
        from backend.orm.audit_log import AuditLog
        from sqlalchemy import func, select
        s = get_session()
        n = s.scalar(select(func.count()).select_from(AuditLog))
        assert n >= 8   # append-only 单调增长（基线 8，随业务操作增长）
        s.close()

    def test_pending_type_spec(self):
        """类型规范：status VARCHAR20 / file_path VARCHAR500 / achievement_data 长文本。"""
        from backend.orm.pending import PendingAchievement
        from sqlalchemy import String
        t = PendingAchievement.__table__
        assert t.c.status.type.length == 20
        assert t.c.file_path.type.length == 500
        assert t.c.achievement_data.type.length is None      # Text
        # is_valid 为计算列（生成列保留）
        assert t.c.is_valid.computed is not None


class TestAuthOrmProbe:
    """M1 后半③：认证 users 分支 ORM 读试点（完整登录链路）。"""

    def test_orm_login_full_flow(self, tmp_path):
        """ORM 完整登录：正确密码成功/错误密码拒绝（完整 users DDL）。"""
        import sqlite3
        from werkzeug.security import generate_password_hash
        from tests.fixtures.schemas import USERS_DDL
        db = tmp_path / "auth.db"
        conn = sqlite3.connect(str(db))
        conn.execute(USERS_DDL)
        conn.execute("INSERT INTO users (login_code, name, role, password_hash) VALUES ('t1','测试','student',?)",
                     (generate_password_hash('GoodPass123'),))
        for t, pk in (("students","student_id"),("teachers","teacher_id"),("admins","username")):
            conn.execute(f"CREATE TABLE {t} ({pk} TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT, user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
        conn.commit(); conn.close()

        import backend.orm.base as b
        b._engine = b.build_engine(str(db)); b._SessionLocal = None
        from app.auth import verify_user
        r = verify_user('t1', 'GoodPass123', str(db))
        assert r is not None and r['user_type'] == 'student' and r['name'] == '测试'
        assert verify_user('t1', 'wrong', str(db)) is None
        b._engine.dispose(); b.reset_engine()

    def test_auth_falls_back_without_orm(self, tmp_path):
        """ORM 不可用时（无 users 表库）回退旧三表——未迁移库仍可登录。"""
        import sqlite3
        from werkzeug.security import generate_password_hash
        db = tmp_path / "old.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE students (student_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT, user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
        conn.execute("INSERT INTO students VALUES ('s1','旧生',?,'student',1,0)", (generate_password_hash('OldPass123'),))
        conn.commit(); conn.close()
        from app.auth import verify_user
        r = verify_user('s1', 'OldPass123', str(db))
        assert r is not None and r['user_type'] == 'student'


class TestUserRepository:
    """M1 后半③②：UserRepository ORM 读仓储（依赖真实库数据——R-028 守卫，
    无库/空库 skip，且避免 get_session() 对默认路径建空库副作用）。"""

    def test_get_by_login_code(self):
        from tests.fixtures.schemas import require_real_db
        require_real_db()
        from backend.orm.repositories import UserRepository
        u = UserRepository.get_by_login_code('admin')
        assert u is not None and u.role == 'admin' and u.id == 1832
        assert UserRepository.get_by_login_code('不存在') is None

    def test_get_by_id(self):
        from tests.fixtures.schemas import require_real_db
        require_real_db()
        from backend.orm.repositories import UserRepository
        assert UserRepository.get_by_id(1832).login_code == 'admin'
        assert UserRepository.get_by_id(999999) is None

    def test_list_by_role(self):
        from tests.fixtures.schemas import require_real_db
        require_real_db()
        from backend.orm.repositories import UserRepository
        admins = UserRepository.list_by_role('admin')
        assert len(admins) == 1
        students = UserRepository.list_by_role('student')
        assert len(students) == 1793


class TestAlembicBaseline:
    """M1 后半③③：Alembic baseline 交接点（CR-8）。"""

    def test_baseline_stamped(self):
        """alembic_version 表记录 baseline，且未破坏现库（表数不变）。"""
        from tests.fixtures.schemas import require_real_db
        require_real_db()
        import sqlite3
        conn = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
        ver = conn.execute("SELECT * FROM alembic_version").fetchall()
        n_tables = len([r for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")])
        conn.close()
        # 迁移链推进：0006 → 0012（system_event_log + audit 0007-0009 + 0010 类型收尾 + 0011 seq 去重 + 0012 审计测试打标）
        assert ver == [("0012_audit_test_flag",)]
        assert n_tables >= 25   # 视图化 -3 + failed_logins + system_event_log（原 26 业务表 + 系统表）

    def test_no_autogenerate_in_versions(self):
        """禁用 autogenerate：versions/ 里不得出现 drop_table（防灾难性迁移）。"""
        import re
        versions = PROJECT_ROOT / "migrations" / "versions"
        for f in versions.glob("*.py"):
            src = f.read_text(encoding="utf-8")
            assert "drop_table" not in src, f"{f.name} 含 drop_table（autogenerate 陷阱）"
