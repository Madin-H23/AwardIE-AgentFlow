## Parent

#1

## What to build

审核闭环(tracer 收口):教师批准/驳回,状态机 pending→submit→archived/rejected 与 v1 等价;驳回必须可修改后重新提交(BR-5);学生端时间线页展示完整事件链(提交/AI 建议/审核)。完成后 tracer 主线"提交→AI 建议→审核→时间线"可端到端演示。

## Acceptance criteria

- [ ] 批准→archived,驳回→rejected 且记录原因
- [ ] 驳回后学生修改重新提交(BR-5),状态机合法流转
- [ ] 学生时间线页展示全部事件(含 AI 建议记录)
- [ ] JUnit 状态机与权限(学生不能审、教师只能审权限内)~10 例
- [ ] 手动全链演示脚本(三角色走一遍)通过

## Blocked by

-  #7、 #9
