"""
专利和软著抽取器单元测试

测试CertificateExtractor基类、PatentExtractor和SoftwareExtractor的核心功能。
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

from backend.extract.extractors.certificate import (
    CertificateExtractor,
    PatentExtractor,
    SoftwareExtractor
)
from backend.extract.extractors.base import ExtractContext
from backend.extract.types import ExtractStatus, TemplateType


# ==================== CertificateExtractor 测试 ====================

class TestCertificateExtractor:
    """证书抽取器基类测试"""

    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        return {
            "enabled": True,
            "extensions": [".pdf", ".jpg", ".png"],
            "keywords": ["测试", "证书"],
            "min_confidence": 0.3,
            "fields_file": "patent_fields.json"
        }

    @pytest.fixture
    def mock_ocr_engine(self):
        """模拟OCR引擎"""
        mock = Mock()
        mock.extract_text = Mock(return_value={
            "text": "测试OCR文本内容\n包含专利信息\n申请号：202310123456.7",
            "from_cache": False
        })
        return mock

    @pytest.fixture
    def mock_llm_engine(self):
        """模拟LLM引擎"""
        mock = Mock()
        mock.call = Mock(return_value={
            "content": '{"patent_name": "测试专利", "patent_type": "发明专利"}',
            "from_cache": False
        })
        return mock

    def test_init(self, mock_config):
        """测试初始化"""
        # 创建一个测试子类
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        assert extractor.name == "test"
        assert ".pdf" in extractor.extensions
        assert "测试" in extractor.keywords

    def test_matches_extension(self, mock_config):
        """测试扩展名匹配"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        assert extractor.matches_extension(".pdf") == True
        assert extractor.matches_extension(".PDF") == True
        assert extractor.matches_extension(".jpg") == True
        assert extractor.matches_extension(".xlsx") == False

    def test_matches_keywords(self, mock_config):
        """测试关键词匹配"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        assert extractor.matches_keywords("这是一个测试证书") == True
        assert extractor.matches_keywords("这是测试证书") == True
        assert extractor.matches_keywords("这是文档") == False
        assert extractor.matches_keywords("") == False

    def test_parse_llm_response_json(self, mock_config):
        """测试LLM响应解析 - 标准JSON"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        # 标准JSON
        response = '{"patent_name": "测试", "patent_type": "发明专利"}'
        result = extractor._parse_llm_response(response)
        assert result == {"patent_name": "测试", "patent_type": "发明专利"}

    def test_parse_llm_response_code_block(self, mock_config):
        """测试LLM响应解析 - 代码块"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        # 代码块格式
        response = '''```json
{
  "patent_name": "测试",
  "patent_type": "发明专利"
}
```'''
        result = extractor._parse_llm_response(response)
        assert result == {"patent_name": "测试", "patent_type": "发明专利"}

    def test_parse_llm_response_invalid(self, mock_config):
        """测试LLM响应解析 - 无效格式"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        # 无效格式
        response = "这是一段普通文本，没有JSON"
        result = extractor._parse_llm_response(response)
        assert result == {}

    def test_validate_data_valid(self, mock_config):
        """测试数据验证 - 有效数据"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        data = {"patent_name": "测试", "patent_type": "发明专利"}
        assert extractor._validate_data(data) == True

    def test_validate_data_all_null(self, mock_config):
        """测试数据验证 - 全部为null"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        data = {"patent_name": None, "patent_type": None}
        assert extractor._validate_data(data) == False

    def test_extract_success(self, mock_config, mock_ocr_engine, mock_llm_engine):
        """测试成功抽取"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
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
            assert result.data.get("patent_name") == "测试专利"

        finally:
            import os
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_extract_unsupported_extension(self, mock_config, mock_ocr_engine, mock_llm_engine):
        """测试不支持的扩展名"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
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
            assert "扩展名" in result.data.get("note", "")

        finally:
            import os
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_extract_no_keywords(self, mock_config, mock_ocr_engine, mock_llm_engine):
        """测试关键词不匹配"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        # 修改OCR返回值，使其不包含关键词
        mock_ocr_engine.extract_text = Mock(return_value={
            "text": "这是一段普通文本，没有关键词",
            "from_cache": False
        })

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
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

    def test_extract_with_preloaded_ocr(self, mock_config, mock_llm_engine):
        """测试使用预加载的OCR文本"""
        class TestExtractor(CertificateExtractor):
            template_type = "test"
            fields_name = "patent"

        extractor = TestExtractor(mock_config)

        ctx = ExtractContext(
            file_path="test.pdf",
            ocr_text="测试证书文本内容\n包含测试关键词",
            use_ocr_cache=False,
            use_llm_cache=False,
            ocr_engine=None,
            llm_engine=mock_llm_engine
        )

        result = extractor.extract(ctx)

        assert result.status == ExtractStatus.SUCCESS
        # 验证没有调用OCR引擎
        assert ctx.ocr_engine is None


# ==================== PatentExtractor 测试 ====================

class TestPatentExtractor:
    """专利抽取器测试"""

    @pytest.fixture
    def config(self):
        """专利抽取器配置"""
        return {
            "enabled": True,
            "extensions": [".pdf", ".jpg", ".png"],
            "keywords": ["专利", "发明专利", "实用新型", "外观设计"],
            "min_confidence": 0.3,
            "fields_file": "patent_fields.json"
        }

    def test_init(self, config):
        """测试初始化"""
        extractor = PatentExtractor(config)

        assert extractor.name == "patent"
        assert extractor.template_type == "patent"
        assert ".pdf" in extractor.extensions
        assert "专利" in extractor.keywords

    def test_build_prompt(self, config):
        """测试提示词构建"""
        extractor = PatentExtractor(config)

        prompt = extractor._build_prompt("测试OCR文本")

        assert "专利" in prompt
        assert "测试OCR文本" in prompt
        assert "JSON格式" in prompt

    def test_template_type(self, config):
        """测试模板类型"""
        extractor = PatentExtractor(config)

        assert extractor.template_type == "patent"
        assert TemplateType.PATENT == "patent"


# ==================== SoftwareExtractor 测试 ====================

class TestSoftwareExtractor:
    """软著抽取器测试"""

    @pytest.fixture
    def config(self):
        """软著抽取器配置"""
        return {
            "enabled": True,
            "extensions": [".pdf", ".jpg", ".png"],
            "keywords": ["软件", "著作权", "软著"],
            "min_confidence": 0.3,
            "fields_file": "software_fields.json"
        }

    def test_init(self, config):
        """测试初始化"""
        extractor = SoftwareExtractor(config)

        assert extractor.name == "software"
        assert extractor.template_type == "software"
        assert ".pdf" in extractor.extensions
        assert "软件" in extractor.keywords

    def test_build_prompt(self, config):
        """测试提示词构建"""
        extractor = SoftwareExtractor(config)

        prompt = extractor._build_prompt("测试OCR文本")

        assert "软件" in prompt or "著作权" in prompt
        assert "测试OCR文本" in prompt
        assert "JSON格式" in prompt

    def test_template_type(self, config):
        """测试模板类型"""
        extractor = SoftwareExtractor(config)

        assert extractor.template_type == "software"
        assert TemplateType.SOFTWARE == "software"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
