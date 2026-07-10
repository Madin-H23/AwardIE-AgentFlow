"""
LLM抽取器选择详细测试

专门用于深入了解多抽取器场景下LLM判断的完整流程：
- LLM提示词的完整内容
- LLM的原始返回结果
- 解析后的抽取器列表
- 抽取器的调用顺序和结果
"""
import json
import tempfile
import os
from pathlib import Path
from typing import List, Tuple

# 项目根
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(project_root))

from backend.extract.types import ExtractResult, ExtractStatus, TemplateType
from backend.extract.extractors.base import ExtractContext, Extractor
from backend.extract.framework import ExtractFramework


class DetailedMockLLM:
    """详细的Mock LLM引擎，记录所有调用信息"""
    def __init__(self, response: str = '["award"]', cached: bool = False):
        self.response = response
        self.cached = cached
        self.last_messages: List[dict] = []
        self.call_count = 0
        self.last_prompt: str = ""
        self.last_raw_response: str = ""
        self.temperature_used: float = 0.0
        self.use_cache_used: bool = False

    def chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> Tuple[str, bool]:
        self.last_messages = messages
        self.call_count += 1
        self.last_prompt = messages[0].get("content", "") if messages else ""
        self.temperature_used = temperature
        self.use_cache_used = use_cache
        self.last_raw_response = self.response
        return self.response, self.cached


class DetailedMockOCR:
    """详细的Mock OCR引擎"""
    def __init__(self, text: str = "mock ocr", cached: bool = False):
        self.text = text
        self.cached = cached
        self.call_count = 0
        self.last_file_path: str = ""
        self.last_use_cache: bool = False
        self.last_is_precise: bool = False

    def get_text(self, file_path: str, use_cache: bool = True, is_precise: bool = False) -> Tuple[str, bool]:
        self.call_count += 1
        self.last_file_path = file_path
        self.last_use_cache = use_cache
        self.last_is_precise = is_precise
        return self.text, self.cached


class DetailedMockExtractor(Extractor):
    """详细的Mock抽取器，记录所有调用信息"""
    def __init__(
        self,
        name: str,
        extensions: List[str],
        keywords: List[str],
        description: str = None,
        judgment_text: str = None,
        result_template_type: str = TemplateType.OTHER,
        result_data: dict = None,
    ):
        super().__init__(
            name=name,
            description=description or f"描述-{name}",
            keywords=keywords,
            judgment_text=judgment_text or f"判断文本-{name}",
            extensions=extensions,
            validator=None,
        )
        self._result_type = result_template_type
        self._result_data = result_data or {}
        self._extract_called = 0
        self._extract_contexts: List[ExtractContext] = []

    def extract(self, ctx: ExtractContext) -> ExtractResult:
        self._extract_called += 1
        self._extract_contexts.append(ctx)
        return ExtractResult(
            status=ExtractStatus.SUCCESS if self._result_type != TemplateType.OTHER else ExtractStatus.NO_TEMPLATE,
            data=self._result_data,
            template_type=self._result_type,
        )


