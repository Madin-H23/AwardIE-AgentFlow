# 文档抽取模块 (backend/extract)

## 概述

`backend/extract` 是一个统一的文档抽取框架，从 `backend/document_extract` 重构而来。它提供统一的接口从各种文档（奖状、专利、软著、大创项目等）中提取结构化数据。

### 核心特性

- **统一入口**：单一 API 调用，自动识别文档类型并选择合适的抽取器
- **可扩展架构**：通过注册机制轻松添加新的抽取器
- **模板匹配**：支持基于模板的智能匹配，提高抽取准确率
- **多级缓存**：OCR 和 LLM 缓存，降低成本和延迟
- **验证系统**：内置数据验证和值映射功能

## 文档导航

### 快速开始

- [安装与配置](#安装与配置)
- [基础使用](#基础使用)
- [API 参考](#api-参考)

### 架构设计

- [抽取框架设计](./抽取框架设计.md) - 框架总体架构、类关系、执行流程
- [模板系统设计](./template-migration-plan.md) - 模板管理、匹配机制
- [验证模块设计](./validation_architecture.md) - 数据验证、值映射

### 抽取器文档

- [奖状抽取器](./award_extractor_design.md) - AwardExtractor 设计与实现
- [专利/软著抽取器](./patent_software_extractors.md) - PatentExtractor/SoftwareExtractor
- [大创抽取器](./大创抽取器设计.md) - InnovationExtractor 设计

### LLM 模块

- [LLM 模块设计](./LLM模块设计.md) - LLM 引擎、提供者配置
- [LLM 抽取器选择](./LLM抽取器选择详细说明.md) - 多抽取器时的 LLM 选择机制
- [LLM 测试用例](./LLM测试用例.md) - LLM 相关测试用例

### 测试文档

- [集成测试要求](./集成测试程序的要求.md) - 集成测试规范
- [模板测试指南](./template-testing-guide.md) - 模板测试用例
- [抽取框架测试用例](./抽取框架测试用例.md) - 框架测试用例

### 迁移文档

- [奖状抽取器迁移](./AWARD_EXTRACTOR_MIGRATION.md) - 迁移记录
- [模板迁移计划](./template-migration-plan.md) - 模板系统迁移
- [重构总结](./validation_refactor_summary.md) - 验证模块重构总结
- [模块总结](./EXTRACT_MODULE_SUMMARY.md) - 整体总结

## 安装与配置

### 依赖

模块依赖于以下组件：

- `backend/ocr` - OCR 引擎
- `backend/extract/llm` - LLM 引擎
- `backend/extract/template` - 模板管理
- `database/competitions.db` - 数据库（模板、竞赛数据）

### 配置文件

配置来自 `config/settings.json`：

```json
{
  "extract": {
    "image_extensions": [".jpg", ".jpeg", ".png", ".pdf", ".jfif"],
    "other": {
      "note_no_extension": "不支持的文件扩展名",
      "note_no_match": "无法识别的文档类型"
    },
    "llm_max_text_length": 2000,
    "llm_selector_prompt_template": "..."
  },
  "ocr": {
    "default_provider": "zhipu",
    "providers": {...}
  },
  "llm": {
    "default_provider": "zhipu",
    "providers": {...}
  }
}
```

## 基础使用

### 初始化框架

```python
from backend.extract import ExtractFramework
from config.loader import get_config

# 初始化
config_loader = get_config()
framework = ExtractFramework.from_config_loader(config_loader)

# 注册抽取器
framework.register(AwardExtractor(config, template_manager))
framework.register(PatentExtractor(config, template_manager))
framework.register(SoftwareExtractor(config, template_manager))
```

### 执行抽取

```python
# 简单调用
result = framework.extract("path/to/certificate.jpg")

# 检查结果
if result.status == ExtractStatus.SUCCESS:
    print(f"类型: {result.template_type}")
    print(f"数据: {result.data}")
    print(f"OCR缓存: {result.ocr_cache_hit}")
    print(f"LLM缓存: {result.llm_cache_hit}")
```

## API 参考

### ExtractFramework

| 方法 | 说明 |
|------|------|
| `extract(file_path, use_ocr_cache, use_llm_cache)` | 执行抽取 |
| `register(extractor)` | 注册抽取器 |
| `from_config_loader(config_loader)` | 从配置创建实例 |

### ExtractResult

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `ExtractStatus` | 抽取状态（含 `ocr_error`、`llm_error`） |
| `data` | `Dict` | 抽取的数据；OCR/LLM 失败时为 `{"note": "用户可见提示"}` |
| `error_message` | `str` | 错误说明，与 `data.note` 在异常场景下一致 |
| `template_type` | `str` | 模板类型 (award/patent/software/other) |
| `extractor_name` | `str` | 抽取器名称 |
| `ocr_text` | `str` | OCR 识别的文本 |
| `ocr_cache_hit` | `bool` | OCR 缓存命中 |
| `llm_cache_hit` | `bool` | LLM 缓存命中 |
| `validation_result` | `ValidationResult` | 验证结果 |

**异常与用户提示**：OCR/LLM 失败（如 429、费用不足）时，框架与抽取器会通过 `user_facing_message(exc)` 统一成用户可见文案（如「OCR/LLM 费用不足，无法处理」），并写入 `error_message` 与 `data.note`，便于界面展示。详见 [抽取框架设计 - OCR/LLM 异常与用户可见提示](./抽取框架设计.md#ocrllm-异常与用户可见提示)。

## 目录结构

```
backend/extract/
├── __init__.py              # 框架入口，导出 ExtractFramework
├── exceptions.py            # 自定义异常
├── types.py                 # 数据类型：ExtractResult, ExtractStatus 等
├── framework.py             # 抽取框架核心
├── validator.py             # 数据验证器
├── extractors/              # 抽取器模块
│   ├── __init__.py
│   ├── base.py              # 抽取器基类
│   ├── other.py             # Other 默认抽取器
│   ├── award.py             # 奖状抽取器
│   ├── patent.py            # 专利抽取器
│   ├── software.py          # 软著抽取器
│   └── certificate.py       # 证书类抽取器基类
├── template/                # 模板管理模块
│   ├── __init__.py
│   ├── template.py          # Template 类
│   ├── manager.py           # TemplateManager 类
│   ├── matcher.py           # TemplateMatcher, TypeMatcher
│   └── competition.py       # CompetitionMatcher
├── llm/                     # LLM 引擎模块
│   ├── __init__.py
│   ├── engine.py            # LLMEngine 类
│   └── provider.py          # 提供者基类
├── prompts/                 # 提示词和字段定义
│   ├── award_fields.json    # 奖状字段定义
│   ├── patent_fields.json   # 专利字段定义
│   ├── software_fields.json # 软著字段定义
│   └── default_prompt.json  # 默认提示词模板
└── config/                  # 配置文件
    └── type_rules.json      # 类型识别规则
```

## 与旧模块的关系

### 从 document_extract 迁移

| 旧模块 | 新模块 | 状态 |
|--------|--------|------|
| `backend/document_extract/core/legacy_extractor.py` | `backend/extract/extractors/` | ✅ 已完成 |
| `backend/document_extract/core/template_manager.py` | `backend/extract/template/` | ✅ 已完成 |
| `backend/document_extract/validation/` | `backend/extract/validator.py` | ✅ 已完成 |
| `backend/document_extract/llm/` | `backend/extract/llm/` | ✅ 已完成 |

### 不兼容的变化

1. **导入路径变化**：
   - 旧: `from backend.document_extract import DocumentEngine`
   - 新: `from backend.extract import ExtractFramework`

2. **API 变化**：
   - 旧: `engine.get_text(file_path)` 获取文本，再 `extract_from_text(text)` 抽取
   - 新: `framework.extract(file_path)` 一步完成

3. **配置变化**：
   - 模板配置从 `backend/document_extract/config/` 迁移到数据库
   - 类型规则迁移到 `backend/extract/config/type_rules.json`

## 开发指南

### 添加新的抽取器

1. 继承 `Extractor` 基类
2. 实现 `extract(ctx: ExtractContext) -> ExtractResult` 方法
3. 注册到框架: `framework.register(NewExtractor(...))`

详见 [抽取框架设计](./抽取框架设计.md#如何实现抽取器)

### 添加新的模板

模板存储在数据库 `templates` 表中，可以通过 Flask 管理界面添加。

详见 [模板测试指南](./template-testing-guide.md)

## 测试

### 运行测试

```bash
# 单元测试
python -m pytest tests/extract/unit/ -v

# 集成测试
python tests/extract/integration/test_award_integration.py

# 生成 HTML 报告
python -m pytest tests/extract/ --html=tests/reports/extract/report.html
```

### 测试覆盖

- 单元测试: 抽取器、验证器、模板管理
- 集成测试: 端到端抽取流程
- UI 测试: Flask test_client

## 常见问题

### Q: 如何禁用缓存？

```python
result = framework.extract(
    "path/to/file.jpg",
    use_ocr_cache=False,
    use_llm_cache=False
)
```

### Q: 如何处理不支持的语言？

默认支持中文和英文。其他语言需要：
1. 在 `type_rules.json` 中添加识别规则
2. 在抽取器中添加翻译逻辑

### Q: 模板匹配失败怎么办？

框架会回退到默认提示词。如果默认提示词也失败，返回 `other` 类型。

### Q: OCR/LLM 失败（如 429、费用不足）时如何查看原因？

- 抽取结果中 `result.error_message` 与 `result.data.note` 会统一为面向用户的提示（如「OCR/LLM 费用不足，无法处理」）。
- 运行 `python tests/quick_extract_test.py` 或 `python tests/extract_test.py` 时，若出现异常/other，控制台会打印 `[异常/other]` 及 `error_message`、`data.note`、`status`，便于测试。
- 文件导入结果页中，other 类型会展示「无法处理原因：{note}」。

## 贡献指南

1. 遵循现有代码风格
2. 添加单元测试和集成测试
3. 更新相关文档
4. 不硬编码配置，使用配置文件或数据库

## 许可证

内部项目，仅供教学使用。
