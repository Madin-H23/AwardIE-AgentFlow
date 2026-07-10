"""
检测模块的数据模型
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class ValidationErrorSeverity(Enum):
    """错误严重程度"""
    ERROR = "error"      # 错误：必须修复，is_valid = False
    WARNING = "warning"  # 警告：建议修复，不影响 is_valid


@dataclass
class ValidationError:
    """
    单个检测错误

    Attributes:
        field: 字段名（如 'winner_name', 'competition_id'）
        message: 错误消息（人类可读）
        severity: 严重程度（error 或 warning）
        code: 错误代码（用于程序处理）
    """
    field: str
    message: str
    severity: ValidationErrorSeverity
    code: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'field': self.field,
            'message': self.message,
            'severity': self.severity.value,
            'code': self.code
        }

    @classmethod
    def error(cls, field: str, message: str, code: str) -> 'ValidationError':
        """创建一个错误级别的验证错误"""
        return cls(field, message, ValidationErrorSeverity.ERROR, code)

    @classmethod
    def warning(cls, field: str, message: str, code: str) -> 'ValidationError':
        """创建一个警告级别的验证错误"""
        return cls(field, message, ValidationErrorSeverity.WARNING, code)


@dataclass
class ValidationResult:
    """
    检测结果

    Attributes:
        is_valid: 是否通过检测（无 error 级别的错误）
        completeness_issues: 必填字段缺失问题
        content_issues: 内容格式/业务规则问题
        warnings: 警告（不影响 is_valid）
    """
    is_valid: bool
    completeness_issues: List[ValidationError] = field(default_factory=list)
    content_issues: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """是否有错误"""
        return bool(self.completeness_issues or self.content_issues)

    @property
    def has_warnings(self) -> bool:
        """是否有警告"""
        return bool(self.warnings)

    @property
    def all_issues(self) -> List[ValidationError]:
        """所有问题（包括警告）"""
        return self.completeness_issues + self.content_issues + self.warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'completeness_issues': [e.to_dict() for e in self.completeness_issues],
            'content_issues': [e.to_dict() for e in self.content_issues],
            'warnings': [e.to_dict() for e in self.warnings]
        }

    def to_json(self, ensure_ascii: bool = False) -> str:
        """序列化为 JSON"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii)

    @classmethod
    def valid(cls) -> 'ValidationResult':
        """创建一个通过检测的结果"""
        return cls(is_valid=True)

    @classmethod
    def invalid(cls, completeness_issues: List[ValidationError] = None,
                content_issues: List[ValidationError] = None) -> 'ValidationResult':
        """创建一个未通过检测的结果"""
        return cls(
            is_valid=False,
            completeness_issues=completeness_issues or [],
            content_issues=content_issues or []
        )
