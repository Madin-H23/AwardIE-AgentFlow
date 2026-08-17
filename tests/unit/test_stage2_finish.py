"""阶段二收尾回归：P1-8 归档闸+补偿 / 首登强制改密 / health 真实校验。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------- P1-8 ----------
@pytest.fixture()
def pm(tmp_path):
    import sqlite3
    db = tmp_path / "t.db"
    real = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
    ddl = real.execute("SELECT sql FROM sqlite_master WHERE name='pending_achievements'").fetchone()[0]
    real.close()
    conn = sqlite3.connect(str(db))
    conn.execute(ddl)
    conn.execute("INSERT INTO pending_achievements (achievement_type, achievement_data, submitter_type, submitter_id, status) "
                 "VALUES ('award','{}','student',7,'submit')")
    conn.commit()
    conn.close()
    from backend.models.pending_achievement import PendingAchievementManager
    return PendingAchievementManager(str(db))


class TestArchiveGate:
    def test_unarchive_roundtrip(self, pm):
        assert pm.archive(1) is True
        assert pm.get_pending_by_id(1).status == "archived"
        assert pm.unarchive(1) is True
        assert pm.get_pending_by_id(1).status == "submit"

    def test_unarchive_only_archived(self, pm):
        assert pm.unarchive(1) is False          # submit 态不可回滚（防误操作）

    def test_archive_as_gate(self, pm):
        """并发防重：二次 archive 失败（闸生效）。"""
        assert pm.archive(1) is True
        assert pm.archive(1) is False


class TestForcedPasswordChange:
    def test_admin_reset_uses_strong_pwd_and_flag(self):
        """T22：admin 重置密码必须随机强密码 + needs_password_change=1（源码防回退默认密码）。"""
        src = (PROJECT_ROOT / "app" / "routes" / "admin.py").read_text(encoding='utf-8')
        assert "get_default_password" not in src, "admin.py 仍引用默认密码"
        assert src.count("needs_password_change=1") >= 4     # 4 处重置/创建

    def test_verify_user_returns_flag(self, tmp_path):
        """登录返回 needs_password_change（全角色标记）。"""
        import sqlite3
        from werkzeug.security import generate_password_hash
        db = tmp_path / "u.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE admins(username TEXT PRIMARY KEY, name TEXT, password_hash TEXT, user_activated INTEGER, needs_password_change INTEGER)")
        conn.execute("CREATE TABLE students(student_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT, user_activated INTEGER, needs_password_change INTEGER)")
        conn.execute("CREATE TABLE teachers(teacher_id TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT, user_activated INTEGER, needs_password_change INTEGER)")
        conn.execute("INSERT INTO teachers VALUES ('t1','张',?,'teacher',1,1)", (generate_password_hash('GoodPass123'),))
        conn.commit()
        conn.close()
        from app.auth import verify_user
        info = verify_user('t1', 'GoodPass123', str(db))
        assert info and info.get('needs_password_change') is True

    def test_user_common_no_student_only(self):
        """强制改密拦截不再限定 student（全角色）。"""
        src = (PROJECT_ROOT / "app" / "routes" / "user_common.py").read_text(encoding='utf-8')
        assert "and user_type == 'student'" not in src


class TestHealth:
    def test_health_includes_db_and_breaker(self):
        """health 返回 db 探活 + 熔断状态（P2 假绿修复）。"""
        from config.flask import TestingConfig
        from app import create_app
        app = create_app(TestingConfig)
        app.config.update(SECRET_KEY="health-test-key-0123456789")
        c = app.test_client()
        data = c.get("/assistant/health").get_json()
        assert "db" in data and data["db"] is True          # 主库可达
        assert "breaker" in data and "llm" in data["breaker"]
        assert data["status"] == "ok"
