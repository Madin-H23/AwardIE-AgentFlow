"""
用户工具模块（T73 单一真源收敛）

原实现：app/utils.py 文件与 app/utils/ 包同名并存，__init__ 用 importlib 以
"app.utils_module" 第二命名空间加载文件版——全局 _managers 缓存因此存在两份，
任何清缓存逻辑都必须记得清两处（T64 曾踩：漏一处=测试静默读真库）。

现实现：原 utils.py 内容已迁移为包内子模块 app/utils/_core.py（git mv 保历史），
__init__ 直接 re-export——_managers 全局仅 _core 一份。
"""
from .user_routes import get_user_route_url, get_user_route_name
from ._core import (
    get_app_context_instance,
    get_app_config,
    get_doc_rec_context,
    reset_doc_rec_context,
    get_document_engine,
    get_extractor,
    calculate_file_hash,
    get_competition_level_badge_class,
    get_competition_levels_for_ui,
    get_all_competition_levels,
    get_default_password,
    reset_runtime_caches,
)

__all__ = [
    'get_user_route_url',
    'get_user_route_name',
    'get_app_context_instance',
    'get_app_config',
    'get_doc_rec_context',
    'reset_doc_rec_context',
    'get_document_engine',
    'get_extractor',
    'calculate_file_hash',
    'get_competition_level_badge_class',
    'get_competition_levels_for_ui',
    'get_all_competition_levels',
    'get_default_password',
    'reset_runtime_caches',
]
