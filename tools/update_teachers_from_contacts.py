# tools/update_teachers_from_contacts.py
import pandas as pd
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目根目录到路径，确保可以导入 config 和 backend 模块
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

def parse_contacts_excel(file_path: str) -> List[Dict[str, Optional[str]]]:
    """
    读取通讯录Excel文件，提取教师数据

    支持格式：.xls 和 .xlsx
    布局：双列布局（左半部分列0-4，右半部分列5-9）
    前3行为标题行，从第4行（索引3）开始是数据

    Args:
        file_path: Excel文件路径

    Returns:
        [{'name': str, 'teacher_id': str, 'phone': str, 'title': Optional[str]}, ...]

    Raises:
        FileNotFoundError: 文件不存在
        Exception: 读取Excel文件失败
    """
    try:
        df = pd.read_excel(file_path, header=None)
    except FileNotFoundError:
        logger.error(f"文件不存在: {file_path}")
        raise
    except Exception as e:
        logger.error(f"读取Excel文件失败: {e}")
        raise

    results = []

    # 从第4行（索引3）开始是数据
    for i in range(3, len(df)):
        row = df.iloc[i]

        # 处理左半部分（列0-4）
        if pd.notna(row[1]):  # 姓名列
            name = str(row[1]).strip()
            if name:  # 跳过空姓名
                teacher_id = str(row[2]).strip() if pd.notna(row[2]) else None
                phone = str(row[3]).strip() if pd.notna(row[3]) else None
                title = str(row[4]).strip() if pd.notna(row[4]) else None
                if title == 'nan' or title == 'None':
                    title = None

                results.append({
                    'name': name,
                    'teacher_id': teacher_id,
                    'phone': phone,
                    'title': title
                })

        # 处理右半部分（列5-9）
        if pd.notna(row[6]):  # 姓名列
            name = str(row[6]).strip()
            if name:
                teacher_id = str(row[7]).strip() if pd.notna(row[7]) else None
                phone = str(row[8]).strip() if pd.notna(row[8]) else None
                title = str(row[9]).strip() if pd.notna(row[9]) else None
                if title == 'nan' or title == 'None':
                    title = None

                results.append({
                    'name': name,
                    'teacher_id': teacher_id,
                    'phone': phone,
                    'title': title
                })

    logger.info(f"解析Excel文件，找到 {len(results)} 条教师记录")
    return results


def match_teachers(existing_teachers: List, contacts_data: List[Dict]) -> Dict:
    """
    按姓名匹配现有教师

    Args:
        existing_teachers: 现有教师对象列表
        contacts_data: 通讯录数据列表

    Returns:
        {
            'to_update': [{'teacher': obj, 'data': dict}, ...],
            'to_insert': [dict, ...]
        }
    """
    # 构建姓名索引（不区分大小写）
    name_index = {}
    for teacher in existing_teachers:
        name = str(teacher.name)
        name_lower = name.lower()
        name_index[name_lower] = teacher

    to_update = []
    to_insert = []

    for contact in contacts_data:
        name = contact['name']
        name_lower = str(name).lower()

        if name_lower in name_index:
            # 找到匹配的教师
            teacher = name_index[name_lower]
            to_update.append({
                'teacher': teacher,
                'data': contact
            })
            logger.debug(f"匹配到现有教师: {name}")
        else:
            # 新教师
            to_insert.append(contact)
            logger.debug(f"新教师: {name}")

    logger.info(f"匹配结果: 需要更新 {len(to_update)} 条, 需要新增 {len(to_insert)} 条")

    return {
        'to_update': to_update,
        'to_insert': to_insert
    }


def update_teacher_info(teacher_manager, teacher, data: Dict) -> bool:
    """
    更新教师的工号、手机号、职称

    Args:
        teacher_manager: TeacherManager 实例
        teacher: 教师对象
        data: 更新数据字典

    Returns:
        bool: 更新是否成功
    """
    try:
        # 构建更新参数
        # 注意：不能将 'teacher_id' 作为关键字参数传递，
        # 因为 update_teacher 的第一个参数也叫 teacher_id（数据库主键）
        # 所以需要特殊处理 teacher_id 字段的更新
        updates = {}

        # M1 后半②：视图化后旧表不可写——更新直写 users 真源
        from backend.orm.repositories import UserRepository
        updates = {}
        if data.get('phone') is not None:
            updates['phone'] = data.get('phone')
        if data.get('title') is not None:
            updates['title'] = data.get('title')
        if updates:
            UserRepository.update_profile(teacher.teacher_id, **updates)
        # 工号变更 = users.login_code 变更（id 不变，历史引用安全）
        if data.get('teacher_id') is not None and data['teacher_id'] != teacher.teacher_id:
            UserRepository.update_login_code(teacher.teacher_id, data['teacher_id'])

        logger.info(f"✓ 更新: {teacher.name} (工号: {data.get('teacher_id')}, 手机: {data.get('phone')}, 职称: {data.get('title')})")
        return True
    except Exception as e:
        logger.error(f"✗ 更新失败 {teacher.name}: {e}")
        return False