def test_llm_selector_detailed():
    """
    详细测试：多抽取器场景下LLM判断的完整流程
    
    场景：
    - 注册3个抽取器：award（奖状）、innovation（大创）、patent（专利）
    - OCR文本包含"奖"关键词，3个抽取器都匹配
    - LLM需要判断应该使用哪些抽取器
    """
    print("\n" + "="*80)
    print("LLM抽取器选择详细测试")
    print("="*80)
    
    # 1. 准备测试数据
    ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛\n一等奖\n获奖者：张三\n项目名称：智能识别系统"
    llm_response = '["award", "innovation"]'  # LLM返回两个抽取器
    
    # 2. 创建Mock对象
    mock_ocr = DetailedMockOCR(text=ocr_text, cached=False)
    mock_llm = DetailedMockLLM(response=llm_response, cached=False)
    
    # 3. 创建框架
    framework = ExtractFramework(
        ocr_engine=mock_ocr,
        llm_engine=mock_llm,
        image_extensions=[".jpg", ".png", ".pdf"],
        other_notes={
            "no_extension": "不支持的文件扩展名",
            "no_match": "没有抽取器能够处理此文件"
        },
    )
    
    # 4. 注册3个抽取器
    extractor_award = DetailedMockExtractor(
        name="award",
        extensions=[".jpg"],
        keywords=["奖", "一等奖", "二等奖", "三等奖"],
        description="奖状类别。特征：包含竞赛名称、奖项等级（如一等奖、二等奖、三等奖、金奖、银奖、铜奖）、获奖者姓名等信息。通常出现在竞赛证书、获奖证明、奖状等文档中。",
        judgment_text="奖状类别。特征：包含竞赛名称、奖项等级（如一等奖、二等奖、三等奖、金奖、银奖、铜奖）、获奖者姓名等信息。通常出现在竞赛证书、获奖证明、奖状等文档中。",
        result_template_type=TemplateType.OTHER,  # 第一个返回other
    )
    
    extractor_innovation = DetailedMockExtractor(
        name="innovation",
        extensions=[".jpg"],
        keywords=["奖", "大创", "创新", "项目"],
        description="大创项目类别。特征：包含项目名称、项目负责人、项目成员、指导教师、项目级别（国家级/省级/院级）等信息。通常出现在大学生创新创业训练计划项目申报书、项目证书等文档中。",
        judgment_text="大创项目类别。特征：包含项目名称、项目负责人、项目成员、指导教师、项目级别（国家级/省级/院级）等信息。通常出现在大学生创新创业训练计划项目申报书、项目证书等文档中。",
        result_template_type=TemplateType.INNOVATION,  # 第二个返回innovation
        result_data={"project_name": "智能识别系统", "leader": "张三"},
    )
    
    extractor_patent = DetailedMockExtractor(
        name="patent",
        extensions=[".jpg"],
        keywords=["奖", "专利", "发明"],
        description="专利类别。特征：包含专利名称、专利号、发明人、专利类型（发明专利/实用新型/外观设计）等信息。通常出现在专利证书、专利申请文件等文档中。",
        judgment_text="专利类别。特征：包含专利名称、专利号、发明人、专利类型（发明专利/实用新型/外观设计）等信息。通常出现在专利证书、专利申请文件等文档中。",
        result_template_type=TemplateType.PATENT,
    )
    
    framework.register(extractor_award)
    framework.register(extractor_innovation)
    framework.register(extractor_patent)
    
    print(f"\n【1. 注册的抽取器】")
    print(f"  - {extractor_award.name}: {extractor_award.description}")
    print(f"  - {extractor_innovation.name}: {extractor_innovation.description}")
    print(f"  - {extractor_patent.name}: {extractor_patent.description}")
    
    print(f"\n【2. OCR文本】")
    print(f"  {ocr_text}")
    
    print(f"\n【3. 关键词匹配结果】")
    matched = [e for e in [extractor_award, extractor_innovation, extractor_patent] 
               if e.matches_keywords(ocr_text)]
    print(f"  匹配的抽取器数量: {len(matched)}")
    for ex in matched:
        print(f"    - {ex.name} (关键词: {ex.keywords})")
    
    # 5. 执行抽取
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        result = framework.extract(path, use_ocr_cache=True, use_llm_cache=True)
        
        # 6. 输出详细信息
        print(f"\n【4. OCR调用信息】")
        print(f"  调用次数: {mock_ocr.call_count}")
        print(f"  文件路径: {mock_ocr.last_file_path}")
        print(f"  使用缓存: {mock_ocr.last_use_cache}")
        print(f"  是否高精度: {mock_ocr.last_is_precise}")
        print(f"  缓存命中: {mock_ocr.cached}")
        
        print(f"\n【5. LLM调用信息】")
        print(f"  调用次数: {mock_llm.call_count}")
        print(f"  温度参数: {mock_llm.temperature_used}")
        print(f"  使用缓存: {mock_llm.use_cache_used}")
        print(f"  缓存命中: {mock_llm.cached}")
        
        print(f"\n【6. LLM提示词（完整内容）】")
        print("-" * 80)
        if mock_llm.last_prompt:
            print(mock_llm.last_prompt)
        else:
            print("  (未调用LLM)")
        print("-" * 80)
        
        print(f"\n【7. LLM原始返回】")
        print(f"  原始响应: {mock_llm.last_raw_response}")
        
        # 解析LLM返回
        from backend.extract.framework import _parse_extractor_list
        parsed = _parse_extractor_list(mock_llm.last_raw_response)
        print(f"  解析结果: {parsed}")
        
        print(f"\n【8. 抽取器调用顺序和结果】")
        print(f"  按LLM返回顺序调用抽取器:")
        for i, name in enumerate(parsed, 1):
            ex = next((e for e in matched if e.name == name), None)
            if ex:
                print(f"    {i}. {ex.name}")
                print(f"       调用次数: {ex._extract_called}")
                if ex._extract_called > 0:
                    last_result = ex._extract_contexts[-1] if ex._extract_contexts else None
                    print(f"       接收的OCR文本: {last_result.ocr_text[:50] if last_result and last_result.ocr_text else 'None'}...")
        
        print(f"\n【9. 最终抽取结果】")
        print(f"  状态: {result.status}")
        print(f"  模板类型: {result.template_type}")
        print(f"  抽取器名称: {result.extractor_name}")
        print(f"  数据: {result.data}")
        print(f"  OCR文本: {result.ocr_text[:100] if result.ocr_text else 'None'}...")
        print(f"  OCR缓存命中: {result.ocr_cache_hit}")
        print(f"  LLM缓存命中: {result.llm_cache_hit}")
        
        print(f"\n【10. 验证】")
        # 验证LLM被调用
        assert mock_llm.call_count == 1, "LLM应该被调用1次"
        # 验证提示词包含所有匹配的抽取器
        assert "award" in mock_llm.last_prompt.lower(), "提示词应包含award"
        assert "innovation" in mock_llm.last_prompt.lower(), "提示词应包含innovation"
        assert "patent" in mock_llm.last_prompt.lower(), "提示词应包含patent"
        # 验证抽取器调用顺序
        assert extractor_award._extract_called == 1, "award应该被调用"
        assert extractor_innovation._extract_called == 1, "innovation应该被调用"
        assert extractor_patent._extract_called == 0, "patent不应该被调用（LLM未返回）"
        # 验证最终结果
        assert result.template_type == TemplateType.INNOVATION, "最终结果应该是innovation"
        assert result.extractor_name == "innovation", "最终使用的抽取器应该是innovation"
        
        print("  [OK] 所有验证通过")
        
    finally:
        os.unlink(path)
    
    print("\n" + "="*80)
    print("测试完成")
    print("="*80 + "\n")


