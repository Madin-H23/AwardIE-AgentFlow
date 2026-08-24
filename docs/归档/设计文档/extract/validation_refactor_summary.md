> ⚠️ 已归档（2026-08-24）：本文档为历史资料，不反映项目现状。现行权威文档见 docs/README.md 路由。

# 验证架构重构总结

## 变更概述

将验证逻辑从统一的 ExtractorValidator 模块迁移到各个抽取器内部实现，使每个抽取器能够根据自己的业务需求进行独立的验证。

## 设计原则

### 分离关注点

| 验证类型 | 负责模块 | 职责 | 示例 |
|---------|---------|------|------|
| **格式验证** | 抽取器内部 | 领域特定规则 | 学号必须是9位数字 |
| **必需字段检查** | 抽取器内部 | 业务规则验证 | 大创项目必须有项目名称 |
| **值映射** | 配置驱动/LLM Prompt | 数据标准化 | LLM直接返回标准中文值 |

### 原有 ExtractorValidator 的处理

1. **标记为已弃用**：添加 deprecation 警告
2. **保留向后兼容**：framework.py 中的 `_validate_and_return` 方法仍支持旧的 validator
3. **文档说明**：建议通过配置或 LLM prompt 处理值映射

## 修改的文件

### 1. InnovationExtractor (backend/extract/extractors/innovation.py)

**变更：**
- 移除 `self.validator = None`
- 修改 `_validate()` 方法返回 `(validated_projects, ValidationResult)`
- 添加必需字段检查：
  - 项目名称 (必须非空)
  - 年份
  - 项目级别
  - 负责人（姓名和学号）
  - 指导教师

**验证规则：**
```python
# 必需字段 (completeness_issues)
- project_name: 必须非空
- year: 必须存在
- project_level: 必须存在
- leader_name: 必须存在
- leader_student_id: 必须存在且为9位数字
- supervisors: 至少一个

# 格式验证 (content_issues)
- leader_name: 2-5字符，不包含数字
- leader_student_id: 固定9位数字
- members: 学号格式验证
```

### 2. CertificateExtractor (backend/extract/extractors/certificate.py)

**变更：**
- 修改 `_validate_data()` 返回 `ValidationResult` 而不是 `bool`
- 添加 `_validate_specific_fields()` 抽象方法，由子类实现

### 3. PatentExtractor (backend/extract/extractors/certificate.py)

**新增验证方法：**
```python
def _validate_specific_fields(self, data: Dict[str, Any]) -> Dict[str, List[ValidationError]]:
    # 必需字段
    required_fields = {
        "patent_name": "专利名称",
        "patent_type": "专利类型",
        "application_number": "申请号"
    }

    # 格式验证
    - patent_type: 必须是"发明专利"、"实用新型"或"外观设计"
    - application_date: 必须为 YYYY-MM-DD 格式
```

### 4. SoftwareExtractor (backend/extract/extractors/certificate.py)

**新增验证方法：**
```python
def _validate_specific_fields(self, data: Dict[str, Any]) -> Dict[str, List[ValidationError]]:
    # 必需字段
    required_fields = {
        "software_name": "软件名称",
        "registration_number": "登记号"
    }

    # 格式验证
    - registration_date: 必须为 YYYY-MM-DD 格式
```

### 5. ExtractorValidator (backend/extract/validator.py)

**变更：**
- 标记为已弃用
- 添加文档说明验证逻辑现在由各个抽取器内部实现
- 保留类定义用于向后兼容

### 6. Extractor 基类 (backend/extract/extractors/base.py)

**变更：**
- 添加弃用警告（如果传入 validator 参数）
- 更新文档说明

### 7. ExtractFramework (backend/extract/framework.py)

**变更：**
- 修改 `_validate_and_return()` 方法：
  - 优先使用抽取器返回的 `validation_result`
  - 向后兼容支持旧的 `validator` 属性

## 验证输出格式

与原有 document_extract 设计保持一致：

```python
@dataclass
class ValidationResult:
    is_valid: bool                              # 是否通过验证
    content_issues: List[ValidationError]       # 内容问题列表
    completeness_issues: List[ValidationError]  # 完整性问题列表
    mapped_data: Optional[Dict[str, Any]]       # 映射后的数据（预留）
```

### 问题类型

| 类型 | 类别 | 说明 | 示例 |
|------|------|------|------|
| missing | completeness | 缺少必需字段 | 缺少项目名称 |
| invalid | content | 格式不正确 | 学号不是9位数字 |

## 测试结果

### InnovationExtractor 集成测试
- 9个测试全部通过
- 验证正确识别缺失的必需字段

### CertificateExtractor 集成测试
- 10个测试全部通过
- 3个专利文件 + 7个软著文件

### Framework 综合集成测试
- 5个测试全部通过
- 正确路由：other, patent, software, innovation

## 使用示例

### 检查验证结果

```python
result = extractor.extract(context)

# 检查是否有验证问题
if result.validation_result:
    # 内容问题（需要修正）
    for issue in result.validation_result.content_issues:
        print(f"内容问题: {issue.field_name} - {issue.error_message}")
        print(f"  当前值: {issue.invalid_value}")

    # 完整性问题（需要补充）
    for issue in result.validation_result.completeness_issues:
        print(f"完整性问题: {issue.field_name} - {issue.error_message}")

    # 判断是否完全有效
    if result.validation_result.is_valid:
        print("数据验证通过")
    else:
        print("数据存在问题，需要处理")
```

## 迁移指南

### 如果需要值映射功能

原有 ExtractorValidator 的值映射功能可以通过以下方式实现：

1. **配置文件 + 抽取器内部处理**
```python
# config/settings.json
{
  "extract": {
    "innovation": {
      "value_mappings": {
        "project_level": {
          "国家级": "国家级",
          "省级": "省级"
        }
      }
    }
  }
}
```

2. **LLM Prompt 直接要求标准化值**
```python
prompt_template = """请提取项目信息，注意：
- project_level 必须是：国家级、省级、院级之一
- 返回标准化的中文值
"""
```

## 相关文档

- [validation_architecture.md](./validation_architecture.md) - 验证架构设计文档
- [validator.md](./validator.md) - ExtractorValidator 详细文档（已弃用）
- [大创抽取器设计.md](./大创抽取器设计.md) - 大创抽取器设计
- [patent_software_extractors.md](./patent_software_extractors.md) - 专利/软著抽取器设计
