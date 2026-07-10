# LLM抽取器选择详细说明

## 概述

当多个抽取器同时匹配关键词时，框架会调用LLM来判断应该使用哪些抽取器。本文档详细说明这一流程。

## 触发条件

LLM选择抽取器的触发条件：
1. **文件类型为图片**（扩展名在 `extract.image_extensions` 中，包括 `.pdf`）
2. **OCR识别成功**，得到文本内容
3. **关键词匹配结果**：有**2个或更多**抽取器同时匹配关键词

如果只有1个抽取器匹配，直接使用该抽取器，**不调用LLM**。

## 完整流程

### 1. 关键词匹配阶段

框架对OCR文本进行关键词匹配：

```python
matched = [e for e in candidates if e.matches_keywords(text)]
```

- `candidates`：已通过扩展名匹配的抽取器列表
- `matches_keywords(text)`：检查OCR文本是否包含抽取器的任意关键词（不区分大小写）

### 2. LLM调用阶段（仅当 `len(matched) >= 2`）

#### 2.1 组装提示词

**代码位置**：`backend/extract/framework.py:_llm_select_extractors()`

**提示词模板**（可配置，默认值）：
```
以下是一段文档的 OCR 识别文本。请将其归类到以下类别之一（或几个）。

**分类任务说明：**
请仔细分析 OCR 文本的内容，判断文档属于哪个类别。每个类别都有明确的特征和应包含的信息。

**重要规则：**
1. 优先选择最匹配的单一类别，只有在文档确实包含多种类型信息时才返回多个
2. 如果文档明显是某一种类型（如奖状、证书），即使包含其他类型的关键词，也只返回该类型
3. 仅返回 JSON 数组，元素为类别标识（见下方说明）。例如 ["award"] 或 ["award","innovation"]

**类别说明：**
{extractors}

**OCR 文本：**
{ocr_text}
```

**提示词优化说明**：
- **明确分类任务**：将任务表述为"归类"任务，让LLM更容易理解这是在做文档分类
- **强调类别特征**：每个类别的描述应包含该类别的特征和通常应包含的信息
- 强调"优先选择最匹配的单一类别"，避免因为文本中包含其他类型关键词而误判
- 例如：奖状文档中可能包含"项目名称"等关键词，但文档的主要类型是奖状，应只返回 `["award"]`
- 只有在文档确实包含多种类型信息（如同时是奖状和大创项目）时，才返回多个类别

**类别说明格式**：
```
- {extractor.name}（类别标识）: {extractor.judgment_text or extractor.description}
```

**示例**（抽取器的 `judgment_text` 应包含类别特征和包含的信息）：
```
- award（类别标识）: 奖状类别。特征：包含竞赛名称、奖项等级（如一等奖、二等奖）、获奖者姓名等信息。通常出现在竞赛证书、获奖证明等文档中。
- innovation（类别标识）: 大创项目类别。特征：包含项目名称、项目负责人、项目成员、指导教师、项目级别（国家级/省级/院级）等信息。通常出现在大学生创新创业训练计划项目申报书、项目证书等文档中。
- patent（类别标识）: 专利类别。特征：包含专利名称、专利号、发明人、专利类型（发明专利/实用新型/外观设计）等信息。通常出现在专利证书、专利申请文件等文档中。
```

**OCR文本处理**：
- 如果OCR文本长度超过 `llm_max_text_length`（默认4000字符），会被截断
- 截断后的文本用于组装提示词

**配置位置**：`config/settings.json`
```json
{
  "extract": {
    "llm_max_text_length": 4000,
    "llm_selector_prompt_template": "以下是一段 OCR 文本..."
  }
}
```

#### 2.2 调用LLM

**代码位置**：`backend/extract/framework.py:296`

```python
messages = [{"role": "user", "content": prompt}]
raw, llm_cached = self.llm_engine.chat(
    messages, 
    temperature=0.1,  # 低温度，确保结果稳定
    use_cache=use_llm_cache  # 使用缓存节省Token
)
```

