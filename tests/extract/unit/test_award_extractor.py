"""
奖状抽取器单元测试

测试AwardExtractor的核心功能。
"""
import sys
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# 添加项目根到路径
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.extract.extractors.award import AwardExtractor
from backend.extract.extractors.base import ExtractContext
from backend.extract.types import ExtractStatus, TemplateType


class TestAwardExtractorCreation:
    """测试奖状抽取器创建"""

    @pytest.fixture
    def config(self):
        """默认配置"""
        return {
            "extensions": [".pdf", ".jpg", ".jpeg", ".png", ".jfif"],
            "keywords": ["奖", "证书", "赛", "竞赛"],
            "min_confidence": 0.3,
            "enable_quick_screen": True,
            "quick_screen_min_length": 15,
            "quick_screen_max_length": 500,
            "english_ratio_threshold": 0.7
        }

    def test_init(self, config):
        """测试初始化"""
        extractor = AwardExtractor(config)

        assert extractor.name == "award"
        assert extractor.template_type == "award"
        assert ".pdf" in extractor.extensions
        assert "奖" in extractor.keywords

    def test_matches_extension(self, config):
        """测试扩展名匹配"""
        extractor = AwardExtractor(config)

        assert extractor.matches_extension(".pdf") == True
        assert extractor.matches_extension(".jpg") == True
        assert extractor.matches_extension(".png") == True
        assert extractor.matches_extension(".jfif") == True
        assert extractor.matches_extension(".xlsx") == False

    def test_matches_keywords(self, config):
        """测试关键词匹配"""
        extractor = AwardExtractor(config)

        assert extractor.matches_keywords("蓝桥杯获奖证书") == True
        assert extractor.matches_keywords("竞赛证书") == True
        assert extractor.matches_keywords("这是一段普通文本") == False
        assert extractor.matches_keywords("") == False


class TestQuickScreen:
    """测试快速筛选功能"""

    @pytest.fixture
    def config(self):
        """配置"""
        return {
            "extensions": [".jpg"],
            "keywords": ["奖"],
            "enable_quick_screen": True,
            "quick_screen_min_length": 15,
            "quick_screen_max_length": 500
        }

    @pytest.fixture
    def extractor(self, config):
        """创建抽取器实例"""
        return AwardExtractor(config)

    def test_valid_award_text_passes(self, extractor):
        """测试有效奖状文本通过筛选（长度在范围内）"""
        text = "蓝桥杯全国软件和信息技术专业人才大赛省赛二等奖获奖证书"
        ok, _ = extractor._quick_screen(text)
        assert ok is True

    def test_no_keyword_fails(self, extractor):
        """测试过短文本未通过快速筛选（快速筛选只检查长度）"""
        text = "短" * 5  # 5个字符，低于最小长度15
        ok, _ = extractor._quick_screen(text)
        assert ok is False

    def test_too_short_fails(self, extractor):
        """测试过短文本失败"""
        text = "获奖证书"  # 4个字符
        ok, _ = extractor._quick_screen(text)
        assert ok is False

    def test_too_long_fails(self, extractor):
        """测试过长文本失败"""
        text = "a" * 600  # 600个字符
        ok, _ = extractor._quick_screen(text)
        assert ok is False

    def test_primary_keyword_passes(self, extractor):
        """测试长度在范围内通过"""
        text = "奖" * 20  # 20个字符，在15-500内
        ok, _ = extractor._quick_screen(text)
        assert ok is True

    def test_award_keyword_passes(self, extractor):
        """测试长度在范围内通过"""
        text = "竞赛" * 10  # 20个字符，在15-500内
        ok, _ = extractor._quick_screen(text)
        assert ok is True


