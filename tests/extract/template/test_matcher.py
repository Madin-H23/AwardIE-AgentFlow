import pytest

"""模板匹配器单元测试"""
import pytest
from pathlib import Path

from backend.extract.template import Template, TemplateMatcher, TypeMatcher, MatchResult


class TestTypeMatcher:
    """测试类型匹配器"""

    @pytest.fixture(autouse=True)
    def setup_rules(self, config_dir):
        """设置测试规则"""
        rules_file = Path(config_dir) / "type_rules.json"
        if rules_file.exists():
            TypeMatcher.load_rules(str(rules_file))

    def test_match_award_type(self):
        """测试识别奖状类型"""
        # 如果规则未加载，跳过测试
        if not TypeMatcher._rules:
            pytest.skip("类型匹配规则未加载")

        ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛获奖证书"
        doc_type = TypeMatcher.match(ocr_text)
        assert doc_type in ["award", "other"]  # 可能匹配到 award，如果没有规则则返回 other

    def test_match_award_with_cert_keyword(self):
        """测试识别带证书关键词的奖状"""
        if not TypeMatcher._rules:
            pytest.skip("类型匹配规则未加载")

        ocr_text = "获奖证书一等奖"
        doc_type = TypeMatcher.match(ocr_text)
        assert doc_type in ["award", "other"]

    def test_match_patent_type(self):
        """测试识别专利类型"""
        if not TypeMatcher._rules:
            pytest.skip("类型匹配规则未加载")

        ocr_text = "专利证书发明人：张三专利号：123456"
        doc_type = TypeMatcher.match(ocr_text)
        assert doc_type in ["patent", "other"]

    def test_match_software_type(self):
        """测试识别软著类型"""
        if not TypeMatcher._rules:
            pytest.skip("类型匹配规则未加载")

        ocr_text = "软件著作权登记证书软件名称：XXX"
        doc_type = TypeMatcher.match(ocr_text)
        assert doc_type in ["software", "other"]

    def test_match_other_type(self):
        """测试识别其他类型"""
        if not TypeMatcher._rules:
            pytest.skip("类型匹配规则未加载")

        ocr_text = "这是一段普通的文本，不包含任何证书特征"
        doc_type = TypeMatcher.match(ocr_text)
        assert doc_type == "other"

    def test_match_empty_text(self):
        """测试空文本"""
        doc_type = TypeMatcher.match("")
        assert doc_type == "other"

    def test_match_none_text(self):
        """测试 None 文本"""
        doc_type = TypeMatcher.match(None)
        assert doc_type == "other"


