# 03 — 五类成果字段校验器 + 提交 service

**What to build:** 新增 `SubmissionValidator`(纯函数,可直测):按 achievementType 分发五类校验,逐条对齐 v2 SubmissionService——award 必填 competition_name/award_level/winner_name/date + date 四格式(yyyy-MM-dd/yyyy-MM/yyyy-M/yyyy/MM/dd)且年份 2000-2100;patent 必填 patent_name + application_number CN 开头且≥5 位 + patent_type 白名单;software 必填 software_name + registration_number 20 开头 11 位;innovation 必填 project_name;other 必填 title;未知类型抛 PENDING_ACHIEVEMENT_TYPE_UNKNOWN。新增 `PendingSubmissionService.submit(...)`:三校验(委托 T01)→ 字段校验 → store → sha256+status=pending 去重(拒则 1003002001)→ 入库(status=pending, version=1, validation_result JSON)。

**Blocked by:** 01(文件域)、02(表与错误码段)

**Status:** ready-for-agent

- [ ] 五类各一用例:合法数据 is_valid=true;缺必填 → is_valid=false + issues 含中文原因
- [ ] date 四格式各通过;年份 1999/2101 拒绝;格式非法归入 content_issues
- [ ] patent 申请号非 CN 开头、长度 <5 拒绝;patent_type 非法值拒绝
- [ ] software 登记号非 20 开头或长度≠11 拒绝
- [ ] 未知类型 → 1003002005
- [ ] 同 sha256 + status=pending 重复提交 → 1003002001;status 非 pending(直插 archived)则允许
- [ ] validation_result JSON 结构与 v2 一致(is_valid/content_issues/completeness_issues)
- [ ] p3c 增量 0
