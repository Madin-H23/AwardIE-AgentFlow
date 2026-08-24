> ⚠️ 已归档（2026-08-24）：本文档为历史资料，不反映项目现状。现行权威文档见 docs/README.md 路由。

# 模板模块测试指南

**文档日期**: 2026-01-23
**适用范围**: backend/extract/template/ 模块测试

---

## 一、测试概述

### 1.1 测试目标

1. **单元测试**：测试各个类和方法的独立功能
2. **集成测试**：测试模板匹配的完整流程
3. **实际验证**：使用真实奖状图片验证匹配效果

### 1.2 测试图片来源

测试图片位于 `images/测试图片/奖状/` 目录：

| 文件名 | 类型 | 预期匹配模板 |
|--------|------|--------------|
| 蓝桥杯教师_国赛_项目实战赛_项目实战赛-智能体开发大学组_二等奖_陈品天_阴爱英.jpg | 奖状(教师) | 蓝桥杯教师模板 |
| 2024数据安全-李杰-省赛-二等奖.jpg | 奖状(学生) | 数据安全竞赛模板 |
| 2024数据安全-颜琪原等-省赛-三等奖.jpg | 奖状(学生) | 数据安全竞赛模板 |
| 2025ciscn-吴凌森等-国赛-二等奖.jpg | 奖状(学生) | CISCN模板 |
| 2025蓝桥杯网络安全赛道-陈鸿秋-省赛-二等奖.jpg | 奖状(学生) | 蓝桥杯模板 |
| 数据大赛-省二.jpg | 奖状(学生) | 数据大赛模板 |
| 睿抗-国家一等奖-高映轩.jpg | 奖状(学生) | 睿抗模板 |
| 大学生信息安全铁人三项-国家二等奖.jpg | 奖状(学生) | 信息安全铁人三项模板 |
| 全国大学生信息安全与对抗技术-国家一等奖-颜琪原.png | 奖状(学生) | 信息安全与对抗技术模板 |
| 全国高校计算机能力挑战-国家三等奖-曾慧珍.jpg | 奖状(学生) | 计算机能力挑战赛模板 |
| 2024支付宝小程序国家二等奖.jpg | 奖状(学生) | 支付宝小程序模板（可能无模板） |
| 国际奖-马景川.jfif | 奖状(学生) | 国际奖模板（可能无模板） |
| 初中竞赛奖状.pdf | 奖状(学生) | 可能无匹配模板 |
| 英文奖状1.jpg | 奖状(学生) | 英文奖状模板 |
| MCIM2.jpg | 奖状(学生) | MCIM模板（可能无模板） |
| acm.jpg | 奖状(学生) | ACM模板（可能无模板） |

### 1.3 测试结果参考

根据 `tests/reports/批量图片抽取测试(ver1).html` 报告：

- **有模板匹配成功**：蓝桥杯、数据安全、睿抗、全国大学生信息安全与对抗技术、全国高校计算机能力挑战赛
- **有模板但验证失败**：CISCN、蓝桥杯网络安全赛道、信息安全铁人三项
- **无模板匹配**：支付宝小程序、国际奖、初中竞赛、MCIM、ACM

---

## 二、单元测试

### 2.1 测试文件结构

```
tests/extract/
├── __init__.py
├── conftest.py                    # pytest fixtures
├── test_template.py               # Template 类测试
├── test_manager.py                # TemplateManager 类测试
├── test_matcher.py                # 模板匹配器测试
├── test_competition_matcher.py    # CompetitionMatcher 测试
└── integration/
    ├── __init__.py
    └── test_template_matching.py  # 集成测试
```

### 2.2 conftest.py - Fixtures 配置

