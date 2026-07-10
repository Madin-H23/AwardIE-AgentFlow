"""抽取框架类型定义。"""
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional


class ExtractStatus(str, Enum):
    SUCCESS = "success"
    NO_TEMPLATE = "no_template"
    PARSE_ERROR = "parse_error"
    OCR_ERROR = "ocr_error"
    LLM_ERROR = "llm_error"
    FILE_ERROR = "file_error"


class TemplateType:
    """模板类型常量"""
    AWARD = "award"       # 奖状
    PATENT = "patent"     # 专利
    SOFTWARE = "software" # 软著
    INNOVATION = "innovation"  # 大创项目
    OTHER = "other"       # 其他

    # 类型列表
    ALL = [AWARD, PATENT, SOFTWARE, INNOVATION, OTHER]

    # 类型显示名称
    DISPLAY_NAMES = {
        AWARD: "奖状",
        PATENT: "专利",
        SOFTWARE: "软件著作权",
        INNOVATION: "大创项目",
        OTHER: "其他"
    }

    @classmethod
    def validate(cls, type_value: str) -> bool:
        """验证类型是否有效"""
        return type_value in cls.ALL

    @classmethod
    def get_display_name(cls, type_value: str) -> str:
        """获取类型的显示名称"""
        return cls.DISPLAY_NAMES.get(type_value, type_value)


@dataclass
class ValidationError:
    field_name: str
    error_type: str
    error_message: str
    error_category: str = "content"
    invalid_value: Optional[Any] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "field": self.field_name,
            "error_type": self.error_type,
            "message": self.error_message,
            "category": self.error_category,
        }
        if self.invalid_value is not None:
            out["invalid_value"] = self.invalid_value
        if self.suggestion is not None:
            out["suggestion"] = self.suggestion
        return out


@dataclass
class ValidationResult:
    is_valid: bool
    content_issues: List[ValidationError] = field(default_factory=list)
    completeness_issues: List[ValidationError] = field(default_factory=list)
    mapped_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "content_issues": [e.to_dict() for e in self.content_issues],
            "completeness_issues": [e.to_dict() for e in self.completeness_issues],
            "mapped_data": self.mapped_data,
        }

    def to_json(self, ensure_ascii: bool = False) -> str:
        """将 ValidationResult 序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii)


@dataclass
class ExtractResult:
    status: ExtractStatus
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    template_type: Optional[str] = None
    extractor_name: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_cache_hit: bool = False
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    llm_cache_hit: bool = False
    validation_result: Optional[ValidationResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== 类型别名 ====================

# 前向引用，避免循环导入
if TYPE_CHECKING:
    from backend.extract.template import Template

TemplateList = List["Template"]
"""模板列表类型别名"""

FieldDefinitions = Dict[str, str]
"""字段定义类型别名: {字段名: 描述}"""

DefaultFields = Dict[str, Any]
"""默认字段类型别名"""
