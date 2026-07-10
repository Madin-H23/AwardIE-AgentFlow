"""
OCR模块类型定义

定义模块中使用的公共数据类型
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class FileType(Enum):
    """支持的文件类型"""
    IMAGE = "image"
    PDF = "pdf"


@dataclass
class OCRResult:
    """OCR识别结果"""

    text: str
    from_cache: bool
    confidence: Optional[float] = None
    processing_time: Optional[float] = None
    file_type: Optional[FileType] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        from dataclasses import asdict
        result = asdict(self)
        if self.file_type:
            result['file_type'] = self.file_type.value
        return result


@dataclass
class OCRAPIData:
    """OCR API原始响应数据"""

    task_id: str
    message: str
    status: str
    words_result: list

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OCRAPIData":
        """从字典创建"""
        return cls(
            task_id=data.get("task_id", ""),
            message=data.get("message", ""),
            status=data.get("status", ""),
            words_result=data.get("words_result", []),
        )

    def is_success(self) -> bool:
        """检查是否成功"""
        return self.status.lower() in ("success", "succeeded", "成功")


@dataclass
class CacheStats:
    """缓存统计信息"""

    count: int
    oldest: Optional[str]
    newest: Optional[str]

    @classmethod
    def from_db_row(cls, row: Any) -> "CacheStats":
        """从数据库行创建"""
        return cls(
            count=row[0] if row else 0,
            oldest=row[1] if row and len(row) > 1 else None,
            newest=row[2] if row and len(row) > 2 else None,
        )
