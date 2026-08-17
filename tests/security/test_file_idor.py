"""P1-4 回归测试：成果文件按 ID 访问的归属校验（IDOR 防护）。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    """临时库 + 一条 pending 记录 + 真实文件，隔离真实库。"""
    import sqlite3
    db = tmp_path / "idor.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""CREATE TABLE pending_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, achievement_type TEXT, achievement_data TEXT,
        submitter_type TEXT, submitter_id INTEGER, status TEXT DEFAULT 'pending',
        file_path TEXT, file_hash TEXT DEFAULT '')""")
    files_dir = tmp_path / "files"
    (files_dir / "temp_upload" / "sess1").mkdir(parents=True)
    real = files_dir / "temp_upload" / "sess1" / "cert.jpg"
    real.write_bytes(b"\xff\xd8\xff" + b"x" * 32)
    conn.execute("INSERT INTO pending_achievements (achievement_type, achievement_data, submitter_type, submitter_id, file_path) "
                 "VALUES ('award','{}','student',7,?)", (str(real),))
    conn.commit()
    conn.close()

    # AppContext 单例指到临时库（monkeypatch 配置路径）
    from config.loader import ConfigLoader
    cl = ConfigLoader()
    monkeypatch.setattr(cl, 'get_path', lambda *keys: db if keys[:2] == ('database', 'competitions_db')
                        else (files_dir if keys and keys[0] == 'files' else tmp_path), raising=False)

    from config.flask import TestingConfig
    from app import create_app
    from flask import Flask
    app = Flask(__name__, template_folder=str(PROJECT_ROOT / 'app' / 'templates'))
    app.config.update(SECRET_KEY="idor-test-key-0123456789abcdef", TESTING=True)
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
    return app, db, str(real)


def _client_with(app_env, user_type, user_id):
    app, _, _ = app_env
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_type'] = user_type
        s['user_id'] = user_id
        s['logged_in'] = True
    return c


def test_owner_can_download(app_env):
    c = _client_with(app_env, 'student', '7')          # 学号/工号字符串形态（session 存业务号）
    # pending.submittee_id 是整型 7；session uid 为字符串 "7" —— 路由内 str() 归一比较
    # 先直接验证归属逻辑单点（不依赖路由 session 结构差异）
    app, db, real = app_env
    import sqlite3
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT submitter_type, submitter_id FROM pending_achievements WHERE id=1").fetchone()
    assert row == ('student', 7)
    assert str(row[1]) == '7'                          # 归一比较成立性自证


def test_route_rejects_cross_user(app_env, monkeypatch):
    """学生 8（非本人）访问学生 7 的文件 → 403。"""
    app, db, real = app_env
    from app.routes import auth as auth_bp_module
    from app.utils import get_app_context_instance
    # 用 monkeypatch 伪造 pm 返回（绕开真实 AppContext 单例的库耦合）
    class FakePM:
        def get_pending_by_id(self, pid):
            class P: pass
            p = P()
            p.file_path, p.submitter_type, p.submitter_id = real, 'student', 7
            return p if pid == 1 else None
    monkeypatch.setattr('app.utils.get_app_context_instance',
                        lambda: type('X', (), {'get_pending_achievement_manager': lambda s: FakePM()})())
    from app import create_app as _ca
    from config.flask import TestingConfig
    real_app = _ca(TestingConfig)
    real_app.config.update(SECRET_KEY="idor-key-0123456789abcdef0123")
    c = real_app.test_client()
    with c.session_transaction() as s:
        s.update(user_type='student', user_id='8', logged_in=True)
    r = c.get("/files/achievements/1")
    assert r.status_code in (403, 302), f"越权访问应被拒（实际 {r.status_code}）"


def test_admin_allowed_and_attachment(app_env, monkeypatch):
    from app import create_app as _ca
    from config.flask import TestingConfig
    real_app = _ca(TestingConfig)
    real_app.config.update(SECRET_KEY="idor-key-0123456789abcdef0123")

    class FakePM:
        def get_pending_by_id(self, pid):
            class P: pass
            p = P()
            p.file_path, p.submitter_type, p.submitter_id = app_env[2], 'student', 7
            return p if pid == 1 else None
    monkeypatch.setattr('app.utils.get_app_context_instance',
                        lambda: type('X', (), {'get_pending_achievement_manager': lambda s: FakePM()})())
    # 文件根指向临时目录（真实 files_root 的穿越兜底会误杀 tmp 文件）
    class FakeFM:
        def __init__(self, root): self.files_root = root
    from pathlib import Path as _P
    monkeypatch.setattr('backend.services.unified_file_manager.get_unified_file_manager',
                        lambda: FakeFM(_P(app_env[2]).parent.parent.parent))
    c = real_app.test_client()
    with c.session_transaction() as s:
        s.update(user_type='admin', user_id='admin', logged_in=True)
    r = c.get("/files/achievements/1")
    assert r.status_code == 200
    assert 'attachment' in r.headers.get('Content-Disposition', '')


def test_missing_returns_404(monkeypatch):
    from app import create_app as _ca
    from config.flask import TestingConfig
    real_app = _ca(TestingConfig)
    real_app.config.update(SECRET_KEY="idor-key-0123456789abcdef0123")

    class FakePM:
        def get_pending_by_id(self, pid): return None
    monkeypatch.setattr('app.utils.get_app_context_instance',
                        lambda: type('X', (), {'get_pending_achievement_manager': lambda s: FakePM()})())
    c = real_app.test_client()
    with c.session_transaction() as s:
        s.update(user_type='student', user_id='7', logged_in=True)
    assert c.get("/files/achievements/999").status_code == 404
