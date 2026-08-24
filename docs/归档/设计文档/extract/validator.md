> ⚠️ 已归档（2026-08-24）：本文档为历史资料，不反映项目现状。现行权威文档见 docs/README.md 路由。

# 抽取验证模块文档

## 1. 概述

抽取验证模块（`ExtractorValidator`）是文档抽取框架中的数据验证组件，负责对抽取结果进行后处理和值标准化。

### 核心功能

1. **值映射（Value Mappings）**：将非标准值映射为标准值
2. **数据验证**：验证抽取数据的完整性和正确性（预留功能）
3. **结果返回**：返回包含映射后数据和验证信息的 `ValidationResult`

### 设计目标

- **数据标准化**：确保抽取的数据使用统一的值（如"金奖"而非"Gold Medal"）
- **可配置性**：所有映射规则通过配置文件定义
- **易扩展性**：预留扩展接口，便于添加更多验证规则

## 2. 核心类结构

### ExtractorValidator

**位置**：`backend/extract/validator.py`

```python
class ExtractorValidator:
    """抽取器验证器"""

    def __init__(self, value_mappings: Dict[str, Dict[str, str]]):
        """
        Args:
            value_mappings: 字段名 -> { 原始值: 映射值 }，用于值标准化
        """
        self.value_mappings = value_mappings or {}

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        先应用 value_mappings，再校验（当前无额外规则，仅映射）

        Returns:
            ValidationResult: 包含映射后的数据和验证结果
        """
```

### ValidationResult

**位置**：`backend/extract/types.py`

```python
@dataclass
class ValidationResult:
    is_valid: bool                              # 是否通过验证
    content_issues: List[ValidationError]       # 内容问题列表
    completeness_issues: List[ValidationError]  # 完整性问题列表
    mapped_data: Optional[Dict[str, Any]]       # 映射后的数据
```

## 3. 配置说明

### 3.1 配置位置

配置文件：`config/settings.json`

配置节：`validation.value_mappings`

### 3.2 配置结构

```json
{
  "validation": {
    "value_mappings": {
      // 竞赛等级映射
      "competition_level": {
        "区域赛": "省赛"
      },
      // 奖项等级映射（英文 -> 中文）
      "award_level": {
        "Bronze Medal": "铜奖",
        "Silver Medal": "银奖",
        "Gold Medal": "金奖",
        "First Prize": "一等奖",
        "Second Prize": "二等奖",
        "Third Prize": "三等奖",
        "Excellent Award": "优秀奖",
        "Special Prize": "特等奖"
      }
    }
  }
}
```

### 3.3 配置说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `competition_level` | object | 竞赛等级映射，如"区域赛"映射为"省赛" |
| `award_level` | object | 奖项等级映射，英文奖级映射为中文 |
| `patent_type` | object | 专利类型映射（可扩展） |
| `project_level` | object | 项目级别映射（可扩展） |

## 4. 工作原理

### 4.1 验证流程

```
原始数据
    ↓
应用值映射 (value_mappings)
    ↓
标准化数据 (mapped_data)
    ↓
ValidationResult
```

### 4.2 值映射逻辑

1. **精确匹配**：首先尝试精确匹配原始值
2. **大小写不敏感匹配**：如果精确匹配失败，尝试忽略大小写匹配
3. **保持原值**：如果所有匹配都失败，保持原始值不变

### 4.3 映射示例

**输入数据**：
```python
{
    "award_level": "Gold Medal",
    "competition_level": "区域赛",
    "year": "2024"
}
```

**配置映射**：
```python
{
    "award_level": {"Gold Medal": "金奖"},
    "competition_level": {"区域赛": "省赛"}
}
```

**输出数据**：
```python
{
    "award_level": "金奖",
    "competition_level": "省赛",
    "year": "2024"
}
```

## 5. 使用方式

### 5.1 在抽取器中使用

```python
from backend.extract.extractors.base import Extractor
from backend.extract.validator import ExtractorValidator

# 创建验证器
validator = ExtractorValidator(
    value_mappings={
        "award_level": {
            "Gold Medal": "金奖",
            "First Prize": "一等奖"
        }
    }
)

# 在抽取器中使用
class MyExtractor(Extractor):
    def __init__(self, config):
        super().__init__(...)
        self.validator = validator

    def extract(self, ctx):
        # 执行抽取
        result = self._do_extract(ctx)

        # 应用验证
        if self.validator and result.data:
            validation_result = self.validator.validate(result.data)
            result.validation_result = validation_result
            # 使用映射后的数据
            if validation_result.mapped_data:
                result.data = validation_result.mapped_data

        return result
```

### 5.2 在框架中配置