```python
"""pytest 配置和 fixtures"""
import pytest
import sqlite3
from pathlib import Path
from backend.extract.template import Template, TemplateManager

@pytest.fixture
def test_db_path(tmp_path):
    """创建临时测试数据库"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    # 创建测试表结构
    conn.execute("""
        CREATE TABLE templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_type TEXT NOT NULL,
            min_length INTEGER DEFAULT 0,
            max_length INTEGER DEFAULT 0,
            keywords TEXT,
            sample_text TEXT,
            sample_extracted TEXT,
            default_fields TEXT,
            llm_fields TEXT,
            language TEXT DEFAULT 'zh',
            need_translate INTEGER DEFAULT 0,
            is_manual_edited INTEGER DEFAULT 0,
            sample_image_blob BLOB,
            competition_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture
def sample_template():
    """示例模板 fixture"""
    return Template(
        template_type="award",
        keywords=["蓝桥杯", "省赛"],
        min_length=50,
        default_fields={
            "competition_name": "蓝桥杯",
            "granted_role": "学生"
        },
        sample_text="蓝桥杯全国软件和信息技术专业人才大赛获奖证书获得者：张三",
        sample_extracted='{"winner_name": "张三", "award_level": "一等奖"}'
    )


@pytest.fixture
def ocr_text_samples():
    """OCR 文本样本 fixture"""
    return {
        "蓝桥杯省赛": "蓝桥杯全国软件和信息技术专业人才大赛省赛获奖证书获得者：李明",
        "数据安全": "数据安全竞赛省赛二等奖获奖者：王芳",
        "无匹配": "这是一段普通的文本，不包含任何竞赛关键词"
    }


@pytest.fixture
def manager_with_templates(test_db_path, sample_template):
    """包含模板的管理器 fixture"""
    manager = TemplateManager(db_path=test_db_path)
    manager.add_template(sample_template)
    return manager
```

### 2.3 test_template.py - Template 类测试

```python
"""Template 类单元测试"""
import pytest
from backend.extract.template import Template

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

    def test_invalid_template_type_raises_error(self):
        """测试无效模板类型抛出异常"""
        with pytest.raises(ValueError):
            Template(template_type="invalid_type", keywords=[])


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
            min_length=10
        )
        ocr_text = "任意文本内容"
        assert template.match_score(ocr_text) == 1.0


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

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "type": "award",
            "keywords": ["蓝桥杯"],
            "template_id": 1,
            "default_fields": {"competition_name": "蓝桥杯"}
        }
        template = Template.from_dict(data)
        assert template.template_type == "award"
        assert template.keywords == ["蓝桥杯"]
        assert template.template_id == 1


class TestTemplatePromptGeneration:
    """测试提示词生成"""

    def test_generate_prompt_with_sample(self, sample_template):
        """测试生成带样本的提示词"""
        base_fields = {
            "winner_name": "获奖者姓名",
            "award_level": "获奖等级"
        }
        ocr_text = "蓝桥杯获奖证书"
        prompt = sample_template.generate_prompt(ocr_text, base_fields)
        assert "蓝桥杯获奖证书" in prompt
        assert "winner_name" in prompt
        assert "例如针对【】中的OCR文本" in prompt

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


class TestTemplateResultCompletion:
    """测试结果补全"""

    def test_complete_result_with_default_fields(self):
        """测试补全默认字段"""
        template = Template(
            template_type="award",
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


class TestTemplateImageCompression:
    """测试图片压缩"""

    def test_compress_image(self):
        """测试图片压缩功能"""
        template = Template(template_type="award", keywords=[])
        # 创建一个简单的测试图片（1x1 红色像素）
        from PIL import Image
        import io
        img = Image.new('RGB', (1000, 1000), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()

        compressed = template.compress_image(image_bytes, max_size_kb=100)
        assert len(compressed) < 100 * 1024  # 小于 100KB
```

### 2.4 test_manager.py - TemplateManager 类测试

