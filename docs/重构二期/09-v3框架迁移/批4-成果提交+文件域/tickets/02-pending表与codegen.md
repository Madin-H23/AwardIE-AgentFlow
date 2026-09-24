# 02 — pending_achievements 表 + codegen CRUD 骨架

**What to build:** `awardie-business.sql` 追加 `awardie_pending_achievements`(对照 v2 20 列:achievement_type/achievement_data JSON/validation_result JSON/submitter_type/submitter_id/submit_time/status/reviewer_id/review_time/review_comment/file_path/assigned_reviewer_type/reviewer_type/file_hash/ocr_text/llm_prompt/llm_response JSON/ext_info JSON/session_id/laboratory_id/version + 审计/逻辑删除/租户列,全列 COMMENT);菜单 SQL 追加 pending 域菜单与 `business:pending-achievements:*` 权限点(固定 ID 幂等)+ 角色授权;用芋道 codegen 生成 CRUD 骨架(落盘时包名单数化 `pendingsubmission`);错误码段 1_003_002_000 起;dev/test 两库执行。

**Blocked by:** 无

**Status:** ready-for-agent

- [ ] codegen 导表成功(全列有注释)
- [ ] `mvn -q install -DskipTests` 通过
- [ ] 菜单 SQL 幂等(两跑一致);awardie_admin 与 super_admin 权限面含新权限点
- [ ] dev/test 两库表结构一致,行数 0
- [ ] file_hash 不加 DB 唯一索引(只对 status=pending 去重,DB 唯一会误伤 archived/rejected)——理由写入 SQL 注释
