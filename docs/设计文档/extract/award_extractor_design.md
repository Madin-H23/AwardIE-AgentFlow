# 奖状抽取器设计文档

**文档日期**: 2026-01-23
**模块**: backend/extract/extractors/award.py
**参考**: patent_software_extractors.md

---

## 一、设计概述

### 1.1 目标

创建 `AwardExtractor` 类，从奖状图片/PDF中提取结构化数据，采用简化验证方案。

### 1.2 设计原则

- 继承 `Extractor` 基类，与 PatentExtractor/SoftwareExtractor 保持一致
- 使用 `TemplateManager` 进行模板匹配
- 简化验证：内部实现 `_validate_specific_fields()` 方法
- 不依赖 validation.db 数据库
- 不依赖 detection 模块

---

## 二、核心功能

### 2.1 抽取流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     AwardExtractor 抽取流程                       │
└─────────────────────────────────────────────────────────────────┘

输入：file_path + ExtractContext
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤1: 检查文件扩展名                                            │
│ - 支持扩展名: .pdf, .jpg, .jpeg, .png, .jfif                     │
└─────────────────────────────────────────────────────────────────┘
    │ 通过
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤2: 快速OCR筛选（可选）                                       │
│ - 使用 RapidOCR 快速识别                                         │
│ - 关键词匹配: 奖、证书、赛、竞赛、比赛、获奖、名次               │
│ - 字数检查: 15-500 字符                                          │
│ - 未通过 → 返回 other                                            │
└─────────────────────────────────────────────────────────────────┘
    │ 通过
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤3: 准确OCR识别                                               │
│ - 使用配置的 OCR 引擎                                            │
│ - 检查缓存                                                       │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤4: 关键词匹配                                                │
│ - 匹配奖状相关关键词                                             │
│ - 未匹配 → 返回 other                                            │
└─────────────────────────────────────────────────────────────────┘
    │ 匹配
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤5: 模板匹配（可选）                                          │
│ - 使用 TemplateManager.match_full()                             │
│ - 获取模板或使用默认提示词                                        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤6: 生成LLM提示词                                             │
│ - 检测英文奖状（英文字符比例 > 70%）                             │
│ - 英文奖状：添加翻译要求                                         │
│ - 使用字段定义生成提示词                                          │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤7: 调用LLM并解析                                            │
│ - 检查缓存                                                       │
│ - 调用 LLM API                                                  │
│ - 解析 JSON 响应                                                 │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤8: 奖状有效性检查                                            │
│ - 检查 is_valid_certificate 字段                                │
│ - 检查 winner_name 是否为空                                    │
│ - 无效 → 返回 other                                              │
└─────────────────────────────────────────────────────────────────┘
    │ 有效
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤9: 清理和合并数据                                            │
│ - 清理字段值（姓名去数字、去空格）                               │
│ - 合并模板默认字段                                               │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤10: 验证数据                                                 │
│ - 必需字段检查                                                   │
│ - 日期格式验证                                                   │
│ - award_level 枚举验证                                           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
输出：ExtractResult (包含 validation_result)
```

### 2.2 快速OCR筛选逻辑

```python
def _quick_screen(self, ocr_text: str) -> bool:
    """
    快速筛选：判断文本是否可能是奖状

    条件（满足其一即可）：
    1. 包含主要关键词 + 字数 15-400
    2. 包含奖状辅助关键词 + 字数 15-500
    3. 包含主要关键词 + 字数 >= 10

    主要关键词: 奖、证书、专利、软件著作权
    奖状辅助关键词: 赛、竞赛、比赛、获奖、名次、第、等、名
    """
```

### 2.3 英文奖状检测

```python
def _is_english_certificate(self, ocr_text: str) -> bool:
    """
    检测是否为英文奖状

    Returns:
        True if 英文字符比例 > 70%
    """
    english_chars = sum(1 for c in ocr_text if c.isascii() and c.isalpha())
    total_chars = sum(1 for c in ocr_text if c.isalpha())
    return total_chars > 0 and english_chars / total_chars > 0.7
```

### 2.4 英文奖状翻译提示

```
**重要翻译要求：**
1. **人名保持原文**：学生姓名、指导教师姓名等所有人名必须保持原文的英文形式
2. **其他内容翻译**：除人名外的所有英文内容必须转换为对应的中文正式表述
   - "Winner" → "获奖者"
   - "First Prize" → "一等奖"
   - "Bronze Medal" → "铜奖"