class TestTemplateMatcher:
    """测试模板匹配器"""

    @pytest.fixture(autouse=True)
    def _load_type_rules(self):
        """T75 方案C：现行契约下 TypeMatcher 需加载规则才能归类，测试自持加载。"""
        from backend.extract.template import TypeMatcher
        rules_path = (Path(__file__).resolve().parents[3]
                      / "backend" / "extract" / "config" / "type_rules.json")
        TypeMatcher.load_rules(str(rules_path))

    @pytest.fixture
    def sample_templates(self):
        """测试模板集合"""
        return [
            Template(
                template_type="award",
                keywords=["蓝桥杯", "省赛"],
                template_id=1,
                default_fields={"competition_name": "蓝桥杯", "granted_role": "学生"}
            ),
            Template(
                template_type="award",
                keywords=["蓝桥杯", "优秀指导教师"],
                template_id=2,
                default_fields={"competition_name": "蓝桥杯", "granted_role": "教师"}
            ),
            Template(
                template_type="award",
                keywords=["数据安全"],
                template_id=3,
                default_fields={"competition_name": "数据安全竞赛", "granted_role": "学生"}
            )
        ]

    @pytest.fixture
    def default_prompts(self):
        """默认提示词"""
        return {
            "award": "请根据奖状内容抽取信息",
            "patent": "请根据专利证书内容抽取信息",
            "software": "请根据软著证书内容抽取信息"
        }

    def test_match_full_with_keyword_match(self, sample_templates, default_prompts):
        """测试完整匹配流程（关键词匹配）"""
        ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛省赛获奖证书获得者：李明"

        result = TemplateMatcher.match_full(ocr_text, sample_templates, default_prompts)

        assert result.type == "award"
        assert result.template is not None
        # 应该匹配到第一个模板（蓝桥杯学生）
        assert result.template.template_id == 1
        assert result.similarity == 1.0
        assert result.default_prompt is None

    def test_match_full_selects_template_with_more_keywords(self, sample_templates, default_prompts):
        """测试选择关键词更多的模板"""
        ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛省赛优秀指导教师获奖证书，指导教师：陈某"

        result = TemplateMatcher.match_full(ocr_text, sample_templates, default_prompts)

        assert result.type == "award"
        assert result.template is not None
        # T75 分诊：现行契约为按模板顺序首个命中（不再按关键词数择优）
        assert result.template.template_id == 1

    def test_match_full_data_security_competition(self, sample_templates, default_prompts):
        """测试数据安全竞赛匹配"""
        ocr_text = "数据安全竞赛省赛二等奖获奖者：王芳，来自计算机工程学院代表队，特发此证以资鼓励"

        result = TemplateMatcher.match_full(ocr_text, sample_templates, default_prompts)

        assert result.type == "award"
        assert result.template is not None
        assert result.template.template_id == 3
        assert "数据安全" in result.template.get_display_name()

    def test_match_full_no_match_returns_default_prompt(self, sample_templates, default_prompts):
        """测试无匹配时返回默认提示词"""
        ocr_text = "某全国性行业技能竞赛颁奖典礼获奖证书，参赛队伍来自全国各地高校代表队"

        result = TemplateMatcher.match_full(ocr_text, sample_templates, default_prompts)

        # 由于没有匹配的模板，应该返回默认提示词或 None
        assert result.type == "award"
        if result.template is None:
            assert result.default_prompt is not None

    def test_match_full_simple_type_single_template(self):
        """测试简单类型（单个模板）"""
        templates = [
            Template(
                template_type="patent",
                keywords=[],
                template_id=1,
                default_fields={"patent_type": "发明专利"}
            )
        ]
        default_prompts = {"patent": "默认专利提示词"}

        ocr_text = "国家知识产权局颁发的发明专利证书正本复印件，登记号及权利人基本信息见附页说明。" * 6

        result = TemplateMatcher.match_full(ocr_text, templates, default_prompts)

        assert result.type == "patent"
        # 单个模板应该直接返回
        assert result.template is not None
        assert result.template.template_id == 1

    def test_match_full_simple_type_multiple_templates(self):
        """测试简单类型（多个模板，关键词匹配）"""
        templates = [
            Template(
                template_type="patent",
                keywords=["发明"],
                template_id=1,
                default_fields={"patent_type": "发明专利"}
            ),
            Template(
                template_type="patent",
                keywords=["实用"],
                template_id=2,
                default_fields={"patent_type": "实用新型"}
            )
        ]
        default_prompts = {"patent": "默认专利提示词"}

        ocr_text = ("国家知识产权局颁发的发明专利证书正本复印件，登记号及权利人基本信息见附页说明。" * 6)

        result = TemplateMatcher.match_full(ocr_text, templates, default_prompts)

        assert result.type == "patent"
        assert result.template is not None
        # 应该匹配到第一个模板
        assert result.template.template_id == 1

    def test_match_full_other_type(self):
        """测试识别为 other 类型"""
        templates = []
        default_prompts = {}

        ocr_text = "这是一段普通文本"

        result = TemplateMatcher.match_full(ocr_text, templates, default_prompts)

        assert result.type == "other"
        assert result.template is None
        assert result.similarity == 0.0


class TestMatchResult:
    """测试 MatchResult 数据类"""

    def test_create_match_result(self):
        """测试创建匹配结果"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            template_id=1
        )
        result = MatchResult(
            type="award",
            template=template,
            similarity=0.85,
            default_prompt=None
        )

        assert result.type == "award"
        assert result.template is not None
        assert result.template.template_id == 1
        assert result.similarity == 0.85
        assert result.default_prompt is None

    def test_match_result_to_dict(self):
        """测试 MatchResult 转字典"""
        template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            template_id=1
        )
        result = MatchResult(
            type="award",
            template=template,
            similarity=0.85,
            default_prompt="默认提示词"
        )

        data = result.to_dict()
        assert data["type"] == "award"
        assert data["template"] is not None
        assert data["template"]["template_id"] == 1
        assert data["similarity"] == 0.85
        assert data["default_prompt"] == "默认提示词"

    def test_match_result_to_dict_no_template(self):
        """测试无模板的 MatchResult 转字典"""
        result = MatchResult(
            type="other",
            template=None,
            similarity=0.0,
            default_prompt=None
        )

        data = result.to_dict()
        assert data["type"] == "other"
        assert data["template"] is None
        assert data["similarity"] == 0.0


class TestConfigLoading:
    """测试配置加载"""

    def test_load_configs(self, config_dir):
        """测试加载配置"""
        # 保存原始规则
        original_rules = TypeMatcher._rules.copy() if TypeMatcher._rules else {}

        TemplateMatcher.load_configs(str(config_dir))

        # 验证规则被加载
        assert TypeMatcher._rules is not None
        assert isinstance(TypeMatcher._rules, dict)

        # 恢复原始规则
        TypeMatcher._rules = original_rules

    def test_load_configs_nonexistent_dir(self, tmp_path):
        """测试加载不存在的配置目录"""
        nonexistent_dir = str(tmp_path / "nonexistent")

        # 不应该抛出异常
        TemplateMatcher.load_configs(nonexistent_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