def test_llm_prompt_structure():
    """
    测试LLM提示词的结构
    """
    print("\n" + "="*80)
    print("LLM提示词结构分析")
    print("="*80)
    
    mock_llm = DetailedMockLLM(response='["award"]', cached=False)
    framework = ExtractFramework(
        ocr_engine=DetailedMockOCR(text="测试文本"),
        llm_engine=mock_llm,
        image_extensions=[".jpg"],
        other_notes={"no_extension": "不支持", "no_match": "无匹配"},
    )
    
    # 注册抽取器
    ex1 = DetailedMockExtractor(
        name="award",
        extensions=[".jpg"],
        keywords=["奖"],
        description="奖状类别。特征：包含竞赛名称、奖项等级、获奖者姓名等信息。通常出现在竞赛证书、获奖证明等文档中。",
        judgment_text="奖状类别。特征：包含竞赛名称、奖项等级、获奖者姓名等信息。通常出现在竞赛证书、获奖证明等文档中。",
    )
    ex2 = DetailedMockExtractor(
        name="innovation",
        extensions=[".jpg"],
        keywords=["奖"],
        description="大创项目类别。特征：包含项目名称、项目负责人、项目成员、指导教师、项目级别等信息。通常出现在大学生创新创业训练计划项目申报书等文档中。",
        judgment_text="大创项目类别。特征：包含项目名称、项目负责人、项目成员、指导教师、项目级别等信息。通常出现在大学生创新创业训练计划项目申报书等文档中。",
    )
    framework.register(ex1).register(ex2)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        framework.extract(path)
        
        print(f"\n【提示词结构分析】")
        prompt = mock_llm.last_prompt
        print(f"  总长度: {len(prompt)} 字符")
        print(f"\n  完整内容:")
        print("-" * 80)
        print(prompt)
        print("-" * 80)
        
        # 分析提示词组成部分
        print(f"\n【提示词组成部分】")
        if "抽取器说明" in prompt:
            print("  ✓ 包含'抽取器说明'部分")
        if "OCR 文本" in prompt:
            print("  ✓ 包含'OCR 文本'部分")
        if "award" in prompt.lower():
            print("  ✓ 包含award抽取器信息")
        if "innovation" in prompt.lower():
            print("  ✓ 包含innovation抽取器信息")
        if "判断文本" in prompt or "judgment" in prompt.lower():
            print("  ✓ 包含judgment_text")
        
    finally:
        os.unlink(path)
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    test_llm_selector_detailed()
    test_llm_prompt_structure()
