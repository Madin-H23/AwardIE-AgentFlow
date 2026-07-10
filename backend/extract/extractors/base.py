"""抽取器基类与上下文。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.extract.types import ExtractResult
from backend.extract.validator import ExtractorValidator


@dataclass
class ExtractContext:
    """抽取上下文。"""
    file_path: str
    ocr_text: Optional[str] = None
    use_ocr_cache: bool = True
    use_llm_cache: bool = True
    ocr_engine: Optional[Any] = None
    llm_engine: Optional[Any] = None
    use_default_prompt_only: bool = False
    force_type: bool = False  # 手动导入/创建模板：不校验奖状有效性，直接返回抽取结果


class Extractor(ABC):
    """抽取器抽象基类。"""

    def __init__(
        self,
        name: str,
        description: str,
        keywords: List[str],
        judgment_text: str,
        extensions: List[str],
        validator: Optional[ExtractorValidator] = None,
    ):
        self.name = name
        self.description = description
        self.keywords = keywords
        self.judgment_text = judgment_text
        self.extensions = [e.lower() if e.startswith(".") else f".{e}".lower() for e in extensions]
        self.validator = validator

    def matches_extension(self, ext: str) -> bool:
        return ext.lower() in self.extensions

    def matches_keywords(self, text: str) -> bool:
        if not text or not self.keywords:
            return False
        t = text.lower()
        return any(k.lower() in t for k in self.keywords)

    @abstractmethod
    def extract(self, ctx: ExtractContext) -> ExtractResult:
        """执行抽取。ctx.ocr_text 有值时表示图片分支（已 OCR），否则为非图片，按需读 file_path。"""
        pass
