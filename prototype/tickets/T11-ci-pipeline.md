## Parent

#1

## What to build

CI 完整护栏:GitHub Actions 流水线——Java 测试(用 postgres service,与本地 5433 等价语义)+ 前端构建 + Playwright ≤3 条演示主线冒烟。推送/PR 红绿可见,成为 tracer 主线的回归护栏。

## Acceptance criteria

- [ ] push/PR 触发:JUnit 全量 + 前端 build/lint 门禁
- [ ] CI 用 `services: postgres` 语义等价本地实例(Flyway+ETL 夹具同构)
- [ ] Playwright 3 条:登录/提交奖状/看时间线
- [ ] 失败时 GitHub 通知可见;main 分支红即修纪律写进 CONTRIBUTING 或 README
- [ ] 流水线总时长可接受(<15min 量级)

## Blocked by

-  #6、 #11