3. 如果学校名、公司名等有官方中文名，使用官方中文名；否则保持原文
```

---

## 三、字段定义

### 3.1 award_fields.json

```json
{
  "competition_name": "竞赛全称",
  "award_level": "获奖等级（如：一等奖、二等奖、三等奖、优秀奖、金奖、银奖、铜奖等）",
  "winners": "获奖者列表，多人用逗号分隔",
  "winner_name": "获奖者姓名（单人奖状使用）",
  "certificate_id": "证书编号",
  "date": "获奖日期（格式：YYYY-MM或YYYY.MM）",
  "year": "获奖年份",
  "month": "获奖月份",
  "issuer": "颁发单位",
  "province": "省份（如：省赛、国赛）",
  "group_name": "组别",
  "track": "赛道",
  "supervisors": "指导教师列表，多人用逗号分隔",
  "supervisor_name": "指导教师姓名（单人使用）",
  "granted_role": "授予对象身份（学生/教师）",
  "is_valid_certificate": "是否为真实奖状证书（true/false），排除获奖通知、空白模板等"
}
```

### 3.2 奖状级别枚举值

预定义的 award_level 值列表：
- 一等奖、二等奖、三等奖
- 特等奖、优秀奖、鼓励奖
- 金奖、银奖、铜奖
- 国家级、省级、市级
- 国赛、省赛、校赛

---

## 四、验证规则

### 4.1 必需字段

| 字段 | 说明 | 优先级 |
|------|------|--------|
| competition_name | 竞赛名称 | 高 |
| award_level | 获奖等级 | 高 |
| winners 或 winner_name | 获奖者 | 高 |

### 4.2 格式验证

| 字段 | 规则 | 错误类型 |
|------|------|----------|
| date | YYYY-MM 或 YYYY.MM 格式 | invalid |
| award_level | 必须在预定义列表中 | invalid |

### 4.3 奖状有效性检查

| 条件 | 结果 |
|------|------|
| is_valid_certificate == false | 返回 other |
| winner_name 为空 | 返回 other |

---

## 五、类设计

### 5.1 AwardExtractor 类

```python
class AwardExtractor(Extractor):
    """
    奖状抽取器

    从奖状图片/PDF中提取结构化数据。
    支持中文和英文奖状，自动检测并进行翻译。
    """

    template_type = "award"
    fields_name = "award"

    # 关键词配置
    PRIMARY_KEYWORDS = [
        '奖', '证书', '专利', '软件著作权',
        'award', 'certificate', 'patent', 'softwarecopyright'
    ]

    AWARD_KEYWORDS = [
        '赛', '竞赛', '比赛', '获奖', '名次', '第', '等', '名',
        '特等奖', '一等奖', '二等奖', '三等奖', '优秀奖', '鼓励奖',
        'honor', 'prize', 'competition', 'contest', 'winner'
    ]

    AWARD_LEVELS = [
        '特等奖', '一等奖', '二等奖', '三等奖', '优秀奖', '鼓励奖',
        '金奖', '银奖', '铜奖', '国家级', '省级', '市级',
        '国赛', '省赛', '校赛'
    ]

    def __init__(self, config: Dict[str, Any]):
        \"\"\"
        初始化奖状抽取器

        Args:
            config: 配置字典，包含：
                - extensions: 支持的文件扩展名列表
                - keywords: 关键词列表
                - min_confidence: 最小置信度
                - enable_quick_screen: 是否启用快速OCR筛选
        \"\"\"

    def extract(self, ctx: ExtractContext) -> ExtractResult:
        \"\"\"执行抽取\"\"\"

    def _quick_screen(self, ocr_text: str) -> bool:
        \"\"\"快速筛选：判断文本是否可能是奖状\"\"\"

    def _is_english_certificate(self, ocr_text: str) -> bool:
        \"\"\"检测是否为英文奖状\"\"\"

    def _build_prompt(self, ocr_text: str) -> str:
        \"\"\"构建LLM提示词（含英文检测和翻译要求）\"\"\"

    def _check_valid_certificate(self, data: Dict[str, Any]) -> bool:
        \"\"\"检查是否为真实奖状证书\"\"\"

    def _clean_field_value(self, field_name: str, value: Any) -> Any:
        \"\"\"清理字段值（姓名去数字、去空格）\"\"\"

    def _validate_specific_fields(self, data: Dict[str, Any]) -> Dict[str, List[ValidationError]]:
        \"\"\"验证奖状特定字段\"\"\"
