"""Template 类单元测试"""
import pytest
import io
from PIL import Image

from backend.extract.template import Template
from backend.extract.types import TemplateType


class TestTemplateCreation:
    """测试模板创建"""

    def test_create_basic_template(self):
        """测试创建基本模板"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            min_length=50
        )
        assert template.template_type == "award"
        assert template.keywords == ["蓝桥杯"]
        assert template.min_length == 50
        assert template.max_length == 0

    def test_create_template_with_all_fields(self):
        """测试创建包含所有字段的模板"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯", "省赛"],
            min_length=50,
            max_length=500,
            default_fields={"competition_name": "蓝桥杯"},
            llm_fields={"winner_name": "获奖者姓名"},
            sample_text="样本文本",
            sample_extracted='{"winner_name": "张三"}',
            language="zh",
            need_translate=False
        )
        assert template.default_fields["competition_name"] == "蓝桥杯"
        assert template.llm_fields["winner_name"] == "获奖者姓名"
        assert template.language == "zh"
        assert template.need_translate is False

    def test_invalid_template_type_raises_error(self):
        """测试无效模板类型抛出异常"""
        with pytest.raises(ValueError, match="无效的模板类型"):
            Template(template_type="invalid_type", keywords=[])


class TestTemplateDisplayInfo:
    """测试模板显示信息"""

    def test_get_display_name_award(self):
        """测试获取奖状模板显示名称"""
        template = Template(
            template_type="award",
            keywords=[],
            default_fields={"competition_name": "蓝桥杯"}
        )
        assert template.get_display_name() == "蓝桥杯"

    def test_get_display_name_no_name(self):
        """测试无名称模板的显示名称"""
        template = Template(
            template_type="award",
            keywords=[]
        )
        assert template.get_display_name() == "未命名奖状模板"

    def test_get_type_display_name(self):
        """测试获取类型显示名称"""
        template = Template(template_type="award", keywords=[])
        assert template.get_type_display_name() == "奖状"

    def test_get_field_type(self):
        """测试获取字段类型"""
        template = Template(
            template_type="award",
            keywords=[],
            default_fields={"competition_name": "蓝桥杯"},
            llm_fields={"winner_name": "获奖者姓名"}
        )
        assert template.get_field_type("competition_name") == 'default'
        assert template.get_field_type("winner_name") == 'extract'
        assert template.get_field_type("unknown") == 'empty'


class TestTemplateMatching:
    """测试模板匹配功能"""

    def test_match_by_keywords_all_match(self):
        """测试关键词全匹配"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯", "省赛"]
        )
        ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛省赛获奖证书"
        assert template.match_by_keywords(ocr_text) is True

    def test_match_by_keywords_partial_match(self):
        """测试关键词部分匹配（应返回 False）"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯", "省赛", "一等奖"]
        )
        ocr_text = "蓝桥杯省赛获奖证书"  # 缺少"一等奖"
        assert template.match_by_keywords(ocr_text) is False

    def test_match_by_keywords_no_match(self):
        """测试关键词不匹配"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"]
        )
        ocr_text = "数据安全竞赛获奖证书"
        assert template.match_by_keywords(ocr_text) is False

    def test_match_by_keywords_empty_text(self):
        """测试空文本"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"]
        )
        assert template.match_by_keywords("") is False
        assert template.match_by_keywords(None) is False

    def test_match_score_below_min_length(self):
        """测试低于最小长度返回 0.0"""
        template = Template(
            template_type="award",
            keywords=[],
            min_length=100
        )
        ocr_text = "短文本"
        assert template.match_score(ocr_text) == 0.0

    def test_match_score_above_max_length(self):
        """测试超过最大长度返回 0.0"""
        template = Template(
            template_type="award",
            keywords=[],
            min_length=0,
            max_length=100
        )
        ocr_text = "a" * 200  # 超过最大长度
        assert template.match_score(ocr_text) == 0.0

    def test_match_score_with_sample_text(self):
        """测试有样本文本的相似度计算"""
        template = Template(
            template_type="award",
            keywords=[],
            min_length=10,
            sample_text="蓝桥杯全国软件和信息技术专业人才大赛"
        )
        ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛"
        score = template.match_score(ocr_text)
        assert score > 0.8  # 高相似度

    def test_match_score_no_sample_text(self):
        """测试无样本文本返回 1.0"""
        template = Template(
            template_type="award",
            keywords=[],
            min_length=0  # 设置为 0 以确保测试文本能通过长度检查
        )
        ocr_text = "任意文本内容"
        score = template.match_score(ocr_text)
        # 无样本且通过长度检查时，应该返回 1.0
        assert score == 1.0

    def test_match_score_with_keywords(self):
        """测试带关键词的分数计算"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            min_length=5  # 降低最小长度要求
        )
        ocr_text = "蓝桥杯获奖证书"
        score = template.match_score(ocr_text)
        # 有关键词匹配且通过长度检查
        assert score == 1.0

    def test_match_score_keywords_not_matched(self):
        """测试关键词不匹配返回 0.0"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            min_length=10
        )
        ocr_text = "其他竞赛获奖证书"
        score = template.match_score(ocr_text)
        assert score == 0.0


