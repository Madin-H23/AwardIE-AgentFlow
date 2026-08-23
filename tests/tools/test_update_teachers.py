"""
教师通讯录更新工具测试

测试 Excel 解析器是否能正确从通讯录文件中提取教师数据。
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock

# 添加项目根目录到路径（与项目其他测试保持一致）
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.update_teachers_from_contacts import parse_contacts_excel


def test_parse_excel_file():
    """测试解析 Excel 文件"""
    # 使用绝对路径获取测试固件文件
    fixtures_dir = Path(__file__).parent.parent / 'fixtures'
    file_path = fixtures_dir / 'test_contacts.xlsx'

    result = parse_contacts_excel(str(file_path))

    # 验证返回的是列表
    assert isinstance(result, list), "解析结果应该是列表"

    # 验证提取了5条记录（3个已有 + 2个新增）
    assert len(result) == 5, f"应该提取5条记录，实际提取了{len(result)}条"

    # 验证第一条记录（马云莺）
    assert result[0]['name'] == '马云莺'
    assert result[0]['teacher_id'] == '02114818'
    assert result[0]['phone'] == '13950308256'
    assert result[0]['title'] == '讲师'

    # 验证新教师记录（张三）- 使用 next() 确保字段在同一记录中
    zhangsan = next((r for r in result if r['name'] == '张三'), None)
    assert zhangsan is not None, "未找到张三的记录"
    assert zhangsan['teacher_id'] == '99991001'
    assert zhangsan['phone'] == '13800000001'
    assert zhangsan['title'] == '教授'


def test_parse_excel_with_empty_name(tmp_path):
    """测试跳过空姓名记录（T71 零头清理：原 skip 待实现已落地）"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for _ in range(3):          # 前 3 行为标题区（解析器从索引 3 起读数据）
        ws.append(["占位"] * 10)
    ws.append([None, "有效教师", "02190001", "13800000999", "讲师",
               None, None, None, None, None])            # 左块：有效行
    ws.append([None, "   ", "02190002", "13800000002", None,
               None, "王空名", "02190003", "13800000003", None])  # 左姓名空白+右块有效
    ws.append([None, "", "", "", "",
               None, "李亦空", "02190004", "", ""])       # 右块：下一行的左块全空
    xlsx = tmp_path / "contacts_empty.xlsx"
    wb.save(xlsx)

    result = parse_contacts_excel(str(xlsx))
    names = [r["name"] for r in result]
    assert "有效教师" in names and "王空名" in names
    assert all(n.strip() for n in names), f"空姓名未被跳过: {names}"
    # 左块第2行姓名为纯空白 → 被跳过；其余 3 条（左1+右2）正常提取
    assert len(result) == 3, f"应提取 3 条有效记录，实际 {len(result)}: {result}"


# ============================================================================
# Task 4: Teacher Matcher Tests
# ============================================================================

from tools.update_teachers_from_contacts import match_teachers


def test_match_teachers_for_update():
    """测试匹配现有教师进行更新"""
    # 模拟现有教师 - 使用 configure_mock 来设置属性
    existing = []
    for name_val, id_val in [('马云莺', 1), ('阴爱英', 2), ('陈欣', 3)]:
        mock = Mock()
        mock.configure_mock(name=name_val, id=id_val)
        existing.append(mock)

    # 通讯录数据
    contacts = [
        {'name': '马云莺', 'teacher_id': '02114818', 'phone': '13950308256', 'title': '讲师'},
        {'name': '张三', 'teacher_id': '99991001', 'phone': '13800000001', 'title': '教授'},
    ]

    result = match_teachers(existing, contacts)

    # 验证需要更新的数量
    assert len(result['to_update']) == 1
    assert result['to_update'][0]['teacher'].name == '马云莺'

    # 验证需要插入的数量
    assert len(result['to_insert']) == 1
    assert result['to_insert'][0]['name'] == '张三'


def test_match_teachers_case_insensitive():
    """测试姓名匹配不区分大小写"""
    mock = Mock()
    mock.configure_mock(name='马云莺', id=1)
    existing = [mock]
    contacts = [{'name': '马云莺', 'teacher_id': '001', 'phone': '111', 'title': '讲师'}]

    result = match_teachers(existing, contacts)

    assert len(result['to_update']) == 1


def test_match_teachers_no_match():
    """测试没有匹配到的情况"""
    mock = Mock()
    mock.configure_mock(name='王五', id=1)
    existing = [mock]
    contacts = [{'name': '赵六', 'teacher_id': '001', 'phone': '111', 'title': '讲师'}]

    result = match_teachers(existing, contacts)

    assert len(result['to_update']) == 0
    assert len(result['to_insert']) == 1


# ============================================================================
# Task 6: Teacher Updater Tests
# ============================================================================

from tools.update_teachers_from_contacts import update_teacher_info


def test_update_teacher_success():
    """测试成功更新教师信息"""
    # 模拟 teacher_manager
    mock_manager = Mock()
    mock_manager.update_teacher.return_value = True

    # 模拟数据库连接
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_manager._get_db_connection.return_value = mock_conn

    # 模拟教师对象
    mock_teacher = Mock()
    mock_teacher.configure_mock(id=1, name='马云莺', teacher_id='02114818')

    # 更新数据
    data = {
        'teacher_id': '02114818',
        'phone': '13950308256',
        'title': '讲师'
    }

    from unittest.mock import patch
    with patch('backend.orm.repositories.UserRepository') as mock_repo:
        result = update_teacher_info(mock_manager, mock_teacher, data)

        # M1 后半②：直写 users 真源（update_profile + update_login_code）
        mock_repo.update_profile.assert_called_once_with(
            '02114818', phone='13950308256', title='讲师')
        # 工号未变（teacher.teacher_id 也是 02114818）→ 不调 update_login_code
        mock_repo.update_login_code.assert_not_called()
        assert result is True


