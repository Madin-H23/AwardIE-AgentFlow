> ⚠️ 已归档（2026-08-24）：本文档为历史资料，不反映项目现状。现行权威文档见 docs/README.md 路由。

# 抽取验证架构设计文档

## 1. 架构概述

### 1.1 问题背景

在文档抽取框架中，存在两种不同类型的验证需求：

1. **值映射（Value Mapping）**：将非标准值转换为标准值
   - 例如："Gold Medal" → "金奖"、"区域赛" → "省赛"
   - 这是**跨领域的共同需求**

2. **格式验证（Format Validation）**：验证字段格式是否符合业务规则
   - 例如：学号必须是9位数字、日期格式必须是YYYY-MM-DD
   - 这是**特定领域的业务规则**

### 1.2 架构原则

**分离关注点（Separation of Concerns）**：

```
┌──────────────────────────────────────────────────────────────────┐
│                         ExtractorValidator                        │
│                   统一值映射层 (跨抽取器共享)                        │
│                                                                   │
│  职责:                                                            │
│  - 值标准化 (Value Standardization)                               │
│  - 配置驱动 (Configuration-Driven)                                │
│  - 跨领域一致性 (Cross-Domain Consistency)                        │
│                                                                   │
│  示例:                                                            │
│  "Gold Medal" → "金奖"                                            │
│  "区域赛" → "省赛"                                                │
│  "First Prize" → "一等奖"                                         │
└──────────────────────────────────────────────────────────────────┘
                              ↑ 调用
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐   ┌────────▼────────┐   ┌────────▼────────┐
│  Innovation    │   │  Patent         │   │  Software       │
│  Extractor     │   │  Extractor      │   │  Extractor      │
├────────────────┤   ├─────────────────┤   ├─────────────────┤
│ 职责:          │   │ 职责:            │   │ 职责:            │
│ - Excel解析    │   │ - OCR+LLM抽取    │   │ - OCR+LLM抽取    │
│ - 列名映射     │   │ - 关键词匹配     │   │ - 关键词匹配     │
│ - 数据解析     │   │ - 数据解析       │   │ - 数据解析       │
│               │   │                 │   │                 │
│ 内部验证:      │   │ 内部验证:        │   │ 内部验证:        │
│ - 学号9位数字  │   │ - 申请号格式     │   │ - 登记号格式     │
│ - 姓名2-5字符  │   │ - 公开号格式     │   │ - 证书号格式     │
│ - 日期格式     │   │ - 日期格式       │   │ - 日期格式       │
│ - 成员格式     │   │                 │   │                 │
│               │   │                 │   │                 │
│ 调用:          │   │ 调用:            │   │ 调用:            │
│ Validator进行  │   │ Validator进行    │   │ Validator进行    │
│ 值映射         │   │ 值映射           │   │ 值映射           │
└────────────────┘   └─────────────────┘   └─────────────────┘
```

## 2. 验证类型对比

| 特性 | ExtractorValidator (统一验证器) | 抽取器内部验证 |
|------|--------------------------------|----------------|
| **职责** | 值映射（Value Mapping） | 格式验证（Format Validation） |
| **范围** | 跨领域（所有抽取器共享） | 特定领域（每个抽取器独有） |
| **配置** | `settings.json` 统一配置 | 抽取器代码内部实现 |
| **扩展性** | 配置驱动，易于添加新映射 | 需要修改代码 |
| **示例** | "Gold Medal" → "金奖" | 学号必须是9位数字 |

## 3. ExtractorValidator 的职责

### 3.1 值映射

ExtractorValidator **只做值映射**，不做格式验证：

```python
class ExtractorValidator:
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        # 应用值映射
        mapped = self._apply_mappings(data)
        # 返回映射后的数据（当前不做其他验证）
        return ValidationResult(is_valid=True, mapped_data=mapped)
```

### 3.2 配置示例

```json
{
  "validation": {
    "value_mappings": {
      "award_level": {
        "Gold Medal": "金奖",
        "Silver Medal": "银奖",
        "Bronze Medal": "铜奖",
        "First Prize": "一等奖",
        "Second Prize": "二等奖",
        "Third Prize": "三等奖"
      },
      "competition_level": {
        "区域赛": "省赛",
        "Regional": "省赛"
      },
      "patent_type": {
        "Invention": "发明专利",
        "Utility": "实用新型",
        "Design": "外观设计"
      }
    }
  }
}
```

### 3.3 映射规则

1. **精确匹配**：首先尝试精确匹配原始值
2. **大小写不敏感**：如果精确匹配失败，尝试忽略大小写匹配
3. **保持原值**：如果所有匹配都失败，保持原始值不变

## 4. 抽取器内部验证

### 4.1 InnovationExtractor 内部验证

```python
class DataParser:
    # 学号验证：固定9位数字
    STUDENT_ID_PATTERN = re.compile(r'^\d{9}$')

    # 姓名验证：2-5字符，不包含数字
    NAME_PATTERN = re.compile(r'^[^\d]{2,5}$')

    @classmethod
    def validate_student_id(cls, student_id: str) -> bool:
        """验证学号格式（固定9位数字）"""
        return bool(cls.STUDENT_ID_PATTERN.match(student_id))

    @classmethod
    def validate_name(cls, name: str) -> bool:
        """验证姓名格式（2-5字符，不包含数字）"""
        return bool(cls.NAME_PATTERN.match(name))
```

