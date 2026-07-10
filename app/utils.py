"""
Web层工具函数
延迟导入管理器，避免启动时导入错误
"""
import json
import hashlib
from pathlib import Path
from flask import current_app, has_app_context

# 全局管理器实例（单例）
_managers = {}
_config_cache = None
_doc_rec_context = None

def _get_managers():
    """延迟导入和初始化管理器"""
    global _managers
    
    if not _managers:
        if not has_app_context():
            raise RuntimeError("Cannot access app context outside of request")
        
        # 延迟导入，避免启动时错误
        try:
            from backend.models.app_context import init_app_context
            # 使用AppContext方式
            db_path = current_app.config.get('DATABASE_PATH')
            
            if not db_path:
                raise ValueError("DATABASE_PATH not configured")
            
            # 转换为Path对象
            if isinstance(db_path, str):
                db_path = Path(db_path)
            
            # 初始化AppContext
            app_context = init_app_context(str(db_path))
            _managers['_app_context'] = app_context
            return app_context
        except ImportError as e:
            # 如果AppContext不存在，尝试直接导入管理器
            try:
                from backend.models.award import AwardManager
                from backend.models.competition import CompetitionManager
                from backend.models.student import StudentManager
                from backend.models.teacher import TeacherManager
            except ImportError as import_err:
                # 如果模型文件都不存在，抛出更友好的错误
                raise RuntimeError(
                    f"无法导入后端模型文件: {import_err}\n"
                    f"请确保 backend/models/ 目录下存在以下文件:\n"
                    f"- award.py (AwardManager)\n"
                    f"- competition.py (CompetitionManager)\n"
                    f"- student.py (StudentManager)\n"
                    f"- teacher.py (TeacherManager)\n"
                    f"- app_context.py (AppContext, init_app_context)\n"
                    f"\n原始错误: {e}\n导入错误: {import_err}"
                ) from import_err
            
            # 从Flask配置获取路径
            db_path = current_app.config.get('DATABASE_PATH')
            
            if not db_path:
                raise ValueError("DATABASE_PATH not configured")
            
            # 转换为字符串路径
            if isinstance(db_path, Path):
                db_path = str(db_path)
            
            # 初始化管理器 - AwardManager会自动从统一文件管理器获取images_dir
            _managers['award'] = AwardManager(db_path)
            _managers['competition'] = CompetitionManager(db_path)
            _managers['student'] = StudentManager(db_path)
            _managers['teacher'] = TeacherManager(db_path)
            
            # 初始化 LaboratoryManager（需要先初始化）
            from backend.models.laboratory import LaboratoryManager
            _managers['laboratory'] = LaboratoryManager(
                db_path=db_path,
                student_manager=_managers['student'],
                teacher_manager=_managers['teacher']
            )

            # AchievementManager（活动—成果）已废弃，不再初始化。

            # 返回一个类似AppContext的包装对象
            class ManagerWrapper:
                def get_award_manager(self):
                    return _managers['award']

                def get_competition_manager(self):
                    return _managers['competition']

                def get_student_manager(self):
                    return _managers['student']

                def get_teacher_manager(self):
                    return _managers['teacher']

                def get_laboratory_manager(self):
                    return _managers.get('laboratory')

                def get_patent_manager(self):
                    return _managers.get('patent')

                def get_software_copyright_manager(self):
                    return _managers.get('software_copyright')

                def get_innovation_project_manager(self):
                    return _managers.get('innovation_project')

                def get_pending_achievement_manager(self):
                    return _managers.get('pending_achievement')

                def get_other_file_manager(self):
                    return _managers.get('other_file')

                def get_user_photo_manager(self):
                    return _managers.get('user_photo')

            return ManagerWrapper()
    
    # 如果已经有AppContext，直接返回
    if '_app_context' in _managers:
        return _managers['_app_context']

    # 否则返回管理器包装对象
    class ManagerWrapper:
        def get_award_manager(self):
            return _managers['award']

        def get_competition_manager(self):
            return _managers['competition']

        def get_student_manager(self):
            return _managers['student']

        def get_teacher_manager(self):
            return _managers['teacher']

        def get_laboratory_manager(self):
            return _managers.get('laboratory')

        def get_patent_manager(self):
            return _managers.get('patent')

        def get_software_copyright_manager(self):
            return _managers.get('software_copyright')

        def get_innovation_project_manager(self):
            return _managers.get('innovation_project')

        def get_pending_achievement_manager(self):
            return _managers.get('pending_achievement')

        def get_other_file_manager(self):
            return _managers.get('other_file')

        def get_user_photo_manager(self):
            return _managers.get('user_photo')

    return ManagerWrapper()