```python
from backend.extract import ExtractFramework
from config import ConfigLoader

config_loader = ConfigLoader(project_root)
framework = ExtractFramework.from_config_loader(config_loader)

# 框架会自动从配置文件加载验证器配置
# 并在抽取过程中自动应用
```

## 6. 验证场景覆盖

### 6.1 已支持的验证场景

| 场景 | 说明 | 状态 |
|------|------|------|
| 精确值映射 | "Gold Medal" → "金奖" | ✓ 支持 |
| 大小写不敏感映射 | "gold medal" → "金奖" | ✓ 支持 |
| 多字段同时映射 | 多个字段同时应用映射 | ✓ 支持 |
| 空值处理 | None/空字符串保持不变 | ✓ 支持 |
| 无映射字段 | 未配置映射的字段保持不变 | ✓ 支持 |

### 6.2 预留扩展场景

| 场景 | 说明 | 状态 |
|------|------|------|
| 枚举值验证 | 验证值是否在允许的枚举列表中 | 预留 |
| 格式验证 | 验证日期、学号等格式 | 预留 |
| 范围验证 | 验证年份、数值范围 | 预留 |
| 必填字段验证 | 验证必填字段是否存在 | 预留 |
| 关联验证 | 验证字段间的逻辑关系 | 预留 |

## 7. 测试用例

### 7.1 单元测试覆盖

测试文件：`tests/extract/unit/test_validator.py`

| 测试用例 | 说明 |
|---------|------|
| test_validate_empty_data | 测试空数据验证 |
| test_validate_with_mapping | 测试精确值映射 |
| test_validate_case_insensitive | 测试大小写不敏感映射 |
| test_validate_no_mapping | 测试无映射字段保持不变 |
| test_validate_null_value | 测试空值处理 |
| test_validate_multiple_fields | 测试多字段同时映射 |
| test_validate_nested_mapping | 测试嵌套映射 |

### 7.2 集成测试覆盖

测试文件：`tests/extract/integration/test_validator_integration.py`

| 测试用例 | 说明 |
|---------|------|
| test_award_level_mapping | 测试奖项等级映射 |
| test_competition_level_mapping | 测试竞赛等级映射 |
| test_full_extraction_with_validation | 测试完整抽取流程+验证 |

## 8. 注意事项

### 8.1 使用建议

1. **集中配置**：所有映射规则应在 `settings.json` 中集中配置
2. **向后兼容**：添加新映射时注意保持已有映射的有效性
3. **测试覆盖**：每次修改映射规则后应运行测试验证
4. **日志记录**：映射过程会记录调试日志，便于问题排查

### 8.2 常见问题

**Q: 为什么映射没有生效？**

A: 检查以下几点：
1. 确认映射配置在 `validation.value_mappings` 中
2. 确认字段名匹配（区分大小写）
3. 确认抽取器设置了 `validator` 属性
4. 查看日志中是否有映射记录

**Q: 如何添加新的映射规则？**

A: 在 `config/settings.json` 的 `validation.value_mappings` 中添加：

```json
{
  "validation": {
    "value_mappings": {
      "your_field": {
        "original_value": "mapped_value"
      }
    }
  }
}
```

**Q: 验证失败会怎样？**

A: 当前版本验证器主要做值映射，不会返回验证失败。所有数据都会通过验证，只是可能被映射为标准值。

## 9. 扩展指南

### 9.1 添加新的验证规则

如需添加更复杂的验证逻辑（如格式验证、范围验证），可以扩展 `ExtractorValidator` 类：

```python
class ExtractorValidator:
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        # 应用值映射
        mapped = self._apply_mappings(data)

        # 执行额外验证
        content_issues = []
        completeness_issues = []

        # 示例：验证日期格式
        if "date" in mapped:
            if not self._is_valid_date(mapped["date"]):
                content_issues.append(
                    ValidationError(
                        field_name="date",
                        error_type="invalid",
                        error_message="日期格式不正确"
                    )
                )

        is_valid = len(content_issues) == 0 and len(completeness_issues) == 0

        return ValidationResult(
            is_valid=is_valid,
            content_issues=content_issues,
            completeness_issues=completeness_issues,
            mapped_data=mapped
        )

    def _is_valid_date(self, date_str: str) -> bool:
        # 实现日期验证逻辑
        pass
```

### 9.2 配置驱动验证

建议通过配置文件定义验证规则，使验证逻辑更加灵活：

```json
{
  "validation": {
    "rules": {
      "date": {
        "format": "YYYY-MM-DD",
        "required": false
      },
      "student_id": {
        "pattern": "^\\d{9}$",
        "required": true
      }
    }
  }
}
```

## 10. 相关文档

- [抽取框架设计文档](./framework_design.md)
- [类型定义](../types.md)
- [配置说明](../../config/README.md)
