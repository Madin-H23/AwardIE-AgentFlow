"""P1-1 回归测试：CSRF 全局防护（无 Token 写请求必须被拒）。"""
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

def _require_real_db():
    """共享守卫（schemas.require_real_db）：文件存在且 users 表存在，否则 skip（R-028 升级）。"""
    from tests.fixtures.schemas import require_real_db
    require_real_db()


LOGIN = "/login"   # auth 蓝图无 url_prefix


@pytest.fixture(scope="module")
def client():
    from config.flask import TestingConfig
    from app import create_app
    app = create_app(TestingConfig)
    app.config.update(WTF_CSRF_ENABLED=True, SECRET_KEY="test-secret-key-for-csrf-only!")
    return app.test_client()


def _meta_token(client):
    """模拟前端：GET 登录页，从 meta 取 token（同一 client 保持 session 绑定）。"""
    html = client.get(LOGIN).get_data(as_text=True)
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None


def test_post_without_token_rejected(client):
    """未携带 Token 的 POST 必须 400（跨站伪造请求的形态）。"""
    r = client.post(LOGIN, data={"username": "x", "password": "y"})
    assert r.status_code == 400


def test_post_with_token_passes_csrf_layer(client):
    _require_real_db()
    """带合法 Token 的 POST 穿过 CSRF 层（到达业务层，凭据错非 400）。"""
    token = _meta_token(client)
    assert token, "登录页未输出 meta token"
    r = client.post(LOGIN, data={"username": "x", "password": "y", "csrf_token": token})
    assert r.status_code != 400, "合法 Token 不应被 CSRF 层拒绝"


def test_wrong_token_rejected(client):
    """伪造/过期 Token 同样拒绝。"""
    r = client.post(LOGIN, data={"username": "x", "password": "y", "csrf_token": "forged-token"})
    assert r.status_code == 400


def test_get_unaffected(client):
    assert client.get(LOGIN).status_code == 200


def test_login_page_has_csrf_meta(client):
    html = client.get(LOGIN).get_data(as_text=True)
    assert re.search(r'<meta name="csrf-token"', html), "登录页缺少 csrf-token meta"


def test_all_three_bases_inject_assets():
    """三套基础模板必须都注入 meta + csrf.js（防后续新增基底遗漏）。"""
    for name in ("base.html", "user_base.html", "base_simple.html"):
        src = (PROJECT_ROOT / "app" / "templates" / name).read_text(encoding="utf-8")
        assert 'meta name="csrf-token"' in src, f"{name} 缺少 meta 注入"
        assert "csrf.js" in src, f"{name} 缺少 csrf.js 引用"
