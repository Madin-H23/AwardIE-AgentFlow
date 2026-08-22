"""T64 防腐 meta-test：app.url_map 的全部页面路由必须登记于清单或唯一豁免表。

判定口径：GET 方法 + 视图函数源码含 render_template。
豁免口径唯一：page_inventory.EXEMPT（type=not_page / bad_page）。
新页面路由不挂清单 → 本测试红（防腐自检）。
"""
import inspect
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fixtures.page_inventory import EXEMPT, PAGES  # noqa: E402
from tests.fixtures.seeded_db import seeded_app  # noqa: E402,F401


def _norm(url_or_rule):
    """归一化参数形态：werkzeug <int:x> 与清单 {x} 统一为 {param}。"""
    s = re.sub(r"<(?:[^:>]+:)?[^>]+>", "{param}", url_or_rule)
    s = re.sub(r"\{[a-z_0-9]+\}", "{param}", s)
    return s


def _collect_page_routes(app):
    """url_map → GET 且源码含 render_template 的 (rule_str, endpoint)。"""
    out = []
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue
        fun = app.view_functions.get(rule.endpoint)
        if fun is None:
            continue
        try:
            src = inspect.getsource(fun)
        except (TypeError, OSError):
            continue
        if "render_template" in src:
            out.append((rule.rule, rule.endpoint))
    return sorted(out)


def test_all_page_routes_are_registered(seeded_app):
    routes = _collect_page_routes(seeded_app)
    assert routes, "未收集到任何页面路由——url_map 扫描失效"

    listed = {_norm(u) for _, u, _, _ in PAGES}
    exempt_norm = {_norm(k) for k in EXEMPT}

    missing = []
    for rule_str, endpoint in routes:
        n = _norm(rule_str)
        if n in exempt_norm or n in listed:
            continue
        missing.append((rule_str, endpoint))

    assert not missing, (
        f"发现 {len(missing)} 个未登记的页面路由（既不在 page_inventory.PAGES，"
        f"也不在 EXEMPT 豁免表）：\n" +
        "\n".join(f"  {u}  ({ep})" for u, ep in missing))


def test_exempt_entries_are_real_routes_or_documented(seeded_app):
    """豁免表条目应能对应到真实路由规则（防豁免表漂移出无效条目）。"""
    rules = {_norm(r.rule) for r in seeded_app.url_map.iter_rules()}
    stale = [k for k in EXEMPT if _norm(k) not in rules]
    assert not stale, f"豁免表存在无法对应真实路由的陈旧条目: {stale}"


def test_inventory_has_no_duplicate_urls():
    urls = [u for _, u, _, _ in PAGES]
    dup = {u for u in urls if urls.count(u) > 1}
    assert not dup, f"PAGES 存在重复条目: {dup}"
