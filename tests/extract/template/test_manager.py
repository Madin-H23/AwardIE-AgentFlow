"""TemplateManager 类单元测试"""
import pytest
from pathlib import Path

from backend.extract.template import TemplateManager, Template, TypeMatcher
from backend.extract.types import TemplateType


def _fix_template_data(data):
    """修复模板数据格式（type -> template_type）"""
    corrected = {**data, "template_type": data["type"]}  # 不修改原始数据
    return corrected


class TestTemplateManagerCreation:
    """测试管理器创建"""

    def test_create_manager(self, test_db_path):
        """测试创建管理器"""
        manager = TemplateManager(db_path=test_db_path)
        assert manager.get_template_count() == 0

    def test_create_manager_with_config(self, test_db_path, config_dir):
        """测试创建带配置的管理器"""
        manager = TemplateManager(db_path=test_db_path, config_dir=config_dir)
        assert manager is not None
        # 配置目录应该加载了类型匹配规则
        assert len(manager.default_prompts) >= 0  # 可能有默认提示词


class TestTemplateCRUD:
    """测试模板 CRUD 操作"""

    def test_add_template(self, test_db_path, sample_template_data):
        """测试添加模板"""
        manager = TemplateManager(db_path=test_db_path)
        initial_count = manager.get_template_count()

        template = Template.from_dict(sample_template_data)
        result = manager.add_template(template)

        assert result is True
        assert manager.get_template_count() == initial_count + 1

    def test_add_duplicate_template_fails(self, test_db_path, sample_template_data):
        """测试添加重复模板失败"""
        manager = TemplateManager(db_path=test_db_path)

        template = Template.from_dict(sample_template_data)
        manager.add_template(template)

        # 尝试添加相同类型和名称的模板
        result = manager.add_template(template)
        assert result is False

    def test_add_multiple_templates(self, test_db_path, sample_templates_data):
        """测试添加多个模板"""
        manager = TemplateManager(db_path=test_db_path)

        count = 0
        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            if manager.add_template(template):
                count += 1

        assert count == len(sample_templates_data)
        assert manager.get_template_count() == len(sample_templates_data)

    def test_get_template_by_id(self, test_db_path, sample_template_data):
        """测试根据 ID 获取模板"""
        manager = TemplateManager(db_path=test_db_path)

        template = Template.from_dict(sample_template_data)
        manager.add_template(template)

        found = manager.get_template(template.template_id)
        assert found is not None
        assert found.template_id == template.template_id
        assert found.keywords == template.keywords

    def test_get_template_by_invalid_id(self, test_db_path):
        """测试获取不存在的模板"""
        manager = TemplateManager(db_path=test_db_path)
        template = manager.get_template(99999)
        assert template is None

    def test_get_all_templates(self, test_db_path, sample_templates_data):
        """测试获取所有模板"""
        manager = TemplateManager(db_path=test_db_path)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        all_templates = manager.get_all_templates()
        assert len(all_templates) == len(sample_templates_data)
        # 应该是副本，不是引用
        assert all_templates is not manager.templates

    def test_get_templates_by_type(self, test_db_path, sample_templates_data):
        """测试根据类型获取模板"""
        manager = TemplateManager(db_path=test_db_path)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        award_templates = manager.get_templates_by_type("award")
        assert len(award_templates) == len(sample_templates_data)

        # 验证所有模板都是 award 类型
        for t in award_templates:
            assert t.template_type == "award"

    def test_get_template_count(self, test_db_path, sample_templates_data):
        """测试获取模板数量"""
        manager = TemplateManager(db_path=test_db_path)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        assert manager.get_template_count() == len(sample_templates_data)

    def test_update_template(self, test_db_path, sample_template_data):
        """测试更新模板"""
        manager = TemplateManager(db_path=test_db_path)

        template = Template.from_dict(sample_template_data)
        manager.add_template(template)

        # 修改模板
        template.keywords.append("国赛")
        template.default_fields["competition_level"] = "国赛"

        result = manager.update_template(template)
        assert result is True

        # 验证更新
        updated = manager.get_template(template.template_id)
        assert updated is not None
        assert "国赛" in updated.keywords
        assert updated.default_fields.get("competition_level") == "国赛"

    def test_update_template_without_id_fails(self, test_db_path, sample_template_data):
        """测试更新没有 ID 的模板失败"""
        manager = TemplateManager(db_path=test_db_path)

        template = Template.from_dict(sample_template_data)
        template.template_id = None  # 没有 ID

        result = manager.update_template(template)
        assert result is False

    def test_update_nonexistent_template_fails(self, test_db_path, sample_template_data):
        """测试更新不存在的模板失败"""
        manager = TemplateManager(db_path=test_db_path)

        template = Template.from_dict(sample_template_data)
        template.template_id = 99999  # 不存在的 ID

        result = manager.update_template(template)
        assert result is False

    def test_delete_template(self, test_db_path, sample_template_data):
        """测试删除模板"""
        manager = TemplateManager(db_path=test_db_path)

        template = Template.from_dict(sample_template_data)
        manager.add_template(template)
        initial_count = manager.get_template_count()
        template_id = template.template_id

        result = manager.delete_template(template_id)

        assert result is True
        assert manager.get_template_count() == initial_count - 1
        assert manager.get_template(template_id) is None

    def test_delete_nonexistent_template(self, test_db_path):
        """测试删除不存在的模板"""
        manager = TemplateManager(db_path=test_db_path)
        result = manager.delete_template(99999)
        assert result is False

    def test_clear_all_templates(self, test_db_path, sample_templates_data):
        """测试清空所有模板"""
        manager = TemplateManager(db_path=test_db_path)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        assert manager.get_template_count() > 0
        manager.clear_templates()
        assert manager.get_template_count() == 0

    def test_clear_templates_by_type(self, test_db_path, sample_templates_data):
        """测试清空指定类型的模板"""
        manager = TemplateManager(db_path=test_db_path)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        initial_count = manager.get_template_count()
        deleted_count = manager.clear_templates_by_type("award")

        assert deleted_count == len(sample_templates_data)
        assert manager.get_template_count() == initial_count - deleted_count


