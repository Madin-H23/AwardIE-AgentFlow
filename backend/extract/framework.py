"""抽取框架：统一入口、抽取器注册与调度。"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.ocr import OCREngine
from backend.extract.llm import LLMEngine
from backend.extract.types import ExtractResult, ExtractStatus, TemplateType
from backend.extract.extractors.base import ExtractContext, Extractor
from backend.extract.extractors.other import OtherExtractor
from backend.extract.exceptions import user_facing_message

logger = logging.getLogger(__name__)


def _file_error_result(path: str, message: str) -> ExtractResult:
    return ExtractResult(
        status=ExtractStatus.FILE_ERROR,
        error_message=message,
        metadata={"file_path": path},
    )


class ExtractFramework:
    """抽取框架。"""

    def __init__(
        self,
        ocr_engine: OCREngine,
        llm_engine: LLMEngine,
        image_extensions: List[str],
        other_notes: Dict[str, str],
        llm_max_text_length: int = 4000,
        llm_selector_prompt_template: str = None,
    ):
        self.ocr_engine = ocr_engine
        self.llm_engine = llm_engine
        self._image_extensions = [e.lower() if e.startswith(".") else f".{e}".lower() for e in image_extensions]
        self._extractors: List[Extractor] = []
        # LLM选择抽取器的配置
        self._llm_max_text_length = llm_max_text_length
        self._llm_selector_prompt_template = llm_selector_prompt_template or (
            "你是一个高精度文本分类专家，负责将 OCR 提取的文本内容归类到以下类别之一，如果无法判断也可以返回最可能的两个。"
            "仅返回 JSON 数组，元素为每个类别的英文名称。例如 [\"award\"] 或 [\"award\",\"innovation\"]。\n\n"
            "类别说明：\n{extractors}\n\nOCR 文本：\n{ocr_text}"
        )
        # 创建默认 other 抽取器（不注册，框架内部使用）
        self._other_extractor = OtherExtractor(
            note_no_extension=other_notes["no_extension"],
            note_no_match=other_notes["no_match"],
        )

    @classmethod
    def from_config_loader(cls, config_loader) -> "ExtractFramework":
        config = config_loader.load_config()
        extract_cfg = config.get("extract")
        if not extract_cfg:
            raise ValueError("config 中缺少 extract 节点，请在 config/settings.json 中配置")
        exts = extract_cfg.get("image_extensions")
        if not exts:
            raise ValueError("extract.image_extensions 未配置，请在 config/settings.json 中配置")
        other_cfg = extract_cfg.get("other") or {}
        note_no_ext = other_cfg.get("note_no_extension", "不支持的文件扩展名")
        note_no_match = other_cfg.get("note_no_match", "没有抽取器能够处理此文件")
        other_notes = {"no_extension": note_no_ext, "no_match": note_no_match}

        # LLM选择抽取器配置
        llm_max_text_length = extract_cfg.get("llm_max_text_length", 4000)
        # 提示词模板使用代码中的默认值，不从配置文件读取
        llm_selector_prompt_template = None

        ocr_engine = OCREngine.from_config_loader(config_loader)
        llm_engine = LLMEngine.from_config_loader(config_loader)

        return cls(
            ocr_engine=ocr_engine,
            llm_engine=llm_engine,
            image_extensions=exts,
            other_notes=other_notes,
            llm_max_text_length=llm_max_text_length,
            llm_selector_prompt_template=llm_selector_prompt_template,
        )

    def register(self, extractor: Extractor) -> "ExtractFramework":
        self._extractors.append(extractor)
        logger.info("注册抽取器: %s", extractor.name)
        return self

    def get_extractor(self, name: str) -> Optional[Extractor]:
        """
        按名称获取已注册的抽取器。

        Args:
            name: 抽取器名称（如 "award", "patent", "software"）

        Returns:
            匹配的抽取器实例，未找到返回 None
        """
        for ex in self._extractors:
            if ex.name == name:
                return ex
        return None

    def extract(
        self,
        file_path: str,
        use_ocr_cache: bool = True,
        use_llm_cache: bool = True,
    ) -> ExtractResult:
        path = Path(file_path)
        # 检查文件是否存在。若不存在，返回文件错误的结果。
        if not path.exists():
            return _file_error_result(str(path), f"文件不存在: {file_path}")

        ext = path.suffix.lower()
        # 统一扩展名格式，确保以"."开头。
        if not ext.startswith("."):
            ext = f".{ext}"

        # 从已注册的抽取器中筛选能处理当前扩展名的抽取器
        candidates = [e for e in self._extractors if e.matches_extension(ext)]
        if not candidates:
            # 如果没有抽取器匹配该扩展名，则使用"other"抽取器
            ctx = self._create_context(str(path), None, use_ocr_cache, use_llm_cache)
            return self._other_extractor.extract(ctx)

        # 判断文件是否为图片（由 image_extensions 配置驱动）
        is_image = ext in self._image_extensions

        if is_image:
            # 如果是图片则调用图片抽取分支
            return self._extract_image(str(path), candidates, use_ocr_cache, use_llm_cache)
        # 否则处理为非图片类型（如 PDF 等）
        return self._extract_non_image(str(path), candidates, use_ocr_cache, use_llm_cache)

    def extract_from_file(
        self,
        file_path: str,
        use_ocr_cache: bool = True,
        use_llm_cache: bool = True,
    ) -> ExtractResult:
        """向后兼容方法：调用 extract()"""
        return self.extract(file_path, use_ocr_cache, use_llm_cache)

    def _create_context(
        self,
        file_path: str,
        ocr_text: Optional[str],
        use_ocr_cache: bool,
        use_llm_cache: bool,
    ) -> ExtractContext:
        """创建抽取上下文（辅助方法，减少重复代码）"""
        return ExtractContext(
            file_path=file_path,
            ocr_text=ocr_text,
            use_ocr_cache=use_ocr_cache,
            use_llm_cache=use_llm_cache,
            ocr_engine=self.ocr_engine,
            llm_engine=self.llm_engine,
        )

    def _extract_non_image(
        self,
        file_path: str,
        candidates: List[Extractor],
        use_ocr_cache: bool,
        use_llm_cache: bool,
    ) -> ExtractResult:
        ctx = self._create_context(file_path, None, use_ocr_cache, use_llm_cache)
        for ex in candidates:
            res = ex.extract(ctx)
            res.extractor_name = ex.name
            if res.template_type and res.template_type != TemplateType.OTHER:
                return self._validate_and_return(ex, res)
        # 所有抽取器都返回 other，使用 no_match 提示（不是扩展名不匹配）
        return self._no_match_result(file_path, None, False, use_ocr_cache, use_llm_cache)

    def _no_match_result(
        self,
        file_path: str,
        ocr_text: Optional[str],
        ocr_cached: bool,
        use_ocr_cache: bool,
        use_llm_cache: bool,
    ) -> ExtractResult:
        """返回"没有抽取器能处理"的other结果"""
        return ExtractResult(
            status=ExtractStatus.NO_TEMPLATE,
            data={"note": self._other_extractor.note_no_match},
            error_message=self._other_extractor.note_no_match,
            template_type=TemplateType.OTHER,
            extractor_name="other",
            ocr_text=ocr_text,
            ocr_cache_hit=ocr_cached,
        )

    def _extract_image(
        self,
        file_path: str,
        candidates: List[Extractor],
        use_ocr_cache: bool,
        use_llm_cache: bool,
    ) -> ExtractResult:
        """图片抽取分支"""
        # 步骤1：先用OCR引擎抽取图片中的文本内容（读取失败时不抛异常，由引擎返回空串并写入 last_ocr_failure_reason）
        try:
            text, ocr_cached = self._ocr_image(file_path, use_ocr_cache)
        except Exception as e:
            logger.exception("OCR 失败: %s", e)
            msg = user_facing_message(e)
            return ExtractResult(
                status=ExtractStatus.OCR_ERROR,
                error_message=msg,
                data={"note": msg},
                template_type=TemplateType.OTHER,
                extractor_name="other",
                metadata={"file_path": file_path},
            )

        if text is None:  # 理论上不应出现，防御性保留
            msg = "OCR识别失败"
            return ExtractResult(
                status=ExtractStatus.OCR_ERROR,
                error_message=msg,
                data={"note": msg},
                template_type=TemplateType.OTHER,
                extractor_name="other",
                metadata={"file_path": file_path},
            )

        # 读取失败时引擎返回空串并设置 last_ocr_failure_reason，转为 OCR_ERROR 结果继续流程（不抛异常）
        failure_reason = getattr(self.ocr_engine, "last_ocr_failure_reason", None)
        if (not (text or "").strip()) and failure_reason:
            return ExtractResult(
                status=ExtractStatus.OCR_ERROR,
                error_message=failure_reason,
                data={"note": failure_reason},
                template_type=TemplateType.OTHER,
                extractor_name="other",
                metadata={"file_path": file_path},
            )

        # 步骤2：根据文本内容，匹配候选抽取器（通过关键词匹配方法）
        # 调试日志：输出OCR识别的文本

        matched = [e for e in candidates if e.matches_keywords(text)]

        # 调试日志：输出匹配结果

        # 步骤2.1：如果没有合适抽取器，走兜底other抽取器
        if not matched:
            return self._other_result(file_path, text, ocr_cached, use_ocr_cache, use_llm_cache)

        # 步骤2.2：如果仅命中一个抽取器，直接用该抽取器抽取
        if len(matched) == 1:
            return self._extract_with_single(matched[0], file_path, text, ocr_cached, use_ocr_cache, use_llm_cache)

        # 步骤2.3：如果有多个抽取器都命中，调用LLM辅助选择
        try:
            chosen = self._llm_select_extractors(text, matched, use_llm_cache)
        except Exception as e:
            logger.exception("LLM 选择抽取器失败: %s", e)
            msg = user_facing_message(e)
            return ExtractResult(
                status=ExtractStatus.LLM_ERROR,
                error_message=msg,
                data={"note": msg},
                template_type=TemplateType.OTHER,
                extractor_name="other",
                ocr_text=text,
                ocr_cache_hit=ocr_cached,
                metadata={"file_path": file_path},
            )

        if not chosen:
            # 若LLM未给出明确选择，则还是走other兜底抽取器
            return self._other_result(file_path, text, ocr_cached, use_ocr_cache, use_llm_cache)

        # 步骤2.4：若LLM只选了一个抽取器，直接用单抽取器逻辑
        if len(chosen) == 1:
            ex = next((e for e in matched if e.name == chosen[0]), None)
            if ex:
                return self._extract_with_single(ex, file_path, text, ocr_cached, use_ocr_cache, use_llm_cache)
            # 理论上 chosen 来自 matched 的名称过滤，不应出现；兜底走 multiple
        # 步骤2.5：多个抽取器时，逐个尝试LLM选择的顺序，取第一个抽取成功且类型不是OTHER的
        return self._extract_with_multiple(chosen, matched, file_path, text, ocr_cached, use_ocr_cache, use_llm_cache)

    def _ocr_image(self, file_path: str, use_cache: bool) -> tuple[Optional[str], bool]:
        """OCR识别图片。异常不在此处捕获，由 _extract_image 统一转为带 note 的 ExtractResult。"""
        text, ocr_cached = self.ocr_engine.get_text(file_path, use_cache=use_cache, is_precise=False)
        return text, ocr_cached

    def _other_result(
        self,
        file_path: str,
        ocr_text: str,
        ocr_cached: bool,
        use_ocr_cache: bool,
        use_llm_cache: bool,
    ) -> ExtractResult:
        """返回other抽取器结果"""
        ctx = self._create_context(file_path, ocr_text, use_ocr_cache, use_llm_cache)
        result = self._other_extractor.extract(ctx)
        result.ocr_cache_hit = ocr_cached
        return result

    def _extract_with_single(
        self,
        extractor: Extractor,
        file_path: str,
        ocr_text: str,
        ocr_cached: bool,
        use_ocr_cache: bool,
        use_llm_cache: bool,
    ) -> ExtractResult:
        """使用单个抽取器进行抽取"""
        ctx = self._create_context(file_path, ocr_text, use_ocr_cache, use_llm_cache)
        res = extractor.extract(ctx)
        res.extractor_name = extractor.name
        # 如果抽取器返回了OCR文本（例如进行了高精度重识别），则保留
        # 否则使用初始的OCR文本
        if res.ocr_text is None:
            res.ocr_text = ocr_text
            res.ocr_cache_hit = ocr_cached
        return self._validate_and_return(extractor, res)

    def _extract_with_multiple(
        self,
        chosen: List[str],
        matched: List[Extractor],
        file_path: str,
        ocr_text: str,
        ocr_cached: bool,
        use_ocr_cache: bool,
        use_llm_cache: bool,
    ) -> ExtractResult:
        """使用多个抽取器进行抽取（按LLM返回顺序）"""
        ctx = self._create_context(file_path, ocr_text, use_ocr_cache, use_llm_cache)
        for name in chosen:
            ex = next((e for e in matched if e.name == name), None)
            if not ex:
                continue
            res = ex.extract(ctx)
            res.extractor_name = ex.name
            
            # 如果抽取器返回了OCR文本（例如进行了高精度重识别），则保留
            # 否则使用初始的OCR文本
            if res.ocr_text is None:
                res.ocr_text = ocr_text
                res.ocr_cache_hit = ocr_cached
                
            # 若抽取类型不是OTHER，验证结果并返回
            if res.template_type and res.template_type != TemplateType.OTHER:
                return self._validate_and_return(ex, res)

        # 所有抽取器都未能有效抽取，最终兜底返回other抽取器结果
        return self._other_result(file_path, ocr_text, ocr_cached, use_ocr_cache, use_llm_cache)

    def _llm_select_extractors(self, ocr_text: str, candidates: List[Extractor], use_llm_cache: bool) -> List[str]:
        """使用LLM选择抽取器（分类任务）"""
        parts = []
        for e in candidates:
            # 使用分类任务的格式：类别名称 + 类别特征和包含的信息
            desc = e.judgment_text  
            parts.append(f"- {e.name} {e.description}: {desc}")

        # 截断OCR文本（使用配置的长度）
        text = ocr_text if len(ocr_text) <= self._llm_max_text_length else ocr_text[:self._llm_max_text_length]

        # 使用配置的提示词模板
        prompt = self._llm_selector_prompt_template.format(
            extractors="\n".join(parts),
            ocr_text=text
        )

        messages = [{"role": "user", "content": prompt}]
        raw, llm_cached = self.llm_engine.chat(messages, temperature=0.1, use_cache=use_llm_cache)
        names = _parse_extractor_list(raw)
        return [n for n in names if n in {e.name for e in candidates}]

    def _validate_and_return(self, extractor: Extractor, result: ExtractResult) -> ExtractResult:
        """
        处理验证结果。

        验证逻辑由各抽取器在 extract() 内部实现，ExtractResult 已包含 validation_result。
        此方法仅负责返回结果。
        """
        return result


def _parse_extractor_list(raw: str) -> List[str]:
    raw = raw.strip()
    for pref in ("```json", "```"):
        if raw.lower().startswith(pref):
            raw = raw[len(pref) :].strip()
        if raw.lower().endswith("```"):
            raw = raw[:-3].strip()
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            return [str(x) for x in arr]
    except json.JSONDecodeError:
        pass
    return []
