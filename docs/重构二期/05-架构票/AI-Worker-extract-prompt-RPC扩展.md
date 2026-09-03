# 架构票:AI Worker extract/prompt RPC 扩展

> 登记:2026-09-03(二级页迁移三批收官时,templates create/detail 挂账的解锁载体)|状态:**✅ 已完成(2026-09-03 深夜,交付物 5 页面批次落地,三段文档见 `06-体验重设计/07-Worker-RPC页面批次/`;1-4 见本目录实施文档)**
> 前置:v2 AI 通道现状=`AiWorkerClient.ask()` 单契约(#33,fake/grpc 双模式,Worker 127.0.0.1:50060,`ai.mode` 切换)

## 一、背景

v1 templates 域(admin/templates/tabs/create+detail)核心能力是 AI 域路由:extract-for-create(OCR+LLM 字段抽取)、generate-prompt(-for-create)(模板 prompt 生成)、test(模板试测)、validation-rules(校验规则)。v2 AI Worker 无对应 RPC,故两页在二级页迁移三批(T 批)中按"未就绪项不硬做"条款显式挂账。同源挂账:图片 OCR 批量导入字段自动抽取(批 5)。

## 二、范围

| # | RPC | 契约 | 解锁 |
|---|---|---|---|
| 1 | `Extract(image, templateRule) → fields` | OCR+LLM 按模板规则抽取字段 | templates create 页、图片批量导入字段自动抽取 |
| 2 | `GeneratePrompt(templateRule, sample) → prompt` | 模板 prompt 生成/试测支撑 | templates create/detail 页、validation-rules 管理 |

## 三、交付物

1. proto 契约扩展(ExtractRequest/ExtractResponse、GeneratePromptRequest/Response);
2. Worker 侧实现 + v2 fake 模式桩(开发/CI 确定性,与 ask 同模式);
3. ChatService 式降级语义(RPC 不可用→明确错误码,参考 4003);
4. 集成测试(fake 模式全绿+真 Worker 冒烟 TaggedPerf 式 *IT 默认跳过);
5. templates create/detail 两页迁移(按三段文档流程,单独批次)。

## 四、验收

- fake 模式下两页可走通"上传→抽取→预览→确认"主链(结构层断言+键名契约);
- 真 Worker 打通后 OCR 抽取准确率抽验(对照 v1 templates test 路由行为);
- 全量回归+五门禁+CI 三 job success。

## 五、关联

- 挂账来源:`docs/重构二期/04-页面迁移/Fix-T-三类成果编辑页/01-方案.md`(范围决策)
- 同源挂账:批 5 图片 OCR 批量导入(字段自动抽取部分)