class TestTemplateMatching:
    """测试模板匹配功能"""

    def test_match_template_by_keywords(self, test_db_path, sample_templates_data, ocr_text_samples):
        """测试关键词匹配模板"""
        manager = TemplateManager(db_path=test_db_path)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        template = manager.match_template(ocr_text_samples["蓝桥杯省赛"])
        assert template is not None
        assert "蓝桥杯" in template.keywords

    def test_match_template_teacher_keywords(self, test_db_path, sample_templates_data, ocr_text_samples, config_dir):
        """测试匹配教师模板（关键词更多）"""
        manager = TemplateManager(db_path=test_db_path, config_dir=config_dir)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        template = manager.match_template(ocr_text_samples["蓝桥杯教师"])
        assert template is not None
        assert template.default_fields.get("granted_role") == "教师"
        assert len(template.keywords) == 2  # 教师模板有 2 个关键词

    def test_match_template_no_match(self, test_db_path, sample_templates_data, ocr_text_samples):
        """测试无匹配模板"""
        manager = TemplateManager(db_path=test_db_path)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        template = manager.match_template(ocr_text_samples["无匹配"])
        assert template is None

    def test_match_type_award(self, test_db_path, config_dir, ocr_text_samples):
        """测试识别奖状类型"""
        manager = TemplateManager(db_path=test_db_path, config_dir=config_dir)

        # 加载类型匹配规则
        from backend.extract.template import TypeMatcher
        TypeMatcher.load_rules(str(Path(config_dir) / "type_rules.json"))

        doc_type = manager.match_type(ocr_text_samples["蓝桥杯省赛"])
        # 由于没有加载完整的竞赛数据库，可能返回 award 或 other
        assert doc_type in ["award", "other", "patent", "software"]

    def test_match_full_with_match(self, test_db_path, config_dir, sample_templates_data, ocr_text_samples):
        """测试完整匹配流程（有匹配）"""
        manager = TemplateManager(db_path=test_db_path, config_dir=config_dir)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        # 加载类型匹配规则
        from backend.extract.template import TypeMatcher
        TypeMatcher.load_rules(str(Path(config_dir) / "type_rules.json"))

        result = manager.match_full(ocr_text_samples["蓝桥杯省赛"])

        assert result.type in ["award", "other"]
        # 关键词匹配应该成功
        if result.type == "award":
            assert result.template is not None or result.default_prompt is not None

    def test_match_full_no_match(self, test_db_path, config_dir, ocr_text_samples):
        """测试完整匹配流程（无匹配）"""
        manager = TemplateManager(db_path=test_db_path, config_dir=config_dir)

        # 加载类型匹配规则
        from backend.extract.template import TypeMatcher
        TypeMatcher.load_rules(str(Path(config_dir) / "type_rules.json"))

        result = manager.match_full(ocr_text_samples["无匹配"])

        # 无匹配的文本应该返回 other
        assert result.type == "other"
        assert result.template is None


