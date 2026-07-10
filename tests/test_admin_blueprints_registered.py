"""
Admin 蓝图注册验证

验证重构后所有 admin 子蓝图已正确注册，关键端点可解析。
用于在拆分 admin 后快速确认路由未丢失。
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
os.chdir(project_root)

from app import create_app
from config.flask import get_config


def test_admin_blueprints_registered():
    """验证 admin 主蓝图与子蓝图均已注册"""
    app = create_app(get_config())
    with app.app_context():
        endpoints = {r.endpoint for r in app.url_map.iter_rules()}

    required_blueprints = [
        'admin',           # 仪表盘、竞赛、学生、教师、设置
        'admin_achievement',
        'admin_awards',
        'admin_export',
        'admin_laboratory',
        'admin_templates',
    ]
    for bp_name in required_blueprints:
        # 至少有一个端点以该蓝图名为前缀
        has_bp = any(e == bp_name or e.startswith(bp_name + '.') for e in endpoints)
        assert has_bp, f"未找到蓝图 {bp_name} 的端点，当前端点示例: {list(endpoints)[:20]}"


def test_admin_achievement_key_endpoints():
    """验证 admin_achievement 关键端点存在"""
    app = create_app(get_config())
    with app.app_context():
        endpoints = {r.endpoint for r in app.url_map.iter_rules()}

    key_endpoints = [
        'admin_awards.awards_list',
        'admin_awards.award_edit',
        'admin_awards.award_image',
        'admin_achievement.achievements',
        'admin_achievement.file_import',
        'admin_achievement.file_import_results',
    ]
    for ep in key_endpoints:
        assert ep in endpoints, f"缺少端点: {ep}"


def test_admin_laboratory_key_endpoints():
    """验证 admin_laboratory 关键端点存在"""
    app = create_app(get_config())
    with app.app_context():
        endpoints = {r.endpoint for r in app.url_map.iter_rules()}

    key_endpoints = [
        'admin_laboratory.laboratories_list',
        'admin_laboratory.laboratory_detail',
        'admin_laboratory.laboratory_edit',
        'admin_laboratory.laboratory_achievements',
        'admin_laboratory.laboratory_competitions',
        'admin_laboratory.laboratory_downloads_list',
        'admin_laboratory.laboratory_download_file',
        'admin_laboratory.laboratory_image_file',
    ]
    for ep in key_endpoints:
        assert ep in endpoints, f"缺少端点: {ep}"


def test_admin_export_key_endpoints():
    """验证 admin_export 关键端点存在"""
    app = create_app(get_config())
    with app.app_context():
        endpoints = {r.endpoint for r in app.url_map.iter_rules()}

    key_endpoints = [
        'admin_export.data_export',
        'admin_export.department_summary',
        'admin_export.department_summary_export',
    ]
    for ep in key_endpoints:
        assert ep in endpoints, f"缺少端点: {ep}"


def test_admin_templates_key_endpoints():
    """验证 admin_templates 关键端点存在"""
    app = create_app(get_config())
    with app.app_context():
        endpoints = {r.endpoint for r in app.url_map.iter_rules()}

    key_endpoints = [
        'admin_templates.templates_list',
        'admin_templates.template_image',
    ]
    for ep in key_endpoints:
        assert ep in endpoints, f"缺少端点: {ep}"


def test_url_for_admin_achievement():
    """验证 admin_achievement 的 url_for 可解析"""
    app = create_app(get_config())
    with app.test_request_context():
        from flask import url_for
        url_for('admin_achievement.achievements')
        url_for('admin_awards.awards_list')
        url_for('admin_achievement.file_import')


def run_standalone():
    """无 pytest 时直接运行"""
    tests = [
        test_admin_blueprints_registered,
        test_admin_achievement_key_endpoints,
        test_admin_laboratory_key_endpoints,
        test_admin_export_key_endpoints,
        test_admin_templates_key_endpoints,
        test_url_for_admin_achievement,
    ]
    for fn in tests:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            print(f"[FAIL] {fn.__name__}: {e}")
            return 1
    print("All checks passed.")
    return 0


if __name__ == '__main__':
    try:
        import pytest
        sys.exit(pytest.main([__file__, '-v']))
    except ImportError:
        sys.exit(run_standalone())