```

### 5.2 配置示例

```json
{
  "extract": {
    "award": {
      "extensions": [".pdf", ".jpg", ".jpeg", ".png", ".jfif"],
      "keywords": ["奖", "证书", "赛", "竞赛"],
      "min_confidence": 0.3,
      "enable_quick_screen": true,
      "quick_screen_min_length": 15,
      "quick_screen_max_length": 500,
      "english_ratio_threshold": 0.7
    }
  }
}
```

---

## 六、与 PatentExtractor/SoftwareExtractor 的差异

| 特性 | Patent/Software | Award |
|------|----------------|-------|
| 关键词匹配 | 简单 | 复杂（主要+辅助） |
| 快速OCR筛选 | 无 | 有 |
| 模板匹配 | 无 | 有（使用 TemplateManager） |
| 英文处理 | 无 | 有（翻译要求） |
| 有效性检查 | 无 | 有（is_valid_certificate） |
| 字段清理 | 简单 | 复杂（姓名去数字） |
| 值映射 | 无 | 有（award_level 枚举） |

---

## 七、测试用例

### 7.1 测试图片清单

| 文件名 | 类型 | 预期结果 |
|--------|------|----------|
| 2024数据安全-李杰-省赛-二等奖.jpg | 中文 | 数据安全竞赛，二等奖 |
| 睿抗-国家一等奖-高映轩.jpg | 中文 | 睿抗，一等奖 |
| 全国大学生信息安全与对抗技术-国家一等奖-颜琪原.png | 中文 | 信息安全与对抗技术，一等奖 |
| 全国高校计算机能力挑战-国家三等奖-曾慧珍.jpg | 中文 | 计算机能力挑战赛，三等奖 |
| 2025蓝桥杯网络安全赛道-陈鸿秋-省赛-二等奖.jpg | 中文 | 蓝桥杯，二等奖 |
| 大学生信息安全铁人三项-国家二等奖.jpg | 中文 | 信息安全铁人三项，二等奖 |
| 英文奖状1.jpg | 英文 | 自动翻译为中文 |
| MCIM1.png | 英文 | 自动翻译为中文 |
| acm.jpg | 英文 | 自动翻译为中文 |

### 7.2 单元测试

```python
class TestAwardExtractorCreation:
    """测试抽取器创建"""

    def test_create_award_extractor(self):
        """测试创建奖状抽取器"""
        extractor = AwardExtractor({
            "extensions": [".jpg", ".png"],
            "keywords": ["奖", "证书"]
        })
        assert extractor.name == "award"
        assert extractor.template_type == "award"

class TestQuickScreen:
    """测试快速筛选"""

    def test_valid_award_text_passes(self):
        """测试有效奖状文本通过筛选"""
        text = "蓝桥杯全国软件和信息技术专业人才大赛省赛二等奖获奖证书"
        assert extractor._quick_screen(text) is True

    def test_no_keyword_fails(self):
        """测试无关键词文本失败"""
        text = "这是一段普通的文本，不包含任何关键词"
        assert extractor._quick_screen(text) is False

    def test_too_short_fails(self):
        """测试过短文本失败"""
        text = "获奖证书"  # 4个字符
        assert extractor._quick_screen(text) is False

    def test_too_long_fails(self):
        """测试过长文本失败"""
        text = "a" * 600  # 600个字符
        assert extractor._quick_screen(text) is False

class TestEnglishDetection:
    """测试英文奖状检测"""

    def test_english_certificate_detected(self):
        """测试英文奖状被正确检测"""
        text = "Certificate of Achievement Winner: Zenan Xiang First Prize"
        assert extractor._is_english_certificate(text) is True

    def test_chinese_certificate_not_detected(self):
        """测试中文奖状不被检测为英文"""
        text = "蓝桥杯全国软件和信息技术专业人才大赛获奖证书"
        assert extractor._is_english_certificate(text) is False