**为什么在抽取器内部？**
- 学号格式是**大创项目的特定规则**，专利和软著不涉及
- 这是**领域特定逻辑**，不应该放在通用验证器中

### 4.2 CertificateExtractor 内部验证

```python
def _validate_data(self, data: Dict[str, Any]) -> bool:
    """验证抽取数据"""
    # 至少需要有一个非null字段
    for value in data.values():
        if value is not None and value != "":
            return True
    return False
```

**注意**：当前 CertificateExtractor 的验证较弱，可以增强为：

```python
def _validate_data(self, data: Dict[str, Any]) -> bool:
    """验证抽取数据（增强版）"""
    # 必填字段检查
    if self.template_type == "patent":
        required = ["patent_name", "patent_type", "application_number"]
    elif self.template_type == "software":
        required = ["software_name", "registration_number"]
    else:
        required = []

    for field in required:
        if not data.get(field):
            logger.warning(f"必填字段缺失: {field}")
            return False

    # 格式验证
    if "application_date" in data:
        if not self._validate_date_format(data["application_date"]):
            logger.warning(f"日期格式不正确: {data['application_date']}")
            return False

    return True
```

## 5. 集成方式

### 5.1 当前问题

| 抽取器 | Validator 状态 | 问题 |
|--------|----------------|------|
| InnovationExtractor | `self.validator = None` | ❌ 完全未使用 |
| PatentExtractor | 继承但未调用 | ❌ 未集成 |
| SoftwareExtractor | 继承但未调用 | ❌ 未集成 |

### 5.2 建议的集成方式

#### 步骤1：在抽取器中初始化 Validator

```python
class InnovationExtractor(Extractor):
    def __init__(self, config: Dict[str, Any]):
        self._config = config
        # ...

        # 从配置加载验证器
        validation_cfg = config.get("validation", {})
        value_mappings = validation_cfg.get("value_mappings", {})
        self.validator = ExtractorValidator(value_mappings=value_mappings)
```

#### 步骤2：在 extract() 方法中调用

```python
def extract(self, ctx: ExtractContext) -> ExtractResult:
    # ... 执行抽取 ...

    projects = self._extract_projects(...)

    # 1. 内部格式验证
    validated = self._validate(projects)

    # 2. 应用值映射
    if self.validator:
        mapped_projects = []
        for project in validated:
            validation_result = self.validator.validate(project)
            if validation_result.mapped_data:
                mapped_projects.append(validation_result.mapped_data)
            else:
                mapped_projects.append(project)
        validated = mapped_projects

    return ExtractResult(...)
```

### 5.3 调用时机

```
抽取流程:
┌─────────────────────────────────────────────────────────────┐
│ 1. 文件识别 (Extension/Keywords)                             │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. 数据抽取 (OCR/LLM/Excel)                                  │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. 抽取器内部格式验证                                         │
│    - 学号格式、姓名格式、日期格式等                           │
│    - 验证失败 → 记录警告 → 继续处理或跳过                     │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. ExtractorValidator 值映射                                 │
│    - "Gold Medal" → "金奖"                                   │
│    - "区域赛" → "省赛"                                       │
│    - 无映射的值保持不变                                       │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. 返回 ExtractResult                                        │
└─────────────────────────────────────────────────────────────┘
```

## 6. 优势分析

### 6.1 分离关注点

| 层次 | 职责 | 优势 |
|------|------|------|
| ExtractorValidator | 值标准化 | 配置驱动、易于维护、跨抽取器共享 |
| 抽取器内部验证 | 格式验证 | 领域特定、精确控制、灵活扩展 |

### 6.2 可维护性

- **添加新值映射**：只需修改 `settings.json`，无需改代码
- **修改格式规则**：只需修改特定抽取器，不影响其他抽取器
- **测试独立性**：值映射和格式验证可以独立测试

### 6.3 扩展性

- **新增抽取器**：可以复用 ExtractorValidator，只需添加内部格式验证
- **新增验证规则**：可以在 ExtractorValidator 中添加新的值映射规则

## 7. 实现建议

### 7.1 立即改进

1. **修改 InnovationExtractor**：
   - 移除 `self.validator = None`
   - 从配置加载 Validator
   - 在 `_validate()` 之后调用值映射

2. **修改 CertificateExtractor**：
   - 在 `extract()` 方法中，`_validate_data()` 之后调用 Validator
   - 增强 `_validate_data()` 添加格式验证

### 7.2 长期优化

1. **扩展 ExtractorValidator**：
   - 添加枚举值验证（如 award_level 只能是"金奖"、"银奖"等）
   - 添加范围验证（如年份必须在合理范围内）

2. **创建验证规则配置**：
   ```json
   {
     "validation": {
       "rules": {
         "innovation": {
           "student_id": {"pattern": "^\\d{9}$"},
           "start_date": {"format": "YYYY-MM-DD"}
         },
         "patent": {
           "application_number": {"pattern": "^\\d{13}$"},
           "patent_type": {"enum": ["发明专利", "实用新型", "外观设计"]}
         }
       }
     }
   }
   ```

## 8. 相关文档

- [validator.md](./validator.md) - ExtractorValidator 详细文档
- [patent_software_extractors.md](./patent_software_extractors.md) - 专利/软著抽取器设计
- [framework_design.md](./framework_design.md) - 框架整体设计
