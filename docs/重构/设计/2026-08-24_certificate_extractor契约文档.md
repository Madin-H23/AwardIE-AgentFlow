# CertificateExtractor 现行行为契约文档（v1.0 · 待 hewj 签认）

> **目的**：T75 剩余项的前置——以源码实测（certificate.py 全部 499 行）+ 18 例冻结测试实跑为据，
> 固化 `CertificateExtractor` 及其子类的**现行行为契约**；hewj 签认后即作为解冻分诊的唯一裁决标准。
> **效力**：签认前本文档为"代拟稿"；签认后为权威契约，任何"期望过时 vs 模块缺陷"的争议以此裁定。
> 编写：2026-08-24 | 依据：`backend/extract/extractors/certificate.py` + `tests/extract/unit/test_certificate_extractor.py` 实跑

---

## §1 类属性契约（子类强制项）

| 属性 | 必需性 | 现行行为 |
| --- | --- | --- |
| `template_type` | ✅ 必须 | 作为抽取器 `name` 与模板类型标识（Patent="patent"、Software="software"） |
| `fields_name` | ✅ 必须 | 决定字段定义文件名 `{fields_name}_fields.json`（可被 config.fields_file 覆盖） |
| `description` | ✅ 必须 | **缺失时 `__init__` 直接 `raise ValueError("{cls} 必须定义 'description' 类属性")`** |
| `judgment_text` | ✅ 必须 | **缺失时同上 fail-fast**——用于文件类型判断的描述文本 |
| `prompt_template` | ⭕ 可选 | 缺省时使用基类内置通用提示词模板；子类可覆写（Patent 已覆写含额外注意事项） |

**fail-fast 是有意设计**：错误信息明确指向缺失属性名，属防呆约定而非缺陷。
（此条即 12 例失败的唯一根因——见 §5）

## §2 构造契约 `__init__(config: Dict)`

| config 键 | 必需性 | 行为 |
| --- | --- | --- |
| `extensions` | ⭕ | 默认 `[".pdf",".jpg",".jpeg",".png",".jfif"]` |
| `keywords` | ⭕ | 列表过滤空串；非列表一律置空 |
| `min_confidence` | ⭕ | 默认 0.3 |
| `fields_file` | ⭕ | 默认 `{fields_name}_fields.json` |

构造副作用：加载字段定义（§3）；校验 description/judgment_text（§1）。

## §3 字段定义资源契约

- 路径固定解析为 `backend/extract/prompts/{fields_file}`；
- 文件不存在 → `FileNotFoundError`；JSON 解析失败 → `RuntimeError`；非 dict → `ValueError`；
- 字段定义驱动 LLM 提示词的 JSON schema 段（`_get_fields_description`），
  并内嵌三条硬约定：无法提取用 null / 日期格式 YYYY-MM-DD / 只返回 JSON。

## §4 LLM 响应解析契约 `_parse_llm_response(response: str) -> Dict`

三级降级解析：①直接 `json.loads` → ②```` ```json ```` 代码块正则提取 → ③花括号平衡提取；
全部失败 → 记 error 日志并**返回空 dict**（不抛异常）。

## §5 数据校验契约 `_validate_data(data) -> ValidationResult`

1. 全字段 null/空 → completeness issue「未抽取到任何有效数据」，is_valid=False；
2. 否则委托 `_validate_specific_fields`（子类扩展点）收集 content/completeness 两类 issue；
3. `is_valid = 无 content_issue 且无 completeness_issue`。

## §6 extract 主流程契约（五步顺序，短路即 `_other_result(SUCCESS+note)`）

| 步 | 检查 | 不通过返回 |
| --- | --- | --- |
| 1 | 扩展名 ∈ extensions | "不支持的文件扩展名" |
| 2 | OCR：ctx.ocr_text 为空才调 ocr_engine.get_text(is_precise=True)，记缓存命中 | 引擎未配置→"OCR引擎未配置" |
| 3 | 关键词匹配 `matches_keywords(ocr_text)`；**ctx.force_type 存在时跳过（手动导入模式）** | "不是证书文件" |
| 4 | LLM 抽取：_build_prompt → llm_engine.call | 引擎未配置→"LLM引擎未配置" |
| 5 | _parse_llm_response → _validate_data → 组装 ExtractResult（含 validation_result/metadata） | — |

注：`_other_result` 返回 `status=SUCCESS + template_type=OTHER + data.note=message`
（沿用 award 同款约定：识别失败不算执行失败）。

## §7 工厂与已知合规子类

- `from_config_loader(cls, config_loader)`：读 `settings.json → extract.{template_type}` 作为 config；
- **PatentExtractor**：desc="专利证书"，judgment_text 含名称/类型/日期/发明人/专利号，
  覆写 prompt_template（patent_type 三选一、application_date 兜底当年 1 月 1 日、inventor 逗号分隔）
  与 `_validate_specific_fields`；
- **SoftwareExtractor**：desc="软著证书"，同样覆写校验与日期格式静态方法。

## §8 冻结测试 18 例对照结论

| 组 | 例数 | 结果 | 根因 |
| --- | --- | --- | --- |
| TestPatentExtractor + TestSoftwareExtractor | 6 | ✅ 全过 | 真实子类本就满足 §1 契约 |
| TestCertificateExtractor（匿名 TestExtractor 子类） | 12 | ❌ 全挂 | **单一根因**：子类仅定义 template_type/fields_name，缺 description/judgment_text → §1 fail-fast。无任何抽取逻辑/解析/schema 层面的行为分歧 |

**修复方案**（契约生效后执行）：12 处 `class TestExtractor(CertificateExtractor):` 统一补两行
`description = "测试证书"` / `judgment_text = "测试判断文本"`（或收敛为一个模块级公共测试子类）；
随后移除文件头 xfail 标记、解冻转正并收编 CI——预计 15 分钟，零模块改动。

## §9 hewj 签认区

- [ ] 确认 §1「description/judgment_text 缺省 fail-fast」为正式契约（非缺陷）；
- [ ] 批准 §8 修复方案执行（12 例补构造属性后解冻转正收编 CI）；
- [ ] （可选）对 §6 手动导入模式 force_type 跳过关键词检查等现行行为补充说明。

签认结果：＿＿＿＿＿＿＿＿＿＿＿＿ 日期：＿＿＿＿＿＿
