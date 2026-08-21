"""手动导入页面 UI 测试（pytest 函数式，T31-T34 批次3 转换；测试期禁 WTF CSRF）。"""
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def client():
    from app import create_app
    from config.flask import get_config

    app = create_app(get_config())
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def test_file_import_page_requires_auth(client):
    """未登录访问文件导入页应重定向到登录页"""
    r = client.get("/admin/file-import")
    assert r.status_code in (302, 303)
    assert "/login" in r.location


def test_manual_api_endpoints_exist(client):
    """手动导入 API 端点存在（未登录 POST 应 401/403）"""
    r = client.post("/admin/file-import/manual/parse",
                    json={"achievement_type": "award", "file_path": "/fake/path.jpg"},
                    content_type="application/json")
    assert r.status_code in (401, 403)

    r = client.post("/admin/file-import/manual/submit",
                    json={"achievement_type": "innovation", "achievement_data": {}},
                    content_type="application/json")
    assert r.status_code in (401, 403)


def test_manual_import_template_exists():
    """手动导入模板文件存在且包含关键元素"""
    template_path = PROJECT_ROOT / "app" / "templates" / "admin" / "file_import" / "upload.html"
    assert template_path.exists(), "upload.html 模板文件应该存在"

    content = template_path.read_text(encoding="utf-8")
    assert "importModeTabs" in content
    assert "autoModeTab" in content
    assert "manualModeTab" in content
    assert 'data-bs-toggle="tab"' in content
    assert "manualImportContent" in content
    assert "typeAward" in content or "manualTypeAward" in content, "缺少奖状类型选项"
    assert "typePatent" in content or "manualTypePatent" in content, "缺少专利类型选项"
    assert "typeSoftware" in content or "manualTypeSoftware" in content, "缺少软著类型选项"


def test_manual_import_service_exists():
    """手动导入服务模块存在"""
    assert (PROJECT_ROOT / "backend" / "services" / "manual_import_service.py").exists()
