"""
文件提交审核流程测试

测试文件提交、解析、保存到 pending_achievements 表的完整流程。

使用方法:
    python tests/test_files_commit.py

作者: Claude
日期: 2026-01-20
"""
import os
import sys
import base64
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from io import BytesIO
import re
import webbrowser

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def validate_innovation_project(data: dict) -> dict:
    """验证单个大创项目数据"""
    issues = []
    
    # 验证配置
    valid_levels = ['国家级', '省级', '院级']
    zh_min_length = 2
    zh_max_length = 4
    min_year = 2000
    max_year = datetime.now().year + 1
    
    def is_valid_chinese_name(name):
        if not name or not isinstance(name, str):
            return False
        name = name.strip()
        if len(name) < zh_min_length or len(name) > zh_max_length:
            return False
        if not re.match(r'^[\u4e00-\u9fa5·]+$', name):
            return False
        return True
    
    # 1. 检查项目名称
    if not data.get('项目名称'):
        issues.append('缺少项目名称')
    
    # 2. 检查学生负责人
    leader = data.get('学生负责人')
    if not leader:
        issues.append('缺少项目负责人')
    elif isinstance(leader, dict):
        leader_name = leader.get('姓名', '')
        if not leader_name:
            issues.append('项目负责人姓名为空')
        elif not is_valid_chinese_name(leader_name):
            issues.append(f'项目负责人姓名不合法: {leader_name}')
    
    # 3. 检查指导教师
    teachers = data.get('指导教师')
    if not teachers:
        issues.append('缺少指导教师')
    elif isinstance(teachers, list):
        if len(teachers) == 0:
            issues.append('指导教师列表为空')
        else:
            for teacher in teachers:
                if not is_valid_chinese_name(teacher):
                    issues.append(f'指导教师姓名不合法: {teacher}')
    
    # 4. 检查项目级别
    level = data.get('项目级别')
    if not level:
        issues.append('缺少项目级别')
    elif level not in valid_levels:
        issues.append(f'项目级别不合法: {level}')
    
    # 5. 检查年份
    year = data.get('年份')
    if year is None:
        issues.append('缺少年份')
    elif isinstance(year, int):
        if year < min_year or year > max_year:
            issues.append(f'年份超出范围: {year}')
    
    return {
        'is_valid': len(issues) == 0,
        'issues': issues
    }


class MockFile:
    """模拟Flask的文件对象，用于测试文件上传服务"""
    def __init__(self, file_path: Path):
        self.filename = file_path.name
        self.file_path = file_path
        self.content = None

    def read(self):
        """读取文件内容"""
        if self.content is None:
            with open(self.file_path, 'rb') as f:
                self.content = f.read()
        return self.content

    def save(self, dst_path: str):
        """保存文件到目标路径"""
        import shutil
        shutil.copy(str(self.file_path), dst_path)


