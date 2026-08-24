> ⚠️ 已归档（2026-08-24）：本文档为历史资料，不反映项目现状。现行权威文档见 docs/README.md 路由。

# 专利和软著抽取器设计文档

## 1. 概述

### 1.1 目标

创建专利（Patent）和软著（Software）抽取器，用于从专利证书和软件著作权证书（PDF/图片格式）中提取结构化数据。

### 1.2 技术方案

- **OCR识别**：使用OCR引擎从PDF/图片文件中提取文本
- **LLM抽取**：使用大语言模型从OCR文本中提取结构化数据
- **关键词匹配**：通过关键词识别文件类型（专利/软著）

### 1.3 与大创抽取器的区别

| 特性 | 大创抽取器 | 专利/软著抽取器 |
|------|-----------|----------------|
| 文件格式 | Excel (.xlsx, .xls) | PDF/图片 (.pdf, .jpg, .png, .jpeg) |
| 数据来源 | 直接读取Excel单元格 | OCR识别后的文本 |
| 抽取方式 | 列名映射+正则解析 | LLM结构化抽取 |
| 模板匹配 | 文件名+第一行关键词 | OCR文本关键词匹配 |

## 2. 数据结构

### 2.1 专利 (Patent)

根据 `backend/models/patent.py` 和文档指南，输出格式为：

```python
{
    "patent_name": str,           # 专利名称
    "patent_type": str,           # 专利类型：发明专利/实用新型/外观设计
    "application_number": str,    # 申请号，如：202310123456.7
    "publication_number": str,    # 公开号，如：CN1234567A
    "inventor": str,              # 发明人（多人用逗号分隔）
    "application_date": str,      # 申请日期，格式：YYYY-MM-DD
    "patentee": str,              # 专利权人
}
```

### 2.2 软著 (Software)

根据 `backend/models/software_copyright.py` 和文档指南，输出格式为：

```python
{
    "software_name": str,         # 软件名称
    "software_version": str,      # 版本号，如：V1.0
    "registration_number": str,   # 登记号，如：2023SR123456
    "certificate_no": str,        # 证书号，如：软著登字第14406738号
    "registration_date": str,     # 登记日期，格式：YYYY-MM-DD
    "copyright_owner": str,       # 著作权人
}
```

## 3. 抽取器设计

### 3.1 基类设计

继承 `Extractor` 基类，实现以下核心方法：

```python
class CertificateExtractor(Extractor):
    """证书抽取器基类（专利/软著）"""

    def extract(self, ctx: ExtractContext) -> ExtractResult:
        """执行抽取"""
        # 1. 执行OCR（如果ctx.ocr_text为空）
        # 2. 检查是否匹配类型
        # 3. 调用LLM抽取结构化数据
        # 4. 验证和返回结果
```

### 3.2 PatentExtractor

**配置**：
```json
{
    "enabled": true,
    "extensions": [".pdf", ".jpg", ".jpeg", ".png", ".jfif"],
    "keywords": ["专利", "发明专利", "实用新型", "外观设计", "申请号", "公开号"],
    "fields_file": "patent_fields.json"
}
```

**处理流程**：
1. 检查文件扩展名是否支持
2. 如果ctx.ocr_text为空，调用OCR引擎提取文本
3. 检查OCR文本中是否包含专利关键词
4. 如果匹配，调用LLM进行结构化抽取
5. 解析LLM返回的JSON数据
6. 返回ExtractResult

### 3.3 SoftwareExtractor

**配置**：
```json
{
    "enabled": true,
    "extensions": [".pdf", ".jpg", ".jpeg", ".png", ".jfif"],
    "keywords": ["软件", "著作权", "登记号", "证书号", "软著"],
    "fields_file": "software_fields.json"
}
```

**处理流程**：与PatentExtractor类似

## 4. LLM提示词设计

### 4.1 专利抽取提示词

```
你是一个专业的专利证书信息提取助手。请从以下OCR识别的文本中提取专利信息。

{ocr_text}

请提取以下字段，以JSON格式返回：
{
  "patent_name": "专利名称",
  "patent_type": "专利类型（发明专利/实用新型/外观设计）",
  "application_number": "申请号",
  "publication_number": "公开号",
  "inventor": "发明人（多人用逗号分隔）",
  "application_date": "申请日期（YYYY-MM-DD格式）",
  "patentee": "专利权人"
}

注意：
- 如果某个字段无法从文本中提取，请使用null
- 日期格式必须为YYYY-MM-DD
- 发明人多人用逗号分隔
```

### 4.2 软著抽取提示词

```
你是一个专业的软件著作权证书信息提取助手。请从以下OCR识别的文本中提取软件著作权信息。

{ocr_text}

请提取以下字段，以JSON格式返回：
{
  "software_name": "软件名称",
  "software_version": "版本号（如V1.0）",
  "registration_number": "登记号（如2023SR123456）",
  "certificate_no": "证书号（如软著登字第XXXX号）",
  "registration_date": "登记日期（YYYY-MM-DD格式）",
  "copyright_owner": "著作权人"
}

注意：
- 如果某个字段无法从文本中提取，请使用null
- 日期格式必须为YYYY-MM-DD
- 版本号保留V前缀
```

## 5. 配置文件

在 `config/settings.json` 中添加：

```json
{
  "extract": {
    "patent": {
      "enabled": true,
      "extensions": [".pdf", ".jpg", ".jpeg", ".png", ".jfif"],
      "keywords": ["专利", "发明专利", "实用新型", "外观设计", "申请号", "公开号"],
      "min_confidence": 0.3,
      "fields_file": "patent_fields.json"
    },
    "software": {
      "enabled": true,
      "extensions": [".pdf", ".jpg", ".jpeg", ".png", ".jfif"],
      "keywords": ["软件", "著作权", "登记号", "证书号", "软著"],
      "min_confidence": 0.3,
      "fields_file": "software_fields.json"
    }
  }
}
```

## 6. 测试设计

### 6.1 单元测试

**测试文件**：
- `tests/extract/unit/test_patent_extractor.py`
- `tests/extract/unit/test_software_extractor.py`

**测试用例**：
1. 测试扩展名匹配
2. 测试关键词匹配
3. 测试OCR文本处理
4. 测试LLM响应解析
5. 测试错误处理

### 6.2 集成测试

**测试文件**：
- `tests/extract/integration/test_patent_integration.py`
- `tests/extract/integration/test_software_integration.py`

**测试数据**：
使用 `files/patents/` 和 `files/software/` 中的真实证书文件

**测试用例**：
1. 专利证书抽取测试
2. 软著证书抽取测试
3. 非证书文件处理测试
4. 生成HTML测试报告

## 7. 实现计划

1. ✅ 设计文档完成
2. ⏳ 实现PatentExtractor
3. ⏳ 实现SoftwareExtractor
4. ⏳ 编写单元测试
5. ⏳ 编写集成测试
6. ⏳ 运行测试验证

## 8. 注意事项

1. **OCR缓存**：使用ocr_engine的缓存功能，避免重复识别
2. **LLM缓存**：使用llm_engine的缓存功能，避免重复调用
3. **错误处理**：OCR失败、LLM调用失败、JSON解析失败等异常情况的处理
4. **日志记录**：记录关键步骤的日志，便于调试
5. **类型转换**：确保日期格式正确（YYYY-MM-DD）
6. **null值处理**：无法提取的字段应返回null而非空字符串

## 9. 后续扩展

- 支持批量证书处理
- 支持证书模板匹配（类似奖状的模板系统）
- 支持证书验证规则（如申请号格式验证）
- 支持多语言证书