**参数说明**：
- `temperature=0.1`：低温度参数，确保LLM返回结果稳定
- `use_cache`：是否使用LLM缓存（由 `extract()` 的 `use_llm_cache` 参数控制）

#### 2.3 解析LLM返回

**代码位置**：`backend/extract/framework.py:_parse_extractor_list()`

LLM返回的格式可能是：
- 纯JSON数组：`["award", "innovation"]`
- 带代码块：````json\n["award"]\n````
- 其他格式：解析失败时返回空列表

**解析逻辑**：
1. 去除首尾空白
2. 去除代码块标记（` ```json`、` ``` `）
3. 尝试解析JSON
4. 验证是否为列表类型
5. 转换为字符串列表

**过滤无效名称**：
```python
names = _parse_extractor_list(raw)
return [n for n in names if n in {e.name for e in candidates}]
```
只返回在候选抽取器列表中的名称，过滤掉LLM返回的无效名称。

### 3. 抽取器调用阶段

**代码位置**：`backend/extract/framework.py:_extract_with_multiple()`

按LLM返回的顺序依次调用抽取器：

```python
for name in chosen:  # chosen 是LLM返回的抽取器名称列表
    ex = next((e for e in matched if e.name == name), None)
    if not ex:
        continue
    res = ex.extract(ctx)
    res.extractor_name = ex.name
    res.ocr_text = text
    res.ocr_cache_hit = ocr_cached
    # 若抽取类型不是OTHER，验证结果并返回
    if res.template_type and res.template_type != TemplateType.OTHER:
        return self._validate_and_return(ex, res)
```

**关键逻辑**：
- **首个非other即返回**：一旦某个抽取器返回 `template_type != TemplateType.OTHER`，立即验证并返回，不再调用后续抽取器
- **全部other则兜底**：如果所有抽取器都返回 `other`，最终调用 `OtherExtractor` 返回 `note_no_match`

## 示例场景

### 场景1：LLM返回单一抽取器

**输入**：
- OCR文本：`"蓝桥杯 一等奖 张三"`
- 匹配的抽取器：`award`、`innovation`（都包含关键词"奖"）
- LLM返回：`["award"]`

**流程**：
1. 调用LLM，提示词包含 `award` 和 `innovation` 的描述
2. LLM返回 `["award"]`
3. 只调用 `award` 抽取器
4. 返回 `award` 的结果

### 场景2：LLM返回多个抽取器（首个成功）

**输入**：
- OCR文本：`"奖 大创 项目"`
- 匹配的抽取器：`award`、`innovation`
- LLM返回：`["award", "innovation"]`
- `award` 返回 `other`，`innovation` 返回 `innovation`

**流程**：
1. 调用LLM
2. LLM返回 `["award", "innovation"]`
3. 先调用 `award`，返回 `other`，继续
4. 再调用 `innovation`，返回 `innovation`，**立即返回**
5. 最终结果：`template_type=innovation`，`extractor_name="innovation"`

### 场景3：LLM返回多个抽取器（全部other）

**输入**：
- OCR文本：`"奖 内容"`
- 匹配的抽取器：`award`、`innovation`
- LLM返回：`["award", "innovation"]`
- 两个抽取器都返回 `other`

**流程**：
1. 调用LLM
2. LLM返回 `["award", "innovation"]`
3. 调用 `award`，返回 `other`
4. 调用 `innovation`，返回 `other`
5. 所有抽取器都返回 `other`，最终调用 `OtherExtractor`，返回 `note_no_match`

### 场景4：LLM返回空列表或解析失败

**输入**：
- OCR文本：`"奖 内容"`
- 匹配的抽取器：`award`、`innovation`
- LLM返回：`[]` 或 `"这不是JSON"`

