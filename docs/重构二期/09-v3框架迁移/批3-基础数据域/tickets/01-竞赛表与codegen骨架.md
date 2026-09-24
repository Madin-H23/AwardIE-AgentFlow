# 01 — 竞赛表结构 + codegen 标准 CRUD 骨架

**What to build:** `awardie-business.sql` 追加 `awardie_competitions` 建表(11 业务字段 + 审计/逻辑删除/租户列,全列 COMMENT);`awardie-business-menus.sql` 追加 competitions 菜单(父 3002 + 权限点 3021-3025 固定 ID 幂等);`awardie-user-domain.sql` awardie_admin 授权 ID 列表扩容;用芋道 codegen(导表→moduleName=business/parentMenuId=3000→preview→落盘)生成 CompetitionsController/Service/Mapper/DO/VO 四层标准 CRUD;错误码段 1_003_001_000 起;dev 与 test 两库执行建表 SQL。

**Blocked by:** 无(批1 模块骨架已就绪)

**Status:** ready-for-agent

- [ ] codegen 导表成功(全列有注释,不报 1001004009)
- [ ] `mvn -q install -DskipTests` 通过;模块编译进 reactor
- [ ] 菜单 SQL 幂等(两跑一致);awardie_admin 与 super_admin 权限面含 business:competitions:*
- [ ] dev/test 两库表结构一致,`awardie_competitions` 行数 0
- [ ] codegen 生成物与后续手写定制的边界记录入 02-实施.md
