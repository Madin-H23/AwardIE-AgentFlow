"""
OCR Provider 工厂

根据配置自动创建对应的 Provider 实例
"""
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from .provider_registry import get_registry
from .providers import OCRProvider
from ..exceptions import OCRConfigError


class ProviderFactory:
    """Provider 工厂类"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化工厂
        
        Args:
            logger: 日志记录器（可选）
        """
        self.logger = logger or logging.getLogger(__name__)
        self.registry = get_registry()
    
    def create_provider(
        self,
        provider_name: str,
        provider_config: Dict[str, Any],
        common_config: Optional[Dict[str, Any]] = None
    ) -> OCRProvider:
        """
        根据配置创建 Provider
        
        Args:
            provider_name: Provider 名称（如 "zhipu", "baidu", "paddle"）
            provider_config: Provider 特定配置（来自 settings.json）
            common_config: 通用配置（缓存路径、临时目录等）
            
        Returns:
            Provider 实例
            
        Raises:
            ValueError: 当 Provider 不存在或配置无效时
        """
        if common_config is None:
            common_config = {}
        
        # 确保 provider_name 是小写
        provider_name = provider_name.lower()
        
        # 从注册表获取 Provider 类
        provider_class = self.registry.get(provider_name)
        if not provider_class:
            available = self.registry.list_providers()
            raise ValueError(
                f"Provider '{provider_name}' 未注册。"
                f"可用的 Provider: {available}。"
                f"请确保 Provider 已使用 @register_provider 装饰器注册。"
            )
        
        # 合并配置
        merged_config = {**common_config, **provider_config}
        
        # 创建 Provider 实例
        try:
            provider = provider_class(merged_config, self.logger)
            self.logger.info(f"成功创建 Provider: {provider_name}")
            return provider
        except Exception as e:
            raise OCRConfigError(
                f"创建 Provider '{provider_name}' 失败: {e}"
            ) from e
    
    def create_from_config_loader(
        self,
        config_loader,
        common_config: Optional[Dict[str, Any]] = None
    ) -> OCRProvider:
        """
        从 ConfigLoader 创建 Provider
        
        Args:
            config_loader: ConfigLoader 实例
            common_config: 通用配置（可选）
            
        Returns:
            Provider 实例
        """
        # 获取默认 Provider
        default_provider = config_loader.get_default_provider('ocr')
        
        # 获取 Provider 配置
        provider_config = config_loader.get_provider_config('ocr', default_provider)
        
        # 创建 Provider
        return self.create_provider(
            provider_name=default_provider,
            provider_config=provider_config,
            common_config=common_config
        )