class FileCommitTester:
    """文件提交测试器"""

    # 默认测试账号配置
    DEFAULT_ACCOUNTS = {
        'teacher': {
            'id': '02114818',
            'name': '教师（默认）',
            'type': 'teacher'
        },
        'student': {
            'id': '212306413',
            'name': '陈品天',
            'type': 'student',
            'laboratory': '智创学生实验室'
        },
        'admin': {
            'id': 'admin',
            'name': '管理员',
            'type': 'admin'
        }
    }

    def __init__(self):
        self.test_images_dir = Path(__file__).parent.parent / "images" / "测试图片"
        self.selected_path: Optional[Path] = None
        self.results: List[Dict[str, Any]] = []
        self.current_submitter = None
        self.upload_service = None
        self.pending_manager = None
        self.review_log_manager = None
        self.laboratory_manager = None
        self.student_manager = None
        self.teacher_manager = None
        self.db_path = None
        self.files_dir = None
        
        # ReviewService 实例
        self.review_service = None

        # 存储OCR和LLM厂商信息
        self.ocr_provider = "unknown"
        self.llm_provider = "unknown"
        
        # 成果类型映射（从 ReviewService 常量获取）
        from backend.services.review_service import ACHIEVEMENT_TYPES, IMAGE_EXTENSIONS
        self.ACHIEVEMENT_TYPES = ACHIEVEMENT_TYPES
        
        # 图片文件扩展名（从 ReviewService 常量获取）
        self.IMAGE_EXTENSIONS = IMAGE_EXTENSIONS

    def print_separator(self, title: str = "") -> str:
        """生成分隔线"""
        if title:
            return f"\n{'=' * 20} {title} {'=' * 20}"
        else:
            return "=" * 60

    def init_services(self):
        """初始化服务"""
        from config.loader import get_config
        from backend.services.file_upload_service import FileUploadService
        from backend.services.review_service import ReviewService
        from backend.models.pending_achievement import PendingAchievementManager
        from backend.models.review_log import ReviewLogManager
        from backend.models.laboratory import LaboratoryManager
        from backend.models.student import StudentManager
        from backend.models.teacher import TeacherManager
        from backend.models.award import AwardManager
        from backend.models.patent import PatentManager
        from backend.models.software_copyright import SoftwareCopyrightManager
        from backend.models.innovation_project import InnovationProjectManager
        from backend.models.competition import CompetitionManager
        from backend.services.context import ServiceContext

        # 获取配置
        config_loader = get_config()
        self.config = config_loader.load_config()

        # 使用统一文件管理器获取临时目录
        from backend.services.unified_file_manager import get_unified_file_manager, SessionStatus
        file_manager = get_unified_file_manager()
        temp_dir = file_manager.files_root / SessionStatus.TEMP_UPLOAD.directory / "uploads"
        self.files_dir = config_loader.get_path("files")
        
        # 直接获取数据库路径
        db_path = project_root / "database" / "competitions.db"
        self.db_path = str(db_path)

        # 直接创建管理器实例（不依赖Flask上下文）
        self.student_manager = StudentManager(str(db_path))
        self.teacher_manager = TeacherManager(str(db_path))
        self.pending_manager = PendingAchievementManager(str(db_path))
        self.review_log_manager = ReviewLogManager(str(db_path))
        self.laboratory_manager = LaboratoryManager(
            str(db_path),
            student_manager=self.student_manager,
            teacher_manager=self.teacher_manager
        )
        
        # 创建各类型成果 Manager（用于 ReviewService 提交到主表）
        self.competition_manager = CompetitionManager(str(db_path))
        self.award_manager = AwardManager(str(db_path), images_dir=self.files_dir / "images")
        self.patent_manager = PatentManager(str(db_path), files_dir=self.files_dir / "patents")
        self.software_manager = SoftwareCopyrightManager(str(db_path), files_dir=self.files_dir / "software")
        self.innovation_manager = InnovationProjectManager(str(db_path), files_dir=self.files_dir / "innovation")

        # 初始化ServiceContext以获取文档抽取器
        try:
            self.service_context = ServiceContext()
        except Exception as e:
            print(f"警告: ServiceContext初始化失败: {e}")
            self.service_context = None

        # 创建上传服务
        self.upload_service = FileUploadService(
            temp_dir=temp_dir,
            pending_manager=self.pending_manager,
            laboratory_manager=self.laboratory_manager
        )
        
        # 创建 ReviewService（包含所有 Manager）
        self.review_service = ReviewService(
            pending_manager=self.pending_manager,
            review_log_manager=self.review_log_manager,
            laboratory_manager=self.laboratory_manager,
            student_manager=self.student_manager,
            teacher_manager=self.teacher_manager,
            # 各类型成果 Manager
            award_manager=self.award_manager,
            patent_manager=self.patent_manager,
            software_manager=self.software_manager,
            innovation_manager=self.innovation_manager,
            competition_manager=self.competition_manager,
            # 配置
            files_dir=self.files_dir
        )

        # 获取OCR和LLM厂商信息
        ocr_provider = self.config.get('ocr', {}).get('default_provider', 'unknown')
        llm_provider = self.config.get('llm', {}).get('default_provider', 'unknown')
        self.ocr_provider = ocr_provider
        self.llm_provider = llm_provider

        return True

    def show_role_menu(self) -> bool:
        """显示角色选择菜单"""
        print(self.print_separator("选择上传角色"))
        print("\n请选择上传角色:")
        print("  1. 教师（工号: 02114818）")
        print("  2. 学生（学号: 212306413，陈品天，智创学生实验室）")
        print("  3. 管理员")
        print("  q. 退出")
        print()

        while True:
            choice = input("请输入选项 (1-3, q): ").strip()
            if choice.lower() == 'q':
                return False
            elif choice == '1':
                self.current_submitter = self.DEFAULT_ACCOUNTS['teacher'].copy()
                # 获取教师ID（需要从数据库查询）
                self._get_teacher_id_from_db()
                return True
            elif choice == '2':
                self.current_submitter = self.DEFAULT_ACCOUNTS['student'].copy()
                # 获取学生ID（需要从数据库查询）
                self._get_student_id_from_db()
                return True
            elif choice == '3':
                self.current_submitter = self.DEFAULT_ACCOUNTS['admin'].copy()
                # 管理员ID固定为1
                self.current_submitter['db_id'] = 1
                return True
            else:
                print("无效选项，请重新输入")

    def _get_student_id_from_db(self):
        """从数据库获取学生ID"""
        from backend.models.student import StudentManager
        db_path = project_root / "database" / "competitions.db"
        student_manager = StudentManager(str(db_path))
        student = student_manager.get_student_by_student_id(self.current_submitter['id'])
        if student:
            self.current_submitter['db_id'] = student.id
            print(f"\n已选择: {self.current_submitter['name']} (ID: {student.id})")
        else:
            print(f"\n警告: 未找到学号为 {self.current_submitter['id']} 的学生，使用ID=1")
            self.current_submitter['db_id'] = 1

    def _get_teacher_id_from_db(self):
        """从数据库获取教师ID"""
        from backend.models.teacher import TeacherManager
        db_path = project_root / "database" / "competitions.db"
        teacher_manager = TeacherManager(str(db_path))
        teacher = teacher_manager.get_teacher_by_teacher_id(self.current_submitter['id'])
        if teacher:
            self.current_submitter['db_id'] = teacher.id
            print(f"\n已选择: {self.current_submitter['name']} (ID: {teacher.id})")
        else:
            print(f"\n警告: 未找到工号为 {self.current_submitter['id']} 的教师，使用ID=1")
            self.current_submitter['db_id'] = 1

    def show_action_menu(self) -> Optional[str]:
        """显示操作菜单"""
        print(self.print_separator("选择操作"))
        print(f"\n当前角色: {self.current_submitter['name']} ({self.current_submitter['type']})")
        print("\n请选择操作:")
        print("  1. 提交文件")
        print("  2. 审核提交记录")
        print("  b. 返回（重新选择角色）")
        print("  q. 退出")
        print()

        while True:
            choice = input("请输入选项 (1-2, b, q): ").strip().lower()
            if choice == 'q':
                return 'quit'
            elif choice == 'b':
                return 'back'
            elif choice == '1':
                return 'submit'
            elif choice == '2':
                return 'review'
            else:
                print("无效选项，请重新输入")

    # ============================================================
    # 审核提交记录相关方法
    # ============================================================

    def show_review_menu(self):
        """审核提交记录主入口"""
        while True:
            # 显示第一级菜单：成果类型
            category = self.show_review_category_menu()
            if category is None:
                return  # 用户选择返回
            
            # 显示第二级菜单：验证状态
            result = self.show_review_status_menu(category)
            if result == 'back':
                continue  # 返回第一级菜单
            elif result == 'quit':
                return  # 退出审核菜单

    def show_review_category_menu(self) -> Optional[str]:
        """显示第一级菜单：成果类型分类"""
        # 先获取各类型的统计数据
        stats = self._get_pending_stats_by_type()
        
        print(self.print_separator("审核提交记录 - 选择成果类型"))
        print()
        
        # 显示各类型及其数量
        type_keys = list(self.ACHIEVEMENT_TYPES.keys())
        for idx, type_key in enumerate(type_keys, 1):
            type_name = self.ACHIEVEMENT_TYPES[type_key]
            type_stats = stats.get(type_key, {'valid': 0, 'invalid': 0, 'total': 0})
            total = type_stats['total']
            valid = type_stats['valid']
            invalid = type_stats['invalid']
            
            if total > 0:
                print(f"  {idx}. {type_name} (共{total}条: 验证通过{valid}, 待修订{invalid})")
            else:
                print(f"  {idx}. {type_name} (无记录)")
        
        print()
        print("  b. 返回")
        print("  q. 退出")
        print()
        
        while True:
            choice = input(f"请选择类型 (1-{len(type_keys)}, b, q): ").strip().lower()
            if choice == 'q':
                return None
            elif choice == 'b':
                return None
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(type_keys):
                    selected_type = type_keys[idx]
                    type_stats = stats.get(selected_type, {'total': 0})
                    if type_stats['total'] == 0:
                        print(f"\n{self.ACHIEVEMENT_TYPES[selected_type]} 类型没有待审核的记录")
                        continue
                    return selected_type
                else:
                    print("无效选项")
            else:
                print("无效选项")

    def show_review_status_menu(self, category: str) -> str:
        """
        显示第二级菜单：验证状态
        
        Returns:
            'back' - 返回上级菜单
            'quit' - 退出审核菜单
            'done' - 处理完成
        """
        while True:
            # 获取该类型下的待审核记录
            pending_list = self._get_pending_by_type(category)
            
            # 分类为验证通过和待修订
            valid_items = [p for p in pending_list if self._is_validation_passed(p)]
            invalid_items = [p for p in pending_list if not self._is_validation_passed(p)]
            
            category_name = self.ACHIEVEMENT_TYPES.get(category, category)
            print(self.print_separator(f"审核 {category_name} - 选择验证状态"))
            print()
            print(f"  1. 验证通过 ({len(valid_items)}条)")
            print(f"  2. 待修订 ({len(invalid_items)}条)")
            print()
            print("  b. 返回（选择其他类型）")
            print("  q. 退出审核")
            print()
            
            choice = input("请选择 (1-2, b, q): ").strip().lower()
            
            if choice == 'q':
                return 'quit'
            elif choice == 'b':
                return 'back'
            elif choice == '1':
                if not valid_items:
                    print("\n没有验证通过的记录")
                    continue
                self._review_pending_list(valid_items, category, is_valid=True)
            elif choice == '2':
                if not invalid_items:
                    print("\n没有待修订的记录")
                    continue
                self._review_pending_list(invalid_items, category, is_valid=False)
            else:
                print("无效选项")

    def _get_pending_stats_by_type(self) -> Dict[str, Dict[str, int]]:
        """获取各类型的统计数据"""
        stats = {key: {'valid': 0, 'invalid': 0, 'total': 0} for key in self.ACHIEVEMENT_TYPES.keys()}
        
        for pending in self.pending_manager.pending:
            achievement_type = pending.achievement_type or 'other'
            if achievement_type not in stats:
                achievement_type = 'other'
            
            stats[achievement_type]['total'] += 1
            if self._is_validation_passed(pending):
                stats[achievement_type]['valid'] += 1
            else:
                stats[achievement_type]['invalid'] += 1
        
        return stats

    def _get_pending_by_type(self, category: str) -> List:
        """获取指定类型的待审核记录"""
        from backend.models.pending_achievement import PendingAchievementFilter
        filter_obj = PendingAchievementFilter(achievement_type=category)
        return self.pending_manager.query_pending(filter_obj)

    def _is_validation_passed(self, pending) -> bool:
        """判断验证是否通过"""
        validation = pending.get_validation_result()
        return validation.get('is_valid', False)

    def _review_pending_list(self, pending_list: List, category: str, is_valid: bool):
        """审核待审核记录列表"""
        status_name = "验证通过" if is_valid else "待修订"
        category_name = self.ACHIEVEMENT_TYPES.get(category, category)
        
        current_idx = 0
        while current_idx < len(pending_list):
            # 每次循环从列表获取 pending，然后刷新获取最新数据
            pending_from_list = pending_list[current_idx]
            pending = self.pending_manager.get_pending_by_id(pending_from_list.id)
            
            if not pending:
                # 记录已被删除，刷新列表
                pending_list = [p for p in self._get_pending_by_type(category) 
                               if self._is_validation_passed(p) == is_valid]
                if current_idx >= len(pending_list):
                    current_idx = len(pending_list) - 1
                if current_idx < 0:
                    print("\n所有记录已处理完毕")
                    return
                continue
            
            print(self.print_separator(f"审核 {category_name} - {status_name} [{current_idx + 1}/{len(pending_list)}]"))
            
            # 显示记录详情
            self._display_pending_detail(pending)
            
            # 显示操作菜单
            print("\n操作选项:")
            if is_valid:
                print("  1. 确认通过（关联实验室并提交）")
                print("  2. 跳过")
                print("  3. 删除记录")
                print("  n. 下一条")
                print("  p. 上一条")
                print("  b. 返回")
                print()

                choice = input("请选择: ").strip().lower()

                if choice == '1':
                    self._confirm_valid_pending(pending)
                    # 重新获取列表（因为可能已删除）
                    pending_list = [p for p in self._get_pending_by_type(category) if self._is_validation_passed(p)]
                    if current_idx >= len(pending_list):
                        current_idx = len(pending_list) - 1
                    if current_idx < 0:
                        print("\n所有记录已处理完毕")
                        return
                elif choice == '2':
                    current_idx += 1
                elif choice == '3':
                    print("\n确认删除此记录及关联文件？")
                    confirm = input("(y/n): ").strip().lower()
                    if confirm == 'y':
                        self._delete_pending(pending)
                        pending_list = [p for p in self._get_pending_by_type(category) if self._is_validation_passed(p)]
                        if current_idx >= len(pending_list):
                            current_idx = len(pending_list) - 1
                        if current_idx < 0:
                            print("\n所有记录已处理完毕")
                            return
                elif choice == 'n':
                    current_idx += 1
                elif choice == 'p':
                    current_idx = max(0, current_idx - 1)
                elif choice == 'b':
                    return
            else:
                print("  1. 修改字段（重新验证）")
                print("  2. 强制通过（跳过验证）")
                print("  3. 删除记录")
                print("  n. 下一条")
                print("  p. 上一条")
                print("  b. 返回")
                print()
                
                choice = input("请选择: ").strip().lower()
                
                if choice == '1':
                    result = self._show_revision_menu(pending)
                    
                    # 重新获取最新的 pending 对象
                    pending = self.pending_manager.get_pending_by_id(pending.id)
                    if not pending:
                        print("\n记录已不存在")
                        pending_list = [p for p in self._get_pending_by_type(category) if not self._is_validation_passed(p)]
                        if current_idx >= len(pending_list):
                            current_idx = len(pending_list) - 1
                        if current_idx < 0:
                            print("\n所有记录已处理完毕")
                            return
                        continue
                    
                    # 检查返回值，如果用户选择提交
                    if result == 'submit':
                        self._confirm_valid_pending(pending)
                        pending_list = [p for p in self._get_pending_by_type(category) if not self._is_validation_passed(p)]
                        if current_idx >= len(pending_list):
                            current_idx = len(pending_list) - 1
                        if current_idx < 0:
                            print("\n所有记录已处理完毕")
                            return
                    # 如果验证通过但用户没有选择提交，继续显示当前记录（刷新后的）
                    # 由于 pending 已刷新，下一次循环会显示正确的验证状态
                    
                elif choice == '2':
                    print("\n确认强制通过？这将跳过验证直接提交。")
                    confirm = input("(y/n): ").strip().lower()
                    if confirm == 'y':
                        self._confirm_valid_pending(pending, force=True)
                        pending_list = [p for p in self._get_pending_by_type(category) if not self._is_validation_passed(p)]
                        if current_idx >= len(pending_list):
                            current_idx = len(pending_list) - 1
                        if current_idx < 0:
                            print("\n所有记录已处理完毕")
                            return
                elif choice == '3':
                    print("\n确认删除此记录及关联文件？")
                    confirm = input("(y/n): ").strip().lower()
                    if confirm == 'y':
                        self._delete_pending(pending)
                        pending_list = [p for p in self._get_pending_by_type(category) if not self._is_validation_passed(p)]
                        if current_idx >= len(pending_list):
                            current_idx = len(pending_list) - 1
                        if current_idx < 0:
                            print("\n所有记录已处理完毕")
                            return
                elif choice == 'n':
                    current_idx += 1
                elif choice == 'p':
                    current_idx = max(0, current_idx - 1)
                elif choice == 'b':
                    return

    def _display_pending_detail(self, pending):
        """显示待审核记录的详情"""
        data = pending.get_achievement_data()
        validation = pending.get_validation_result()
        
        print(f"\n[ID: {pending.id}]")
        print(f"类型: {self.ACHIEVEMENT_TYPES.get(pending.achievement_type, pending.achievement_type)}")
        print(f"文件: {pending.file_path}")
        print(f"提交人: {pending.submitter_type}/{pending.submitter_id}")
        print(f"提交时间: {pending.created_at}")
        
        # 显示主要数据字段
        print("\n--- 数据内容 ---")
        if isinstance(data, dict):
            for key, value in data.items():
                if key not in ('import_session_id', 'file_path', 'preview_image_path'):
                    # 截断过长的值
                    str_value = str(value)
                    if len(str_value) > 100:
                        str_value = str_value[:100] + "..."
                    print(f"  {key}: {str_value}")
        
        # 显示识别的关联实验室
        print("\n--- 关联实验室 ---")
        lab_id, reason = self.review_service.determine_laboratory(pending)
        if lab_id:
            lab = self.laboratory_manager.get_laboratory_by_id(lab_id)
            lab_name = lab.name if lab else f"ID: {lab_id}"
            print(f"  实验室: {lab_name}")
            print(f"  关联原因: {reason}")
        else:
            print("  实验室: 无")
            print("  说明: 无法自动关联实验室")
        
        # 显示验证结果
        print("\n--- 验证结果 ---")
        is_valid = validation.get('is_valid', False)
        print(f"  验证状态: {'通过' if is_valid else '未通过'}")
        
        if not is_valid:
            # 使用 ReviewService 的 collect_validation_issues 方法来收集并去重问题
            all_issues = self.review_service.collect_validation_issues(validation)
            
            if all_issues:
                print("  问题列表:")
                for issue in all_issues:
                    field = issue.get('field', '未知')
                    message = issue.get('message', str(issue))
                    print(f"    - {field}: {message}")

    def _determine_laboratory(self, pending, interactive: bool = False) -> Optional[int]:
        """
        确定成果关联的实验室

        Args:
            pending: 待审核记录
            interactive: 是否允许交互式选择（用于 other 类型）

        Returns:
            实验室ID，如果无法确定则返回None
        """
        # 先尝试自动确定
        lab_id, reason = self.review_service.determine_laboratory(pending)

        # 如果是 other 类型且无法自动确定实验室，显示选择菜单
        if interactive and pending.achievement_type == 'other' and lab_id is None:
            lab_id = self._show_laboratory_selection_menu(pending)
            if lab_id:
                reason = f"用户手动选择实验室 (ID: {lab_id})"

        if lab_id and reason:
            print(f"  [实验室关联] {reason}")
        elif lab_id is None:
            print("  [实验室关联] 无法确定关联的实验室")
        return lab_id

    def _show_laboratory_selection_menu(self, pending) -> Optional[int]:
        """
        显示实验室选择菜单

        用于 other 类型文件需要手动指定实验室的情况

        Returns:
            选中的实验室ID，如果用户取消则返回None
        """
        # 获取学生所属的实验室
        if pending.submitter_type == 'student' and pending.submitter_id:
            student_labs = self._get_student_laboratories(pending.submitter_id)
        else:
            student_labs = []

        # 获取所有实验室
        all_labs = self.laboratory_manager.get_all()

        print("\n--- 学生实验室选择 ---")
        print(f"提交人: {pending.submitter_type}/{pending.submitter_id}")
        print(f"文件: {pending.file_path}")

        # 如果学生有所属实验室，优先显示
        if student_labs:
            print("\n学生所属实验室:")
            for i, lab in enumerate(student_labs, 1):
                print(f"  {i}. {lab.name} (ID: {lab.id})")

            print("\n其他实验室:")
            start_idx = len(student_labs) + 1
            for lab in all_labs:
                if lab not in student_labs:
                    print(f"  {start_idx}. {lab.name} (ID: {lab.id})")
                    start_idx += 1

            print("\n  0. 不关联实验室")
            print("  q. 取消审核")
            print()

            # 构建选项映射
            lab_options = student_labs + [lab for lab in all_labs if lab not in student_labs]

            while True:
                choice = input(f"请选择实验室 (0-{len(lab_options)}, q): ").strip().lower()

                if choice == 'q':
                    print("已取消审核")
                    return None
                elif choice == '0':
                    print("选择不关联实验室")
                    return None
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(lab_options):
                        selected_lab = lab_options[idx]
                        print(f"已选择: {selected_lab.name}")
                        return selected_lab.id
                    else:
                        print("无效选项")
                else:
                    print("无效输入")
        else:
            # 学生没有所属实验室，显示所有实验室
            print("\n可用实验室:")
            if not all_labs:
                print("  (无可用实验室)")
                return None

            for i, lab in enumerate(all_labs, 1):
                print(f"  {i}. {lab.name} (ID: {lab.id})")

            print("\n  0. 不关联实验室")
            print("  q. 取消审核")
            print()

            while True:
                choice = input(f"请选择实验室 (0-{len(all_labs)}, q): ").strip().lower()

                if choice == 'q':
                    print("已取消审核")
                    return None
                elif choice == '0':
                    print("选择不关联实验室")
                    return None
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(all_labs):
                        selected_lab = all_labs[idx]
                        print(f"已选择: {selected_lab.name}")
                        return selected_lab.id
                    else:
                        print("无效选项")
                else:
                    print("无效输入")

    def _get_student_laboratories(self, student_id: int) -> List:
        """获取学生所属的所有实验室 - 委托给 ReviewService"""
        return self.review_service.get_student_laboratories(student_id)

    def _confirm_valid_pending(self, pending, force: bool = False):
        """
        确认验证通过的记录，使用 ReviewService 执行审核操作

        Args:
            pending: 待审核记录
            force: 是否强制通过（跳过验证）
        """
        from backend.services.review_service import Reviewer

        print("\n--- 处理中 ---")

        # 对于 other 类型，如果无法自动确定实验室，显示选择菜单
        lab_id = None
        if pending.achievement_type == 'other':
            lab_id = self._determine_laboratory(pending, interactive=True)

        # 构建审核人信息
        reviewer = Reviewer(
            reviewer_type=self.current_submitter['type'],
            reviewer_id=self.current_submitter['id']
        )

        # 使用 ReviewService 执行审核（传入 lab_id）
        result = self.review_service.approve_single(
            pending_id=pending.id,
            reviewer=reviewer,
            lab_id=lab_id,
            force=force
        )

        # 显示结果
        print(f"\n成果类型: {self.ACHIEVEMENT_TYPES.get(pending.achievement_type, pending.achievement_type)}")

        if result.laboratory_name:
            print(f"关联实验室: {result.laboratory_name}")
        else:
            print("关联实验室: 无")

        if result.success:
            if result.target_table:
                print(f"\n[OK] 已提交到 {result.target_table} 表 (ID: {result.target_id})")
            if result.file_moved_to:
                print(f"[OK] 文件已移动到: {result.file_moved_to}")
            print(f"[OK] pending 记录已删除 (id: {result.pending_id})")
        else:
            print(f"\n[ERROR] 审核失败: {result.error}")

    def _handle_normal_type(self, pending, lab_id: Optional[int]):
        """处理普通类型成果 - 已由 _confirm_valid_pending 统一处理"""
        # 保留此方法以兼容旧代码，实际逻辑已移至 ReviewService
        pass

    def _handle_other_type(self, pending, lab_id: Optional[int]):
        """处理 other 类型成果 - 已由 _confirm_valid_pending 统一处理"""
        # 保留此方法以兼容旧代码，实际逻辑已移至 ReviewService
        pass

    def _is_image_file(self, file_path: str) -> bool:
        """判断文件是否为图片 - 委托给 ReviewService"""
        return self.review_service.is_image_file(file_path)

    def _move_to_lab_album(self, pending, lab_id: int):
        """将图片移动到实验室相册 - 已由 ReviewService 统一处理"""
        # 保留此方法以兼容旧代码，实际逻辑已移至 LaboratoryManager.move_file_to_album
        pass

    def _move_to_lab_downloads(self, pending, lab_id: int):
        """将文件移动到实验室下载专区 - 已由 ReviewService 统一处理"""
        # 保留此方法以兼容旧代码，实际逻辑已移至 LaboratoryManager.move_file_to_downloads
        pass

    def _delete_pending(self, pending):
        """删除 pending 记录及关联文件 - 使用 ReviewService"""
        from backend.services.review_service import Reviewer
        
        reviewer = Reviewer(
            reviewer_type=self.current_submitter['type'],
            reviewer_id=self.current_submitter['id']
        )
        
        result = self.review_service.discard_single(
            pending_id=pending.id,
            reviewer=reviewer,
            reason='用户手动删除'
        )
        
        if result.success:
            print(f"[OK] 记录已删除 (pending_id: {result.pending_id})")
        else:
            print(f"[ERROR] 删除失败: {result.error}")

    def _show_revision_menu(self, pending):
        """
        显示待修订编辑菜单
        
        允许用户选择验证失败的域进行修改，然后重新验证
        """
        pending_id = pending.id  # 保存 ID，用于重新获取最新数据
        
        while True:
            # 每次循环开始时重新获取 pending 对象，确保数据是最新的
            pending = self.pending_manager.get_pending_by_id(pending_id)
            if not pending:
                print("\n记录已不存在")
                return
            
            validation = pending.get_validation_result()
            data = pending.get_achievement_data()
            
            # 收集所有验证问题
            issues = self._collect_validation_issues(validation)
            
            if not issues:
                print("\n验证已通过，没有问题需要修改")
                # 验证通过后提示是否立即提交
                submit_choice = input("是否立即提交？(y/n): ").strip().lower()
                if submit_choice == 'y':
                    return 'submit'  # 返回特殊标记表示需要提交
                return 'passed'  # 返回标记表示验证已通过
            
            print(self.print_separator("修改字段"))
            print("\n验证失败的字段:")
            
            for idx, issue in enumerate(issues, 1):
                field = issue.get('field', '未知字段')
                message = issue.get('message', '未知错误')
                current_value = data.get(field, '(无)')
                if isinstance(current_value, (dict, list)):
                    current_value = json.dumps(current_value, ensure_ascii=False)[:50] + "..."
                print(f"  {idx}. {field}: {message}")
                print(f"      当前值: {current_value}")
            
            print()
            print("  r. 重新验证（不修改）")
            print("  b. 返回")
            print()
            
            choice = input(f"请选择要修改的字段 (1-{len(issues)}, r, b): ").strip().lower()
            
            if choice == 'b':
                return
            elif choice == 'r':
                self._revalidate_pending(pending)
                if self._is_validation_passed(pending):
                    print("\n验证已通过！")
                    return
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(issues):
                    field = issues[idx].get('field')
                    if field:
                        self._modify_field(pending, field)
                    else:
                        print("无法识别要修改的字段")
                else:
                    print("无效选项")
            else:
                print("无效选项")

    def _collect_validation_issues(self, validation: Dict) -> List[Dict]:
        """收集验证问题 - 委托给 ReviewService"""
        return self.review_service.collect_validation_issues(validation)

    def _modify_field(self, pending, field: str):
        """修改单个字段的值 - 使用 ReviewService"""
        from backend.services.review_service import Reviewer
        
        data = pending.get_achievement_data()
        current_value = data.get(field, '')
        
        print(f"\n修改字段: {field}")
        print(f"当前值: {current_value}")
        
        if isinstance(current_value, (dict, list)):
            print("\n该字段是复杂类型，请输入 JSON 格式的新值:")
            new_value = input("新值: ").strip()
            try:
                new_value = json.loads(new_value)
            except json.JSONDecodeError:
                print("JSON 格式错误，取消修改")
                return
        else:
            new_value = input("新值: ").strip()
        
        # 使用 ReviewService 修改字段
        modifier = Reviewer(
            reviewer_type=self.current_submitter['type'],
            reviewer_id=self.current_submitter['id']
        )
        
        result = self.review_service.modify_field(
            pending_id=pending.id,
            field_name=field,
            new_value=new_value,
            modifier=modifier
        )
        
        if result.success:
            print(f"[OK] 字段已更新")
            # 重新验证
            self._revalidate_pending(pending)
        else:
            print(f"[ERROR] 更新失败: {result.error}")

    def _revalidate_pending(self, pending):
        """重新验证 pending 记录 - 使用 ReviewService"""
        print("\n重新验证中...")
        
        try:
            # 使用 ReviewService 重新验证
            validation_result = self.review_service.revalidate(pending.id)
            
            # 重新加载 pending 对象以获取最新数据
            self.pending_manager._load_all_from_db()
            
            # 显示验证结果
            is_valid = validation_result.get('is_valid', False)
            if is_valid:
                print("[OK] 验证通过")
            else:
                print("[X] 验证未通过")
                issues = self.review_service.collect_validation_issues(validation_result)
                if issues:
                    for issue in issues[:5]:
                        print(f"    - {issue.get('field', '未知')}: {issue.get('message', str(issue))}")
            
        except Exception as e:
            print(f"[ERROR] 验证失败: {e}")
            import traceback
            traceback.print_exc()

    def navigate_directory(self, current_dir: Path) -> Optional[Tuple[Path, str]]:
        """
        目录导航，返回选择的文件或目录

        Returns:
            Tuple[Path, str]: (路径, 操作类型)
            - ('file', Path): 选择单个文件
            - ('navigate', Path): 进入目录
            - ('select_dir', Path): 选择当前目录的所有文件
            - None: 取消或退出
        """
        while True:
            print(self.print_separator(f"当前目录: {current_dir.name}"))
            print()

            # 列出子目录和文件
            items = self.list_directory_items(current_dir)

            if not items:
                print("目录为空")
                return None

            # 显示菜单
            print(f"{'序号':<6} {'类型':<10} {'名称'}")
            print("-" * 80)
            for idx, item in enumerate(items):
                item_type = "[目录]" if item['is_dir'] else "[文件]"
                print(f"{idx + 1:<6} {item_type:<10} {item['name']}")

            print()
            print("  0. 返回上级目录 (如果已在根目录则返回)")
            print("  d. 选择当前目录 (遍历目录中的所有文件)")
            print("  q. 取消选择")
            print()

            choice = input("请选择序号或操作: ").strip()

            if choice.lower() == 'q':
                return None
            elif choice == '0':
                # 返回上级目录
                if current_dir == self.test_images_dir or current_dir.parent == self.test_images_dir:
                    print("已在根目录")
                    continue
                else:
                    return (current_dir.parent, 'navigate')
            elif choice.lower() == 'd':
                # 选择当前目录
                return (current_dir, 'select_dir')
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(items):
                    item = items[idx]
                    item_path = current_dir / item['name']

                    if item['is_dir']:
                        # 进入子目录
                        return (item_path, 'navigate')
                    else:
                        # 选择文件
                        return (item_path, 'file')
                else:
                    print("无效序号")
            else:
                print("无效输入")

    def list_directory_items(self, directory: Path) -> List[Dict[str, Any]]:
        """列出目录项（包括所有类型的文件）"""
        items = []

        # 先列目录
        try:
            for item in sorted(directory.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    items.append({
                        'name': item.name,
                        'is_dir': True,
                        'path': item
                    })
        except Exception as e:
            print(f"读取目录失败: {e}")
            return []

        # 列出所有文件（不限制扩展名）
        try:
            for item in sorted(directory.iterdir()):
                # 过滤临时文件（以 ~$ 开头的 Excel 临时文件）和隐藏文件
                if item.is_file() and not item.name.startswith('.') and not item.name.startswith('~$'):
                    items.append({
                        'name': item.name,
                        'is_dir': False,
                        'path': item
                    })
        except Exception as e:
            print(f"读取文件失败: {e}")

        return items

    def collect_files_from_directory(self, directory: Path) -> List[Path]:
        """
        递归收集目录中的所有文件（不限制扩展名）
        """
        files = []

        try:
            for item in directory.rglob('*'):
                # 过滤临时文件（以 ~$ 开头的 Excel 临时文件）和隐藏文件
                if item.is_file() and not item.name.startswith('.') and not item.name.startswith('~$'):
                    files.append(item)
        except Exception as e:
            print(f"遍历目录时出错: {e}")

        return sorted(files)

    def select_files(self, root_path: Path) -> List[Path]:
        """选择要处理的文件"""
        files = []
        current_path = root_path

        while True:
            result = self.navigate_directory(current_path)
            if result is None:
                # 用户取消或退出
                break

            selected_path, action_type = result

            if action_type == 'navigate':
                # 进入目录
                current_path = selected_path
            elif action_type == 'select_dir':
                # 选择当前目录的所有文件
                dir_files = self.collect_files_from_directory(selected_path)
                if dir_files:
                    files.extend(dir_files)
                    print(f"\n已选择目录: {selected_path.name}")
                    print(f"找到 {len(dir_files)} 个文件:")
                    for f in dir_files[:10]:  # 只显示前10个
                        print(f"  - {f.name}")
                    if len(dir_files) > 10:
                        print(f"  ... 还有 {len(dir_files) - 10} 个文件")

                    # 询问是否继续选择
                    continue_choice = input("\n是否继续选择其他文件或目录? (y/n): ").strip().lower()
                    if continue_choice != 'y':
                        break
                else:
                    print(f"\n目录中没有找到支持的文件")
            elif action_type == 'file':
                # 选择了一个文件
                files.append(selected_path)
                print(f"\n已选择: {selected_path.name}")

                # 询问是否继续选择
                continue_choice = input("\n是否继续选择其他文件? (y/n): ").strip().lower()
                if continue_choice != 'y':
                    break

        return files

    def process_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """处理单个文件，返回测试结果列表

        对于普通文件，返回包含1个元素的列表
        对于大创xlsx文件，返回包含多个项目的列表
        """
        print(f"\n处理中: {file_path.name}...")

        base_result = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'submitter': self.current_submitter.copy(),
            'success': False,
            'error': None
        }

        try:
            # 创建模拟文件对象
            mock_file = MockFile(file_path)

            # 调用上传服务
            upload_result = self.upload_service.upload_file(
                uploaded_file=mock_file,
                submitter_type=self.current_submitter['type'],
                submitter_id=self.current_submitter['db_id']
            )

            base_result['upload_result'] = upload_result

            if upload_result.success:
                base_result['success'] = True
                base_result['pending_id'] = upload_result.pending_id
                base_result['is_duplicate'] = upload_result.is_duplicate
                base_result['file_hash'] = upload_result.file_hash
                base_result['file_path'] = upload_result.file_path

                # 从 pending_manager 获取详细信息
                pending = self.pending_manager.get_pending_by_id(upload_result.pending_id)
                if pending:
                    pending_dict = self._pending_to_dict(pending)
                    base_result['pending'] = pending_dict
                    base_result['ocr_text'] = pending.ocr_text
                    base_result['llm_prompt'] = pending.llm_prompt
                    base_result['llm_response'] = pending.llm_response
                    base_result['ext_info'] = pending.get_ext_info()

                    # 检查是否是大创类型，包含多个项目
                    if (pending_dict.get('achievement_type') == 'innovation' and
                        isinstance(pending_dict.get('achievement_data'), dict)):
                        achievement_data = pending_dict['achievement_data']
                        if 'projects' in achievement_data and isinstance(achievement_data['projects'], list):
                            projects = achievement_data['projects']
                            print(f"  [OK] 成功 - pending_id: {upload_result.pending_id}, 包含 {len(projects)} 个大创项目")
                            if upload_result.is_duplicate:
                                print(f"    (文件已更新，覆盖原有记录)")

                            # 为每个项目创建独立的测试结果
                            results = []
                            for i, project in enumerate(projects):
                                project_result = base_result.copy()
                                # 创建一个只包含单个项目的 achievement_data
                                project_pending = pending_dict.copy()
                                project_pending['achievement_data'] = project
                                project_pending['project_index'] = i + 1  # 项目索引
                                project_result['pending'] = project_pending
                                project_result['project_name'] = project.get('项目名称', f'项目{i+1}')
                                results.append(project_result)

                            return results

                print(f"  [OK] 成功 - pending_id: {upload_result.pending_id}")
                if upload_result.is_duplicate:
                    print(f"    (文件已更新，覆盖原有记录)")
            else:
                base_result['success'] = False
                base_result['error'] = upload_result.error
                print(f"  [X] 失败 - {upload_result.error}")

        except Exception as e:
            base_result['success'] = False
            base_result['error'] = str(e)
            print(f"  [X] 异常 - {e}")
            import traceback
            traceback.print_exc()

        return [base_result]

    def _pending_to_dict(self, pending) -> Dict[str, Any]:
        """将 PendingAchievement 对象转换为字典"""
        # 解析验证结果
        validation_result = None
        if pending.validation_result:
            try:
                validation_result = json.loads(pending.validation_result)
            except:
                validation_result = pending.validation_result

        return {
            'id': pending.id,
            'achievement_type': pending.achievement_type,
            'achievement_data': json.loads(pending.achievement_data) if pending.achievement_data else {},
            'validation_result': validation_result,
            'submitter_type': pending.submitter_type,
            'submitter_id': pending.submitter_id,
            'submit_time': pending.submit_time,
            'status': pending.status,
            'assigned_reviewer_type': pending.assigned_reviewer_type,
            'file_hash': pending.file_hash,
            'file_path': pending.file_path,
            'created_at': pending.created_at,
        }

    def _organize_results_by_category(self) -> Dict[str, Dict[str, Any]]:
        """按类型和验证状态组织测试结果

        对于大创类型，按文件分组而不是按项目分组。

        Returns:
            {
                'award': {
                    'name': '奖状',
                    'passed': [result1, result2],
                    'pending_revision': [result3]
                },
                'innovation': {
                    'name': '大创',
                    'files': {
                        'file_path1': {
                            'file_name': 'xxx.xlsx',
                            'projects': [...],
                            'validations': [...],
                            'results': [...]
                        }
                    }
                },
                ...
            }
        """
        categories = {
            'award': {'name': '奖状', 'passed': [], 'pending_revision': []},
            'patent': {'name': '专利', 'passed': [], 'pending_revision': []},
            'software': {'name': '软著', 'passed': [], 'pending_revision': []},
            'innovation': {'name': '大创', 'files': {}},
            'other': {'name': '其他', 'passed': [], 'pending_revision': []},
        }

        for result in self.results:
            # 只处理成功的结果
            if not result['success']:
                continue

            achievement_type = result.get('pending', {}).get('achievement_type', 'other')
            if achievement_type not in categories:
                achievement_type = 'other'

            # 大创类型特殊处理：按文件分组
            if achievement_type == 'innovation':
                file_path = result.get('file_path', '')
                file_name = result.get('file_name', '')
                
                if file_path not in categories['innovation']['files']:
                    categories['innovation']['files'][file_path] = {
                        'file_name': file_name,
                        'file_path': file_path,
                        'projects': [],
                        'validations': [],
                        'results': []
                    }
                
                # 获取项目数据
                project_data = result.get('pending', {}).get('achievement_data', {})
                categories['innovation']['files'][file_path]['projects'].append(project_data)
                categories['innovation']['files'][file_path]['results'].append(result)
                
                # 验证项目
                validation = validate_innovation_project(project_data)
                categories['innovation']['files'][file_path]['validations'].append(validation)
            else:
                # 其他类型：判断验证状态
                validation_result = result.get('pending', {}).get('validation_result')
                if validation_result:
                    is_valid = validation_result.get('is_valid')
                    if is_valid is True:
                        categories[achievement_type]['passed'].append(result)
                    else:
                        # is_valid为False或validation_result存在但验证失败
                        categories[achievement_type]['pending_revision'].append(result)
                else:
                    # 没有validation_result，放入待修订
                    categories[achievement_type]['pending_revision'].append(result)

        return categories

    def generate_html_report(self):
        """生成HTML报告"""
        print("\n生成HTML报告...")

        report_dir = project_root / "tests" / "reports" / "html"
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        role_name = self.current_submitter['name'] if self.current_submitter else 'unknown'
        report_name = f"文件提交测试_{role_name}_{timestamp}.html"
        report_path = report_dir / report_name

        html = self._build_html()

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"报告已生成: {report_path}")
        
        # 自动在浏览器中打开报告
        try:
            webbrowser.open(str(report_path))
            print("已在浏览器中打开报告")
        except Exception as e:
            print(f"无法自动打开报告: {e}")
        
        return report_path

    def _build_nav_categories(self, categories: Dict) -> str:
        """生成三级导航栏（成果类型 -> 验证状态/文件 -> 测试项）
        
        对于大创类型，二级显示文件列表而不是验证状态。
        """
        html = ''

        for cat_key, cat_data in categories.items():
            # 大创类型特殊处理
            if cat_key == 'innovation':
                files = cat_data.get('files', {})
                if not files:
                    continue
                
                # 计算总项目数
                total_projects = sum(len(f['projects']) for f in files.values())
                
                cat_id = f'nav-cat-{cat_key}'
                html += f'''
                <div class="nav-category">
                    <div class="nav-category-header" onclick="toggleCategory(event, '{cat_id}')">
                        <span>📁 {cat_data['name']}</span>
                        <span>
                            <span class="nav-category-icon" id="icon-{cat_id}">▶</span>
                            <span class="nav-category-count">({len(files)}个文件, {total_projects}个项目)</span>
                        </span>
                    </div>
                    <div class="nav-category-content" id="{cat_id}">'''
                
                # 二级：按文件分组
                for file_idx, (file_path, file_data) in enumerate(files.items(), 1):
                    file_name = file_data['file_name']
                    project_count = len(file_data['projects'])
                    valid_count = sum(1 for v in file_data['validations'] if v['is_valid'])
                    
                    # 判断文件整体状态
                    if valid_count == project_count:
                        file_class = 'valid'
                        file_icon = '✓'
                    elif valid_count == 0:
                        file_class = 'invalid'
                        file_icon = '✗'
                    else:
                        file_class = 'partial'
                        file_icon = '⚠'
                    
                    file_id = f'innovation-file-{file_idx}'
                    
                    html += f'''
                        <div class="nav-validation">
                            <a href="#innovation-file-{file_idx}" class="nav-validation-header {file_class}" 
                               onclick="scrollToTest(event, 'innovation-file-{file_idx}')" style="text-decoration:none;">
                                <span>  {file_icon} {self._escape_html(file_name)}</span>
                                <span class="nav-validation-count">({valid_count}/{project_count})</span>
                            </a>
                        </div>'''
                
                html += '''
                    </div>
                </div>'''
                continue
            
            # 其他类型：原有逻辑
            total_count = len(cat_data.get('passed', [])) + len(cat_data.get('pending_revision', []))

            if total_count == 0:
                continue

            cat_id = f'nav-cat-{cat_key}'
            html += f'''
                <div class="nav-category">
                    <div class="nav-category-header" onclick="toggleCategory(event, '{cat_id}')">
                        <span>📁 {cat_data['name']}</span>
                        <span>
                            <span class="nav-category-icon" id="icon-{cat_id}">▶</span>
                            <span class="nav-category-count">({total_count})</span>
                        </span>
                    </div>
                    <div class="nav-category-content" id="{cat_id}">'''

            # 二级：验证状态
            validation_sections = []
            if cat_data.get('passed'):
                validation_sections.append(('passed', '验证通过', 'valid', cat_data['passed']))
            if cat_data.get('pending_revision'):
                validation_sections.append(('pending_revision', '待修订', 'invalid', cat_data['pending_revision']))

            for val_key, val_name, val_class, results in validation_sections:
                if not results:
                    continue
                val_id = f'{cat_id}-{val_key}'
                html += f'''
                        <div class="nav-validation">
                            <div class="nav-validation-header {val_class}" onclick="toggleValidation(event, '{val_id}')">
                                <span>  {'✓' if val_key == 'passed' else '⚠'} {val_name}</span>
                                <span>
                                    <span class="nav-validation-icon" id="icon-{val_id}">▶</span>
                                    <span class="nav-validation-count">({len(results)})</span>
                                </span>
                            </div>
                            <div class="nav-validation-content" id="{val_id}">'''

                # 三级：测试项
                for result in results:
                    # 找到该结果在全部结果中的索引
                    result_idx = self.results.index(result) + 1

                    # 确定显示名称
                    display_name = result['file_name']

                    icon = '📄'

                    html += f'''
                                <a href="#test-item-{result_idx}" class="nav-test-item" onclick="scrollToTest(event, 'test-item-{result_idx}')">
                                    <span class="nav-test-icon success">{icon}</span>
                                    <span>{self._escape_html(display_name)}</span>
                                </a>'''

                html += '''
                            </div>
                        </div>'''

            html += '''
                    </div>
                </div>'''

        return html

    def _build_main_content(self, categories: Dict) -> str:
        """生成三级主内容区（按分类组织）
        
        对于大创类型，为每个文件生成一个包含所有项目的表格。
        """
        html = ''

        for cat_key, cat_data in categories.items():
            # 大创类型特殊处理
            if cat_key == 'innovation':
                files = cat_data.get('files', {})
                if not files:
                    continue
                
                total_projects = sum(len(f['projects']) for f in files.values())
                
                # 分类标题
                html += f'''
                <div class="content-category" id="content-cat-{cat_key}">
                    <h2 class="category-title">{cat_data['name']} ({len(files)}个文件, {total_projects}个项目)</h2>'''
                
                # 为每个文件生成表格
                for file_idx, (file_path, file_data) in enumerate(files.items(), 1):
                    html += self._build_innovation_file_table(file_idx, file_data)
                
                html += '''
                </div>'''
                continue
            
            # 其他类型：原有逻辑
            total_count = len(cat_data.get('passed', [])) + len(cat_data.get('pending_revision', []))

            if total_count == 0:
                continue

            # 分类标题
            html += f'''
                <div class="content-category" id="content-cat-{cat_key}">
                    <h2 class="category-title">{cat_data['name']} ({total_count})</h2>'''

            # 二级：验证状态区块
            validation_sections = []
            if cat_data.get('passed'):
                validation_sections.append(('passed', '验证通过', 'valid', cat_data['passed']))
            if cat_data.get('pending_revision'):
                validation_sections.append(('pending_revision', '待修订', 'invalid', cat_data['pending_revision']))

            for val_key, val_name, val_class, results in validation_sections:
                if not results:
                    continue

                html += f'''
                    <div class="content-validation validation-{val_class}">
                        <h3 class="validation-title">{val_name} ({len(results)})</h3>'''

                # 三级：测试项
                for result in results:
                    result_idx = self.results.index(result) + 1
                    html += self._build_test_item(result_idx, result)

                html += '''
                    </div>'''

            html += '''
                </div>'''

        return html
    
    def _build_innovation_file_table(self, file_idx: int, file_data: Dict) -> str:
        """为单个大创文件生成 HTML 表格（类似 test_invo.py）"""
        file_name = file_data['file_name']
        file_path = file_data['file_path']
        projects = file_data['projects']
        validations = file_data['validations']
        
        total = len(projects)
        valid_count = sum(1 for v in validations if v['is_valid'])
        invalid_count = total - valid_count
        
        # 确定整体状态样式
        if valid_count == total:
            status_class = 'validation-valid'
            status_text = '全部通过'
        elif valid_count == 0:
            status_class = 'validation-invalid'
            status_text = '全部失败'
        else:
            status_class = 'validation-partial'
            status_text = '部分通过'
        
        html = f'''
            <div class="test-item innovation-file-block {status_class}" id="innovation-file-{file_idx}">
                <div class="test-header">
                    <h3>📊 {self._escape_html(file_name)}</h3>
                    <span class="status-badge {'status-success' if valid_count == total else 'status-error'}">{status_text}</span>
                </div>
                
                <div class="innovation-file-meta" style="background:#f8f9fa;padding:15px;border-radius:8px;margin-bottom:20px;">
                    <p style="margin:5px 0;"><strong>文件路径：</strong>{self._escape_html(file_path)}</p>
                </div>
                
                <div class="innovation-stats" style="display:flex;gap:15px;margin-bottom:20px;">
                    <div style="background:#667eea;color:white;padding:15px 25px;border-radius:8px;text-align:center;">
                        <div style="font-size:24px;font-weight:bold;">{total}</div>
                        <div style="font-size:12px;">总项目数</div>
                    </div>
                    <div style="background:#52c41a;color:white;padding:15px 25px;border-radius:8px;text-align:center;">
                        <div style="font-size:24px;font-weight:bold;">{valid_count}</div>
                        <div style="font-size:12px;">验证通过</div>
                    </div>
                    <div style="background:#ff4d4f;color:white;padding:15px 25px;border-radius:8px;text-align:center;">
                        <div style="font-size:24px;font-weight:bold;">{invalid_count}</div>
                        <div style="font-size:12px;">验证失败</div>
                    </div>
                </div>
                
                <table class="innovation-table" style="width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <thead>
                        <tr style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);color:white;">
                            <th style="padding:12px 10px;text-align:left;width:40px;">#</th>
                            <th style="padding:12px 10px;text-align:left;width:80px;">项目编号</th>
                            <th style="padding:12px 10px;text-align:left;width:200px;">项目名称</th>
                            <th style="padding:12px 10px;text-align:left;width:60px;">年份</th>
                            <th style="padding:12px 10px;text-align:left;width:60px;">级别</th>
                            <th style="padding:12px 10px;text-align:left;width:100px;">负责人</th>
                            <th style="padding:12px 10px;text-align:left;width:100px;">指导教师</th>
                            <th style="padding:12px 10px;text-align:left;width:150px;">其他成员</th>
                            <th style="padding:12px 10px;text-align:left;width:80px;">起止时间</th>
                            <th style="padding:12px 10px;text-align:left;width:60px;">验收等级</th>
                            <th style="padding:12px 10px;text-align:left;width:120px;">验证结果</th>
                        </tr>
                    </thead>
                    <tbody>'''
        
        for i, (project, validation) in enumerate(zip(projects, validations), 1):
            # 处理负责人
            leader = project.get('学生负责人', {})
            if isinstance(leader, dict):
                leader_name = leader.get('姓名', '')
                leader_id = leader.get('学号', '')
                leader_str = f"{self._escape_html(leader_name)}" + (f"<br><span style='color:#999;font-size:12px;'>{leader_id}</span>" if leader_id else "")
            else:
                leader_str = self._escape_html(str(leader)) if leader else "<span style='color:#bfbfbf;font-style:italic;'>-</span>"
            
            # 处理指导教师
            teachers = project.get('指导教师', [])
            if isinstance(teachers, list) and teachers:
                teachers_str = "<br>".join(self._escape_html(t) for t in teachers)
            else:
                teachers_str = "<span style='color:#bfbfbf;font-style:italic;'>-</span>"
            
            # 处理其他成员
            members = project.get('项目其他成员信息', [])
            if isinstance(members, list) and members:
                member_strs = []
                for m in members:
                    if isinstance(m, dict):
                        name = m.get('姓名', '')
                        sid = m.get('学号', '')
                        member_strs.append(f"{self._escape_html(name)}" + (f"({sid})" if sid else ""))
                    else:
                        member_strs.append(self._escape_html(str(m)))
                members_str = "<br>".join(member_strs) if member_strs else "<span style='color:#bfbfbf;font-style:italic;'>-</span>"
            else:
                members_str = "<span style='color:#bfbfbf;font-style:italic;'>-</span>"
            
            # 处理起止时间
            start = project.get('项目开始时间', '')
            end = project.get('项目结束时间', '')
            time_str = f"{start or '-'}<br>~{end or '-'}"
            
            # 处理验证结果
            if validation['is_valid']:
                validation_str = "<span style='color:#52c41a;font-weight:bold;'>✓ 通过</span>"
            else:
                issues_html = "<ul style='margin:5px 0;padding-left:15px;font-size:12px;color:#ff4d4f;'>" + "".join(f"<li>{self._escape_html(issue)}</li>" for issue in validation['issues']) + "</ul>"
                validation_str = f"<span style='color:#ff4d4f;font-weight:bold;'>✗ 失败</span>{issues_html}"
            
            row_bg = '#f8f9fa' if i % 2 == 0 else 'white'
            
            html += f'''
                        <tr style="background:{row_bg};">
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;color:#999;font-size:12px;">{i}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;">{self._escape_html(str(project.get('项目编号', ''))) or "<span style='color:#bfbfbf;font-style:italic;'>-</span>"}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;">{self._escape_html(str(project.get('项目名称', ''))) or "<span style='color:#bfbfbf;font-style:italic;'>-</span>"}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;">{project.get('年份', '') or "<span style='color:#bfbfbf;font-style:italic;'>-</span>"}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;">{self._escape_html(str(project.get('项目级别', ''))) or "<span style='color:#bfbfbf;font-style:italic;'>-</span>"}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;">{leader_str}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;font-size:12px;color:#666;">{teachers_str}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;font-size:12px;color:#666;">{members_str}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;">{time_str}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;">{self._escape_html(str(project.get('验收等级', ''))) or "<span style='color:#bfbfbf;font-style:italic;'>-</span>"}</td>
                            <td style="padding:12px 10px;border-bottom:1px solid #f0f0f0;">{validation_str}</td>
                        </tr>'''
        
        html += '''
                    </tbody>
                </table>
            </div>'''
        
        return html

    def _build_html(self) -> str:
        """构建HTML内容（三级分类结构）"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ocr_provider = self.ocr_provider.upper()
        llm_provider = self.llm_provider.upper()

        # 组织结果
        categories = self._organize_results_by_category()

        # 生成左侧导航栏（按分类组织）
        nav_items = self._build_nav_categories(categories)

        # 生成主内容区
        main_content = self._build_main_content(categories)

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件提交测试报告（分类视图）</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 0;
            line-height: 1.6;
        }}
        .main-wrapper {{
            display: flex;
            min-height: 100vh;
        }}
        /* 左侧导航栏 */
        .sidebar {{
            width: 350px;
            background: white;
            height: 100vh;
            position: sticky;
            top: 0;
            overflow-y: auto;
            border-right: 1px solid #e9ecef;
            flex-shrink: 0;
        }}
        .sidebar::-webkit-scrollbar {{ width: 6px; }}
        .sidebar::-webkit-scrollbar-thumb {{ background: #667eea; border-radius: 3px; }}
        .sidebar-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        .sidebar-header h2 {{ font-size: 1.3em; margin-bottom: 8px; }}
        .sidebar-header .meta {{ font-size: 0.8em; opacity: 0.9; }}
        .sidebar-info {{
            padding: 15px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .sidebar-info-item {{ margin-bottom: 8px; font-size: 0.9em; }}
        .sidebar-info-label {{ color: #6c757d; }}
        .sidebar-info-value {{ font-weight: 600; color: #667eea; }}

        /* 一级分类：成果类型 */
        .nav-category {{
            border-bottom: 1px solid #e9ecef;
        }}
        .nav-category-header {{
            padding: 15px 20px;
            background: #f8f9fa;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 600;
            color: #495057;
            user-select: none;
        }}
        .nav-category-header:hover {{ background: #e9ecef; }}
        .nav-category-icon {{ transition: transform 0.3s ease; }}
        .nav-category-icon.open {{ transform: rotate(90deg); }}
        .nav-category-count {{
            font-size: 0.85em;
            color: #6c757d;
            font-weight: normal;
        }}
        .nav-category-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }}
        .nav-category-content.open {{ max-height: 2000px; }}

        /* 二级分类：验证状态 */
        .nav-validation {{
            border-bottom: 1px solid #dee2e6;
        }}
        .nav-validation:last-child {{ border-bottom: none; }}
        .nav-validation-header {{
            padding: 12px 20px 12px 35px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9em;
            user-select: none;
        }}
        .nav-validation-header:hover {{ background: #f8f9fa; }}
        .nav-validation-header.valid {{ color: #28a745; }}
        .nav-validation-header.invalid {{ color: #dc3545; }}
        .nav-validation-header.no-validation {{ color: #6c757d; }}
        .nav-validation-header.error {{ color: #dc3545; }}
        .nav-validation-icon {{ transition: transform 0.3s ease; font-size: 12px; }}
        .nav-validation-icon.open {{ transform: rotate(90deg); }}
        .nav-validation-count {{
            font-size: 0.85em;
            opacity: 0.7;
        }}
        .nav-validation-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }}
        .nav-validation-content.open {{ max-height: 2000px; }}

        /* 三级：测试项 */
        .nav-test-item {{
            padding: 10px 20px 10px 50px;
            cursor: pointer;
            display: flex;
            align-items: center;
            font-size: 0.85em;
            color: #495057;
            text-decoration: none;
            transition: all 0.2s ease;
        }}
        .nav-test-item:hover {{ background: #e7f1ff; }}
        .nav-test-item.active {{ background: #d1e7ff; font-weight: 600; }}
        .nav-test-icon {{ margin-right: 8px; }}
        .nav-test-icon.success {{ color: #28a745; }}
        .nav-test-icon.error {{ color: #dc3545; }}

        /* 三级内容区块样式 */
        .content-category {{
            margin-bottom: 50px;
        }}
        .category-title {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            border-radius: 12px;
            margin-bottom: 25px;
            font-size: 1.5em;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }}
        .content-validation {{
            margin-bottom: 30px;
            padding: 20px;
            border-radius: 12px;
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}
        .content-validation.validation-valid {{
            border-left: 5px solid #28a745;
        }}
        .content-validation.validation-invalid {{
            border-left: 5px solid #dc3545;
            background: #fff5f5;
        }}
        .content-validation.validation-no-validation {{
            border-left: 5px solid #6c757d;
        }}
        .content-validation.validation-error {{
            border-left: 5px solid #dc3545;
            background: #f8d7da;
        }}
        .validation-title {{
            margin: 0 0 20px 0;
            padding-bottom: 15px;
            border-bottom: 2px solid #e9ecef;
            font-size: 1.2em;
            color: #495057;
        }}
        .content-validation.validation-valid .validation-title {{
            color: #28a745;
        }}
        .content-validation.validation-invalid .validation-title {{
            color: #dc3545;
        }}

        /* 右侧主内容区 */
        .main-content {{
            flex: 1;
            overflow-y: auto;
            padding: 40px;
        }}
        .main-content::-webkit-scrollbar {{
            width: 8px;
        }}
        .main-content::-webkit-scrollbar-thumb {{
            background: rgba(102, 126, 234, 0.5);
            border-radius: 4px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        .header .meta {{
            color: #6c757d;
            font-size: 0.9em;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .summary-card .number {{
            font-size: 2.5em;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .summary-card .label {{
            color: #6c757d;
            font-size: 0.9em;
        }}

        /* 测试项 */
        .test-item {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            scroll-margin-top: 20px;
        }}
        .test-header {{
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }}
        .test-header h3 {{
            color: #333;
            margin: 0;
        }}
        .status-badge {{
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
            margin-left: 15px;
        }}
        .status-success {{ background: #d4edda; color: #155724; }}
        .status-error {{ background: #f8d7da; color: #721c24; }}

        /* 图片容器 */
        .image-container {{
            text-align: center;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
        }}
        .image-container img {{
            max-width: 100%;
            max-height: 500px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            cursor: pointer;
            transition: transform 0.3s ease;
        }}
        .image-container img:hover {{
            transform: scale(1.02);
        }}

        /* 图片和验证结果左右分栏 */
        .image-validation-split {{
            display: flex;
            gap: 20px;
            margin: 20px 0;
        }}
        .split-left {{
            flex: 1;
            min-width: 0;
        }}
        .split-right {{
            flex: 0 0 400px;
            min-width: 350px;
        }}
        @media (max-width: 1024px) {{
            .image-validation-split {{
                flex-direction: column;
            }}
            .split-right {{
                flex: 1;
                min-width: 0;
            }}
        }}

        /* pending_achievements 表格 */
        .pending-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .pending-table th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        .pending-table td {{
            padding: 12px;
            border-bottom: 1px solid #e9ecef;
            word-break: break-word;
        }}
        .pending-table tr:last-child td {{
            border-bottom: none;
        }}
        .pending-table tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        .field-name {{
            font-weight: 600;
            color: #495057;
            width: 200px;
        }}
        .field-value {{
            color: #212529;
        }}

        /* 可折叠区块 */
        .collapsible-section {{
            margin: 20px 0;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            overflow: hidden;
        }}
        .collapsible-header {{
            background: #f8f9fa;
            padding: 15px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            user-select: none;
        }}
        .collapsible-header:hover {{
            background: #e9ecef;
        }}
        .collapsible-title {{
            font-weight: 600;
            color: #495057;
        }}
        .collapsible-icon {{
            transition: transform 0.3s ease;
            font-size: 16px;
        }}
        .collapsible-icon.rotated {{
            transform: rotate(180deg);
        }}
        .collapsible-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}
        .collapsible-content.show {{
            max-height: 3000px;
            transition: max-height 0.5s ease-in;
        }}
        .collapsible-content-inner {{
            padding: 20px;
            background: white;
        }}
        /* 验证结果特殊样式 */
        .collapsible-section.validation-failed .collapsible-header {{
            background: #fff5f5;
            border-left: 4px solid #dc3545;
        }}
        .collapsible-section.validation-failed .collapsible-title {{
            color: #dc3545;
        }}
        .collapsible-section.validation-passed .collapsible-header {{
            background: #f0fff4;
            border-left: 4px solid #28a745;
        }}
        .collapsible-section.validation-passed .collapsible-title {{
            color: #28a745;
        }}
        .code-block {{
            background: #282c34;
            color: #abb2bf;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85em;
            line-height: 1.5;
            white-space: pre-wrap;
            max-height: 300px;
            overflow-y: auto;
        }}
        .json-block {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85em;
            line-height: 1.5;
        }}

        /* 移动端响应式 */
        @media (max-width: 768px) {{
            .main-wrapper {{ flex-direction: column; }}
            .sidebar {{ width: 100%; height: auto; max-height: 200px; }}
            .main-content {{ padding: 20px; }}
        }}

        /* 模态框 */
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            cursor: pointer;
        }}
        .modal img {{
            max-width: 90%;
            max-height: 90%;
            margin: auto;
            display: block;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }}
    </style>
</head>
<body>
    <div class="main-wrapper">
        <!-- 左侧导航栏 -->
        <div class="sidebar">
            <div class="sidebar-header">
                <h2>测试导航</h2>
                <div class="meta">{current_time}</div>
            </div>
            <div class="sidebar-info">
                <div class="sidebar-info-item">
                    <span class="sidebar-info-label">提交人:</span>
                    <span class="sidebar-info-value">{self._escape_html(self.current_submitter['name']) if self.current_submitter else 'unknown'}</span>
                </div>
                <div class="sidebar-info-item">
                    <span class="sidebar-info-label">类型:</span>
                    <span class="sidebar-info-value">{self.current_submitter['type'] if self.current_submitter else 'unknown'}</span>
                </div>
                <div class="sidebar-info-item">
                    <span class="sidebar-info-label">OCR:</span>
                    <span class="sidebar-info-value">{ocr_provider}</span>
                </div>
                <div class="sidebar-info-item">
                    <span class="sidebar-info-label">LLM:</span>
                    <span class="sidebar-info-value">{llm_provider}</span>
                </div>
            </div>
            <div class="nav-list">
                {nav_items}
            </div>
        </div>

        <!-- 右侧主内容区 -->
        <div class="main-content">
            <div class="container">
                <div class="header">
                    <h1>文件提交测试报告</h1>
                    <div class="meta">
                        生成时间: {current_time} |
                        提交人: {self._escape_html(self.current_submitter['name']) if self.current_submitter else 'unknown'} |
                        OCR: {ocr_provider} |
                        LLM: {llm_provider}
                    </div>
                </div>

                <div class="summary">
'''

        # 计算统计数据
        total = len(self.results)
        success = sum(1 for r in self.results if r['success'])
        failed = total - success
        duplicate = sum(1 for r in self.results if r.get('is_duplicate'))

        html += f'''
                    <div class="summary-card">
                        <div class="number">{total}</div>
                        <div class="label">处理文件数</div>
                    </div>
                    <div class="summary-card">
                        <div class="number">{success}</div>
                        <div class="label">成功</div>
                    </div>
                    <div class="summary-card">
                        <div class="number">{failed}</div>
                        <div class="label">失败</div>
                    </div>
                    <div class="summary-card">
                        <div class="number">{duplicate}</div>
                        <div class="label">重复更新</div>
                    </div>
                </div>
'''

        # 使用新的三级分类内容
        html += main_content

        html += '''
            </div>
        </div>
    </div>

    <div id="imageModal" class="modal" onclick="closeModal()">
        <img id="modalImage">
    </div>

    <script>
        // 图片模态框
        function openModal(img) {
            document.getElementById('modalImage').src = img.src;
            document.getElementById('imageModal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('imageModal').style.display = 'none';
        }

        // 可折叠区块
        function toggleSection(header) {
            const content = header.nextElementSibling;
            const icon = header.querySelector('.collapsible-icon');
            content.classList.toggle('show');
            icon.classList.toggle('rotated');
        }

        // 三级导航展开/折叠 - 成果类型
        function toggleCategory(event, catId) {
            if (event) event.stopPropagation();
            const content = document.getElementById(catId);
            const icon = document.getElementById('icon-' + catId);
            if (content && icon) {
                content.classList.toggle('open');
                icon.classList.toggle('open');
            }
        }

        // 三级导航展开/折叠 - 验证状态
        function toggleValidation(event, valId) {
            if (event) event.stopPropagation();
            const content = document.getElementById(valId);
            const icon = document.getElementById('icon-' + valId);
            if (content && icon) {
                content.classList.toggle('open');
                icon.classList.toggle('open');
            }
        }

        // 滚动到指定测试项
        function scrollToTest(event, targetId) {
            event.preventDefault();
            event.stopPropagation();
            const targetElement = document.getElementById(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        // 导航高亮
        document.addEventListener('DOMContentLoaded', function() {
            const navItems = document.querySelectorAll('.nav-test-item');
            const testItems = document.querySelectorAll('.test-item');

            navItems.forEach(item => {
                item.addEventListener('click', function(e) {
                    // 滚动功能已由 scrollToTest 处理
                });
            });

            function highlightNavOnScroll() {
                let current = '';
                testItems.forEach(item => {
                    const rect = item.getBoundingClientRect();
                    if (rect.top <= 100) {
                        current = item.id;
                    }
                });

                navItems.forEach(item => {
                    item.classList.remove('active');
                    const href = item.getAttribute('href');
                    if (href && href === '#' + current) {
                        item.classList.add('active');
                    }
                });
            }

            const mainContent = document.querySelector('.main-content');
            mainContent.addEventListener('scroll', highlightNavOnScroll);
            window.addEventListener('scroll', highlightNavOnScroll);
        });
    </script>
</body>
</html>
'''
        return html

    def _build_test_item(self, idx: int, result: Dict[str, Any]) -> str:
        """构建单个测试项的HTML"""
        status_class = "status-success" if result['success'] else "status-error"
        status_text = "成功" if result['success'] else "失败"

        # 检查是否是大创项目
        is_innovation = (result.get('pending') and
                        result['pending'].get('achievement_type') == 'innovation')

        # 对于大创项目，显示项目详情而不是图片
        if is_innovation and result.get('project_name'):
            # 获取项目数据
            project_data = result['pending'].get('achievement_data', {})

            # 构建项目详情表格
            detail_rows = []
            for key, value in project_data.items():
                if value is not None and value != '':
                    detail_rows.append(f'''
                        <tr>
                            <td class="field-name">{self._escape_html(str(key))}</td>
                            <td class="field-value">{self._escape_html(str(value))}</td>
                        </tr>''')

            detail_table = f'''
                <table style="width:100%;border-collapse:collapse;">
                    {''.join(detail_rows)}
                </table>''' if detail_rows else '<div style="color:#6c757d;">无项目数据</div>'

            img_html = f'''
                <div style="padding:20px;background:#f8f9fa;border-radius:8px;">
                    <h4 style="margin:0 0 15px 0;color:#495057;font-size:1.1em;">
                        {self._escape_html(result['project_name'])}
                    </h4>
                    {detail_table}
                </div>'''
        else:
            # 读取并编码图片
            try:
                img_path = Path(result['file_path'])
                if img_path.exists():
                    if img_path.suffix.lower() == '.pdf':
                        img_html = '<div style="padding:40px;text-align:center;color:#6c757d;">PDF文件（无法预览）</div>'
                    elif img_path.suffix.lower() == '.xlsx':
                        img_html = '<div style="padding:40px;text-align:center;color:#6c757d;">Excel文件</div>'
                    else:
                        with open(img_path, "rb") as f:
                            img_b64 = base64.b64encode(f.read()).decode('utf-8')
                        img_html = f'<img src="data:image/jpeg;base64,{img_b64}" alt="{result["file_name"]}" onclick="openModal(this)">'
                else:
                    img_html = '<div style="padding:40px;text-align:center;color:#6c757d;">图片不存在</div>'
            except:
                img_html = '<div style="padding:40px;text-align:center;color:#dc3545;">无法读取图片</div>'

        # 构建验证结果显示
        validation_html = ''
        if result.get('pending') and result['pending'].get('validation_result'):
            validation_result = result['pending']['validation_result']
            is_valid = validation_result.get('is_valid')
            errors = validation_result.get('errors', [])

            if is_valid is True:
                status_badge = '<span style="display:inline-block;padding:6px 12px;background:#d4edda;color:#155724;border-radius:6px;font-size:0.9em;margin-bottom:10px;">✓ 验证通过</span>'
            elif is_valid is False:
                status_badge = '<span style="display:inline-block;padding:6px 12px;background:#f8d7da;color:#721c24;border-radius:6px;font-size:0.9em;margin-bottom:10px;">⚠ 待修订</span>'
            else:
                status_badge = '<span style="display:inline-block;padding:6px 12px;background:#fff3cd;color:#856404;border-radius:6px;font-size:0.9em;margin-bottom:10px;">○ 未知状态</span>'

            validation_html = f'''
                <div style="background:#f8f9fa;padding:20px;border-radius:8px;height:100%;">
                    <h4 style="margin:0 0 15px 0;color:#495057;font-size:1.1em;">验证结果</h4>
                    {status_badge}
                    <div style="margin-top:15px;">
                        <div style="font-weight:600;color:#6c757d;margin-bottom:8px;">is_valid:</div>
                        <div style="font-size:1.1em;color:{'#28a745' if is_valid else '#dc3545'};">
                            {is_valid if is_valid is not None else 'null'}
                        </div>
                    </div>'''

            if errors:
                validation_html += f'''
                    <div style="margin-top:15px;">
                        <div style="font-weight:600;color:#6c757d;margin-bottom:8px;">错误信息:</div>
                        <ul style="margin:0;padding-left:20px;color:#dc3545;">'''
                for error in errors:
                    validation_html += f'<li>{self._escape_html(str(error))}</li>'
                validation_html += '''
                        </ul>
                    </div>'''

            # 显示完整的validation_result JSON
            json_str = json.dumps(validation_result, ensure_ascii=False, indent=2)
            validation_html += f'''
                    <div style="margin-top:15px;">
                        <div style="font-weight:600;color:#6c757d;margin-bottom:8px;">完整结果:</div>
                        <pre style="background:#282c34;color:#abb2bf;padding:12px;border-radius:6px;font-size:0.85em;overflow-x:auto;max-height:200px;overflow-y:auto;">{self._escape_html(json_str)}</pre>
                    </div>'''

            validation_html += '''
                </div>'''
        else:
            validation_html = '''
                <div style="background:#f8f9fa;padding:20px;border-radius:8px;height:100%;">
                    <h4 style="margin:0 0 15px 0;color:#495057;font-size:1.1em;">验证结果</h4>
                    <div style="color:#6c757d;">无验证结果</div>
                </div>'''

        # 确定标题显示
        if is_innovation and result.get('project_name'):
            title = f"{result['project_name']} ({result['file_name']})"
        else:
            title = result['file_name']

        html = f'''
        <div class="test-item" id="test-item-{idx}">
            <div class="test-header">
                <h3>[{idx}] {self._escape_html(title)}</h3>
                <span class="status-badge {status_class}">{status_text}</span>
            </div>

            <!-- 图片和验证结果左右分栏 -->
            <div class="image-validation-split">
                <div class="split-left">
                    <div class="image-container">
                        {img_html}
                    </div>
                </div>
                <div class="split-right">
                    {validation_html}
                </div>
            </div>
'''

        # 添加错误信息（如果有）
        if result.get('error'):
            html += f'''
            <div style="background:#f8d7da;color:#721c24;padding:15px;border-radius:8px;margin:20px 0;">
                <strong>错误:</strong> {self._escape_html(result['error'])}
            </div>
'''

        # 添加 pending_achievements 表格
        if result.get('pending'):
            pending = result['pending']
            html += '''
            <h4 style="margin:30px 0 15px 0;color:#495057;">Pending Achievements 表内容</h4>
            <table class="pending-table">
'''

            # 基本信息
            html += self._build_table_row('ID', pending.get('id'))
            html += self._build_table_row('成果类型', pending.get('achievement_type'))
            html += self._build_table_row('提交人类型', pending.get('submitter_type'))
            html += self._build_table_row('提交人ID', pending.get('submitter_id'))
            html += self._build_table_row('状态', pending.get('status'))
            html += self._build_table_row('预分配审核人', pending.get('assigned_reviewer_type'))
            html += self._build_table_row('文件Hash', pending.get('file_hash'))
            html += self._build_table_row('文件路径', pending.get('file_path'))
            html += self._build_table_row('提交时间', pending.get('submit_time'))
            html += self._build_table_row('创建时间', pending.get('created_at'))

            html += '''
            </table>
'''

        # 添加可折叠的详细信息（OCR、LLM等）
        html += self._build_collapsible_section(idx, result)

        html += '''
        </div>
'''
        return html

    def _build_table_row(self, name: str, value: Any) -> str:
        """构建表格行"""
        if value is None:
            value = '<em style="color:#6c757d;">NULL</em>'
        elif isinstance(value, dict):
            value = f'<pre class="json-block">{self._escape_html(json.dumps(value, ensure_ascii=False, indent=2))}</pre>'
        elif isinstance(value, list):
            value = ', '.join(str(v) for v in value)
        else:
            value = self._escape_html(str(value))

        return f'<tr><td class="field-name">{name}</td><td class="field-value">{value}</td></tr>'

    def _build_collapsible_section(self, idx: int, result: Dict[str, Any]) -> str:
        """构建可折叠的详细信息区块（OCR、LLM等）"""
        html = ''

        # OCR 识别结果
        if result.get('ocr_text'):
            html += self._build_collapsible(
                f'ocr_{idx}',
                'OCR 识别结果',
                result['ocr_text']
            )

        # LLM 提示词
        if result.get('llm_prompt'):
            html += self._build_collapsible(
                f'llm_prompt_{idx}',
                'LLM 提示词（发送给LLM的信息）',
                result['llm_prompt']
            )

        # LLM 响应
        if result.get('llm_response'):
            html += self._build_collapsible(
                f'llm_response_{idx}',
                'LLM 响应（LLM返回的信息）',
                result['llm_response']
            )

        # 最终抽取结果
        if result.get('pending', {}).get('achievement_data'):
            html += self._build_collapsible_json(
                f'extract_result_{idx}',
                '最终抽取结果',
                result['pending']['achievement_data']
            )

        return html

    def _build_collapsible(self, section_id: str, title: str, content: str) -> str:
        """构建可折叠的文本区块"""
        return f'''
        <div class="collapsible-section">
            <div class="collapsible-header" onclick="toggleSection(this)">
                <span class="collapsible-title">{title}</span>
                <span class="collapsible-icon">▼</span>
            </div>
            <div class="collapsible-content" id="{section_id}">
                <div class="collapsible-content-inner">
                    <pre class="code-block">{self._escape_html(content[:10000])}
{'...' if len(content) > 10000 else ''}</pre>
                </div>
            </div>
        </div>
'''

    def _build_collapsible_json(self, section_id: str, title: str, data: Any) -> str:
        """构建可折叠的JSON区块（支持验证结果的特殊样式）"""
        # 判断是否为验证结果
        is_validation = title == '验证结果'
        validation_class = ''
        if is_validation:
            is_valid = data.get('is_valid') if isinstance(data, dict) else None
            if is_valid is False:
                validation_class = 'validation-failed'
            elif is_valid is True:
                validation_class = 'validation-passed'

        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        return f'''
        <div class="collapsible-section {validation_class}">
            <div class="collapsible-header" onclick="toggleSection(this)">
                <span class="collapsible-title">{title}</span>
                <span class="collapsible-icon">▼</span>
            </div>
            <div class="collapsible-content" id="{section_id}">
                <div class="collapsible-content-inner">
                    <pre class="json-block">{self._escape_html(json_str)}</pre>
                </div>
            </div>
        </div>
'''

    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        if not isinstance(text, str):
            return str(text)
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#39;'))

    def run(self):
        """运行测试"""
        print("\n" + "=" * 60)
        print("文件提交审核流程测试")
        print("=" * 60)

        # 初始化服务
        if not self.init_services():
            print("初始化服务失败")
            return

        # 显示角色选择菜单
        if not self.show_role_menu():
            print("退出测试")
            return

        # 主循环
        while True:
            action = self.show_action_menu()

            if action == 'quit':
                print("退出测试")
                break
            elif action == 'back':
                if not self.show_role_menu():
                    print("退出测试")
                    break
                continue

            if action == 'submit':
                # 选择并提交文件
                print(f"\n测试文件目录: {self.test_images_dir}")

                files = self.select_files(self.test_images_dir)

                if not files:
                    print("\n未选择任何文件")
                    continue

                print(f"\n已选择 {len(files)} 个文件，开始处理...")

                # 处理文件
                for file_path in files:
                    results = self.process_file(file_path)
                    # process_file 返回列表，展开到结果集中
                    self.results.extend(results)

                # 生成报告
                if self.results:
                    self.generate_html_report()
                else:
                    print("\n没有生成报告（无结果）")

                # 询问是否继续
                continue_choice = input("\n是否继续测试? (y/n): ").strip().lower()
                if continue_choice != 'y':
                    break
            
            elif action == 'review':
                # 审核提交记录
                self.show_review_menu()


def main():
    """主函数"""
    tester = FileCommitTester()
    tester.run()


if __name__ == "__main__":
    main()