```python
"""TemplateManager 类单元测试"""
import pytest
from backend.extract.template import TemplateManager, Template

class TestTemplateManagerCreation:
    """测试管理器创建"""

    def test_create_manager(self, test_db_path):
        """测试创建管理器"""
        manager = TemplateManager(db_path=test_db_path)
        assert manager.get_template_count() == 0

    def test_load_templates_from_db(self, test_db_path, sample_template):
        """测试从数据库加载模板"""
        # 先添加一个模板
        manager1 = TemplateManager(db_path=test_db_path)
        manager1.add_template(sample_template)

        # 创建新管理器，应能加载到模板
        manager2 = TemplateManager(db_path=test_db_path)
        assert manager2.get_template_count() == 1


class TestTemplateCRUD:
    """测试模板 CRUD 操作"""

    def test_add_template(self, manager_with_templates):
        """测试添加模板"""
        manager = manager_with_templates
        initial_count = manager.get_template_count()

        new_template = Template(
            template_type="award",
            keywords=["数据安全"],
            default_fields={"competition_name": "数据安全竞赛"}
        )
        result = manager.add_template(new_template)

        assert result is True
        assert manager.get_template_count() == initial_count + 1

    def test_add_duplicate_template_fails(self, manager_with_templates, sample_template):
        """测试添加重复模板失败"""
        manager = manager_with_templates
        # 尝试添加相同类型和名称的模板
        result = manager.add_template(sample_template)
        assert result is False

    def test_get_template_by_id(self, manager_with_templates, sample_template):
        """测试根据 ID 获取模板"""
        manager = manager_with_templates
        template = manager.get_template(sample_template.template_id)
        assert template is not None
        assert template.template_id == sample_template.template_id

    def test_get_template_by_invalid_id(self, manager_with_templates):
        """测试获取不存在的模板"""
        manager = manager_with_templates
        template = manager.get_template(99999)
        assert template is None

    def test_get_templates_by_type(self, test_db_path):
        """测试根据类型获取模板"""
        manager = TemplateManager(db_path=test_db_path)

        # 添加不同类型的模板
        award_template = Template(template_type="award", keywords=["奖状"])
        patent_template = Template(template_type="patent", keywords=["专利"])

        manager.add_template(award_template)
        manager.add_template(patent_template)

        award_templates = manager.get_templates_by_type("award")
        patent_templates = manager.get_templates_by_type("patent")

        assert len(award_templates) == 1
        assert len(patent_templates) == 1
        assert award_templates[0].template_type == "award"

    def test_delete_template(self, manager_with_templates):
        """测试删除模板"""
        manager = manager_with_templates
        initial_count = manager.get_template_count()
        template_id = manager.templates[0].template_id

        result = manager.delete_template(template_id)

        assert result is True
        assert manager.get_template_count() == initial_count - 1

    def test_clear_all_templates(self, manager_with_templates):
        """测试清空所有模板"""
        manager = manager_with_templates
        manager.clear_templates()
        assert manager.get_template_count() == 0


class TestTemplateMatching:
    """测试模板匹配功能"""

    def test_match_template_by_keywords(self, manager_with_templates, ocr_text_samples):
        """测试关键词匹配模板"""
        manager = manager_with_templates
        template = manager.match_template(ocr_text_samples["蓝桥杯省赛"])
        assert template is not None
        assert "蓝桥杯" in template.keywords

    def test_match_template_no_match(self, manager_with_templates, ocr_text_samples):
        """测试无匹配模板"""
        manager = manager_with_templates
        template = manager.match_template(ocr_text_samples["无匹配"])
        assert template is None

    def test_match_type_award(self, manager_with_templates, ocr_text_samples):
        """测试识别奖状类型"""
        manager = manager_with_templates
        doc_type = manager.match_type(ocr_text_samples["蓝桥杯省赛"])
        assert doc_type == "award"


class TestTemplateStats:
    """测试统计功能"""

    def test_get_stats(self, test_db_path):
        """测试获取统计信息"""
        manager = TemplateManager(db_path=test_db_path)

        # 添加多个模板
        manager.add_template(Template(template_type="award", keywords=["奖状1"]))
        manager.add_template(Template(template_type="award", keywords=["奖状2"]))
        manager.add_template(Template(template_type="patent", keywords=["专利"]))

        stats = manager.get_stats()
        assert stats["total"] == 3
        assert stats["by_type"]["奖状"] == 2
        assert stats["by_type"]["专利"] == 1
```

### 2.5 test_matcher.py - 模板匹配器测试