**流程**：
1. 调用LLM
2. LLM返回无法解析的内容
3. `_parse_extractor_list()` 返回空列表
4. 直接调用 `OtherExtractor`，返回 `note_no_match`
5. 所有匹配的抽取器都**未被调用**

## 测试覆盖

### 现有测试用例

测试文件：`tests/extract/unit/test_extract_framework.py`

**用例4.3**：`test_image_multi_keyword_llm_single`
- 多命中，LLM返回单一抽取器
- 验证：LLM被调用1次，提示词包含所有匹配抽取器描述，只调用LLM返回的抽取器

**用例4.4**：`test_image_multi_keyword_llm_multi_first_success`
- 多命中，LLM返回多个抽取器（首个成功）
- 验证：按LLM返回顺序调用，首个非other即返回

**用例4.5**：`test_image_multi_keyword_llm_multi_all_other`
- 多命中，LLM返回多个抽取器（全部other）
- 验证：所有抽取器都返回other，最终返回other

**用例4.6**：`test_image_multi_keyword_llm_empty`
- 多命中，LLM返回空列表
- 验证：所有匹配的抽取器都未被调用

**用例5.1**：`test_llm_prompt_contains_all_extractors`
- 验证LLM提示词包含所有匹配抽取器的描述

**用例5.2**：`test_llm_return_nonexistent_extractor`
- LLM返回的抽取器名不在候选列表中
- 验证：过滤无效名称，未被调用的抽取器不会被调用

**用例5.3**：`test_llm_parse_with_code_block`
- LLM返回带代码块的JSON
- 验证：正确解析代码块格式

**用例5.4**：`test_llm_parse_failed`
- LLM返回非JSON格式
- 验证：解析失败时返回空列表，走other分支

### 详细测试用例

测试文件：`tests/extract/unit/test_llm_selector_detail.py`

这个测试文件专门用于深入了解LLM判断的完整流程，包括：
- 完整的LLM提示词内容
- LLM的原始返回结果
- 解析后的抽取器列表
- 抽取器的调用顺序和结果
- 所有验证点

**运行方式**：
```bash
python tests/extract/unit/test_llm_selector_detail.py
```

## 调试信息

### ExtractResult 中的调试字段

`ExtractResult` 包含以下调试字段（可选）：
- `llm_prompt: Optional[str]`：LLM提示词（调试用）
- `llm_response: Optional[str]`：LLM原始返回（调试用）
- `llm_cache_hit: bool`：LLM是否命中缓存

**注意**：当前实现中，这些字段可能未完全填充。如需完整调试信息，可以：
1. 修改 `ExtractFramework._llm_select_extractors()` 方法，将提示词和返回结果写入 `ExtractResult`
2. 或使用详细测试用例查看完整流程

## 性能优化

### 缓存机制

1. **OCR缓存**：图片OCR结果会被缓存，避免重复识别
2. **LLM缓存**：LLM选择抽取器的结果会被缓存，相同提示词直接返回缓存结果

### Token节省

1. **单命中不调LLM**：只有1个抽取器匹配时，直接使用，不调用LLM
2. **OCR文本截断**：超过 `llm_max_text_length` 的文本会被截断
3. **低温度参数**：`temperature=0.1` 确保结果稳定，减少重试

## 配置说明

### 必需配置

`config/settings.json`：
```json
{
  "extract": {
    "image_extensions": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".pdf"],
    "llm_max_text_length": 4000,
    "llm_selector_prompt_template": "以下是一段 OCR 文本..."
  }
}
```

### 可选配置

- `llm_max_text_length`：OCR文本最大长度（默认4000）
- `llm_selector_prompt_template`：LLM提示词模板（可自定义）

## 总结

LLM抽取器选择机制的核心特点：
1. **智能判断**：当多个抽取器匹配时，使用LLM进行智能选择
2. **性能优化**：单命中不调LLM，使用缓存减少Token消耗
3. **容错处理**：LLM返回无效结果时，有完善的兜底机制
4. **灵活配置**：提示词模板和文本长度可配置