def get_app_context_instance():
    """
    获取或初始化AppContext实例（单例模式）
    如果AppContext不存在，则直接返回管理器包装对象
    
    Returns:
        AppContext实例或管理器包装对象
    """
    return _get_managers()

def get_config():
    """获取配置（使用统一的配置加载器）"""
    global _config_cache
    # 在开发环境下每次都重新加载配置，避免缓存导致配置更新不生效
    try:
        from flask import current_app
        is_development = current_app.config.get('DEBUG', False)
    except:
        # 如果不在Flask上下文中，默认重新加载
        is_development = True
    
    if _config_cache is None or is_development:
        try:
            from config.loader import get_config as get_config_loader
            config_loader = get_config_loader()
            # 在开发环境下清除加载器的缓存，强制重新加载
            if is_development:
                config_loader._config = None
            _config_cache = config_loader.load_config()
        except Exception as e:
            raise RuntimeError(f"无法加载配置: {e}") from e
    return _config_cache

def get_doc_rec_context():
    """获取服务上下文（单例）"""
    global _doc_rec_context
    if _doc_rec_context is None:
        from backend.services.context import get_context
        _doc_rec_context = get_context()
    return _doc_rec_context


def reset_doc_rec_context() -> None:
    """重置文档识别上下文单例。在管理端保存 OCR/LLM 默认供应商后调用，使下次请求按新配置创建引擎。"""
    global _doc_rec_context
    _doc_rec_context = None
    try:
        from backend.services.context import reset_context
        reset_context()
    except Exception:
        pass


def get_document_engine():
    """
    获取DocumentEngine实例（已弃用）

    保留此函数以保持向后兼容，但返回doc_rec的OCR引擎
    """
    import warnings
    warnings.warn(
        "get_document_engine() is deprecated, use get_doc_rec_context().extract_framework.ocr_engine instead",
        DeprecationWarning,
        stacklevel=2
    )
    return get_doc_rec_context().extract_framework.ocr_engine

def get_extractor():
    """
    获取AwardExtract实例（已弃用）

    保留此函数以保持向后兼容，但返回doc_rec的抽取框架
    """
    import warnings
    warnings.warn(
        "get_extractor() is deprecated, use get_doc_rec_context().extract_framework instead",
        DeprecationWarning,
        stacklevel=2
    )
    return get_doc_rec_context().extract_framework

