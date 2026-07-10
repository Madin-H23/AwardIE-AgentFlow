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


def test_parse_excel_with_empty_name():
    """测试跳过空姓名记录"""
    # TODO: 添加包含空姓名的测试数据，验证解析器能正确跳过
    pytest.skip("待实现：需要创建包含空姓名的测试数据")


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
    mock_teacher.configure_mock(id=1, name='马云莺')

    # 更新数据
    data = {
        'teacher_id': '02114818',
        'phone': '13950308256',
        'title': '讲师'
    }

    result = update_teacher_info(mock_manager, mock_teacher, data)

    # 验证调用了 update_teacher（只传递 phone 和 title，不传递 teacher_id 关键字参数）
    mock_manager.update_teacher.assert_called_once_with(
        1,  # teacher.id
        phone='13950308256',
        title='讲师'
    )
    # 验证执行了 SQL 更新 teacher_id
    mock_cursor.execute.assert_called_once_with(
        'UPDATE teachers SET teacher_id = ? WHERE id = ?',
        ('02114818', 1)
    )
    # 验证数据库事务提交
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()
    assert result is True


def test_update_teacher_failure():
    """测试更新失败情况"""
    mock_manager = Mock()
    mock_manager.update_teacher.side_effect = Exception("Database error")

    # 模拟数据库连接
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_manager._get_db_connection.return_value = mock_conn

    mock_teacher = Mock()
    mock_teacher.configure_mock(id=1, name='马云莺')
    data = {'teacher_id': '001', 'phone': '111', 'title': '讲师'}

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

    result = insert_new_teacher(mock_manager, data)

    # 验证调用了 add_teacher
    mock_manager.add_teacher.assert_called_once_with(
        teacher_id='99991001',
        name='张三',
        phone='13800000001',
        title='教授',
        department='计算机工程系'
    )
    assert result is True


def test_insert_new_teacher_failure():
    """测试插入失败情况"""
    mock_manager = Mock()
    mock_manager.add_teacher.side_effect = Exception("Duplicate key")

    data = {
        'name': '张三',
        'teacher_id': '99991001',
        'phone': '13800000001',
        'title': '教授'
    }

    result = insert_new_teacher(mock_manager, data)

    assert result is False


# ============================================================================
# Task 10: Main Workflow Tests
# ============================================================================

from unittest.mock import patch, MagicMock
from tools.update_teachers_from_contacts import main


@patch('backend.models.teacher.TeacherManager')
@patch('config.loader.get_config')
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
@patch('config.loader.get_config')
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

    # 运行主流程（非 dry_run）
    result = main('tests/fixtures/test_contacts.xlsx', dry_run=False)

    # 验证实际调用了更新
    assert mock_teacher_manager.update_teacher.called
    assert result['updated'] >= 1
