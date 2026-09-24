# 01 — Prefactor:批1 测试与环境状态解耦

**What to build:** LaboratoriesControllerTest 不再依赖 cleanup 后的 stock admin 口令(ETL 会覆盖该口令)——改为测试自播种用户(mapper 直插 system_users+system_user_role,bcrypt 已知口令),使批1 三例在任意环境状态(cleanup 后/ETL 后)下都绿。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 播种用用户(username 带批标记、bcrypt 口令、角色关联 super_admin 或含 laboratory 权限的角色)
- [ ] 批1 三例仍全绿;dev 库手动跑一遍 ETL 后重跑仍绿(解耦实证)
- [ ] p3c 增量 0 违例
