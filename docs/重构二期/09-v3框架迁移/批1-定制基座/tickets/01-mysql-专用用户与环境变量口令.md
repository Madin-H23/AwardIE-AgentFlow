# 01 — MySQL 专用用户与环境变量口令注入

**What to build:** 应用不再使用 MySQL root:新建专用用户 `awardie_v3`(仅授权 `awardie_v3` 库的增删改查),`application-local.yaml` 数据源口令改为 `${AWARDIE_MYSQL_PASSWORD:123456}` 环境变量注入(未设环境时回退上游默认值,保持上游行为);撤掉 `.git/info/exclude` 里的本地补丁条目;全仓 grep 确认无其他明文口令入库。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] MySQL 用户 awardie_v3 存在且仅能访问 awardie_v3 库(root 之外的连接验证:该用户连不上其他库)
- [ ] yaml 中口令行为环境变量占位符;设 `AWARDIE_MYSQL_PASSWORD` 启动 48080 正常、不设则回退默认(两种都实测)
- [ ] .git/info/exclude 中 application-local.yaml 条目已移除且 git status 干净
- [ ] 全仓(排除 .git)grep 无新增明文口令;git show 最新提交无口令
- [ ] 验收记录落 02-实施.md