class TestEnglishDetection:
    """测试英文奖状检测"""

    @pytest.fixture
    def config(self):
        return {
            "extensions": [".jpg"],
            "keywords": ["award"],
            "english_ratio_threshold": 0.7
        }

    @pytest.fixture
    def extractor(self, config):
        return AwardExtractor(config)

    def test_english_certificate_detected(self, extractor):
        """测试英文奖状被正确检测"""
        text = "Certificate of Achievement Winner: Zenan Xiang First Prize"
        assert extractor._is_english_certificate(text) is True

    def test_chinese_certificate_not_detected(self, extractor):
        """测试中文奖状不被检测为英文"""
        text = "蓝桥杯全国软件和信息技术专业人才大赛获奖证书"
        assert extractor._is_english_certificate(text) is False

    def test_mixed_text_with_more_chinese(self, extractor):
        """测试中英混合文本（中文为主）不被检测为英文"""
        text = "蓝桥杯全国软件和信息技术专业人才大赛获奖证书 Certificate"
        # 中文占大多数，应该不被检测为英文
        assert extractor._is_english_certificate(text) is False

    def test_empty_text_returns_false(self, extractor):
        """测试空文本返回False"""
        assert extractor._is_english_certificate("") is False
        assert extractor._is_english_certificate("   ") is False


class TestValidCertificateCheck:
    """测试奖状有效性检查"""

    @pytest.fixture
    def config(self):
        return {
            "extensions": [".jpg"],
            "keywords": ["奖"]
        }

    @pytest.fixture
    def extractor(self, config):
        return AwardExtractor(config)

    def test_valid_certificate_passes(self, extractor):
        """测试有效奖状通过检查"""
        data = {
            "is_valid_certificate": True,
            "winner_name": "张三"
        }
        assert extractor._check_valid_certificate(data) is True

    def test_invalid_certificate_fails(self, extractor):
        """测试无效奖状失败"""
        data = {
            "is_valid_certificate": False,
            "winner_name": "张三"
        }
        assert extractor._check_valid_certificate(data) is False

    def test_empty_winner_name_fails(self, extractor):
        """测试空获奖者姓名失败"""
        data = {
            "is_valid_certificate": True,
            "winner_name": ""
        }
        assert extractor._check_valid_certificate(data) is False

    def test_null_winner_name_fails(self, extractor):
        """测试None获奖者姓名失败"""
        data = {
            "is_valid_certificate": True,
            "winner_name": None
        }
        assert extractor._check_valid_certificate(data) is False

    def test_no_is_valid_certificate_treats_as_valid(self, extractor):
        """测试没有is_valid_certificate字段时，有winner_name则视为有效"""
        data = {
            "winner_name": "张三"
        }
        assert extractor._check_valid_certificate(data) is True


class TestFieldCleaning:
    """测试字段清理功能"""

    @pytest.fixture
    def config(self):
        return {
            "extensions": [".jpg"],
            "keywords": ["奖"]
        }

    @pytest.fixture
    def extractor(self, config):
        return AwardExtractor(config)

    def test_clean_name_field(self, extractor):
        """测试清理姓名字段"""
        # 姓名字段应去掉数字
        result = extractor._clean_field_value("winner_name", "张123三456")
        assert result == "张三"

    def test_clean_name_field_removes_symbols(self, extractor):
        """测试清理姓名字段（去除符号）"""
        result = extractor._clean_field_value("winner_name", "张#三$李%四")
        assert result == "张三李四"

    def test_clean_non_name_field(self, extractor):
        """测试清理非姓名字段（去空格并合并多个空格）"""
        result = extractor._clean_field_value("competition_name", "  蓝桥杯  竞赛  ")
        # 非姓名字段：多个空格合并为一个，首尾空格去掉
        assert result == "蓝桥杯 竞赛"

    def test_clean_null_value(self, extractor):
        """测试清理None值"""
        result = extractor._clean_field_value("winner_name", None)
        assert result is None

    def test_clean_empty_string(self, extractor):
        """测试清理空字符串"""
        result = extractor._clean_field_value("competition_name", "")
        # 空字符串返回None（设计决定）
        assert result is None

    def test_clean_multi_name_with_commas(self, extractor):
        """测试清理多人姓名（逗号分隔）"""
        result = extractor._clean_field_value("winners", "张三,,,李四,,王五")
        assert result == "张三,李四,王五"