def insert_new_teacher(teacher_manager, data: Dict) -> bool:
    """
    插入新教师记录

    Args:
        teacher_manager: TeacherManager 实例
        data: 教师数据字典

    Returns:
        bool: 插入是否成功
    """
    try:
        from werkzeug.security import generate_password_hash
        from app.password_policy import generate_strong_password
        initial_password = generate_strong_password()   # P1-2：随机强密码，无默认密码
        password_hash = generate_password_hash(initial_password)
        # M1 后半②：视图化后旧表不可写——新增直写 users 真源
        from backend.orm.repositories import UserRepository
        UserRepository.create_user(
            data.get('teacher_id'), data.get('name'), 'teacher',
            password_hash, needs_password_change=1,
            phone=data.get('phone'), title=data.get('title'),
            department='计算机工程系')   # 默认部门
        logger.info(f"✓ 新增: {data.get('name')} (工号: {data.get('teacher_id')}, 手机: {data.get('phone')}, 职称: {data.get('title')})")
        return True
    except Exception as e:
        logger.error(f"✗ 新增失败 {data.get('name')}: {e}")
        return False


def main(excel_file_path: str, dry_run: bool = False) -> Dict:
    """
    主流程：读取Excel、匹配、更新/插入

    Args:
        excel_file_path: Excel文件路径
        dry_run: 是否为预览模式（不实际修改数据库）

    Returns:
        {
            'total': int,      # 通讯录总记录数
            'matched': int,    # 匹配到的现有教师数
            'updated': int,    # 成功更新数
            'inserted': int,   # 成功插入数
            'failed': int      # 失败数
        }
    """
    print("=== 教师信息更新工具 ===")
    print(f"读取通讯录: {excel_file_path}")

    # 1. 解析Excel
    contacts_data = parse_contacts_excel(excel_file_path)
    total = len(contacts_data)
    print(f"找到教师记录: {total}条")

    # 2. 加载配置并获取数据库路径
    from config.loader import get_config
    config = get_config()
    db_path = config.get_path("database", "competitions_db")

    if not db_path:
        logger.error("无法获取数据库路径")
        raise RuntimeError("数据库路径未配置")

    # 3. 加载现有教师
    from backend.models.teacher import TeacherManager
    teacher_manager = TeacherManager(str(db_path))
    existing_teachers = teacher_manager.teachers

    # 4. 匹配分类
    match_result = match_teachers(existing_teachers, contacts_data)
    to_update = match_result['to_update']
    to_insert = match_result['to_insert']

    print(f"\n匹配结果:")
    print(f"  - 需要更新: {len(to_update)}条")
    print(f"  - 需要新增: {len(to_insert)}条")

    # 初始化统计
    stats = {
        'total': total,
        'matched': len(to_update),
        'updated': 0,
        'inserted': 0,
        'failed': 0
    }

    if dry_run:
        print("\n[预览模式] 不会实际修改数据库")
        print("\n将要更新的记录:")
        for item in to_update:
            t = item['teacher']
            d = item['data']
            print(f"  {t.name} -> 工号: {d['teacher_id']}, 手机: {d['phone']}, 职称: {d['title']}")

        print("\n将要新增的记录:")
        for item in to_insert:
            print(f"  {item['name']} -> 工号: {item['teacher_id']}, 手机: {item['phone']}, 职称: {item['title']}")

        return stats

    # 5. 执行更新
    print("\n执行更新:")
    for item in to_update:
        if update_teacher_info(teacher_manager, item['teacher'], item['data']):
            stats['updated'] += 1
        else:
            stats['failed'] += 1

    # 6. 执行插入
    print("\n执行插入:")
    for item in to_insert:
        if insert_new_teacher(teacher_manager, item):
            stats['inserted'] += 1
        else:
            stats['failed'] += 1

    # 7. 输出报告
    print(f"\n=== 完成 ===")
    print(f"更新: {stats['updated']}条")
    print(f"新增: {stats['inserted']}条")
    print(f"失败: {stats['failed']}条")

    return stats


if __name__ == '__main__':
    import sys

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )

    # 解析命令行参数
    excel_path = 'data/1、计算机工程系通讯录.xls'
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv

    if len(sys.argv) > 1 and sys.argv[1] not in ['--dry-run', '-n', '-h', '--help']:
        excel_path = sys.argv[1]

    # 执行
    try:
        main(excel_path, dry_run=dry_run)
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)
