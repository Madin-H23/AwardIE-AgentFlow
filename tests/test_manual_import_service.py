"""
Manual Import Service 单元测试

测试手动导入服务模块的功能。
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.services.manual_import_service import ManualImportService
from backend.extract.types import ExtractResult, ExtractStatus


class TestManualImportService(unittest.TestCase):
    """ManualImportService 单元测试"""

    def setUp(self):
        """测试前准备"""
        # 创建 mock extract_framework
        self.mock_framework = Mock()

        # 创建 mock OCR 引擎
        self.mock_ocr_engine = Mock()
        self.mock_framework.ocr_engine = self.mock_ocr_engine

        # 创建 mock LLM 引擎
        self.mock_llm_engine = Mock()
        self.mock_framework.llm_engine = self.mock_llm_engine

        # 创建 mock 抽取器
        self.mock_award_extractor = Mock()
        self.mock_award_extractor.name = "award"
        self.mock_patent_extractor = Mock()
        self.mock_patent_extractor.name = "patent"
        self.mock_software_extractor = Mock()
        self.mock_software_extractor.name = "software"

        # 设置框架的抽取器列表
        self.mock_framework._extractors = [
            self.mock_award_extractor,
            self.mock_patent_extractor,
            self.mock_software_extractor
        ]

        # 初始化服务
        self.service = ManualImportService(self.mock_framework)

    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.service)
        self.assertEqual(self.service.framework, self.mock_framework)
        self.assertEqual(self.service.ocr_engine, self.mock_ocr_engine)
        self.assertEqual(self.service.llm_engine, self.mock_llm_engine)

    def test_get_extractor_by_type_award(self):
        """测试获取奖状抽取器"""
        extractor = self.service._get_extractor_by_type("award")
        self.assertEqual(extractor.name, "award")

    def test_get_extractor_by_type_patent(self):
        """测试获取专利抽取器"""
        extractor = self.service._get_extractor_by_type("patent")
        self.assertEqual(extractor.name, "patent")

    def test_get_extractor_by_type_software(self):
        """测试获取软著抽取器"""
        extractor = self.service._get_extractor_by_type("software")
        self.assertEqual(extractor.name, "software")

    def test_get_extractor_by_type_invalid(self):
        """测试无效类型"""
        with self.assertRaises(ValueError) as context:
            self.service._get_extractor_by_type("invalid")
        self.assertIn("不支持的类型", str(context.exception))

    def test_parse_by_type_ocr_success(self):
        """测试解析成功流程"""
        # 设置 OCR 返回值
        test_ocr_text = "获奖证书\n一等奖\n张三"
        self.mock_ocr_engine.get_text.return_value = (test_ocr_text, False)

        # 设置抽取器返回值
        mock_result = ExtractResult(
            status=ExtractStatus.SUCCESS,
            data={"competition_name": "测试竞赛", "award_level": "一等奖"},
            template_type="award",
            extractor_name="award",
            ocr_text=test_ocr_text
        )
        self.mock_award_extractor.extract.return_value = mock_result

        # 调用解析
        result = self.service.parse_by_type("/fake/path/award.jpg", "award")

        # 验证
        self.assertEqual(result.status, ExtractStatus.SUCCESS)
        self.assertEqual(result.template_type, "award")
        self.assertEqual(result.data["competition_name"], "测试竞赛")

        # 验证 OCR 被调用
        self.mock_ocr_engine.get_text.assert_called_once()

        # 验证抽取器被调用
        self.mock_award_extractor.extract.assert_called_once()

    def test_parse_by_type_ocr_failure(self):
        """测试 OCR 失败流程"""
        # 设置 OCR 抛出异常
        self.mock_ocr_engine.get_text.side_effect = Exception("OCR failed")

        # 调用解析
        result = self.service.parse_by_type("/fake/path/award.jpg", "award")

        # 验证返回错误结果
        self.assertEqual(result.status, "ocr_error")
        self.assertIn("OCR识别失败", result.error_message)

    def test_parse_by_type_ocr_empty_text(self):
        """测试 OCR 返回空文本"""
        # 设置 OCR 返回空文本
        self.mock_ocr_engine.get_text.return_value = (None, False)

        # 调用解析
        result = self.service.parse_by_type("/fake/path/award.jpg", "award")

        # 验证返回错误结果
        self.assertEqual(result.status, "ocr_error")
        self.assertIn("OCR未能识别出文本", result.error_message)

    def test_parse_by_type_invalid_type(self):
        """测试无效类型"""
        # 设置 OCR 返回值（需要先OCR才能检查类型）
        self.mock_ocr_engine.get_text.return_value = ("test text", False)

        # 调用解析
        result = self.service.parse_by_type("/fake/path/test.jpg", "invalid")

        # 验证返回错误结果
        self.assertEqual(result.status, "error")
        self.assertIn("不支持的类型", result.error_message)

    def test_get_supported_types(self):
        """测试获取支持的类型列表"""
        types = self.service.get_supported_types()
        self.assertEqual(sorted(types), ["award", "patent", "software"])

    def test_parse_by_type_extractor_exception(self):
        """测试抽取器抛出异常"""
        # 设置 OCR 返回值
        test_ocr_text = "获奖证书\n一等奖\n张三"
        self.mock_ocr_engine.get_text.return_value = (test_ocr_text, False)

        # 设置抽取器抛出异常
        self.mock_award_extractor.extract.side_effect = Exception("Extractor failed")

        # 调用解析
        result = self.service.parse_by_type("/fake/path/award.jpg", "award")

        # 验证返回错误结果
        self.assertEqual(result.status, "error")
        self.assertIn("抽取失败", result.error_message)


if __name__ == '__main__':
    unittest.main()
