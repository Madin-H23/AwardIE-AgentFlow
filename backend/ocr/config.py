"""
OCR模块配置管理

提供统一的配置管理类，只保留通用配置，厂商特定配置从 settings.json 读取
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
import os


@dataclass
class OCRConfig:
    """OCR模块通用配置（不包含厂商特定配置）"""

    # ========== 数据库配置 ==========
    db_path: str = ""
    
    # ========== Provider配置 ==========
    provider: str = ""  # Provider 名称，从配置文件中读取
    
    # ========== 临时文件配置 ==========
    temp_dir: str = ""

    # ========== 图片处理配置（通用）==========
    max_image_size: int = 2048
    jpeg_quality: int = 85

    # ========== 日志配置 ==========
    debug: bool = False
    log_file: Optional[str] = None
    log_level: str = "INFO"

    # ========== 缓存配置 ==========
    use_cache: bool = True
    cache_retention_days: int = 30

    def __post_init__(self):
        """
        初始化后处理，验证必需配置
        """
        # 验证必需路径，不允许默认值
        if not self.db_path:
            raise ValueError(
                "OCRConfig.db_path 必须明确指定，不允许使用默认路径。"
                "请从 ServiceContext 或配置文件中获取正确的路径。"
            )
        
        if not self.temp_dir:
            raise ValueError(
                "OCRConfig.temp_dir 必须明确指定，不允许使用默认路径。"
                "请从 ServiceContext 或配置文件中获取正确的路径。"
            )
        
        if not self.provider:
            raise ValueError(
                "OCRConfig.provider 必须明确指定。"
                "请从配置文件的 default_provider 获取。"
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        Returns:
            配置字典
        """
        from dataclasses import asdict
        return asdict(self)

    def validate(self) -> bool:
        """
        验证配置是否有效

        Returns:
            配置是否有效
            
        Raises:
            ValueError: 当配置无效时
        """
        # 验证数值范围
        if self.max_image_size <= 0:
            raise ValueError("max_image_size 必须大于0")

        if not 0 < self.jpeg_quality <= 100:
            raise ValueError("jpeg_quality 必须在 1-100 之间")

        if self.cache_retention_days < 0:
            raise ValueError("cache_retention_days 不能为负数")

        return True
