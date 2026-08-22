"""T64 全页面冒烟：清单驱动参数化（正例 + 未登录守卫 + 越权负例）。

清单唯一事实源 = tests/fixtures/page_inventory.py；防腐自检见 test_page_inventory_meta.py。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fixtures.page_inventory import (  # noqa: E402
    NEGATIVE_DEEP_LINKS, PAGES, seed_ids,
)
from tests.fixtures.seeded_db import login_as, seeded_app, smoke_client  # noqa: E402

SEED_DB = None


@pytest.fixture(scope="session")
def seed_db_path(seeded_app):
    """种子库路径（深链参数来源）；从 app config 取（双路径 patch 后一致）。"""
    return seeded_app.config["DATABASE_PATH"]


def _fill(url, db_path):
    """深链 url 的 {param} 用种子样本 id 填充。"""
    if "{" not in url:
        return url
    ids = seed_ids(db_path)
    keys = ("award_id", "patent_id", "copyright_id", "project_id",
            "lab_id", "student_id", "teacher_id", "pending_id",
            "competition_id", "file_id")
    fmt = {k: ids.get(k, 1) for k in keys}
    fmt["session_id"] = "smoke-seed-session"
    return url.format(**fmt)


# ---------------- 正例：登录态渲染 ----------------

@pytest.mark.parametrize("role,url,expected,anchor", PAGES)
def test_page_renders(seeded_app, smoke_client, seed_db_path, role, url, expected, anchor):
    real_url = _fill(url, seed_db_path)
    login_as(smoke_client, role)
    r = smoke_client.get(real_url)
    head = (r.get_data(as_text=True) or "")[:200].replace("\n", " ")
    assert r.status_code == expected, \
        f"[{role}] GET {real_url} -> {r.status_code}（期望 {expected}）| body[:200]={head}"
    assert "text/html" in (r.content_type or ""), \
        f"[{role}] GET {real_url} content_type={r.content_type}"
    body = r.get_data(as_text=True) or ""
    assert len(body.strip()) > 0, f"[{role}] GET {real_url} 响应体为空"
    if anchor:
        assert anchor in body, f"[{role}] GET {real_url} 缺少锚点 '{anchor}'"


# ---------------- 守卫①：未登录重定向 ----------------

@pytest.mark.parametrize("role,url,expected,anchor",
                         [p for p in PAGES if p[0] != "anon"],
                         ids=lambda v: v if isinstance(v, str) else "")
def test_anon_redirected_to_login(seeded_app, smoke_client, seed_db_path,
                                  role, url, expected, anchor):
    from tests.fixtures.page_inventory import ANON_ALLOWED_PREFIXES
    real_url = _fill(url, seed_db_path)
    if any(real_url.startswith(pre) for pre in ANON_ALLOWED_PREFIXES):
        pytest.skip("设计为公开访问（无需登录守卫）")
    r = smoke_client.get(real_url)
    loc = r.headers.get("Location") or ""
    assert r.status_code in (301, 302) and "/login" in loc, \
        f"[anon] GET {real_url} -> {r.status_code} Location={loc}（未登录应重定向 /login）"


# ---------------- 守卫②③：越权拦截 ----------------

def test_student_cannot_reach_admin_pages(seeded_app, smoke_client):
    login_as(smoke_client, "student")
    for url in ("/admin/dashboard", "/admin/achievements", "/admin/logs"):
        r = smoke_client.get(url)
        assert r.status_code in (302, 403), \
            f"[student] GET {url} -> {r.status_code}（应被角色守卫拦截）"


def test_teacher_cannot_reach_admin_pages(seeded_app, smoke_client):
    login_as(smoke_client, "teacher")
    for url in ("/admin/dashboard", "/admin/settings"):
        r = smoke_client.get(url)
        assert r.status_code in (302, 403)


@pytest.mark.parametrize("role,url,codes", NEGATIVE_DEEP_LINKS)
def test_negative_deep_links(seeded_app, smoke_client, seed_db_path, role, url, codes):
    real_url = _fill(url, seed_db_path)
    login_as(smoke_client, role)
    r = smoke_client.get(real_url)
    assert r.status_code in codes, \
        f"[{role}] GET {real_url} -> {r.status_code}（期望 {codes}）"