"""Other 默认抽取器：处理无法匹配任何抽取器的文件。"""
from typing import Optional

from backend.extract.types import ExtractResult, ExtractStatus, TemplateType
from backend.extract.extractors.base import ExtractContext, Extractor


class OtherExtractor(Extractor):
    """Other 默认抽取器，不需要注册，框架内部使用。"""

    def __init__(self, note_no_extension: str, note_no_match: str):
        """
        初始化 Other 抽取器。

        Args:
            note_no_extension: 扩展名不匹配时的提示信息
            note_no_match: 无抽取器能处理时的提示信息
        """
        super().__init__(
            name="other",
            description="其他",
            keywords=[],
            judgment_text="",
            extensions=[],  # 不匹配任何扩展名，由框架逻辑决定何时使用
            validator=None,
        )
        self.note_no_extension = note_no_extension
        self.note_no_match = note_no_match

    def extract(self, ctx: ExtractContext) -> ExtractResult:
        """
        执行抽取，返回 other 类型结果。

        Args:
            ctx: 抽取上下文
                - ctx.ocr_text=None: 扩展名不匹配，使用 note_no_extension
                - ctx.ocr_text 有值: 关键词不匹配，使用 note_no_match

        Returns:
            ExtractResult，template_type 为 other
        """
        # 判断使用哪个提示信息
        if ctx.ocr_text is None:
            note = self.note_no_extension
        else:
            note = self.note_no_match

        return ExtractResult(
            status=ExtractStatus.NO_TEMPLATE,
            data={"note": note},
            error_message=note,
            template_type=TemplateType.OTHER,
            extractor_name=self.name,
            ocr_text=ctx.ocr_text,
            ocr_cache_hit=False,
        )
