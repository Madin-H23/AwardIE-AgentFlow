"""
手动导入服务

直接调用指定类型的抽取器，绕过框架的类型选择逻辑。
"""
import logging
from typing import Optional

from backend.extract.extractors.base import ExtractContext
from backend.extract.types import ExtractResult

logger = logging.getLogger(__name__)


class ManualImportService:
    """手动导入服务

    提供根据指定类型解析文件的功能，绕过框架的自动类型识别。
    """

    def __init__(self, extract_framework):
        """
        初始化手动导入服务

        Args:
            extract_framework: 抽取框架实例，用于获取 OCR/LLM 引擎和已注册的抽取器
        """
        self.framework = extract_framework
        # 从框架获取 OCR 引擎和 LLM 引擎
        self.ocr_engine = extract_framework.ocr_engine
        self.llm_engine = extract_framework.llm_engine

    def parse_by_type(self, file_path: str, achievement_type: str, use_ocr_cache: bool = True, use_llm_cache: bool = True) -> ExtractResult:
        """
        根据指定类型解析文件

        Args:
            file_path: 文件路径
            achievement_type: 成果类型 (award/patent/software)
            use_ocr_cache: 是否使用OCR缓存，默认True
            use_llm_cache: 是否使用LLM缓存，默认True

        Returns:
            ExtractResult: 抽取结果

        Raises:
            ValueError: 不支持的成果类型
        """
        logger.info(f"手动导入解析: file_path={file_path}, type={achievement_type}, use_ocr_cache={use_ocr_cache}, use_llm_cache={use_llm_cache}")

        # 1. 先执行 OCR
        try:
            ocr_text, ocr_cached = self.ocr_engine.get_text(
                file_path, use_cache=use_ocr_cache, is_precise=False
            )
            logger.info(f"OCR识别完成，缓存命中: {ocr_cached}")
        except Exception as e:
            logger.error(f"OCR 失败: {e}", exc_info=True)
            return ExtractResult(
                status="ocr_error",
                error_message=f"OCR识别失败: {e}",
                metadata={"file_path": file_path}
            )

        if not ocr_text:
            logger.warning(f"OCR未能识别出文本: {file_path}")
            return ExtractResult(
                status="ocr_error",
                error_message="OCR未能识别出文本",
                metadata={"file_path": file_path}
            )

        # 2. 根据类型选择抽取器
        try:
            extractor = self._get_extractor_by_type(achievement_type)
        except ValueError as e:
            logger.error(f"获取抽取器失败: {e}")
            return ExtractResult(
                status="error",
                error_message=str(e),
                metadata={"file_path": file_path, "achievement_type": achievement_type}
            )

        # 3. 创建上下文并调用抽取器（绕过框架的类型选择）
        ctx = ExtractContext(
            file_path=file_path,
            ocr_text=ocr_text,
            ocr_engine=self.ocr_engine,
            llm_engine=self.llm_engine,
            use_ocr_cache=use_ocr_cache,
            use_llm_cache=use_llm_cache
        )
        # 设置force_type标志，告诉抽取器这是手动指定的类型
        ctx.force_type = achievement_type

        # 4. 直接调用抽取器的 extract 方法
        try:
            result = extractor.extract(ctx)
            logger.info(f"抽取器调用完成: status={result.status}, template_type={result.template_type}")
            return result
        except Exception as e:
            logger.error(f"抽取器执行失败: {e}", exc_info=True)
            return ExtractResult(
                status="error",
                error_message=f"抽取失败: {e}",
                metadata={"file_path": file_path, "achievement_type": achievement_type}
            )

    def _get_extractor_by_type(self, achievement_type: str):
        """
        根据类型获取对应的抽取器实例

        Args:
            achievement_type: 成果类型

        Returns:
            Extractor: 抽取器实例

        Raises:
            ValueError: 不支持的类型
        """
        # 从框架中获取已注册的抽取器
        for ex in self.framework._extractors:
            if achievement_type == "award" and ex.name == "award":
                return ex
            elif achievement_type == "patent" and ex.name == "patent":
                return ex
            elif achievement_type == "software" and ex.name == "software":
                return ex

        raise ValueError(f"不支持的类型: {achievement_type}")

    def get_supported_types(self) -> list:
        """
        获取支持的成果类型列表

        Returns:
            list: 支持的类型列表
        """
        types = set()
        for ex in self.framework._extractors:
            if ex.name == "award":
                types.add("award")
            elif ex.name == "patent":
                types.add("patent")
            elif ex.name == "software":
                types.add("software")
        return sorted(list(types))
