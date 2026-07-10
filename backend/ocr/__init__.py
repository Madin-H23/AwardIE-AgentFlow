"""
OCR Core Module - 独立的图片和PDF文本识别模块

这是一个完全独立的OCR模块，支持：
- 图片OCR识别
- PDF第一页OCR识别（通过PDF转图片）
- 数据库缓存管理
- 灵活的配置管理

使用示例:
    >>> from ocr_core import OCRConfig, OCREngine
    >>>
    >>> # 创建配置
    >>> config = OCRConfig(api_key="your_api_key")
    >>>
    >>> # 创建引擎
    >>> ocr = OCREngine(config)
    >>>
    >>> # 识别图片
    >>> text, from_cache = ocr.get_text("image.jpg")
    >>>
    >>> # 识别PDF第一页
    >>> text, from_cache = ocr.get_text("document.pdf")
"""
from .config import OCRConfig
from .core.ocr_engine import OCREngine
from .core.cache_db import CacheDB
from .core.provider_factory import ProviderFactory
from .core.provider_registry import get_registry, register_provider

# 导入所有 Provider 以确保它们被注册
# 这会在模块加载时自动执行 @register_provider 装饰器
from .core.providers import (  # noqa: F401
    OCRProvider,
    ZhipuOCRProvider,
    BaiduOCRProvider,
    PaddleOCRProvider,
    RapidOCRProvider,
    OllamaOCRProvider,
)
from .exceptions import (
    OCRError,
    OCRConfigError,
    OCRAPIServiceError,
    OCRFileNotFoundError,
    OCRFileFormatError,
    OCRCacheError,
    OCRImageProcessingError,
    OCRTimeoutError,
)
from .types import OCRResult, OCRAPIData, CacheStats, FileType

__version__ = "1.0.0"

# 定义导出的公共接口
__all__ = [
    # 版本
    "__version__",
    # 配置
    "OCRConfig",
    # 核心类
    "OCREngine",
    "CacheDB",
    # 异常
    "OCRError",
    "OCRConfigError",
    "OCRAPIServiceError",
    "OCRFileNotFoundError",
    "OCRFileFormatError",
    "OCRCacheError",
    "OCRImageProcessingError",
    "OCRTimeoutError",
    # 类型
    "OCRResult",
    "OCRAPIData",
    "CacheStats",
    "FileType",
]


def create_ocr_engine(
    provider_name: str,
    provider_config: dict,
    db_path: str,
    temp_dir: str,
    debug: bool = False
) -> OCREngine:
    """
    创建OCR引擎的便捷函数（已更新为使用配置驱动模式）

    Args:
        provider_name: Provider 名称（如 "zhipu", "baidu", "paddle"），必须提供
        provider_config: Provider 特定配置字典，必须提供
        db_path: 数据库路径，必须明确指定
        temp_dir: 临时文件目录，必须明确指定
        debug: 是否开启调试模式

    Returns:
        OCREngine实例

    Raises:
        ValueError: 当必需参数未提供时

    Example:
        >>> # 推荐：从 ServiceContext 获取路径
        >>> from backend.services.context import ServiceContext
        >>> context = ServiceContext()
        >>> ocr = create_ocr_engine(
        ...     provider_name="zhipu",
        ...     provider_config={"api_key": "your_key", "api_url": "..."},
        ...     db_path=str(context.ocr_cache_path),
        ...     temp_dir=str(context.temp_dir)
        ... )
        >>> text, cached = ocr.get_text("image.jpg")
    """
    if not provider_name:
        raise ValueError("provider_name 必须提供")
    if not provider_config:
        raise ValueError("provider_config 必须提供")
    if not db_path:
        raise ValueError("db_path 必须明确指定，不允许使用默认路径")
    if not temp_dir:
        raise ValueError("temp_dir 必须明确指定，不允许使用默认路径")
    
    config = OCRConfig(
        db_path=db_path,
        temp_dir=temp_dir,
        provider=provider_name,
        debug=debug
    )
    return OCREngine(config, provider_config=provider_config)