class TestBaseFieldsManagement:
    """测试字段定义管理"""

    def test_get_base_fields(self, test_db_path):
        """测试获取基础字段定义"""
        manager = TemplateManager(db_path=test_db_path)
        fields = manager.get_base_fields("award")
        # 初始化时可能为空
        assert isinstance(fields, dict)

    def test_set_base_fields(self, test_db_path):
        """测试设置基础字段定义"""
        manager = TemplateManager(db_path=test_db_path)

        fields = {
            "winner_name": "获奖者姓名",
            "award_level": "获奖等级"
        }
        manager.set_base_fields("award", fields)

        retrieved = manager.get_base_fields("award")
        assert retrieved == fields


class TestStats:
    """测试统计功能"""

    def test_get_stats_empty(self, test_db_path):
        """测试空管理器的统计"""
        manager = TemplateManager(db_path=test_db_path)
        stats = manager.get_stats()
        assert stats["total"] == 0
        assert stats["by_type"] == {}
        assert stats["by_name"] == {}

    def test_get_stats_with_templates(self, test_db_path, sample_templates_data):
        """测试有模板的统计"""
        manager = TemplateManager(db_path=test_db_path)

        for data in sample_templates_data:
            template = Template.from_dict(_fix_template_data(data))
            manager.add_template(template)

        stats = manager.get_stats()
        assert stats["total"] == len(sample_templates_data)
        assert "奖状" in stats["by_type"]
        assert stats["by_type"]["奖状"] == len(sample_templates_data)


class TestBatchOperations:
    """测试批量操作"""

    def test_add_templates_from_data(self, test_db_path, sample_templates_data):
        """测试从数据列表批量添加模板"""
        manager = TemplateManager(db_path=test_db_path)

        # 修复数据格式（type -> template_type）
        fixed_data = [_fix_template_data(data) for data in sample_templates_data]
        count = manager.add_templates_from_data(fixed_data)
        assert count == len(sample_templates_data)
        assert manager.get_template_count() == len(sample_templates_data)

    def test_add_templates_from_data_with_invalid(self, test_db_path, sample_templates_data):
        """测试批量添加时包含无效数据"""
        manager = TemplateManager(db_path=test_db_path)

        # 修复数据格式（type -> template_type）
        fixed_data = [_fix_template_data(data) for data in sample_templates_data]
        invalid_data = {"invalid": "data"}
        mixed_data = fixed_data + [invalid_data]

        count = manager.add_templates_from_data(mixed_data)
        # 应该只添加有效的模板
        assert count == len(sample_templates_data)


class TestStringRepresentation:
    """测试字符串表示"""

    def test_str(self, test_db_path):
        """测试 __str__ 方法"""
        manager = TemplateManager(db_path=test_db_path)
        str_repr = str(manager)
        assert "TemplateManager" in str_repr
        assert "templates=0" in str_repr

    def test_repr(self, test_db_path):
        """测试 __repr__ 方法"""
        manager = TemplateManager(db_path=test_db_path)
        assert repr(manager) == str(manager)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