```python
"""模板匹配器单元测试"""
import pytest
from backend.extract.template import Template, TemplateMatcher, TypeMatcher, MatchResult

class TestTypeMatcher:
    """测试类型匹配器"""

    def test_match_award_type(self):
        """测试识别奖状类型"""
        ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛获奖证书"
        doc_type = TypeMatcher.match(ocr_text)
        assert doc_type == "award"

    def test_match_patent_type(self):
        """测试识别专利类型"""
        ocr_text = "专利证书发明人：张三专利号：123456"
        doc_type = TypeMatcher.match(ocr_text)
        assert doc_type == "patent"

    def test_match_software_type(self):
        """测试识别软著类型"""
        ocr_text = "软件著作权登记证书软件名称：XXX"
        doc_type = TypeMatcher.match(ocr_text)
        assert doc_type == "software"

    def test_match_other_type(self):
        """测试识别其他类型"""
        ocr_text = "这是一段普通的文本，不包含任何证书特征"
        doc_type = TypeMatcher.match(ocr_text)
        assert doc_type == "other"


class TestTemplateMatcher:
    """测试模板匹配器"""

    @pytest.fixture
    def templates(self):
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

    def test_match_full_with_keyword_match(self, templates):
        """测试完整匹配流程（关键词匹配）"""
        ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛省赛获奖证书"
        default_prompts = {"award": "默认提示词"}

        result = TemplateMatcher.match_full(ocr_text, templates, default_prompts)

        assert result.type == "award"
        assert result.template is not None
        assert result.template.template_id == 1  # 蓝桥杯学生模板
        assert result.similarity == 1.0
        assert result.default_prompt is None

    def test_match_full_selects_template_with_more_keywords(self, templates):
        """测试选择关键词更多的模板"""
        ocr_text = "蓝桥杯优秀指导教师省赛获奖证书"
        default_prompts = {"award": "默认提示词"}

        result = TemplateMatcher.match_full(ocr_text, templates, default_prompts)

        assert result.template is not None
        assert result.template.template_id == 2  # 蓝桥杯教师模板（2个关键词）

    def test_match_full_no_match_returns_default_prompt(self, templates):
        """测试无匹配时返回默认提示词"""
        ocr_text = "未知竞赛获奖证书"
        default_prompts = {"award": "默认提示词"}

        result = TemplateMatcher.match_full(ocr_text, templates, default_prompts)

        assert result.type == "award"
        assert result.template is None
        assert result.default_prompt == "默认提示词"
```

---

## 三、集成测试

### 3.1 test_template_matching.py - 完整流程测试

