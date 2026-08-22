"""核心业务路由覆盖测试（T24）：三角色登录态下的高频列表页冒烟 + 权限守卫。

目标模块：app/routes/admin.py、teacher.py、student.py（原覆盖率 8-12% 的两个大路由文件）。
依赖真实库（页面渲染走 manager 查询），CI 无库环境自动 skip。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import create_app  # noqa: E402
from config.flask import get_config  # noqa: E402  # Flask Config 类（含 SECRET_KEY）
from tests.fixtures.schemas import require_real_db  # noqa: E402


@pytest.fixture(scope="module")
def client():
    require_real_db()
    # 注意必须用 config.flask.get_config（Flask Config 类）；config.loader.get_config
    # 返回 ConfigLoader 实例，from_object 取不到 SECRET_KEY → 会话/CSRF 全部失效
    app = create_app(get_config())
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    # 生产配置 https-only 会话 cookie 会让 test_client(http) 拿不到 session
    app.config["SESSION_COOKIE_SECURE"] = False
    with app.test_client() as c:
        yield c


def _login(client, role, code):
    with client.session_transaction() as sess:
        sess["user_id"] = code
        sess["role"] = role
        sess["username"] = code
        sess["user_name"] = code
        sess["user_type"] = role


# ---------- 未认证守卫 ----------

def test_protected_pages_redirect_to_login(client):
    for url in ("/admin/dashboard", "/teacher/achievement-review",
                "/student/submissions"):
        r = client.get(url)
        assert r.status_code in (301, 302), f"{url} 应重定向登录"
        assert "/login" in (r.headers.get("Location") or ""), f"{url} 重定向目标应为 /login"


# ---------- admin 列表页 ----------

def test_admin_dashboard_and_achievements(client):
    _login(client, "admin", "admin")
    for url in ("/admin/dashboard", "/admin/achievements"):
        r = client.get(url)
        assert r.status_code == 200, f"GET {url} -> {r.status_code}"
        assert "html" in (r.content_type or "")


def test_admin_logs_page(client):
    _login(client, "admin", "admin")
    r = client.get("/admin/logs")
    assert r.status_code == 200


def test_admin_api_logs_audit_json(client):
    _login(client, "admin", "admin")
    r = client.get("/admin/api/logs/audit?page=1&per_page=5")
    assert r.status_code == 200
    payload = r.get_json()
    assert isinstance(payload, dict)


# ---------- teacher 列表页 ----------

def test_teacher_pages(client):
    _login(client, "teacher", "02110606")
    for url in ("/teacher/dashboard", "/teacher/achievements"):
        r = client.get(url)
        assert r.status_code == 200, f"GET {url} -> {r.status_code}"
    # 审核列表是智能路由：单一类型有数据时 302 直达详情，空/多类型渲染列表 200
    r = client.get("/teacher/achievement-review")
    assert r.status_code in (200, 302), \
        f"GET /teacher/achievement-review -> {r.status_code}"


def test_teacher_cannot_access_admin_pages(client):
    _login(client, "teacher", "02110606")
    r = client.get("/admin/dashboard")
    assert r.status_code in (302, 403)


# ---------- student 列表页 ----------

def test_student_pages(client):
    _login(client, "student", "212306413")
    for url in ("/student/dashboard", "/student/achievements",
                "/student/achievement-submit"):
        r = client.get(url)
        assert r.status_code == 200, f"GET {url} -> {r.status_code}"
    # /submissions 是向后兼容重定向（设计行为：302 → achievement-submit）
    r = client.get("/student/submissions")
    assert r.status_code == 302 and "/student/achievement-submit" in r.headers.get("Location", "")


def test_student_cannot_access_admin_pages(client):
    _login(client, "student", "212306413")
    r = client.get("/admin/achievements")
    assert r.status_code in (302, 403)