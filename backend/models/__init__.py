"""
后端模型模块
包含所有数据模型和管理器
"""

# 这个文件确保 backend.models 是一个Python包
# 实际的模型类定义在各自的文件中

__all__ = [
    'AwardManager',
    'Award',
    'CompetitionManager',
    'Competition',
    'StudentManager',
    'Student',
    'TeacherManager',
    'Teacher',
    'AppContext',
    'init_app_context',
    'get_app_context',
    # New achievement types
    'PatentManager',
    'Patent',
    'SoftwareCopyrightManager',
    'SoftwareCopyright',
    'InnovationProjectManager',
    'InnovationProject',
    # Pending achievements and file management
    'PendingAchievementManager',
    'PendingAchievement',
    'OtherFileManager',
    'OtherFile',
    'UserPhotoManager',
    'UserPhoto',
    # Auto archive config
    'AutoArchiveConfigManager',
    'AutoArchiveConfig',
]