```python
"""模板匹配集成测试"""
import pytest
from pathlib import Path
from backend.ocr import OCREngine
from backend.extract.template import TemplateManager, Template
from backend.extract.extractors import CertificateExtractor

class TestRealImageMatching:
    """使用真实图片的模板匹配测试"""

    @pytest.fixture
    def test_images_dir(self):
        """测试图片目录"""
        return Path("images/测试图片/奖状")

    @pytest.fixture
    def manager(self, test_db_path):
        """初始化带模板的管理器"""
        manager = TemplateManager(db_path=test_db_path)

        # 添加常用模板
        templates = [
            Template(
                template_type="award",
                keywords=["蓝桥杯"],
                default_fields={"competition_name": "蓝桥杯", "granted_role": "学生"}
            ),
            Template(
                template_type="award",
                keywords=["蓝桥杯", "优秀指导教师"],
                default_fields={"competition_name": "蓝桥杯", "granted_role": "教师"}
            ),
            Template(
                template_type="award",
                keywords=["数据安全"],
                default_fields={"competition_name": "数据安全竞赛", "granted_role": "学生"}
            ),
            Template(
                template_type="award",
                keywords=["睿抗"],
                default_fields={"competition_name": "睿抗", "granted_role": "学生"}
            ),
            Template(
                template_type="award",
                keywords=["信息安全与对抗技术"],
                default_fields={"competition_name": "全国大学生信息安全与对抗技术", "granted_role": "学生"}
            ),
            Template(
                template_type="award",
                keywords=["计算机能力挑战"],
                default_fields={"competition_name": "全国高校计算机能力挑战赛", "granted_role": "学生"}
            )
        ]

        for template in templates:
            manager.add_template(template)

        return manager

    @pytest.mark.parametrize("filename,expected_competition,has_template", [
        ("蓝桥杯教师_国赛_项目实战赛_项目实战赛-智能体开发大学组_二等奖_陈品天_阴爱英.jpg", "蓝桥杯", True),
        ("2024数据安全-李杰-省赛-二等奖.jpg", "数据安全竞赛", True),
        ("2024数据安全-颜琪原等-省赛-三等奖.jpg", "数据安全竞赛", True),
        ("睿抗-国家一等奖-高映轩.jpg", "睿抗", True),
        ("全国大学生信息安全与对抗技术-国家一等奖-颜琪原.png", "全国大学生信息安全与对抗技术", True),
        ("全国大学生信息安全与对抗技术国家一等奖林宇轩.png", "全国大学生信息安全与对抗技术", True),
        ("全国高校计算机能力挑战-国家三等奖-曾慧珍.jpg", "全国高校计算机能力挑战赛", True),
        ("2024支付宝小程序国家二等奖.jpg", None, False),
        ("国际奖-马景川.jfif", None, False),
        ("初中竞赛奖状.pdf", None, False),
    ])
    def test_match_real_images(self, manager, test_images_dir, filename, expected_competition, has_template):
        """测试真实图片的模板匹配

        测试图片展示：
        ![测试图片](../../../images/测试图片/奖状/{{filename}})

        预期结果：
        - has_template=True: 应匹配到模板
        - has_template=False: 应不匹配模板（使用默认提示词）
        """
        image_path = test_images_dir / filename

        if not image_path.exists():
            pytest.skip(f"测试图片不存在: {filename}")

        # 获取 OCR 文本
        ocr_engine = OCREngine.from_config_loader(get_config())
        ocr_text, _ = ocr_engine.get_text(str(image_path), use_cache=True, is_precise=False)

        # 匹配模板
        result = manager.match_full(ocr_text)

        if has_template:
            assert result.template is not None, f"{filename} 应该匹配到模板"
            if expected_competition:
                actual = result.template.default_fields.get("competition_name")
                assert actual == expected_competition, f"竞赛名称不匹配: 期望 {expected_competition}, 实际 {actual}"
        else:
            assert result.template is None, f"{filename} 不应该匹配到模板"


class TestTemplateCreationWorkflow:
    """测试模板创建工作流"""

    def test_add_new_template_for_unmatched_certificate(self, test_db_path, test_images_dir):
        """测试：为未匹配的奖状添加新模板后能够匹配

        场景：
        1. 使用现有模板匹配"支付宝小程序"奖状 → 无匹配
        2. 添加支付宝小程序模板
        3. 再次匹配 → 应该成功匹配

        测试图片：
        ![支付宝小程序奖状](../../../images/测试图片/奖状/2024支付宝小程序国家二等奖.jpg)
        """
        # 步骤1：初始无模板匹配
        manager = TemplateManager(db_path=test_db_path)
        manager.add_template(Template(
            template_type="award",
            keywords=["蓝桥杯"],
            default_fields={"competition_name": "蓝桥杯"}
        ))

        image_path = test_images_dir / "2024支付宝小程序国家二等奖.jpg"
        if not image_path.exists():
            pytest.skip("测试图片不存在")

        ocr_engine = OCREngine.from_config_loader(get_config())
        ocr_text, _ = ocr_engine.get_text(str(image_path), use_cache=True, is_precise=False)

        result1 = manager.match_full(ocr_text)
        assert result1.template is None, "初始状态应无模板匹配"

        # 步骤2：添加支付宝小程序模板
        new_template = Template(
            template_type="award",
            keywords=["支付宝", "小程序"],
            default_fields={"competition_name": "支付宝小程序创新大赛", "granted_role": "学生"}
        )
        manager.add_template(new_template)

        # 步骤3：再次匹配应该成功
        result2 = manager.match_full(ocr_text)
        assert result2.template is not None, "添加模板后应该匹配成功"
        assert result2.template.default_fields.get("competition_name") == "支付宝小程序创新大赛"


class TestKeywordPriorityMatching:
    """测试关键词优先级匹配"""

    def test_teacher_template_has_priority_over_student(self, test_db_path):
        """测试：教师模板应优先于学生模板（关键词更多）

        场景：
        - 模板A：关键词=["蓝桥杯"]（学生）
        - 模板B：关键词=["蓝桥杯", "优秀指导教师"]（教师）
        - OCR文本包含"蓝桥杯"和"优秀指导教师"

        预期：应匹配模板B（关键词更多）
        """
        manager = TemplateManager(db_path=test_db_path)

        student_template = Template(
            template_type="award",
            keywords=["蓝桥杯"],
            default_fields={"competition_name": "蓝桥杯", "granted_role": "学生"}
        )
        teacher_template = Template(
            template_type="award",
            keywords=["蓝桥杯", "优秀指导教师"],
            default_fields={"competition_name": "蓝桥杯", "granted_role": "教师"}
        )

        manager.add_template(student_template)
        manager.add_template(teacher_template)

        ocr_text = "蓝桥杯优秀指导教师获奖证书"
        result = manager.match_full(ocr_text)

        assert result.template is not None
        assert result.template.default_fields.get("granted_role") == "教师"


class TestSimilarityMatching:
    """测试相似度匹配"""

    def test_similarity_match_with_sample_text(self, test_db_path):
        """测试基于样本文本的相似度匹配"""
        manager = TemplateManager(db_path=test_db_path)

        template = Template(
            template_type="award",
            keywords=[],  # 无关键词，使用相似度匹配
            min_length=20,
            sample_text="第十五届全国大学生信息安全与对抗技术竞赛获奖证书",
            default_fields={"competition_name": "全国大学生信息安全与对抗技术"}
        )
        manager.add_template(template)

        # 相似的OCR文本（年份不同）
        ocr_text = "第十六届全国大学生信息安全与对抗技术竞赛获奖证书"
        result = manager.match_full(ocr_text)

        assert result.template is not None
        assert result.similarity > 0.7  # 应该有较高相似度
```

