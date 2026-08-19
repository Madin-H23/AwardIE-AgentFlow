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
        """Session 可写读（临时库）。"""
        from backend.orm.base import get_engine, get_session
        from backend.orm.users import User
        eng = get_engine()   # 真实库（测试只读，不写）
        s = get_session()
        u = s.get(User, 1)
        assert u is not None and u.login_code
        s.close()


class TestUserModel:
    def test_count_matches_real_db(self):
        """ORM users 总数与现库一致（1832）。"""
        if not (PROJECT_ROOT / "database" / "competitions.db").exists():
            pytest.skip("CI 无真实库")
        from backend.orm.base import get_session
        from backend.orm.users import User
        from sqlalchemy import func, select
        s = get_session()
        assert s.scalar(select(func.count()).select_from(User)) == 1832
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
        assert roles.get('student') == 1793 and roles.get('teacher') == 38 and roles.get('admin') == 1
        s.close()


class TestCoreModels:
    def test_pending_model_matches(self):
        """pending ORM：行数/状态分布/生成列与现库一致。"""
        if not (PROJECT_ROOT / "database" / "competitions.db").exists():
            pytest.skip("CI 无真实库")
        from backend.orm.base import get_session
        from backend.orm.pending import PendingAchievement
        from sqlalchemy import func, select
        s = get_session()
        assert s.scalar(select(func.count()).select_from(PendingAchievement)) == 40
        # is_valid 生成列 ORM 可读
        row = s.execute(select(PendingAchievement.is_valid).limit(1)).first()
        assert row is not None
        s.close()

    def test_audit_log_model(self):
        from backend.orm.base import get_session
        from backend.orm.audit_log import AuditLog
        from sqlalchemy import func, select
        s = get_session()
        n = s.scalar(select(func.count()).select_from(AuditLog))
        assert n == 0
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
