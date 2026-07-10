"""
应用上下文类
统一管理所有管理器对象，提供全局访问入口
"""
import logging
from pathlib import Path
from typing import Optional

from backend.models.competition import CompetitionManager
from backend.models.award import AwardManager
from backend.models.student import StudentManager
from backend.models.teacher import TeacherManager
from backend.models.laboratory import LaboratoryManager
# AchievementManager（活动—成果）已废弃，不再导入。

# New achievement type managers
from backend.models.patent import PatentManager
from backend.models.software_copyright import SoftwareCopyrightManager
from backend.models.innovation_project import InnovationProjectManager
from backend.models.pending_achievement import PendingAchievementManager
from backend.models.other_file import OtherFileManager
from backend.models.user_photo import UserPhotoManager
from backend.models.review_log import ReviewLogManager
from backend.models.auto_archive_config import AutoArchiveConfigManager

logger = logging.getLogger(__name__)


class AppContext:
    """应用上下文类，统一管理所有管理器"""

    def __init__(self, db_path: str, images_dir: Optional[Path] = None):
        """
        初始化应用上下文

        Args:
            db_path: 数据库文件路径
            images_dir: 图片存储目录（可选，如果不提供则自动推断）
        """
        # 统一解析为绝对路径，避免相对路径导致的问题
        resolved = Path(db_path).resolve()
        self.db_path: str = str(resolved)
        self.images_dir: Optional[Path] = images_dir
        logger.info("AppContext 使用数据库: %s", self.db_path)

        # 基础管理器对象
        self.competition_manager: Optional[CompetitionManager] = None
        self.student_manager: Optional[StudentManager] = None
        self.teacher_manager: Optional[TeacherManager] = None
        self.award_manager: Optional[AwardManager] = None
        self.laboratory_manager: Optional[LaboratoryManager] = None

        # 新成果类型管理器
        self.patent_manager: Optional[PatentManager] = None
        self.software_copyright_manager: Optional[SoftwareCopyrightManager] = None
        self.innovation_project_manager: Optional[InnovationProjectManager] = None
        self.pending_achievement_manager: Optional[PendingAchievementManager] = None
        self.other_file_manager: Optional[OtherFileManager] = None
        self.user_photo_manager: Optional[UserPhotoManager] = None
        self.review_log_manager: Optional[ReviewLogManager] = None
        self.auto_archive_config_manager: Optional[AutoArchiveConfigManager] = None

        # 初始化所有管理器
        self._initialize_managers()
    
    def _initialize_managers(self):
        """初始化所有管理器（按依赖顺序）"""
        logger.info("开始初始化应用上下文...")

        try:
            # 1. 初始化基础管理器（无依赖）
            logger.info("初始化 CompetitionManager...")
            self.competition_manager = CompetitionManager(self.db_path)

            logger.info("初始化 StudentManager...")
            self.student_manager = StudentManager(self.db_path)

            logger.info("初始化 TeacherManager...")
            self.teacher_manager = TeacherManager(self.db_path)

            # 2. 初始化 AwardManager（依赖：无，但需要 images_dir）
            logger.info("初始化 AwardManager...")
            self.award_manager = AwardManager(self.db_path, self.images_dir)

            # 3. 初始化 LaboratoryManager（依赖：student_manager, teacher_manager）
            logger.info("初始化 LaboratoryManager...")
            self.laboratory_manager = LaboratoryManager(
                db_path=self.db_path,
                student_manager=self.student_manager,
                teacher_manager=self.teacher_manager
            )

            # 5. AchievementManager（活动—成果）已废弃：活动概念已从系统移除，不再初始化。

            # 6. 初始化新成果类型管理器
            # 使用统一文件管理器获取files_root路径，不依赖images_dir
            from backend.services.unified_file_manager import get_unified_file_manager
            file_manager = get_unified_file_manager()
            files_dir = file_manager.files_root

            logger.info("初始化 PatentManager...")
            self.patent_manager = PatentManager(self.db_path, files_dir)

            logger.info("初始化 SoftwareCopyrightManager...")
            self.software_copyright_manager = SoftwareCopyrightManager(self.db_path, files_dir)

            logger.info("初始化 InnovationProjectManager...")
            self.innovation_project_manager = InnovationProjectManager(self.db_path, files_dir)

            logger.info(f"初始化 PendingAchievementManager...{self.db_path}")
            self.pending_achievement_manager = PendingAchievementManager(self.db_path)

            logger.info("初始化 OtherFileManager...")
            self.other_file_manager = OtherFileManager(self.db_path, files_dir)

            logger.info("初始化 UserPhotoManager...")
            self.user_photo_manager = UserPhotoManager(self.db_path, files_dir)

            logger.info("初始化 ReviewLogManager...")
            self.review_log_manager = ReviewLogManager(self.db_path)

            logger.info("初始化 AutoArchiveConfigManager...")
            self.auto_archive_config_manager = AutoArchiveConfigManager(self.db_path)

            logger.info("应用上下文初始化完成")

        except Exception as e:
            logger.error(f"初始化应用上下文失败: {e}")
            raise
    
    def get_competition_manager(self) -> CompetitionManager:
        """获取竞赛管理器"""
        if self.competition_manager is None:
            raise RuntimeError("CompetitionManager 未初始化")
        return self.competition_manager
    
    def get_student_manager(self) -> StudentManager:
        """获取学生管理器"""
        if self.student_manager is None:
            raise RuntimeError("StudentManager 未初始化")
        return self.student_manager
    
    def get_teacher_manager(self) -> TeacherManager:
        """获取教师管理器"""
        if self.teacher_manager is None:
            raise RuntimeError("TeacherManager 未初始化")
        return self.teacher_manager
    
    def get_award_manager(self) -> AwardManager:
        """获取奖状管理器"""
        if self.award_manager is None:
            raise RuntimeError("AwardManager 未初始化")
        return self.award_manager
    
    def get_laboratory_manager(self) -> LaboratoryManager:
        """获取实验室管理器"""
        if self.laboratory_manager is None:
            raise RuntimeError("LaboratoryManager 未初始化")
        return self.laboratory_manager

    # New achievement type manager getters
    def get_patent_manager(self) -> PatentManager:
        """获取专利管理器"""
        if self.patent_manager is None:
            raise RuntimeError("PatentManager 未初始化")
        return self.patent_manager

    def get_software_copyright_manager(self) -> SoftwareCopyrightManager:
        """获取软著管理器"""
        if self.software_copyright_manager is None:
            raise RuntimeError("SoftwareCopyrightManager 未初始化")
        return self.software_copyright_manager

    def get_innovation_project_manager(self) -> InnovationProjectManager:
        """获取大创项目管理器"""
        if self.innovation_project_manager is None:
            raise RuntimeError("InnovationProjectManager 未初始化")
        return self.innovation_project_manager

    def get_pending_achievement_manager(self) -> PendingAchievementManager:
        """获取待审核成果管理器"""
        if self.pending_achievement_manager is None:
            raise RuntimeError("PendingAchievementManager 未初始化")
        return self.pending_achievement_manager

    def get_other_file_manager(self) -> OtherFileManager:
        """获取其他文件管理器"""
        if self.other_file_manager is None:
            raise RuntimeError("OtherFileManager 未初始化")
        return self.other_file_manager

    def get_review_log_manager(self) -> ReviewLogManager:
        """获取审核日志管理器"""
        if self.review_log_manager is None:
            raise RuntimeError("ReviewLogManager 未初始化")
        return self.review_log_manager

    def get_user_photo_manager(self) -> UserPhotoManager:
        """获取用户相册管理器"""
        if self.user_photo_manager is None:
            raise RuntimeError("UserPhotoManager 未初始化")
        return self.user_photo_manager

    def get_auto_archive_config_manager(self) -> AutoArchiveConfigManager:
        """获取自动归档配置管理器"""
        if self.auto_archive_config_manager is None:
            raise RuntimeError("AutoArchiveConfigManager 未初始化")
        return self.auto_archive_config_manager

    def __repr__(self):
        """返回应用上下文的字符串表示"""
        managers_initialized = all([
            self.competition_manager is not None,
            self.student_manager is not None,
            self.teacher_manager is not None,
            self.award_manager is not None,
            self.laboratory_manager is not None,
            # New managers
            self.patent_manager is not None,
            self.software_copyright_manager is not None,
            self.innovation_project_manager is not None,
            self.pending_achievement_manager is not None,
            self.other_file_manager is not None,
            self.user_photo_manager is not None,
            self.auto_archive_config_manager is not None,
        ])
        return f"AppContext(db_path={self.db_path}, managers_initialized={managers_initialized})"


# 全局应用上下文实例（单例模式）
_global_app_context: Optional[AppContext] = None


def init_app_context(db_path: str, images_dir: Optional[Path] = None) -> AppContext:
    """
    初始化全局应用上下文
    
    Args:
        db_path: 数据库文件路径
        images_dir: 图片存储目录（可选）
    
    Returns:
        应用上下文实例
    """
    global _global_app_context
    if _global_app_context is not None:
        logger.warning("应用上下文已经初始化，将重新初始化")
    
    _global_app_context = AppContext(db_path, images_dir)
    return _global_app_context


def get_app_context() -> AppContext:
    """
    获取全局应用上下文
    
    Returns:
        应用上下文实例
    
    Raises:
        RuntimeError: 如果应用上下文未初始化
    """
    global _global_app_context
    if _global_app_context is None:
        raise RuntimeError("应用上下文未初始化，请先调用 init_app_context()")
    return _global_app_context


def reset_app_context():
    """重置全局应用上下文（主要用于测试）"""
    global _global_app_context
    _global_app_context = None

