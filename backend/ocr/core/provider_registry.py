"""
OCR Provider 注册机制

支持 Provider 自动注册和配置驱动的初始化
"""
from typing import Dict, Type, Any, Optional, TYPE_CHECKING
import logging
from abc import ABC

# 使用 TYPE_CHECKING 避免循环导入
if TYPE_CHECKING:
    from .providers import OCRProvider


class ProviderRegistry:
    """Provider 注册表（单例）"""

    _instance = None
    _providers: Dict[str, Type] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, name: str, provider_class: Type):
        """
        注册 Provider

        Args:
            name: Provider 名称（小写）
            provider_class: Provider 类
        """
        name_lower = name.lower()
        if name_lower in self._providers:
            import warnings
            warnings.warn(f"Provider '{name_lower}' 已存在，将被覆盖")
        self._providers[name_lower] = provider_class
    
    def get(self, name: str) -> Optional[Type]:
        """
        获取 Provider 类

        Args:
            name: Provider 名称

        Returns:
            Provider 类，如果不存在返回 None
        """
        return self._providers.get(name.lower())
    
    def list_providers(self) -> list:
        """列出所有已注册的 Provider"""
        return list(self._providers.keys())
    
    def create_provider(
        self,
        name: str,
        provider_config: Dict[str, Any],
        common_config: Dict[str, Any],
        logger: logging.Logger
    ) -> Any:
        """
        根据配置创建 Provider 实例
        
        Args:
            name: Provider 名称
            provider_config: Provider 特定配置（来自 settings.json）
            common_config: 通用配置（缓存路径等）
            logger: 日志记录器
            
        Returns:
            Provider 实例
            
        Raises:
            ValueError: 当 Provider 不存在时
        """
        provider_class = self.get(name)
        if not provider_class:
            available = self.list_providers()
            raise ValueError(
                f"Provider '{name}' 未注册。"
                f"可用的 Provider: {available}"
            )
        
        # 合并配置：Provider 特定配置优先，通用配置作为默认值
        merged_config = {**common_config, **provider_config}
        
        # 创建 Provider 实例
        # Provider 的 __init__ 应该接受 (config_dict, logger)
        return provider_class(merged_config, logger)


# 全局注册表实例
_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """获取全局 Provider 注册表"""
    return _registry


def register_provider(name: str):
    """
    装饰器：注册 Provider

    使用示例:
        @register_provider("zhipu")
        class ZhipuOCRProvider(OCRProvider):
            ...
    """
    def decorator(cls: Type) -> Type:
        _registry.register(name, cls)
        return cls
    return decorator