def calculate_file_hash(file_path):
    """计算文件MD5哈希值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def _get_competition_levels_from_config():
    """
    从全局配置获取竞赛等级列表（统一配置源）
    
    Returns:
        list: 竞赛等级配置列表，每个元素是包含 name, standardized, order, mapped_to 等的字典
    """
    config = get_config()
    
    if "competition_levels" not in config:
        raise ValueError(
            "竞赛等级配置缺失：请在 config/settings.json 的根节点配置 competition_levels"
        )
    
    levels = config["competition_levels"]
    if not levels:
        raise ValueError("competition_levels 配置为空")
    
    # 如果是字符串列表，转换为对象列表（向后兼容）
    if isinstance(levels, list) and len(levels) > 0 and isinstance(levels[0], str):
        return [{"name": name, "standardized": True, "order": idx + 1} for idx, name in enumerate(levels)]
    
    return levels


def _get_award_levels_from_config():
    """
    从全局配置获取奖项等级列表（统一配置源）
    
    Returns:
        list: 奖项等级名称列表
    """
    config = get_config()
    
    if "award_levels" not in config:
        raise ValueError(
            "奖项等级配置缺失：请在 config/settings.json 的根节点配置 award_levels"
        )
    
    levels = config["award_levels"]
    if not levels:
        raise ValueError("award_levels 配置为空")
    
    return levels


def _get_color_scheme():
    """
    获取当前使用的颜色方案，使用 zip 方式将颜色列表与竞赛等级列表整合
    颜色方案硬编码在代码中，使用默认方案
    
    Returns:
        dict: 颜色映射字典，格式为 {level_name: color_class, ...}
    """
    # 硬编码的默认颜色方案（包含足够的颜色以支持竞赛级别扩展）
    DEFAULT_COLOR_SCHEME = [
        "bg-danger",      # 国际赛
        "bg-warning",     # 国赛
        "bg-info",        # 省赛
        "bg-primary",     # 区域赛
        "bg-success",     # 校赛
        "bg-secondary",   # 扩展1
        "bg-dark"         # 扩展2
    ]
    
    color_list = DEFAULT_COLOR_SCHEME
    
    # 获取全局竞赛等级列表
    competition_levels = _get_competition_levels_from_config()
    level_names = [level if isinstance(level, str) else level.get("name", "") for level in competition_levels]
    
    # 使用 zip 方式整合：如果颜色列表比等级列表长，只取前 len(level_names) 个
    # 如果颜色列表比等级列表短，循环使用颜色
    color_map = {}
    for idx, level_name in enumerate(level_names):
        if idx < len(color_list):
            color_map[level_name] = color_list[idx]
        else:
            # 如果颜色不够，循环使用
            color_map[level_name] = color_list[idx % len(color_list)]
    
    return color_map


def get_competition_level_badge_class(competition_level: str) -> str:
    """
    获取竞赛等级的Bootstrap badge颜色类（从统一配置和预设颜色方案读取）
    
    Args:
        competition_level: 竞赛等级（如：国际赛、国赛、省赛、校赛、区域赛）
    
    Returns:
        Bootstrap badge颜色类（如：bg-danger, bg-warning等）
    """
    if not competition_level:
        return "bg-secondary"
    
    level = str(competition_level).strip()
    
    try:
        color_map = _get_color_scheme()
        return color_map.get(level, "bg-secondary")
    except ValueError:
        # 重新抛出配置缺失异常
        raise
    except Exception as e:
        # 配置加载失败，抛出异常
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'加载竞赛等级颜色配置失败: {e}')
        raise RuntimeError(
            f"加载竞赛等级颜色配置失败: {e}。"
            "请确保 config/settings.json 中存在 ui.color_schemes 配置"
        ) from e


def get_competition_levels_for_ui():
    """
    获取用于UI显示的竞赛等级列表（从 validation.standardized_competition_levels 读取，如果没有则从全局配置读取）
    
    Returns:
        list: 标准化竞赛等级名称列表
    """
    config = get_config()
    
    # 优先从 validation.standardized_competition_levels 读取
    if "validation" in config and "standardized_competition_levels" in config["validation"]:
        standardized_levels = config["validation"]["standardized_competition_levels"]
        if standardized_levels:
            return standardized_levels
    
    # 如果没有配置，从全局配置读取所有等级
    return _get_competition_levels_from_config()


def get_all_competition_levels():
    """
    获取所有竞赛等级列表（包括非标准化的等级，用于检测）
    
    Returns:
        list: 所有竞赛等级名称列表
    """
    levels_config = _get_competition_levels_from_config()
    return [level["name"] for level in levels_config]


def get_default_password():
    """
    从配置文件获取系统默认密码
    
    Returns:
        str: 默认密码
    """
    config = get_config()
    
    if "system" not in config or "default_password" not in config["system"]:
        raise ValueError(
            "默认密码配置缺失：请在 config/settings.json 中配置 system.default_password"
        )
    
    default_password = config["system"]["default_password"]
    if not default_password:
        raise ValueError("system.default_password 配置为空")
    
    return default_password

