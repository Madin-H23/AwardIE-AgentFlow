"""
抽取验证器单元测试

全面测试ExtractorValidator的各项功能，包括值映射、空值处理、大小写不敏感匹配等。
"""
import sys
from pathlib import Path

# 添加项目根到路径
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
from backend.extract.validator import ExtractorValidator
from backend.extract.types import ValidationResult, ValidationError


class TestExtractorValidator:
    """抽取验证器测试"""

    # ==================== 基础功能测试 ====================

    def test_init_empty_mappings(self):
        """测试初始化 - 空映射"""
        validator = ExtractorValidator(value_mappings={})
        assert validator.value_mappings == {}

    def test_init_with_mappings(self):
        """测试初始化 - 带映射"""
        mappings = {"award_level": {"Gold": "金奖"}}
        validator = ExtractorValidator(value_mappings=mappings)
        assert validator.value_mappings == mappings

    # ==================== 值映射测试 ====================

    def test_validate_with_exact_mapping(self):
        """测试精确值映射"""
        validator = ExtractorValidator(
            value_mappings={"award_level": {"Gold Medal": "金奖"}}
        )

        result = validator.validate({"award_level": "Gold Medal"})

        assert result.is_valid == True
        assert result.mapped_data is not None
        assert result.mapped_data["award_level"] == "金奖"

    def test_validate_with_case_insensitive_mapping(self):
        """测试大小写不敏感映射"""
        validator = ExtractorValidator(
            value_mappings={"award_level": {"gold medal": "金奖"}}
        )

        # 测试大写
        result1 = validator.validate({"award_level": "Gold Medal"})
        assert result1.mapped_data["award_level"] == "金奖"

        # 测试小写
        result2 = validator.validate({"award_level": "gold medal"})
        assert result2.mapped_data["award_level"] == "金奖"

        # 测试混合大小写
        result3 = validator.validate({"award_level": "GOLD MEDAL"})
        assert result3.mapped_data["award_level"] == "金奖"

    def test_validate_no_mapping_for_field(self):
        """测试未配置映射的字段保持不变"""
        validator = ExtractorValidator(
            value_mappings={"award_level": {"Gold": "金奖"}}
        )

        result = validator.validate({
            "award_level": "Gold",
            "other_field": "保持不变"
        })

        assert result.mapped_data["award_level"] == "金奖"
        assert result.mapped_data["other_field"] == "保持不变"

    def test_validate_no_matching_mapping(self):
        """测试值不在映射表中时保持不变"""
        validator = ExtractorValidator(
            value_mappings={"award_level": {"Gold": "金奖"}}
        )

        result = validator.validate({"award_level": "银奖"})

        assert result.mapped_data["award_level"] == "银奖"

    def test_validate_multiple_fields(self):
        """测试多字段同时映射"""
        validator = ExtractorValidator(
            value_mappings={
                "award_level": {"First Prize": "一等奖"},
                "competition_level": {"区域赛": "省赛"}
            }
        )

        result = validator.validate({
            "award_level": "First Prize",
            "competition_level": "区域赛",
            "year": "2024"
        })

        assert result.mapped_data["award_level"] == "一等奖"
        assert result.mapped_data["competition_level"] == "省赛"
        assert result.mapped_data["year"] == "2024"

    def test_validate_multiple_values_same_field(self):
        """测试同一字段的多个值映射"""
        validator = ExtractorValidator(
            value_mappings={
                "award_level": {
                    "First Prize": "一等奖",
                    "Gold Medal": "金奖",
                    "Second Prize": "二等奖"
                }
            }
        )

        result1 = validator.validate({"award_level": "First Prize"})
        assert result1.mapped_data["award_level"] == "一等奖"

        result2 = validator.validate({"award_level": "Gold Medal"})
        assert result2.mapped_data["award_level"] == "金奖"

        result3 = validator.validate({"award_level": "Second Prize"})
        assert result3.mapped_data["award_level"] == "二等奖"

    # ==================== 空值处理测试 ====================

    def test_validate_empty_data(self):
        """测试空数据验证"""
        validator = ExtractorValidator(
            value_mappings={"award_level": {"Gold": "金奖"}}
        )

        result = validator.validate({})

        assert result.is_valid == True
        assert result.mapped_data == {}

    def test_validate_null_value(self):
        """测试None值处理"""
        validator = ExtractorValidator(
            value_mappings={"award_level": {"Gold": "金奖"}}
        )

        result = validator.validate({"award_level": None})

        assert result.mapped_data["award_level"] is None

    def test_validate_empty_string(self):
        """测试空字符串处理"""
        validator = ExtractorValidator(
            value_mappings={"award_level": {"Gold": "金奖"}}
        )

        result = validator.validate({"award_level": ""})

        assert result.mapped_data["award_level"] == ""

    def test_validate_whitespace_only_string(self):
        """测试纯空格字符串处理"""
        validator = ExtractorValidator(
            value_mappings={"Gold": "金奖"}
        )

        result = validator.validate({"award_level": "   "})

        assert result.mapped_data["award_level"] == "   "

    # ==================== 复杂场景测试 ====================

    def test_validate_mixed_valid_and_invalid(self):
        """测试部分字段有映射，部分没有"""
        validator = ExtractorValidator(
            value_mappings={
                "award_level": {"Gold": "金奖"},
                "competition_level": {"区域赛": "省赛"}
            }
        )

        result = validator.validate({
            "award_level": "Gold",
            "competition_level": "国家级",  # 没有映射配置
            "year": "2024"
        })

        assert result.mapped_data["award_level"] == "金奖"
        assert result.mapped_data["competition_level"] == "国家级"
        assert result.mapped_data["year"] == "2024"

    def test_validate_preserves_original_data_structure(self):
        """测试保持原始数据结构"""
        validator = ExtractorValidator(
            value_mappings={"level": {"A": "一级"}}
        )

        original_data = {
            "level": "A",
            "nested": {
                "field1": "value1",
                "field2": "value2"
            },
            "list": [1, 2, 3]
        }

        result = validator.validate(original_data)

        assert result.mapped_data["level"] == "一级"
        assert result.mapped_data["nested"] == original_data["nested"]
        assert result.mapped_data["list"] == original_data["list"]

    def test_validate_with_complex_values(self):
        """测试复杂值的映射"""
        validator = ExtractorValidator(
            value_mappings={
                "status": {
                    "pending": "待审核",
                    "approved": "已通过",
                    "rejected": "已拒绝"
                }
            }
        )

        result = validator.validate({
            "status": "pending",
            "id": 12345,
            "timestamp": "2024-01-01 12:00:00"
        })

        assert result.mapped_data["status"] == "待审核"
        assert result.mapped_data["id"] == 12345
        assert result.mapped_data["timestamp"] == "2024-01-01 12:00:00"

    # ==================== ValidationResult 测试 ====================

    def test_validation_result_structure(self):
        """测试ValidationResult结构"""
        validator = ExtractorValidator(value_mappings={})
        result = validator.validate({"test": "value"})

        assert hasattr(result, "is_valid")
        assert hasattr(result, "content_issues")
        assert hasattr(result, "completeness_issues")
        assert hasattr(result, "mapped_data")
        assert result.is_valid == True
        assert result.content_issues == []
        assert result.completeness_issues == []

    # ==================== 竞赛等级映射测试 ====================

    def test_competition_level_mapping(self):
        """测试竞赛等级映射（区域赛 -> 省赛）"""
        validator = ExtractorValidator(
            value_mappings={"competition_level": {"区域赛": "省赛"}}
        )

        result = validator.validate({"competition_level": "区域赛"})

        assert result.mapped_data["competition_level"] == "省赛"

    # ==================== 奖项等级映射测试 ====================

    def test_award_level_english_to_chinese(self):
        """测试奖项等级英文转中文"""
        validator = ExtractorValidator(
            value_mappings={
                "award_level": {
                    "Gold Medal": "金奖",
                    "Silver Medal": "银奖",
                    "Bronze Medal": "铜奖",
                    "First Prize": "一等奖",
                    "Second Prize": "二等奖",
                    "Third Prize": "三等奖"
                }
            }
        )

        # 测试各种奖项
        assert validator.validate({"award_level": "Gold Medal"}).mapped_data["award_level"] == "金奖"
        assert validator.validate({"award_level": "Silver Medal"}).mapped_data["award_level"] == "银奖"
        assert validator.validate({"award_level": "First Prize"}).mapped_data["award_level"] == "一等奖"

    # ==================== 专利类型映射测试 ====================

    def test_patent_type_mapping(self):
        """测试专利类型映射"""
        validator = ExtractorValidator(
            value_mappings={
                "patent_type": {
                    "Invention": "发明专利",
                    "Utility": "实用新型",
                    "Design": "外观设计"
                }
            }
        )

        assert validator.validate({"patent_type": "Invention"}).mapped_data["patent_type"] == "发明专利"
        assert validator.validate({"patent_type": "Utility"}).mapped_data["patent_type"] == "实用新型"
        assert validator.validate({"patent_type": "Design"}).mapped_data["patent_type"] == "外观设计"

    # ==================== 边界情况测试 ====================

    def test_validate_with_non_string_values(self):
        """测试非字符串值处理"""
        validator = ExtractorValidator(
            value_mappings={"level": {"A": "一级"}}
        )

        result = validator.validate({
            "level": "A",
            "count": 10,
            "ratio": 0.85,
            "flag": True
        })

        assert result.mapped_data["level"] == "一级"
        assert result.mapped_data["count"] == 10
        assert result.mapped_data["ratio"] == 0.85
        assert result.mapped_data["flag"] == True

    def test_validate_with_unicode_values(self):
        """测试Unicode字符处理"""
        validator = ExtractorValidator(
            value_mappings={"level": {"特等奖": "Special Prize"}}
        )

        result = validator.validate({"level": "特等奖"})

        assert result.mapped_data["level"] == "Special Prize"

    def test_validate_with_special_characters(self):
        """测试特殊字符处理"""
        validator = ExtractorValidator(
            value_mappings={"code": {"A-1": "类型A-1"}}
        )

        result = validator.validate({"code": "A-1"})

        assert result.mapped_data["code"] == "类型A-1"

    # ==================== 性能测试 ====================

    def test_validate_large_dataset(self):
        """测试大数据集验证性能"""
        validator = ExtractorValidator(
            value_mappings={
                "level": {"A": "一级", "B": "二级"},
                "status": {"1": "启用", "0": "禁用"}
            }
        )

        # 创建包含1000条记录的测试数据
        test_data = {
            "items": [
                {"id": i, "level": "A" if i % 2 == 0 else "B", "status": "1"}
                for i in range(1000)
            ]
        }

        import time
        start = time.time()
        result = validator.validate(test_data)
        elapsed = time.time() - start

        assert result.is_valid == True
        # 确保在合理时间内完成（< 1秒）
        assert elapsed < 1.0


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
