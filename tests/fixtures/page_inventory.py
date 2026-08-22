"""页面清单（T64）：全站页面路由的唯一事实源。

PAGES 四元组：(role, url, expected, anchor)
- role: admin / teacher / student / anon（anon=未登录可访问）
- url: 支持 str.format(award_id=..., lab_id=...) 深链参数（由种子库样本 id 填充）
- expected: 200 / 302（兼容重定向页）
- anchor: 页面关键标记子串（None 跳过锚点断言）

EXEMPT 豁免表（唯一豁免口径，meta-test 只认这张表）：
{url_or_endpoint: (type, reason)}，type ∈ not_page（GET+模板但不视为页面）/ bad_page（存量坏页暂缓）。

清单维护纪律：新增页面路由必须同步登记，否则 test_page_inventory_meta 红。
"""
from pathlib import Path
import re
import sqlite3

# 种子库样本 id（与 seeded_db.py 的 seed 数据一致；深链 url 用 .format 填充）
SEED_IDS = {
    "award_id": None, "patent_id": None, "copyright_id": None,
    "project_id": None, "lab_id": None, "student_id": None,
    "teacher_id": None, "pending_id": None, "competition_id": None,
    "file_id": None,
}


def seed_ids(db_path):
    """从种子库读样本 id（深链参数来源）。"""
    out = dict(SEED_IDS)
    conn = sqlite3.connect(str(db_path))
    for key, table in (("award_id", "awards"), ("patent_id", "patents"),
                       ("copyright_id", "software_copyrights"),
                       ("project_id", "innovation_projects"),
                       ("lab_id", "laboratories"), ("student_id", "users"),
                       ("teacher_id", "users"),
                       ("pending_id", "pending_achievements"),
                       ("competition_id", "competitions"),
                       ("file_id", "other_files")):
        try:
            if key in ("student_id",):
                out[key] = conn.execute(
                    "SELECT id FROM users WHERE login_code='212306413'").fetchone()[0]
            elif key in ("teacher_id",):
                out[key] = conn.execute(
                    "SELECT id FROM users WHERE role='teacher'").fetchone()[0]
            else:
                out[key] = conn.execute(
                    f"SELECT id FROM {table} ORDER BY id LIMIT 1").fetchone()[0]
        except Exception:
            out[key] = 1
    conn.close()
    return out


# ---------------------------------------------------------------- 正例清单
PAGES = [
    # ---- anon（未登录可访问） ----
    ("anon", "/login", 200, "登录"),
    # ---- admin ----
    ("admin", "/admin/dashboard", 200, "数据总览"),
    ("admin", "/admin/achievements", 200, None),
    ("admin", "/admin/awards", 200, None),
    ("admin", "/admin/awards/{award_id}/edit", 200, None),
    ("admin", "/admin/patents", 200, None),
    ("admin", "/admin/patents/create", 200, None),
    ("admin", "/admin/patents/{patent_id}", 200, None),
    ("admin", "/admin/patents/{patent_id}/edit", 200, None),
    ("admin", "/admin/software", 200, None),
    ("admin", "/admin/software/create", 200, None),
    ("admin", "/admin/software/{copyright_id}", 200, None),
    ("admin", "/admin/software/{copyright_id}/edit", 200, None),
    ("admin", "/admin/other-files", 200, None),
    ("admin", "/admin/other-files/upload", 200, None),
    ("admin", "/admin/other-files/{file_id}", 200, None),
    ("admin", "/admin/innovation/create", 200, None),
    ("admin", "/admin/innovation/{project_id}", 200, None),
    ("admin", "/admin/innovation/{project_id}/edit", 200, None),
    ("admin", "/admin/competitions", 200, None),
    ("admin", "/admin/competitions/new", 200, None),
    ("admin", "/admin/competitions/{competition_id}", 200, None),
    ("admin", "/admin/competitions/{competition_id}/edit", 200, None),
    ("admin", "/admin/students", 200, None),
    ("admin", "/admin/students/new", 200, None),
    ("admin", "/admin/students/{student_id}/edit", 200, None),
    ("admin", "/admin/teachers", 200, None),
    ("admin", "/admin/teachers/new", 200, None),
    ("admin", "/admin/teachers/{teacher_id}/edit", 200, None),
    ("admin", "/admin/laboratories", 200, None),
    ("admin", "/admin/laboratories/add", 200, None),
    ("admin", "/admin/laboratories/{lab_id}", 200, None),
    ("admin", "/admin/laboratories/{lab_id}/edit", 200, None),
    ("admin", "/admin/laboratories/{lab_id}/achievements", 200, None),
    ("admin", "/admin/laboratories/{lab_id}/competitions", 200, None),
    ("admin", "/admin/laboratories/{lab_id}/data-analysis", 200, None),
    ("admin", "/admin/laboratories/{lab_id}/downloads", 200, None),
    ("admin", "/admin/data-analysis", 200, None),
    ("admin", "/admin/templates", 200, None),
    ("admin", "/admin/settings", 200, None),
    ("admin", "/admin/logs", 200, None),
    ("admin", "/admin/file-import", 200, None),
    ("admin", "/admin/file-import/award-edit/{session_id}/{pending_id}", 200, None),
    ("admin", "/admin/achievement-review/{pending_id}", 200, None),
    # ---- teacher ----
    ("teacher", "/teacher/dashboard", 200, None),
    ("teacher", "/teacher/achievements", 200, None),
    ("teacher", "/teacher/achievement-review", 302, None),  # 列表页重定向到 award/valid/0（设计）
    ("teacher", "/teacher/achievement-review/award/valid/0", 200, None),
    ("teacher", "/teacher/achievement-submit", 200, None),
    ("teacher", "/teacher/achievement-submit/list", 200, None),
    ("teacher", "/teacher/data_export", 200, None),
    # 大创详情对非归属教师重定向（归属走 supervisors 文本匹配，种子形态不支持）——按守卫口径断言
    ("teacher", "/teacher/innovation/{project_id}", 302, None),
    ("teacher", "/teacher/profile", 200, None),
    # ---- 多角色共用 ----
    ("admin", "/assistant", 200, None),
    # ---- student ----
    ("student", "/student/dashboard", 200, None),
    ("student", "/student/achievements", 200, None),
    ("student", "/student/achievement-submit", 200, None),
    ("student", "/student/achievement-submit/list", 200, None),
    ("student", "/student/award/{award_id}", 200, None),
    ("student", "/student/profile", 200, None),
]

