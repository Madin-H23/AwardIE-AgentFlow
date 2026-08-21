"""手动导入 API 集成测试（pytest 函数式，T31-T34 批次3 转换）。

真实契约（2026-08-21 实测）：
- 未认证 POST → 401 JSON {"message": "请先登录", "success": false}
- 认证后参数缺失/类型非法 → 400 JSON {"message": ..., "success": false}
- 测试期禁用 WTF CSRF（否则所有 POST 被 400 CSRF HTML 拦截，无法到达业务逻辑）
"""
import pytest

from app import create_app
from config.flask import get_config


@pytest.fixture(scope="module")
def client():
    app = create_app(get_config())
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def _login_admin(client):
    """模拟 admin 登录（session 直写；users 认证下 admin 业务号即 'admin'）。"""
    with client.session_transaction() as sess:
        sess["user_id"] = "admin"
        sess["role"] = "admin"
        sess["username"] = "admin"
        sess["user_name"] = "admin"
        sess["user_type"] = "admin"


PARSE_URL = "/admin/file-import/manual/parse"
SUBMIT_URL = "/admin/file-import/manual/submit"


# ---------- 未认证：一律 401 JSON ----------

def test_parse_unauthorized_returns_401(client):
    r = client.post(PARSE_URL, json={"file_path": "/fake/path.jpg"},
                    content_type="application/json")
    assert r.status_code == 401
    assert r.get_json()["success"] is False


def test_parse_unauthorized_invalid_type_returns_401(client):
    r = client.post(PARSE_URL, json={"achievement_type": "invalid", "file_path": "/fake/path.jpg"},
                    content_type="application/json")
    assert r.status_code == 401


def test_parse_unauthorized_valid_types_returns_401(client):
    for achievement_type in ("award", "patent", "software"):
        r = client.post(PARSE_URL, json={"achievement_type": achievement_type,
                                         "file_path": "/fake/path.jpg"},
                        content_type="application/json")
        assert r.status_code == 401


def test_submit_unauthorized_returns_401(client):
    r = client.post(SUBMIT_URL, json={"achievement_data": {}},
                    content_type="application/json")
    assert r.status_code == 401


def test_submit_unauthorized_valid_payload_returns_401(client):
    r = client.post(SUBMIT_URL, json={"achievement_type": "innovation",
                                      "achievement_data": {"project_name": "测试大创项目",
                                                           "project_number": "2026001", "year": 2026},
                                      "submitter_type": "admin"},
                    content_type="application/json")
    assert r.status_code == 401


# ---------- 已认证：参数校验 400 JSON ----------

@pytest.fixture()
def authed_client(client):
    _login_admin(client)
    return client


def test_parse_missing_file_path(authed_client):
    r = authed_client.post(PARSE_URL, json={"achievement_type": "award"},
                           content_type="application/json")
    assert r.status_code == 400
    data = r.get_json()
    assert data and data.get("success") is False


def test_parse_invalid_type(authed_client):
    r = authed_client.post(PARSE_URL, json={"achievement_type": "invalid",
                                            "file_path": "/fake/path.jpg"},
                           content_type="application/json")
    assert r.status_code == 400
    data = r.get_json()
    assert data and data.get("success") is False


def test_parse_file_not_found_graceful(authed_client):
    r = authed_client.post(PARSE_URL, json={"achievement_type": "award",
                                            "file_path": "/nonexistent/file.jpg"},
                           content_type="application/json")
    assert r.status_code in (200, 400, 404)
    data = r.get_json()
    if data:
        assert data.get("success") is not True


def test_submit_missing_achievement_type(authed_client):
    r = authed_client.post(SUBMIT_URL, json={"achievement_data": {"project_name": "测试"},
                                             "submitter_type": "admin"},
                           content_type="application/json")
    assert r.status_code == 400
    data = r.get_json()
    assert data and data.get("success") is False


def test_submit_missing_achievement_data(authed_client):
    r = authed_client.post(SUBMIT_URL, json={"achievement_type": "innovation",
                                             "submitter_type": "admin"},
                           content_type="application/json")
    assert r.status_code == 400
    data = r.get_json()
    assert data and data.get("success") is False


def test_submit_innovation_missing_required_field(authed_client):
    r = authed_client.post(SUBMIT_URL, json={"achievement_type": "innovation",
                                             "achievement_data": {"project_number": "2026001"},
                                             "submitter_type": "admin"},
                           content_type="application/json")
    assert r.status_code == 400
    data = r.get_json()
    assert data and data.get("success") is False
