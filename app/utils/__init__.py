"""
用户工具模块
包含路由工具和其他工具函数

注意：由于 app/utils 现在是目录，而原来的 app/utils.py 是文件，
我们需要通过 importlib 来导入原来的 utils.py 文件
"""
# 导入用户路由工具
from .user_routes import get_user_route_url, get_user_route_name

# 从原来的 utils.py 文件导入所有函数（兼容性）
import importlib.util
import sys
from pathlib import Path

# 获取原来的 utils.py 文件路径
# app/utils/__init__.py 在 app/utils/ 目录下
# utils.py 在 app/ 目录下（上一级）
parent_dir = Path(__file__).parent.parent
utils_file_path = parent_dir / 'utils.py'

# 使用 importlib 加载原来的 utils.py 模块
if utils_file_path.exists():
    spec = importlib.util.spec_from_file_location("app.utils_module", utils_file_path)
    utils_module = importlib.util.module_from_spec(spec)
    sys.modules["app.utils_module"] = utils_module
    spec.loader.exec_module(utils_module)
    
    # 重新导出所有函数
    get_app_context_instance = utils_module.get_app_context_instance
    get_config = utils_module.get_config
    get_doc_rec_context = utils_module.get_doc_rec_context
    reset_doc_rec_context = utils_module.reset_doc_rec_context
    get_document_engine = utils_module.get_document_engine
    get_extractor = utils_module.get_extractor
    calculate_file_hash = utils_module.calculate_file_hash
    get_competition_level_badge_class = utils_module.get_competition_level_badge_class
    get_competition_levels_for_ui = utils_module.get_competition_levels_for_ui
    get_all_competition_levels = utils_module.get_all_competition_levels
    get_default_password = utils_module.get_default_password
else:
    # 如果 utils.py 不存在，抛出错误
    raise ImportError(f"找不到 utils.py 文件: {utils_file_path}")

__all__ = [
    'get_user_route_url',
    'get_user_route_name',
    'get_app_context_instance',
    'get_config',
    'get_doc_rec_context',
    'reset_doc_rec_context',
    'get_document_engine',
    'get_extractor',
    'calculate_file_hash',
    'get_competition_level_badge_class',
    'get_competition_levels_for_ui',
    'get_all_competition_levels',
    'get_default_password'
]

