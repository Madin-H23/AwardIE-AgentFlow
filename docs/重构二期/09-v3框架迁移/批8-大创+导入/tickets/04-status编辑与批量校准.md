# 04 — status 方向1(单项编辑)+ 方向2(批量校准)

**What to build:** 方向1:innovation 专用编辑端点,维护 v2 编辑页全字段(项目编号/类型/名称/状态/起止日期/经费/负责人姓名与学号/其他成员/指导教师/关联实验室),带 status 枚举校验(进行中/已结题/终止)与 project_type 枚举校验——v2 编辑端点无枚举校验、靠 DB CHECK 兜底,v3 改应用层。方向2:`POST /business/innovation/calibrate-status`,严格按 v2 已验收规则:候选集 `status='进行中' AND end_date IS NOT NULL AND btrim(end_date)<>''`;时区 `Asia/Shanghai`;**严格早于今天**才校准(当天不动、未来不动);只动进行中(终止/已结题不动);日期解析支持 `2025-06`/`2024.5.1`/`2025-06-30`/`2025/6/1`/`2025年6月`/`2025年6月30日`/混合分隔,只写年月按**月首日**处理;不可识别(待定/只有年份/13 月/2 月 30 日/多余段)跳过并计数,**绝不猜**;返回 `considered/calibrated/skippedUnparsed/calibratedIds`;顺序重复调用幂等;写审计且 `skippedUnparsed` 计数能从留痕看到(用户指南要求提示该计数)。全部读写带 `tenant_id` + `deleted=0`。

**Blocked by:** 01(领域模型)

**Status:** ready-for-agent

- [ ] 单项编辑改 status/全部字段并落库;非法 status/project_type 被拒
- [ ] 校准覆盖全部边界:过期/未来/当天/NULL/空串/不可解析/终止/已结题
- [ ] 当天到期不校准(次日才改)
- [ ] 只写年月的按月首日处理
- [ ] 重复调用 calibrated=0,分布不变(幂等)
- [ ] 返回四段计数正确;不可解析条数正确
- [ ] 写审计,含 skippedUnparsed 计数
- [ ] 更新语句带 tenant_id + deleted=0
