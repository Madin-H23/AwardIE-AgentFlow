"""
统一值映射器（已弃用）

注意：此模块已弃用。验证逻辑现在由各个抽取器内部实现。
- InnovationExtractor: 内部验证大创项目的必需字段和格式
- PatentExtractor: 内部验证专利证书的必需字段和格式
- SoftwareExtractor: 内部验证软著证书的必需字段和格式

如果需要值映射功能（如 "Gold Medal" → "金奖"），建议：
1. 在配置文件中定义映射规则（config/settings.json）
2. 在抽取器内部读取配置并应用映射
3. 或者直接在 LLM prompt 中要求返回标准化的值

此文件保留仅用于向后兼容。
"""
import logging
from typing import Any, Dict, List

from .types import ValidationError, ValidationResult

logger = logging.getLogger(__name__)


class ExtractorValidator:
    """
    值映射器（已弃用）

    .. deprecated::
        验证逻辑现在由各个抽取器内部实现。
        此类保留仅用于向后兼容。

    原用于值映射，如：
    - "Gold Medal" → "金奖"
    - "区域赛" → "省赛"

    现在建议直接在抽取器内部或配置文件中处理值映射。
    """

    def __init__(self, value_mappings: Dict[str, Dict[str, str]]):
        """
        Args:
            value_mappings: 字段名 -> { 原始值: 映射值 }，用于域修正。
        """
        self.value_mappings = value_mappings or {}
        logger.warning(
            "ExtractorValidator 已弃用。验证逻辑现在由各个抽取器内部实现。"
        )

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        应用值映射

        .. deprecated::
            此方法已弃用。请使用抽取器内部的验证逻辑。

        Args:
            data: 待验证的数据

        Returns:
            ValidationResult with mapped_data
        """
        if not data:
            return ValidationResult(is_valid=True, mapped_data=data)
        mapped = self._apply_mappings(data)
        return ValidationResult(is_valid=True, mapped_data=mapped)

    def _apply_mappings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """应用值映射规则"""
        out = dict(data)
        for field_name, mapping in self.value_mappings.items():
            if field_name not in out:
                continue
            v = out[field_name]
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            s = str(v).strip()
            if s in mapping:
                out[field_name] = mapping[s]
                logger.debug("value_mapping %s: %r -> %r", field_name, s, mapping[s])
            elif isinstance(v, str):
                low = s.lower()
                for k, val in mapping.items():
                    if isinstance(k, str) and k.lower() == low:
                        out[field_name] = val
                        break
        return out
