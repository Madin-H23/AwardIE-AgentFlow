"""P2-25 登录限流集成测试：auth 登录链路连续失败触发锁定，解锁后恢复。"""
import sqlite3
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.schemas import USERS_DDL


@pytest.fixture()
def app(tmp_path):
    """临时应用 + 库（users 表 + admin 账号 + 空旧三表），指向测试库。

    - ORM engine 注入测试库：verify_user 的 users 分支走测试库（否则默认 engine 查真实库）
    - 空旧三表：verify_user 旧表 fallback 不因缺表崩（错误密码时 users 分支不匹配会落回旧表）
    """
    db = tmp_path / "auth.db"
    conn = sqlite3.connect(str(db))
    conn.execute(USERS_DDL)
    for t, pk in (("students", "student_id"), ("teachers", "teacher_id"), ("admins", "username")):
        conn.execute(f"CREATE TABLE {t} ({pk} TEXT PRIMARY KEY, name TEXT, password_hash TEXT, role TEXT, user_activated INTEGER DEFAULT 1, needs_password_change INTEGER DEFAULT 0)")
    conn.execute("INSERT INTO users (login_code, name, role, password_hash, user_activated) "
                 "VALUES ('admin', '管理员', 'admin', ?, 1)", (generate_password_hash('GoodPass123!'),))
    conn.commit()
    conn.close()

    from app import create_app
    import backend.orm.base as b
    b.reset_engine()
    b._engine = b.build_engine(str(db))
    b._SessionLocal = None
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False,
                      DATABASE_PATH=str(db))
    yield app
    if b._engine is not None:
        b._engine.dispose()
    b.reset_engine()


class TestLoginRateLimit:
    @staticmethod
    def _use_test_db(app, monkeypatch):
        """login 路由经 config.flask.get_config().DATABASE_PATH 取库——monkeypatch 指向测试库，
        否则会误写真实库（曾致测试污染 competitions.db 的 failed_logins）。"""
        from types import SimpleNamespace
        import app.routes.auth as auth_mod
        db = app.config["DATABASE_PATH"]
        monkeypatch.setattr(auth_mod, "get_config",
                            lambda: SimpleNamespace(DATABASE_PATH=str(db)))
        return db

    def test_lock_after_repeated_failures(self, app, monkeypatch):
        from backend.utils.login_guard import check_login_allowed
        db = self._use_test_db(app, monkeypatch)
        client = app.test_client()
        # 连续 5 次错误密码
        for _ in range(5):
            r = client.post("/login", data={"username": "admin", "password": "wrong"},
                            follow_redirects=False)
            assert r.status_code == 200
        # 第 6 次应被锁定拦截（提示尝试过于频繁）
        assert check_login_allowed(db, "admin", "127.0.0.1")[0] is False
        r = client.post("/login", data={"username": "admin", "password": "wrong"})
        assert "尝试过于频繁" in r.get_data(as_text=True)

    def test_success_clears_and_login_works(self, app, monkeypatch):
        self._use_test_db(app, monkeypatch)
        client = app.test_client()
        # 正确密码登录成功（前置 4 次失败后成功解锁）
        for _ in range(4):
            client.post("/login", data={"username": "admin", "password": "wrong"})
        r = client.post("/login", data={"username": "admin", "password": "GoodPass123!"},
                        follow_redirects=False)
        assert r.status_code == 302   # 登录成功重定向
        # 解锁后重新可尝试
        r2 = client.post("/login", data={"username": "admin", "password": "GoodPass123!"},
                         follow_redirects=False)
        assert r2.status_code == 302