class TestPromptBuilding:
    """测试提示词构建"""

    @pytest.fixture
    def config(self):
        return {
            "extensions": [".jpg"],
            "keywords": ["奖"]
        }

    @pytest.fixture
    def extractor(self, config):
        return AwardExtractor(config)

    def test_build_prompt_chinese(self, extractor):
        """测试构建中文提示词"""
        ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛获奖证书"
        prompt = extractor._build_prompt(ocr_text, is_english=False)

        assert "蓝桥杯全国软件和信息技术专业人才大赛获奖证书" in prompt
        assert "competition_name" in prompt
        assert "award_level" in prompt
        assert "is_valid_certificate" in prompt

    def test_build_prompt_english_with_translation(self, extractor):
        """测试构建英文提示词（带翻译要求）"""
        ocr_text = "Certificate of Achievement Winner: Zenan Xiang"
        prompt = extractor._build_prompt(ocr_text, is_english=True)

        assert "Certificate of Achievement Winner: Zenan Xiang" in prompt
        assert "人名保持原文" in prompt
        assert "其他内容翻译" in prompt
        assert "competition_name" in prompt

    def test_build_prompt_includes_translation_note(self, extractor):
        """测试提示词包含翻译说明"""
        ocr_text = "Winner: John Smith First Prize"
        prompt = extractor._build_prompt(ocr_text, is_english=True)

        # 检查翻译要求
        assert "First Prize" in prompt or "一等奖" in prompt
        assert "Winner" in prompt or "获奖者" in prompt


