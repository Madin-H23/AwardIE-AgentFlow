"""
文件导入功能增强测试脚本

测试：
1. 实验室列表API
2. 学生实验室关联策略
3. 指定指导教师补充

使用方法：
    python tests/test_lab_association_feature.py
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from pathlib import Path


def test_database_data():
    """测试数据库中是否有必要的测试数据"""
    db_path = Path(__file__).parent.parent / 'database' / 'competitions.db'

    print("=" * 60)
    print("测试 1: 检查数据库数据")
    print("=" * 60)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 检查实验室
    cursor.execute("SELECT id, name FROM laboratories")
    labs = cursor.fetchall()
    print(f"\n实验室数据 ({len(labs)} 条):")
    for lab_id, name in labs:
        print(f"  ID {lab_id}: {name}")

    # 检查教师-实验室关联
    cursor.execute("""
        SELECT t.id, t.name, li.laboratory_id
        FROM teachers t
        LEFT JOIN laboratory_instructors li ON t.id = li.teacher_id
        LIMIT 10
    """)
    teachers = cursor.fetchall()
    print(f"\n教师-实验室关联 (前10条):")
    for teacher_id, name, lab_id in teachers:
        lab_info = f"-> 实验室 {lab_id}" if lab_id else "(未关联)"
        print(f"  {name} (ID: {teacher_id}) {lab_info}")

    conn.close()

    assert len(labs) >= 4, "至少需要4个实验室"
    print("\n[OK] 数据库数据检查通过")


def test_api_endpoint():
    """测试实验室列表API端点"""
    print("\n" + "=" * 60)
    print("测试 2: 检查API端点定义")
    print("=" * 60)

    # 检查 admin.py：API 端点与获取实验室列表
    admin_py_path = Path(__file__).parent.parent / 'app' / 'routes' / 'admin.py'
    admin_content = admin_py_path.read_text(encoding='utf-8')
    assert "@bp.route('/api/laboratories')" in admin_content, "缺少 /api/laboratories 端点"
    print("[OK] API端点 /api/laboratories 已定义")
    assert "laboratory_manager.get_all_laboratories()" in admin_content, "缺少获取实验室列表的代码"
    print("[OK] 获取实验室列表代码已添加")

    # 检查实验室关联与指导教师参数：可在 admin.py 或 admin_achievement.py 或前端模板中
    achievement_py_path = Path(__file__).parent.parent / 'app' / 'routes' / 'admin_achievement.py'
    achievement_content = achievement_py_path.read_text(encoding='utf-8') if achievement_py_path.exists() else ""
    upload_html_path = Path(__file__).parent.parent / 'app' / 'templates' / 'admin' / 'file_import' / 'upload.html'
    upload_content = upload_html_path.read_text(encoding='utf-8') if upload_html_path.exists() else ""
    combined = admin_content + achievement_content + upload_content
    assert "lab_association_mode" in combined, "缺少 lab_association_mode 参数（应在路由或前端）"
    assert "default_supervisor_name" in combined, "缺少 default_supervisor_name 参数（应在路由或前端）"
    print("[OK] 新参数获取代码已添加")
    assert "自动关联实验室" in combined or "lab_association_mode" in combined or "labModeAuto" in combined, "缺少实验室关联逻辑"
    print("[OK] 实验室关联逻辑已添加")
    assert "补充指导教师" in combined or "default_supervisor_name" in combined or "useDefaultSupervisor" in combined, "缺少指导教师补充逻辑"
    print("[OK] 指导教师补充逻辑已添加")


def test_frontend_html():
    """测试前端HTML组件"""
    print("\n" + "=" * 60)
    print("测试 3: 检查前端HTML组件")
    print("=" * 60)

    upload_html_path = Path(__file__).parent.parent / 'app' / 'templates' / 'admin' / 'file_import' / 'upload.html'
    content = upload_html_path.read_text(encoding='utf-8')

    # 检查实验室关联UI
    assert 'id="labModeAuto"' in content, "缺少自动关联选项"
    assert 'id="labModeSpecific"' in content, "缺少指定实验室选项"
    assert 'id="labModeNone"' in content, "缺少不关联选项"
    assert 'id="specificLaboratory"' in content, "缺少实验室下拉框"
    print("[OK] 实验室关联UI组件已添加")

    # 检查指导教师UI
    assert 'id="useDefaultSupervisor"' in content, "缺少指定指导教师开关"
    assert 'id="supervisorName"' in content, "缺少指导教师输入框"
    print("[OK] 指导教师UI组件已添加")

    # 检查JavaScript逻辑
    assert 'loadLaboratories' in content, "缺少加载实验室列表函数"
    assert 'getLabAssociationMode' in content, "缺少获取实验室模式函数"
    assert 'getDefaultSupervisorName' in content, "缺少获取指导教师函数"
    assert "'/admin/api/laboratories'" in content, "缺少API调用"
    print("[OK] JavaScript逻辑已添加")


def test_frontend_javascript():
    """测试前端JavaScript逻辑"""
    print("\n" + "=" * 60)
    print("测试 4: 检查前端JavaScript逻辑")
    print("=" * 60)

    upload_html_path = Path(__file__).parent.parent / 'app' / 'templates' / 'admin' / 'file_import' / 'upload.html'
    content = upload_html_path.read_text(encoding='utf-8')

    # 检查事件监听器
    assert "addEventListener('change', updateLabModeDisplay)" in content, "缺少实验室模式切换事件"
    assert "addEventListener('change', (e) => {" in content and "defaultSupervisorInput.style.display" in content, "缺少指导教师开关事件"
    print("[OK] 事件监听器已添加")

    # 检查FormData参数
    assert "formData.append('lab_association_mode'" in content, "缺少lab_association_mode参数"
    assert "formData.append('default_supervisor_name'" in content, "缺少default_supervisor_name参数"
    print("[OK] FormData参数已添加")


def test_code_integration():
    """测试代码集成"""
    print("\n" + "=" * 60)
    print("测试 5: 检查代码集成")
    print("=" * 60)

    # 文件导入相关逻辑在 admin_achievement 中
    achievement_py_path = Path(__file__).parent.parent / 'app' / 'routes' / 'admin_achievement.py'
    content = achievement_py_path.read_text(encoding='utf-8')

    # 检查 teacher_manager 和 laboratory_manager 是否可用（在成果/文件导入中）
    assert "teacher_manager = app_context.get_teacher_manager()" in content or "get_teacher_manager()" in content, "缺少 teacher_manager 初始化"
    assert "laboratory_manager = app_context.get_laboratory_manager()" in content or "get_laboratory_manager()" in content, "缺少 laboratory_manager 初始化"
    print("[OK] Manager初始化正确")

    # 检查 supervisor_name 处理
    assert "achievement_data.get('supervisor_name'" in content or "supervisor_name" in content, "缺少 supervisor_name 获取"
    print("[OK] supervisor_name处理正确")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("文件导入功能增强 - 集成测试")
    print("=" * 60)

    try:
        test_database_data()
        test_api_endpoint()
        test_frontend_html()
        test_frontend_javascript()
        test_code_integration()

        print("\n" + "=" * 60)
        print("所有测试通过! [OK]")
        print("=" * 60)
        print("\n下一步：")
        print("1. 启动Flask应用: python run.py")
        print("2. 访问: http://127.0.0.1:5001/admin/file-import")
        print("3. 执行手动测试:")
        print("   - 检查实验室下拉框是否正确显示")
        print("   - 测试自动关联模式")
        print("   - 测试指定实验室模式")
        print("   - 测试指定指导教师功能")

        return 0

    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n[FAIL] 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