def test_update_teacher_failure():
    """测试更新失败情况（M1 后：mock UserRepository.update_profile 抛异常）"""
    mock_manager = Mock()

    mock_teacher = Mock()
    mock_teacher.configure_mock(id=1, name='马云莺', teacher_id='02114818')
    data = {'teacher_id': '001', 'phone': '111', 'title': '讲师'}

    from unittest.mock import patch
    with patch('backend.orm.repositories.UserRepository') as mock_repo:
        mock_repo.update_profile.side_effect = Exception("Database error")
        result = update_teacher_info(mock_manager, mock_teacher, data)
        assert result is False


# ============================================================================
# Task 8: Teacher Inserter Tests
# ============================================================================

from tools.update_teachers_from_contacts import insert_new_teacher


def test_insert_new_teacher_success():
    """测试成功插入新教师"""
    mock_manager = Mock()
    mock_manager.add_teacher.return_value = Mock(id=100)

    data = {
        'name': '张三',
        'teacher_id': '99991001',
        'phone': '13800000001',
        'title': '教授'
    }

    from unittest.mock import patch
    with patch('backend.orm.repositories.UserRepository') as mock_repo:
        result = insert_new_teacher(mock_manager, data)

        # M1 后半②：直写 users 真源（create_user，角色 teacher + 首登改密）
        mock_repo.create_user.assert_called_once()
        call_args = mock_repo.create_user.call_args
        assert call_args.args[0] == '99991001'
        assert call_args.args[1] == '张三'
        assert call_args.args[2] == 'teacher'
        assert call_args.kwargs.get('phone') == '13800000001'
        assert call_args.kwargs.get('title') == '教授'
        assert result is True


def test_insert_new_teacher_failure():
    """测试插入失败情况"""
    mock_manager = Mock()

    data = {
        'name': '张三',
        'teacher_id': '99991001',
        'phone': '13800000001',
        'title': '教授'
    }

    from unittest.mock import patch
    with patch('backend.orm.repositories.UserRepository') as mock_repo:
        mock_repo.create_user.side_effect = Exception("Duplicate key")
        result = insert_new_teacher(mock_manager, data)
        assert result is False


# ============================================================================
# Task 10: Main Workflow Tests
# ============================================================================

from unittest.mock import patch, MagicMock
from tools.update_teachers_from_contacts import main


@patch('backend.models.teacher.TeacherManager')
@patch('config.loader.get_config_loader')
def test_main_integration(mock_get_config, mock_teacher_manager_class):
    """测试主流程集成"""
    # 模拟配置
    mock_config = MagicMock()
    mock_config.get_path.return_value = 'database/competitions.db'
    mock_get_config.return_value = mock_config

    # 模拟 teacher_manager
    mock_teacher_manager = MagicMock()
    existing_teachers = []
    for name_val, id_val in [('马云莺', 1), ('阴爱英', 2)]:
        mock = Mock()
        mock.configure_mock(name=name_val, id=id_val)
        existing_teachers.append(mock)

    mock_teacher_manager.teachers = existing_teachers
    mock_teacher_manager.update_teacher.return_value = True
    mock_teacher_manager.add_teacher.return_value = Mock(id=100)
    mock_teacher_manager_class.return_value = mock_teacher_manager

    # 运行主流程
    result = main('tests/fixtures/test_contacts.xlsx', dry_run=True)

    # 验证结果
    assert result['matched'] == 2  # 匹配到2个现有教师
    assert result['updated'] == 0   # dry_run 模式不实际更新
    assert result['inserted'] == 0


@patch('backend.models.teacher.TeacherManager')
@patch('config.loader.get_config_loader')
def test_main_with_real_updates(mock_get_config, mock_teacher_manager_class):
    """测试实际执行更新"""
    # 模拟配置
    mock_config = MagicMock()
    mock_config.get_path.return_value = 'database/competitions.db'
    mock_get_config.return_value = mock_config

    # 模拟 teacher_manager
    mock_teacher_manager = MagicMock()
    existing_teachers = []
    for name_val, id_val in [('马云莺', 1)]:
        mock = Mock()
        mock.configure_mock(name=name_val, id=id_val)
        existing_teachers.append(mock)

    mock_teacher_manager.teachers = existing_teachers
    mock_teacher_manager.update_teacher.return_value = True
    mock_teacher_manager.add_teacher.return_value = Mock(id=100)
    mock_teacher_manager_class.return_value = mock_teacher_manager

    # 运行主流程（非 dry_run）——M1 后半②：更新走 UserRepository.update_profile
    from unittest.mock import patch
    with patch('backend.orm.repositories.UserRepository') as mock_repo:
        mock_repo.update_profile.return_value = True
        result = main('tests/fixtures/test_contacts.xlsx', dry_run=False)
        assert mock_repo.update_profile.called
        assert result['updated'] >= 1