class TestFieldValidation:
    """测试字段验证"""

    @pytest.fixture
    def config(self):
        return {
            "extensions": [".jpg"],
            "keywords": ["奖"]
        }

    @pytest.fixture
    def extractor(self, config):
        return AwardExtractor(config)

    def test_valid_data_passes(self, extractor):
        """测试有效数据通过验证"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winner_name": "张三",
            "supervisor_name": "李老师"  # 包含指导教师
        }
        result = extractor._validate_specific_fields(data)
        assert len(result["completeness"]) == 0
        assert len(result["content"]) == 0

    def test_missing_competition_name(self, extractor):
        """测试缺少竞赛名称"""
        data = {
            "award_level": "一等奖",
            "winners": "张三"
        }
        result = extractor._validate_specific_fields(data)
        assert any(e.field_name == "competition_name" for e in result["completeness"])

    def test_missing_award_level(self, extractor):
        """测试缺少获奖等级"""
        data = {
            "competition_name": "蓝桥杯",
            "winners": "张三"
        }
        result = extractor._validate_specific_fields(data)
        assert any(e.field_name == "award_level" for e in result["completeness"])

    def test_missing_both_winner_fields(self, extractor):
        """测试同时缺少winners和winner_name"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖"
        }
        result = extractor._validate_specific_fields(data)
        assert len(result["completeness"]) > 0

    def test_invalid_date_format(self, extractor):
        """测试无效日期格式"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winners": "张三",
            "date": "2024/01/01"  # 错误格式
        }
        result = extractor._validate_specific_fields(data)
        assert any(e.field_name == "date" for e in result["content"])

    def test_valid_date_formats(self, extractor):
        """测试有效日期格式"""
        valid_dates = ["2024-01", "2024.01", "2024-1", "2024.1"]

        for date in valid_dates:
            data = {
                "competition_name": "蓝桥杯",
                "award_level": "一等奖",
                "winners": "张三",
                "date": date
            }
            result = extractor._validate_specific_fields(data)
            # 不应该有日期格式错误
            assert not any(e.field_name == "date" for e in result["content"])

    def test_invalid_award_level_english(self, extractor):
        """测试英文获奖等级（应翻译）"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "First Prize",  # 英文，应翻译
            "winners": "张三"
        }
        result = extractor._validate_specific_fields(data)
        assert any(e.field_name == "award_level" for e in result["content"])

    def test_valid_award_levels(self, extractor):
        """测试有效获奖等级"""
        valid_levels = ["一等奖", "二等奖", "三等奖", "特等奖", "优秀奖", "金奖", "银奖", "铜奖"]

        for level in valid_levels:
            data = {
                "competition_name": "蓝桥杯",
                "award_level": level,
                "winner_name": "张三",
                "supervisor_name": "李老师"  # 包含指导教师
            }
            result = extractor._validate_specific_fields(data)
            # 不应该有award_level错误
            assert not any(e.field_name == "award_level" for e in result["content"])

    def test_missing_supervisor_name(self, extractor):
        """测试缺少指导教师（应报错）"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winner_name": "张三"
            # 缺少 supervisor_name
        }
        result = extractor._validate_specific_fields(data)
        assert any(e.field_name == "supervisor_name" for e in result["completeness"])
        assert any("缺少指导教师" in e.error_message for e in result["completeness"])

    def test_empty_supervisor_name(self, extractor):
        """测试空字符串指导教师（应报错）"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winner_name": "张三",
            "supervisor_name": ""  # 空字符串
        }
        result = extractor._validate_specific_fields(data)
        assert any(e.field_name == "supervisor_name" for e in result["completeness"])

    def test_teacher_award_no_supervisor_required(self, extractor):
        """测试教师奖状不需要指导教师（例外情况）"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "优秀指导教师",
            "winner_name": "李老师",
            "granted_role": "优秀指导教师"
            # 没有 supervisor_name，但因为是教师奖状，所以不需要
        }
        result = extractor._validate_specific_fields(data)
        # 不应该有 supervisor_name 的完整性问题
        assert not any(e.field_name == "supervisor_name" for e in result["completeness"])

    def test_teacher_award_with_supervisor_name(self, extractor):
        """测试教师奖状有指导教师（应该通过）"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "优秀指导教师",
            "winner_name": "李老师",
            "granted_role": "优秀指导教师",
            "supervisor_name": "王老师"  # 有指导教师也可以
        }
        result = extractor._validate_specific_fields(data)
        # 不应该有 supervisor_name 的完整性问题
        assert not any(e.field_name == "supervisor_name" for e in result["completeness"])

    def test_valid_data_with_supervisor_name(self, extractor):
        """测试有效数据包含指导教师（应通过）"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winner_name": "张三",
            "supervisor_name": "李老师",
            "date": "2024-05"  # 包含日期
        }
        result = extractor._validate_specific_fields(data)
        # 不应该有完整性问题
        assert not any(e.field_name == "supervisor_name" for e in result["completeness"])

    def test_missing_date_year_edition(self, extractor):
        """测试缺少日期、年份、届次（应报错）"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winner_name": "张三",
            "supervisor_name": "李老师"
            # 缺少 date、year、edition
        }
        result = extractor._validate_specific_fields(data)
        assert any("date,year,edition" in e.field_name or e.field_name == "date,year,edition" for e in result["completeness"])
        assert any("奖状无日期" in e.error_message for e in result["completeness"])

    def test_has_date_passes(self, extractor):
        """测试有日期时通过验证"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winner_name": "张三",
            "supervisor_name": "李老师",
            "date": "2024-05"
        }
        result = extractor._validate_specific_fields(data)
        assert not any("date,year,edition" in e.field_name or e.field_name == "date,year,edition" for e in result["completeness"])

    def test_has_year_passes(self, extractor):
        """测试有年份时通过验证"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winner_name": "张三",
            "supervisor_name": "李老师",
            "year": 2024
        }
        result = extractor._validate_specific_fields(data)
        assert not any("date,year,edition" in e.field_name or e.field_name == "date,year,edition" for e in result["completeness"])

    def test_has_edition_passes(self, extractor):
        """测试有届次时通过验证"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winner_name": "张三",
            "supervisor_name": "李老师",
            "edition": 15
        }
        result = extractor._validate_specific_fields(data)
        assert not any("date,year,edition" in e.field_name or e.field_name == "date,year,edition" for e in result["completeness"])


class TestLLMPResponseParsing:
    """测试LLM响应解析"""

    @pytest.fixture
    def config(self):
        return {
            "extensions": [".jpg"],
            "keywords": ["奖"]
        }

    @pytest.fixture
    def extractor(self, config):
        return AwardExtractor(config)

    def test_parse_valid_json(self, extractor):
        """测试解析有效JSON"""
        response = '{"competition_name": "蓝桥杯", "award_level": "一等奖", "winners": "张三", "is_valid_certificate": true}'
        result = extractor._parse_llm_response(response)

        assert result["competition_name"] == "蓝桥杯"
        assert result["award_level"] == "一等奖"
        assert result["winners"] == "张三"
        assert result["is_valid_certificate"] is True

    def test_parse_json_with_code_block(self, extractor):
        """测试解析带代码块的JSON"""
        response = '''```json
{
  "competition_name": "蓝桥杯",
  "award_level": "一等奖",
  "winners": "张三",
  "is_valid_certificate": true
}
```'''
        result = extractor._parse_llm_response(response)

        assert result["competition_name"] == "蓝桥杯"
        assert result["award_level"] == "一等奖"

    def test_parse_invalid_response(self, extractor):
        """测试解析无效响应"""
        response = "这是一段普通文本，没有JSON"
        result = extractor._parse_llm_response(response)
        assert result == {}

    def test_parse_is_valid_certificate_false(self, extractor):
        """测试解析无效证书"""
        response = '{"is_valid_certificate": false}'
        result = extractor._parse_llm_response(response)
        assert result["is_valid_certificate"] is False


class TestExtractionFlow:
    """测试完整抽取流程"""

    @pytest.fixture
    def config(self):
        return {
            "extensions": [".jpg", ".png"],
            "keywords": ["奖", "证书"],
            "enable_quick_screen": True
        }

    @pytest.fixture
    def mock_ocr_engine(self):
        """模拟OCR引擎"""
        mock = Mock()
        mock.get_text = Mock(return_value=("蓝桥杯全国软件和信息技术专业人才大赛省赛二等奖获奖证书 获奖者：张三", False))
        return mock

    @pytest.fixture
    def mock_llm_engine(self):
        """模拟LLM引擎"""
        mock = Mock()
        mock.chat = Mock(return_value=('{"competition_name": "蓝桥杯全国软件和信息技术专业人才大赛", "award_level": "二等奖", "winners": "张三", "is_valid_certificate": true}', False))
        return mock

    def test_extract_success(self, config, mock_ocr_engine, mock_llm_engine):
        """测试成功抽取"""
        extractor = AwardExtractor(config)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name

        try:
            ctx = ExtractContext(
                file_path=temp_path,
                ocr_text=None,
                use_ocr_cache=False,
                use_llm_cache=False,
                ocr_engine=mock_ocr_engine,
                llm_engine=mock_llm_engine
            )

            result = extractor.extract(ctx)

            assert result.status == ExtractStatus.SUCCESS
            assert result.template_type == "award"
            assert result.data["competition_name"] == "蓝桥杯全国软件和信息技术专业人才大赛"
            assert result.data["award_level"] == "二等奖"
            assert result.data["winners"] == "张三"

        finally:
            import os
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_extract_invalid_certificate_returns_other(self, config, mock_ocr_engine, mock_llm_engine):
        """测试无效证书返回other"""
        # LLM返回无效证书
        mock_llm_engine.chat = Mock(return_value=('{"is_valid_certificate": false}', False))

        extractor = AwardExtractor(config)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name

        try:
            ctx = ExtractContext(
                file_path=temp_path,
                ocr_text=None,
                use_ocr_cache=False,
                use_llm_cache=False,
                ocr_engine=mock_ocr_engine,
                llm_engine=mock_llm_engine
            )

            result = extractor.extract(ctx)

            assert result.template_type == TemplateType.OTHER
            assert "不是真实的奖状证书" in result.error_message or "is_valid_certificate" in str(result.data)

        finally:
            import os
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_extract_quick_screen_fails_returns_other(self, config, mock_ocr_engine, mock_llm_engine):
        """测试快速筛选失败返回other"""
        # OCR返回不符合筛选条件的文本（太短且无关键词）
        # 使用一个太短的文本，不会通过快速筛选
        mock_ocr_engine.get_text = Mock(return_value=("测试文本", False))  # 只有4个字符，低于最小长度15

        extractor = AwardExtractor(config)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name

        try:
            ctx = ExtractContext(
                file_path=temp_path,
                ocr_text=None,
                use_ocr_cache=False,
                use_llm_cache=False,
                ocr_engine=mock_ocr_engine,
                llm_engine=mock_llm_engine
            )

            result = extractor.extract(ctx)

            assert result.template_type == TemplateType.OTHER

        finally:
            import os
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
