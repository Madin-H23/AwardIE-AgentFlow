"""
抽取框架单元测试

覆盖扩展名路由、other、非图片/图片分支、关键词过滤、LLM 抽取器选择及验证。
基于 docs/extract/抽取框架测试用例.md。

每个测试用例明确说明：
- 注册的抽取器数量、扩展名、关键词、返回类型
- 预期行为：调用顺序、调用次数、LLM调用条件
"""
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass

# 项目根
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(project_root))

from backend.extract.types import ExtractResult, ExtractStatus, TemplateType
from backend.extract.extractors.base import ExtractContext, Extractor
from backend.extract.validator import ExtractorValidator
from backend.extract.framework import ExtractFramework, _parse_extractor_list


@dataclass
class CaseResult:
    name: str
    passed: bool
    message: str
    duration: float = 0.0


class MockOCR:
    """Mock OCR引擎"""
    def __init__(self, text: str = "mock ocr", cached: bool = False):
        self.text = text
        self.cached = cached
        self.call_count = 0

    def get_text(self, file_path: str, use_cache: bool = True, is_precise: bool = False) -> Tuple[str, bool]:
        self.call_count += 1
        return self.text, self.cached


class MockLLM:
    """Mock LLM引擎，记录调用信息"""
    def __init__(self, response: str = '["award"]', cached: bool = False):
        self.response = response
        self.cached = cached
        self.last_messages: List[dict] = []
        self.call_count = 0

    def chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> Tuple[str, bool]:
        self.last_messages = messages
        self.call_count += 1
        return self.response, self.cached


class MockExtractor(Extractor):
    """Mock抽取器，记录调用信息"""
    def __init__(
        self,
        name: str,
        extensions: List[str],
        keywords: Optional[List[str]] = None,
        result_template_type: str = TemplateType.OTHER,
        result_data: Optional[dict] = None,
        validator: Optional[ExtractorValidator] = None,
    ):
        super().__init__(
            name=name,
            description=f"desc-{name}",
            keywords=keywords or [],
            judgment_text=f"judge-{name}",
            extensions=extensions,
            validator=validator,
        )
        self._result_type = result_template_type
        self._result_data = result_data or {}
        self._extract_called = 0

    def extract(self, ctx: ExtractContext) -> ExtractResult:
        self._extract_called += 1
        return ExtractResult(
            status=ExtractStatus.SUCCESS if self._result_type != TemplateType.OTHER else ExtractStatus.NO_TEMPLATE,
            data=self._result_data,
            template_type=self._result_type,
        )


def _framework(
    image_extensions: Optional[List[str]] = None,
    other_notes: Optional[dict] = None,
    ocr_text: str = "mock",
    ocr_cached: bool = False,
    llm_response: str = '["award"]',
    llm_cached: bool = False,
) -> ExtractFramework:
    """创建测试用的框架实例"""
    return ExtractFramework(
        ocr_engine=MockOCR(text=ocr_text, cached=ocr_cached),
        llm_engine=MockLLM(response=llm_response, cached=llm_cached),
        image_extensions=image_extensions or [".jpg", ".png", ".pdf"],
        other_notes=other_notes or {"no_extension": "不支持的文件扩展名", "no_match": "没有抽取器能够处理此文件"},
    )


# ==================== 用例2：扩展名路由与other ====================