class TestValidCertificateCheck:
    """测试奖状有效性检查"""

    def test_valid_certificate_passes(self):
        """测试有效奖状通过检查"""
        data = {
            "is_valid_certificate": True,
            "winner_name": "张三"
        }
        assert extractor._check_valid_certificate(data) is True

    def test_invalid_certificate_fails(self):
        """测试无效奖状失败"""
        data = {
            "is_valid_certificate": False,
            "winner_name": "张三"
        }
        assert extractor._check_valid_certificate(data) is False

    def test_empty_winner_name_fails(self):
        """测试空获奖者姓名失败"""
        data = {
            "is_valid_certificate": True,
            "winner_name": ""
        }
        assert extractor._check_valid_certificate(data) is False

class TestFieldValidation:
    """测试字段验证"""

    def test_missing_required_field(self):
        """测试缺少必需字段"""
        data = {"award_level": "一等奖"}  # 缺少 competition_name
        result = extractor._validate_specific_fields(data)
        assert len(result["completeness"]) > 0

    def test_invalid_date_format(self):
        """测试无效日期格式"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "一等奖",
            "winners": "张三",
            "date": "2024/01/01"  # 错误格式
        }
        result = extractor._validate_specific_fields(data)
        assert any(e.field_name == "date" for e in result["content"])

    def test_invalid_award_level(self):
        """测试无效获奖等级"""
        data = {
            "competition_name": "蓝桥杯",
            "award_level": "First Prize",  # 英文，应翻译
            "winners": "张三"
        }
        result = extractor._validate_specific_fields(data)
        assert any(e.field_name == "award_level" for e in result["content"])
```

### 7.3 集成测试

```python
class TestAwardExtraction:
    """测试奖状抽取完整流程"""

    @pytest.mark.parametrize("filename,expected_competition,expected_level", [
        ("2024数据安全-李杰-省赛-二等奖.jpg", "数据安全竞赛", "二等奖"),
        ("睿抗-国家一等奖-高映轩.jpg", "睿抗", "一等奖"),
        ("全国大学生信息安全与对抗技术-国家一等奖-颜琪原.png", "全国大学生信息安全与对抗技术", "一等奖"),
        ("全国高校计算机能力挑战-国家三等奖-曾慧珍.jpg", "全国高校计算机能力挑战赛", "三等奖"),
    ])
    def test_extract_chinese_award(self, filename, expected_competition, expected_level):
        """测试抽取中文奖状"""
        result = extractor.extract(context)
        assert result.status == ExtractStatus.SUCCESS
        assert result.template_type == "award"
        assert result.data["competition_name"] == expected_competition
        assert result.data["award_level"] == expected_level

    def test_extract_english_award(self):
        """测试抽取英文奖状并翻译"""
        result = extractor.extract(context)
        assert result.status == ExtractStatus.SUCCESS
        # 英文奖状应翻译为中文
        assert result.data["award_level"] in ["一等奖", "二等奖", "三等奖"]

    def test_non_award_returns_other(self):
        """测试非奖状文件返回 other"""
        result = extractor.extract(context)
        assert result.template_type == TemplateType.OTHER

    def test_invalid_certificate_returns_other(self):
        """测试无效证书返回 other"""
        # 获奖通知、空白模板等
        result = extractor.extract(context)
        assert result.template_type == TemplateType.OTHER
```

---

## 八、实现优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 基础抽取流程 | OCR → LLM → 解析 |
| P0 | 必需字段验证 | competition_name, award_level, winners |
| P1 | 快速OCR筛选 | 提高效率 |
| P1 | 英文奖状处理 | 检测和翻译 |
| P1 | 日期格式验证 | YYYY-MM 或 YYYY.MM |
| P2 | award_level 枚举验证 | 值映射 |
| P2 | 奖状有效性检查 | 排除无效证书 |
| P3 | 模板匹配集成 | 使用 TemplateManager |

---

## 九、相关文档

- [patent_software_extractors.md](./patent_software_extractors.md) - 专利软著抽取器设计
- [抽取框架设计.md](./抽取框架设计.md) - 整体架构设计
- [template-testing-guide.md](./template-testing-guide.md) - 模板测试指南
- [AWARD_EXTRACTOR_MIGRATION.md](./AWARD_EXTRACTOR_MIGRATION.md) - 迁移分析

---

**文档版本**: 1.0
**最后更新**: 2026-01-23
**作者**: Claude Code
