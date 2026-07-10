"""
奖状检测模块

提供统一的奖状数据检测功能，用于：
1. 文件导入时的数据检测
2. 奖状编辑后的实时检测
3. 关联操作后的状态更新
"""

from .award_validator import AwardValidator
from .models import ValidationResult, ValidationError, ValidationErrorSeverity

__all__ = ['AwardValidator', 'ValidationResult', 'ValidationError', 'ValidationErrorSeverity']