class TestTemplatePromptGeneration:
    """测试提示词生成"""

    def test_generate_prompt_with_sample(self, sample_template_data):
        """测试生成带样本的提示词"""
        template = Template.from_dict(sample_template_data)
        base_fields = {
            "winner_name": "获奖者姓名",
            "award_level": "获奖等级"
        }
        ocr_text = "蓝桥杯获奖证书"
        prompt = template.generate_prompt(ocr_text, base_fields)
        assert "蓝桥杯获奖证书" in prompt
        assert "winner_name" in prompt
        # 新实现使用不同的格式，检查样本存在
        assert template.sample_extracted in prompt
        assert "is_valid_certificate" in prompt  # 奖状类型有验证

    def test_generate_prompt_without_sample(self):
        """测试生成无样本的提示词"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            default_fields={"competition_name": "蓝桥杯"}
        )
        base_fields = {"winner_name": "获奖者姓名"}
        ocr_text = "蓝桥杯获奖证书"
        prompt = template.generate_prompt(ocr_text, base_fields)
        assert "蓝桥杯获奖证书" in prompt
        assert "例如针对【】" not in prompt  # 无样本

    def test_generate_prompt_english_with_translate(self):
        """测试英文模板带翻译"""
        template = Template(
            template_type="award",
            keywords=[],
            language="en",
            need_translate=True,
            default_fields={"granted_role": "学生"}
        )
        base_fields = {"winner_name": "Winner name"}
        ocr_text = "Certificate of Achievement"
        prompt = template.generate_prompt(ocr_text, base_fields)
        assert "英文" in prompt
        assert "人名保持原文" in prompt
        assert "其他内容翻译" in prompt

    def test_generate_prompt_english_no_translate(self):
        """测试英文模板不带翻译"""
        template = Template(
            template_type="award",
            keywords=[],
            language="en",
            need_translate=False,
            default_fields={"granted_role": "学生"}
        )
        base_fields = {"winner_name": "Winner name"}
        ocr_text = "Certificate"
        prompt = template.generate_prompt(ocr_text, base_fields)
        # 不需要翻译时不应该有翻译说明
        assert "人名保持原文" not in prompt
        assert "其他内容翻译" not in prompt
        # 应该包含 OCR 文本
        assert "Certificate" in prompt

    def test_generate_prompt_patent_type(self):
        """测试专利类型提示词（无 is_valid_certificate）"""
        template = Template(
            template_type="patent",
            keywords=[],
            default_fields={"patent_type": "发明专利"}
        )
        base_fields = {"patent_name": "专利名称"}
        ocr_text = "专利证书"
        prompt = template.generate_prompt(ocr_text, base_fields)
        assert "专利" in prompt
        assert "is_valid_certificate" not in prompt  # 非奖状类型


class TestTemplateResultCompletion:
    """测试结果补全"""

    def test_complete_result_with_default_fields(self):
        """测试补全默认字段"""
        template = Template(
            template_type="award",
            keywords=[],
            default_fields={
                "competition_name": "蓝桥杯",
                "granted_role": "学生"
            }
        )
        base_fields = {
            "winner_name": "获奖者姓名",
            "award_level": "获奖等级"
        }
        extracted = {"winner_name": "张三"}
        result = template.complete_result(extracted, base_fields)
        assert result["competition_name"] == "蓝桥杯"
        assert result["winner_name"] == "张三"
        assert result["award_level"] is None  # 缺失字段填充 null

    def test_complete_result_none_extracted(self):
        """测试抽取结果为 None"""
        template = Template(
            template_type="award",
            keywords=[],
            default_fields={"competition_name": "蓝桥杯"}
        )
        base_fields = {"winner_name": "获奖者姓名"}
        result = template.complete_result(None, base_fields)
        assert result["competition_name"] == "蓝桥杯"
        assert result["winner_name"] is None


class TestTemplateSerialization:
    """测试模板序列化"""

    def test_to_dict_without_image(self):
        """测试转换为字典（不包含图片）"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            template_id=1,
            default_fields={"competition_name": "蓝桥杯"}
        )
        data = template.to_dict(include_image=False)
        assert data["type"] == "award"
        assert data["keywords"] == ["蓝桥杯"]
        assert data["template_id"] == 1
        assert "sample_image_blob" not in data

    def test_to_dict_with_image(self):
        """测试转换为字典（包含图片）"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            template_id=1,
            sample_image_blob=b"\x89PNG\r\n\x1a\n"  # PNG 文件头
        )
        data = template.to_dict(include_image=True)
        assert "sample_image_blob" in data
        assert data["sample_image_blob"].startswith("89504e47")

    def test_from_dict(self, sample_template_data):
        """测试从字典创建"""
        template = Template.from_dict(sample_template_data)
        assert template.template_type == "award"
        assert template.keywords == ["蓝桥杯", "省赛"]
        assert template.default_fields["competition_name"] == "蓝桥杯"

    def test_from_dict_roundtrip(self, sample_template_data):
        """测试序列化和反序列化往返"""
        template1 = Template.from_dict(sample_template_data)
        data = template1.to_dict(include_image=False)
        template2 = Template.from_dict(data)
        assert template2.template_type == template1.template_type
        assert template2.keywords == template1.keywords


class TestTemplateImageCompression:
    """测试图片压缩"""

    def test_compress_image_basic(self):
        """测试基本图片压缩功能"""
        template = Template(template_type="award", keywords=[])
        # 创建一个简单的测试图片
        img = Image.new('RGB', (1000, 1000), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()

        compressed = template.compress_image(image_bytes, max_size_kb=100)
        assert len(compressed) < 100 * 1024  # 小于 100KB

    def test_compress_image_already_small(self):
        """测试已经小于目标大小的图片"""
        template = Template(template_type="award", keywords=[])
        img = Image.new('RGB', (100, 100), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=95)
        image_bytes = buffer.getvalue()

        compressed = template.compress_image(image_bytes, max_size_kb=500)
        # 已经很小，应该保持原样或稍微变化
        assert len(compressed) <= len(image_bytes) + 1000


class TestTemplateStringRepresentation:
    """测试字符串表示"""

    def test_str(self):
        """测试 __str__ 方法"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            template_id=1,
            default_fields={"competition_name": "蓝桥杯"}
        )
        str_repr = str(template)
        assert "Template" in str_repr
        assert "1" in str_repr
        assert "award" in str_repr or "奖状" in str_repr
        assert "蓝桥杯" in str_repr

    def test_repr(self):
        """测试 __repr__ 方法"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            template_id=1
        )
        assert repr(template) == str(template)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