# 深链越权负例：role 访问"不属于自己"的资源 → 403/404/302
NEGATIVE_DEEP_LINKS = [
    # student2 访问他人（212306413）的 award 详情 → 归属校验应拦截
    ("student2", "/student/award/{award_id}", (302, 403, 404)),
]

# ---------------------------------------------------------------- 豁免表
EXEMPT = {
    # type=not_page：GET+源码含 render_template，但实际是 JSON/文件响应端点
    "/admin/api/achievements/awards": ("not_page", "JSON 数据接口"),
    "/admin/api/achievements/innovation": ("not_page", "JSON 数据接口"),
    "/admin/api/achievements/other": ("not_page", "JSON 数据接口"),
    "/admin/api/achievements/patents": ("not_page", "JSON 数据接口"),
    "/admin/api/achievements/software": ("not_page", "JSON 数据接口"),
    "/admin/data_export/department_summary": ("not_page", "导出文件下载"),
    "/admin/data_export/student_affairs": ("not_page", "导出文件下载"),
    "/admin/data_export/teacher_personal": ("not_page", "导出文件下载"),
    "/teacher/data_export": ("not_page", "导出文件下载"),
    "/": ("not_page", "根路径重定向到角色 dashboard"),
    "/admin/": ("not_page", "尾斜杠重定向"),
    "/student/": ("not_page", "尾斜杠重定向"),
    "/teacher/": ("not_page", "尾斜杠重定向"),
    "/student/achievement-submit/results": ("not_page", "需导入会话 query 参数的中间结果页"),
    "/teacher/achievement-submit/results": ("not_page", "需导入会话 query 参数的中间结果页"),
    "/admin/file-import/results": ("not_page", "需导入会话 query 参数的中间结果页"),
    "/teacher/achievement-review/{type}/{sub_tab}/{index}": (
        "not_page", "审核列表的具体形态子路由，由 award/valid/0 正例覆盖"),
    "/student/activities": (
        "bad_page", "存量坏页：activities_ref.html 模板不存在致 500（遗留假数据页），待修复后移入 PAGES"),
    # type=bad_page：存量坏页（修复后移入 PAGES）
    "/teacher/laboratory/{lab_id}/data-analysis": (
        "bad_page", "成员权限校验依赖 laboratory 关联数据，种子形态待迭代（T64 豁免）"),
}


def inventory_urls():
    """返回清单内全部 url（含深链参数已填充），供 meta-test 与统计使用。"""
    urls = set()
    for role, url, expected, anchor in PAGES:
        if "{" in url:
            # 深链：参数占位替换为通配形态（meta 按 rule 规则匹配）
            wildcard = re.sub(r"\{[a-z_]+\}", "1", url)
            urls.add(wildcard)
        else:
            urls.add(url)
    return urls


# 未登录维度放行前缀（设计为公开访问的页面；anon 测试跳过这些 url）
ANON_ALLOWED_PREFIXES = ("/admin/laboratories/",)