def test_extension_no_match() -> CaseResult:
    """
    用例2.1：扩展名未命中任何抽取器
    注册抽取器：1个（A，扩展名`.xlsx`）
    文件扩展名：`.xyz`
    预期：走other，note_no_extension
    """
    t0 = datetime.now().timestamp()
    fw = _framework()
    # 注册1个抽取器A（扩展名.xlsx）
    ex_a = MockExtractor("a", [".xlsx"], result_template_type=TemplateType.AWARD)
    fw.register(ex_a)
    
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.OTHER
            and r.extractor_name == "other"
            and r.data and r.data.get("note") == "不支持的文件扩展名"
            and ex_a._extract_called == 0  # A未被调用
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("2.1 扩展名未命中→other", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_extension_match_no_extractors() -> CaseResult:
    """
    用例2.2：扩展名命中但无抽取器注册
    注册抽取器：0个
    文件扩展名：`.jpg`
    预期：走other，note_no_extension
    """
    t0 = datetime.now().timestamp()
    fw = _framework()  # 无注册抽取器
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.OTHER
            and r.data and r.data.get("note") == "不支持的文件扩展名"
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("2.2 扩展名命中但无抽取器→other", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_nonexistent_file() -> CaseResult:
    """
    用例2.3：文件不存在
    注册抽取器：0个
    预期：FILE_ERROR
    """
    t0 = datetime.now().timestamp()
    fw = _framework()
    r = fw.extract("/nonexistent/file.xyz", use_ocr_cache=True, use_llm_cache=True)
    ok = r.status == ExtractStatus.FILE_ERROR and "文件不存在" in (r.error_message or "")
    elapsed = datetime.now().timestamp() - t0
    return CaseResult("2.3 文件不存在→FILE_ERROR", ok, r.error_message or "" if not ok else "ok", elapsed)


# ==================== 用例3：非图片分支 ====================

def test_non_image_single_non_other() -> CaseResult:
    """
    用例3.1：单抽取器返回非other
    注册抽取器：1个（A，扩展名`.xlsx`，返回`award`）
    文件扩展名：`.xlsx`
    预期：返回A的结果，A被调用1次
    """
    t0 = datetime.now().timestamp()
    fw = _framework(image_extensions=[".jpg", ".png"])
    # 注册1个抽取器A（.xlsx，返回award）
    ex_a = MockExtractor("a", [".xlsx"], result_template_type=TemplateType.AWARD, result_data={"a": 1})
    fw.register(ex_a)
    
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.AWARD
            and r.extractor_name == "a"
            and r.data == {"a": 1}
            and ex_a._extract_called == 1
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("3.1 非图片单抽取器返回非other", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_non_image_single_other() -> CaseResult:
    """
    用例3.2：单抽取器返回other
    注册抽取器：1个（A，扩展名`.xlsx`，返回`other`）
    文件扩展名：`.xlsx`
    预期：返回other（note_no_match），A被调用1次
    """
    t0 = datetime.now().timestamp()
    fw = _framework(image_extensions=[".jpg"])
    # 注册1个抽取器A（.xlsx，返回other）
    ex_a = MockExtractor("a", [".xlsx"], result_template_type=TemplateType.OTHER)
    fw.register(ex_a)
    
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.OTHER
            and r.data and r.data.get("note") == "没有抽取器能够处理此文件"
            and ex_a._extract_called == 1
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("3.2 非图片单抽取器返回other", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_non_image_multi_first_non_other() -> CaseResult:
    """
    用例3.3：多抽取器首个非other即返回
    注册抽取器：2个（A、B，都扩展名`.csv`，A返回`other`，B返回`innovation`）
    文件扩展名：`.csv`
    预期：返回B的结果，A、B各被调用1次
    """
    t0 = datetime.now().timestamp()
    fw = _framework(image_extensions=[".jpg"])
    # 注册2个抽取器：A（.csv，返回other）、B（.csv，返回innovation）
    ex_a = MockExtractor("a", [".csv"], result_template_type=TemplateType.OTHER)
    ex_b = MockExtractor("b", [".csv"], result_template_type=TemplateType.INNOVATION, result_data={"x": 1})
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.INNOVATION
            and r.extractor_name == "b"
            and ex_a._extract_called == 1
            and ex_b._extract_called == 1
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("3.3 非图片多抽取器首个非other即返回", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_non_image_multi_all_other() -> CaseResult:
    """
    用例3.4：多抽取器全部返回other
    注册抽取器：2个（A、B，都扩展名`.csv`，都返回`other`）
    文件扩展名：`.csv`
    预期：返回other（note_no_match），A、B各被调用1次
    """
    t0 = datetime.now().timestamp()
    fw = _framework(image_extensions=[".jpg"])
    # 注册2个抽取器：A、B（都.csv，都返回other）
    ex_a = MockExtractor("a", [".csv"], result_template_type=TemplateType.OTHER)
    ex_b = MockExtractor("b", [".csv"], result_template_type=TemplateType.OTHER)
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.OTHER
            and r.data and r.data.get("note") == "没有抽取器能够处理此文件"
            and ex_a._extract_called == 1
            and ex_b._extract_called == 1
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("3.4 非图片多抽取器全部返回other", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


# ==================== 用例4：图片分支（OCR + 关键词） ====================

def test_image_keyword_single_match() -> CaseResult:
    """
    用例4.1：关键词仅命中一个抽取器
    注册抽取器：1个（A，扩展名`.jpg`，关键词`["蓝桥杯"]`）
    OCR文本："蓝桥杯 一等奖 张三"
    预期：不调用LLM，直接调用A，返回A的结果
    """
    t0 = datetime.now().timestamp()
    fw = _framework(ocr_text="蓝桥杯 一等奖 张三")
    # 注册1个抽取器A（.jpg，关键词["蓝桥杯"]）
    ex_a = MockExtractor("award", [".jpg"], keywords=["蓝桥杯", "一等奖"], result_template_type=TemplateType.AWARD, result_data={"name": "张三"})
    fw.register(ex_a)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        # 验证：不调用LLM（通过检查llm.call_count）
        llm_called = fw.llm_engine.call_count > 0
        ok = (
            r.template_type == TemplateType.AWARD
            and r.extractor_name == "award"
            and r.ocr_text == "蓝桥杯 一等奖 张三"
            and ex_a._extract_called == 1
            and not llm_called  # 不调用LLM
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("4.1 图片关键词仅命中一个抽取器（不调LLM）", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_image_keyword_zero_match() -> CaseResult:
    """
    用例4.2：关键词0个命中
    注册抽取器：1个（A，扩展名`.jpg`，关键词`["蓝桥杯"]`）
    OCR文本："无关内容"
    预期：不调用LLM，不调用A，返回other
    """
    t0 = datetime.now().timestamp()
    fw = _framework(ocr_text="无关内容")
    # 注册1个抽取器A（.jpg，关键词["蓝桥杯"]）
    ex_a = MockExtractor("award", [".jpg"], keywords=["蓝桥杯"], result_template_type=TemplateType.AWARD)
    fw.register(ex_a)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        llm_called = fw.llm_engine.call_count > 0
        ok = (
            r.template_type == TemplateType.OTHER
            and r.data and r.data.get("note") == "没有抽取器能够处理此文件"
            and ex_a._extract_called == 0  # A未被调用
            and not llm_called  # 不调用LLM
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("4.2 图片关键词0命中→other（不调LLM）", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_image_multi_keyword_llm_single() -> CaseResult:
    """
    用例4.3：关键词多命中且LLM返回单一抽取器
    注册抽取器：2个（A、B，都扩展名`.jpg`，都关键词`["奖"]`）
    OCR文本："奖 蓝桥杯 一等奖"
    LLM返回：`["award"]`
    预期：调用LLM 1次，只调用A，返回A的结果
    """
    t0 = datetime.now().timestamp()
    llm = MockLLM(response='["award"]', cached=False)
    fw = _framework(ocr_text="奖 蓝桥杯 一等奖", llm_response='["award"]')
    fw.llm_engine = llm
    # 注册2个抽取器：A、B（都.jpg，都关键词["奖"]）
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.AWARD, result_data={"a": 1})
    ex_b = MockExtractor("innovation", [".jpg"], keywords=["奖"], result_template_type=TemplateType.INNOVATION)
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        # 验证LLM调用
        llm_prompt = llm.last_messages[0].get("content", "") if llm.last_messages else ""
        ok = (
            r.template_type == TemplateType.AWARD
            and r.extractor_name == "award"
            and llm.call_count == 1  # LLM被调用1次
            and "award" in llm_prompt  # 提示词包含A的描述
            and "innovation" in llm_prompt  # 提示词包含B的描述
            and ex_a._extract_called == 1  # A被调用
            and ex_b._extract_called == 0  # B未被调用（LLM只返回了award）
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("4.3 图片多命中LLM返回单一抽取器", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_image_multi_keyword_llm_multi_first_success() -> CaseResult:
    """
    用例4.4：关键词多命中且LLM返回多个抽取器（首个成功）
    注册抽取器：2个（A、B，都扩展名`.jpg`，都关键词`["奖"]`，A返回`other`，B返回`innovation`）
    OCR文本："奖 大创 项目"
    LLM返回：`["award","innovation"]`
    预期：调用LLM 1次，按顺序调用A、B，返回B的结果
    """
    t0 = datetime.now().timestamp()
    llm = MockLLM(response='["award","innovation"]', cached=False)
    fw = _framework(ocr_text="奖 大创 项目", llm_response='["award","innovation"]')
    fw.llm_engine = llm
    # 注册2个抽取器：A（返回other）、B（返回innovation）
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.OTHER)
    ex_b = MockExtractor("innovation", [".jpg"], keywords=["奖"], result_template_type=TemplateType.INNOVATION, result_data={"b": 1})
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.INNOVATION
            and r.extractor_name == "innovation"
            and llm.call_count == 1  # LLM被调用1次
            and ex_a._extract_called == 1  # A被调用（LLM返回的第一个）
            and ex_b._extract_called == 1  # B被调用（LLM返回的第二个，且返回非other）
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("4.4 图片多命中LLM返回多个抽取器（首个成功）", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_image_multi_keyword_llm_multi_all_other() -> CaseResult:
    """
    用例4.5：关键词多命中且LLM返回多个抽取器（全部other）
    注册抽取器：2个（A、B，都扩展名`.jpg`，都关键词`["奖"]`，都返回`other`）
    OCR文本："奖 内容"
    LLM返回：`["award","innovation"]`
    预期：调用LLM 1次，按顺序调用A、B，都返回other，最终返回other
    """
    t0 = datetime.now().timestamp()
    llm = MockLLM(response='["award","innovation"]', cached=False)
    fw = _framework(ocr_text="奖 内容", llm_response='["award","innovation"]')
    fw.llm_engine = llm
    # 注册2个抽取器：A、B（都返回other）
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.OTHER)
    ex_b = MockExtractor("innovation", [".jpg"], keywords=["奖"], result_template_type=TemplateType.OTHER)
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.OTHER
            and r.data and r.data.get("note") == "没有抽取器能够处理此文件"
            and llm.call_count == 1  # LLM被调用1次
            and ex_a._extract_called == 1  # A被调用
            and ex_b._extract_called == 1  # B被调用
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("4.5 图片多命中LLM返回多个抽取器（全部other）", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_image_multi_keyword_llm_empty() -> CaseResult:
    """
    用例4.6：关键词多命中但LLM返回空列表
    注册抽取器：2个（A、B，都扩展名`.jpg`，都关键词`["奖"]`）
    OCR文本："奖 内容"
    LLM返回：`[]`或解析失败
    预期：调用LLM 1次，返回other，A、B未被调用
    """
    t0 = datetime.now().timestamp()
    llm = MockLLM(response='[]', cached=False)
    fw = _framework(ocr_text="奖 内容", llm_response='[]')
    fw.llm_engine = llm
    # 注册2个抽取器：A、B
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.AWARD)
    ex_b = MockExtractor("innovation", [".jpg"], keywords=["奖"], result_template_type=TemplateType.INNOVATION)
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.OTHER
            and r.data and r.data.get("note") == "没有抽取器能够处理此文件"
            and llm.call_count == 1  # LLM被调用1次
            and ex_a._extract_called == 0  # A未被调用
            and ex_b._extract_called == 0  # B未被调用
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("4.6 图片多命中LLM返回空列表", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


# ==================== 用例5：LLM调用验证 ====================

def test_llm_prompt_contains_all_extractors() -> CaseResult:
    """
    用例5.1：LLM提示词包含所有匹配抽取器描述
    注册抽取器：3个（A、B、C，都扩展名`.jpg`，都关键词`["奖"]`）
    OCR文本："奖 内容"
    LLM返回：`["award"]`
    预期：LLM提示词包含A、B、C的judgment_text或description
    """
    t0 = datetime.now().timestamp()
    llm = MockLLM(response='["award"]', cached=False)
    fw = _framework(ocr_text="奖 内容", llm_response='["award"]')
    fw.llm_engine = llm
    # 注册3个抽取器：A、B、C（都.jpg，都关键词["奖"]）
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.AWARD)
    ex_b = MockExtractor("innovation", [".jpg"], keywords=["奖"], result_template_type=TemplateType.INNOVATION)
    ex_c = MockExtractor("patent", [".jpg"], keywords=["奖"], result_template_type=TemplateType.PATENT)
    fw.register(ex_a).register(ex_b).register(ex_c)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        llm_prompt = llm.last_messages[0].get("content", "") if llm.last_messages else ""
        ok = (
            llm.call_count == 1
            and "judge-award" in llm_prompt  # 包含A的judgment_text
            and "judge-innovation" in llm_prompt  # 包含B的judgment_text
            and "judge-patent" in llm_prompt  # 包含C的judgment_text
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("5.1 LLM提示词包含所有匹配抽取器描述", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_llm_return_nonexistent_extractor() -> CaseResult:
    """
    用例5.2：LLM返回的抽取器名不在候选列表中
    注册抽取器：2个（A、B，都扩展名`.jpg`，都关键词`["奖"]`）
    OCR文本："奖 内容"
    LLM返回：`["nonexistent"]`
    预期：LLM被调用，但A、B未被调用（因为LLM返回的抽取器名不在候选列表中）
    """
    t0 = datetime.now().timestamp()
    llm = MockLLM(response='["nonexistent"]', cached=False)
    fw = _framework(ocr_text="奖 内容", llm_response='["nonexistent"]')
    fw.llm_engine = llm
    # 注册2个抽取器：A、B
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.AWARD)
    ex_b = MockExtractor("innovation", [".jpg"], keywords=["奖"], result_template_type=TemplateType.INNOVATION)
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.OTHER
            and llm.call_count == 1  # LLM被调用
            and ex_a._extract_called == 0  # A未被调用
            and ex_b._extract_called == 0  # B未被调用
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("5.2 LLM返回的抽取器名不在候选列表中", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_llm_parse_with_code_block() -> CaseResult:
    """
    用例5.3：LLM解析JSON格式（带代码块）
    注册抽取器：2个（A、B）
    LLM返回：```json\n["award"]\n```
    预期：框架正确解析JSON，提取出["award"]
    """
    t0 = datetime.now().timestamp()
    llm = MockLLM(response='```json\n["award"]\n```', cached=False)
    fw = _framework(ocr_text="奖 内容", llm_response='```json\n["award"]\n```')
    fw.llm_engine = llm
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.AWARD)
    ex_b = MockExtractor("innovation", [".jpg"], keywords=["奖"], result_template_type=TemplateType.INNOVATION)
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.AWARD
            and ex_a._extract_called == 1  # 解析成功，调用了award
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("5.3 LLM解析JSON格式（带代码块）", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_llm_parse_failed() -> CaseResult:
    """
    用例5.4：LLM解析失败（非JSON）
    注册抽取器：2个（A、B）
    LLM返回："这不是JSON"
    预期：框架解析失败，返回空列表，走other
    """
    t0 = datetime.now().timestamp()
    llm = MockLLM(response="这不是JSON", cached=False)
    fw = _framework(ocr_text="奖 内容", llm_response="这不是JSON")
    fw.llm_engine = llm
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.AWARD)
    ex_b = MockExtractor("innovation", [".jpg"], keywords=["奖"], result_template_type=TemplateType.INNOVATION)
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.template_type == TemplateType.OTHER
            and llm.call_count == 1  # LLM被调用
            and ex_a._extract_called == 0  # 解析失败，A未被调用
            and ex_b._extract_called == 0  # 解析失败，B未被调用
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("5.4 LLM解析失败（非JSON）", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


# ==================== 用例6：验证器 ====================

def test_validator_mapping() -> CaseResult:
    """
    用例6.1：验证器值映射
    注册抽取器：1个（A，带验证器，值映射{"award_level": {"Gold": "金奖"}}）
    预期：验证器应用映射，result.data.award_level="金奖"
    """
    t0 = datetime.now().timestamp()
    val = ExtractorValidator(value_mappings={"award_level": {"Gold": "金奖"}})
    res = val.validate({"award_level": "Gold", "x": 1})
    ok = res.is_valid and res.mapped_data is not None and res.mapped_data.get("award_level") == "金奖"
    elapsed = datetime.now().timestamp() - t0
    return CaseResult("6.1 验证器值映射", ok, "ok" if ok else str(res), elapsed)


def test_validator_in_result() -> CaseResult:
    """
    用例6.2：验证器接入抽取结果
    注册抽取器：1个（A，带验证器，值映射{"level": {"A": "一级"}}）
    预期：result.validation_result不为None，result.data.level="一级"（映射后）
    """
    t0 = datetime.now().timestamp()
    val = ExtractorValidator(value_mappings={"level": {"A": "一级"}})
    ex = MockExtractor("v", [".txt"], result_template_type=TemplateType.AWARD, result_data={"level": "A"}, validator=val)
    fw = _framework(image_extensions=[])
    fw.register(ex)
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            r.validation_result is not None
            and r.validation_result.is_valid
            and r.data is not None
            and r.data.get("level") == "一级"
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("6.2 验证器接入抽取结果", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


# ==================== 用例7：缓存 ====================

def test_ocr_cache_hit() -> CaseResult:
    """
    用例7.1：OCR缓存命中
    注册抽取器：1个（A，.jpg，关键词["奖"]）
    OCR缓存：cached=True
    预期：result.ocr_cache_hit=True
    """
    t0 = datetime.now().timestamp()
    fw = _framework(ocr_text="奖 内容", ocr_cached=True)
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.AWARD)
    fw.register(ex_a)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = r.ocr_cache_hit is True
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("7.1 OCR缓存命中", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


def test_llm_cache_hit() -> CaseResult:
    """
    用例7.2：LLM缓存命中（多抽取器场景）
    注册抽取器：2个（A、B，都.jpg，都关键词["奖"]）
    LLM缓存：cached=True
    预期：LLM被调用，llm.cached=True
    """
    t0 = datetime.now().timestamp()
    llm = MockLLM(response='["award"]', cached=True)
    fw = _framework(ocr_text="奖 内容", llm_response='["award"]')
    fw.llm_engine = llm
    ex_a = MockExtractor("award", [".jpg"], keywords=["奖"], result_template_type=TemplateType.AWARD)
    ex_b = MockExtractor("innovation", [".jpg"], keywords=["奖"], result_template_type=TemplateType.INNOVATION)
    fw.register(ex_a).register(ex_b)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        r = fw.extract(path, use_ocr_cache=True, use_llm_cache=True)
        ok = (
            llm.call_count == 1
            and llm.cached is True  # LLM缓存命中
        )
        elapsed = datetime.now().timestamp() - t0
        return CaseResult("7.2 LLM缓存命中（多抽取器场景）", ok, str(r) if not ok else "ok", elapsed)
    finally:
        os.unlink(path)


# ==================== 用例8：配置加载 ====================

def test_from_config_loader_missing_extract() -> CaseResult:
    """
    用例1.2：from_config_loader 缺失 extract 配置
    预期：抛出ValueError
    """
    t0 = datetime.now().timestamp()
    class Loader:
        def load_config(self):
            return {"ocr": {}, "llm": {}}
    try:
        ExtractFramework.from_config_loader(Loader())
        ok = False
        msg = "应抛出 ValueError"
    except ValueError as e:
        ok = "extract" in str(e).lower() or "image_extensions" in str(e).lower()
        msg = str(e)
    elapsed = datetime.now().timestamp() - t0
    return CaseResult("1.2 from_config_loader 缺失 extract", ok, msg, elapsed)


# ==================== 辅助函数 ====================

def test_llm_parse_extractor_list() -> CaseResult:
    """测试LLM返回解析函数"""
    t0 = datetime.now().timestamp()
    ok = _parse_extractor_list('["a","b"]') == ["a", "b"]
    ok = ok and _parse_extractor_list('```json\n["x"]\n```') == ["x"]
    ok = ok and _parse_extractor_list("not json") == []
    elapsed = datetime.now().timestamp() - t0
    return CaseResult("LLM解析抽取器名列表（辅助函数）", ok, "ok" if ok else "parse fail", elapsed)


# ==================== 测试运行 ====================

def run_all() -> List[CaseResult]:
    """运行所有测试用例"""
    cases = [
        # 用例2：扩展名路由与other
        test_extension_no_match,
        test_extension_match_no_extractors,
        test_nonexistent_file,
        # 用例3：非图片分支
        test_non_image_single_non_other,
        test_non_image_single_other,
        test_non_image_multi_first_non_other,
        test_non_image_multi_all_other,
        # 用例4：图片分支
        test_image_keyword_single_match,
        test_image_keyword_zero_match,
        test_image_multi_keyword_llm_single,
        test_image_multi_keyword_llm_multi_first_success,
        test_image_multi_keyword_llm_multi_all_other,
        test_image_multi_keyword_llm_empty,
        # 用例5：LLM调用验证
        test_llm_prompt_contains_all_extractors,
        test_llm_return_nonexistent_extractor,
        test_llm_parse_with_code_block,
        test_llm_parse_failed,
        # 用例6：验证器
        test_validator_mapping,
        test_validator_in_result,
        # 用例7：缓存
        test_ocr_cache_hit,
        test_llm_cache_hit,
        # 用例8：配置加载
        test_from_config_loader_missing_extract,
        # 辅助函数
        test_llm_parse_extractor_list,
    ]
    out: List[CaseResult] = []
    for fn in cases:
        try:
            out.append(fn())
        except Exception as e:
            out.append(CaseResult(fn.__name__, False, f"异常: {e}", 0.0))
    return out


def write_report(results: List[CaseResult], report_dir: Path) -> None:
    """生成测试报告"""
    report_dir.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    lines = [
        "# 抽取框架单元测试报告",
        "",
        f"运行时间: {datetime.now().isoformat()}",
        f"通过: {passed} / {total}",
        "",
        "| 用例 | 结果 | 说明 | 耗时(s) |",
        "|------|------|------|--------|",
    ]
    for r in results:
        status = "通过" if r.passed else "失败"
        lines.append(f"| {r.name} | {status} | {r.message[:80]} | {r.duration:.2f} |")
    path = report_dir / "报告.md"
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    report_base = project_root / "tests" / "reports" / "extract" / "抽取框架单元测试"
    results = run_all()
    write_report(results, report_base)
    failed = [r for r in results if not r.passed]
    for r in results:
        print(f"{'PASS' if r.passed else 'FAIL'}: {r.name} - {r.message}")
    print(f"\n总计: {len(results)}, 通过: {len(results) - len(failed)}, 失败: {len(failed)}")
    if failed:
        raise SystemExit(1)