---

## 四、测试执行

### 4.1 运行所有测试

```bash
# 运行所有测试
python -m pytest tests/extract/ -v

# 运行单元测试
python -m pytest tests/extract/test_*.py -v

# 运行集成测试
python -m pytest tests/extract/integration/ -v

# 生成HTML报告
python -m pytest tests/extract/ --html=tests/reports/template_test_report.html --self-contained-html
```

### 4.2 运行特定测试

```bash
# 测试 Template 类
python -m pytest tests/extract/test_template.py -v

# 测试模板匹配
python -m pytest tests/extract/test_matcher.py -v

# 测试真实图片匹配
python -m pytest tests/extract/integration/test_template_matching.py::TestRealImageMatching -v
```

---

## 五、测试覆盖率目标

| 模块 | 目标覆盖率 | 说明 |
|------|-----------|------|
| template.py | 90%+ | 核心类，需要充分测试 |
| manager.py | 85%+ | 核心管理类 |
| matcher.py | 85%+ | 核心匹配逻辑 |
| competition.py | 80%+ | 辅助类 |

---

## 六、测试图片清单

### 6.1 有匹配模板的奖状

| 文件名 | 预期模板 | 验证要点 |
|--------|----------|----------|
| <img src="../../../images/测试图片/奖状/蓝桥杯教师_国赛_项目实战赛_项目实战赛-智能体开发大学组_二等奖_陈品天_阴爱英.jpg" width="200"> | 蓝桥杯教师 | 关键词优先级：教师模板 > 学生模板 |
| <img src="../../../images/测试图片/奖状/2024数据安全-李杰-省赛-二等奖.jpg" width="200"> | 数据安全竞赛 | 关键词匹配 |
| <img src="../../../images/测试图片/奖状/2024数据安全-颜琪原等-省赛-三等奖.jpg" width="200"> | 数据安全竞赛 | 相同样本匹配多个奖状 |
| <img src="../../../images/测试图片/奖状/睿抗-国家一等奖-高映轩.jpg" width="200"> | 睿抗 | 关键词匹配 |
| <img src="../../../images/测试图片/奖状/全国大学生信息安全与对抗技术-国家一等奖-颜琪原.png" width="200"> | 信息安全与对抗技术 | 相似度匹配（年份不同） |
| <img src="../../../images/测试图片/奖状/全国高校计算机能力挑战-国家三等奖-曾慧珍.jpg" width="200"> | 计算机能力挑战赛 | 关键词匹配 |

### 6.2 无匹配模板的奖状

| 文件名 | 原因 | 处理方式 |
|--------|------|----------|
| <img src="../../../images/测试图片/奖状/2024支付宝小程序国家二等奖.jpg" width="200"> | 无对应模板 | 使用默认提示词 |
| <img src="../../../images/测试图片/奖状/国际奖-马景川.jfif" width="200"> | 无对应模板 | 使用默认提示词 |
| <img src="../../../images/测试图片/奖状/初中竞赛奖状.pdf" width="200"> | 非大学竞赛 | 使用默认提示词 |
| <img src="../../../images/测试图片/奖状/MCIM2.jpg" width="200"> | 无对应模板 | 使用默认提示词 |
| <img src="../../../images/测试图片/奖状/acm.jpg" width="200"> | 无对应模板 | 使用默认提示词 |

### 6.3 特殊情况测试

| 场景 | 文件名 | 测试点 |
|------|--------|--------|
| 英文奖状 | <img src="../../../images/测试图片/奖状/英文奖状1.jpg" width="200"> | 英文模板匹配和翻译 |
| PDF格式 | <img src="../../../images/测试图片/奖状/初中竞赛奖状.pdf" width="200"> | PDF文件处理 |
| 多人获奖 | <img src="../../../images/测试图片/奖状/2024数据安全-颜琪原等-省赛-三等奖.jpg" width="200"> | 多获奖者抽取 |

---

**文档版本**: 1.0
**最后更新**: 2026-01-23
