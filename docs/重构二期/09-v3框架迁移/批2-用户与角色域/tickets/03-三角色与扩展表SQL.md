# 03 — 三角色 SQL+awardie_user_profile 扩展表

**What to build:** 芋道 RBAC 落三角色(code=awardie_admin/awardie_teacher/awardie_student,name=管理员/教师/学生),laboratory 四权限点菜单授 awardie_admin;新建 awardie_user_profile 扩展表(user_id PK、major、grade、title、qq、skills、profile_is_public)。SQL 入 awardie-v3/sql/(幂等,固定 ID 或 ON DUPLICATE)。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 三角色可查(system_role 三行,code 正确);role_menu 授权正确
- [ ] awardie_user_profile 建表;DDL 入 sql 目录且可重复执行
- [ ] dev 库实跑两遍幂等
