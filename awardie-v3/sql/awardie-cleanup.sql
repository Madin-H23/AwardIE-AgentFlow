-- ============================================================================
-- ⚠️⚠️ 危险:本脚本会 DELETE 掉 system_users / system_user_role / system_users_post
--    里 id<>1 的**全部**行。存量用户 ETL(scripts/etl_v2_users_to_v3.py)导入的
--    1834 个师生账号也在这批里。
--
--    2026-09-26 实测事故:在 ETL 已导入的 dev 库(awardie_v3)上直接跑了本脚本,
--    师生账号被清空、admin 身份被改写,登录全部失效。恢复办法是重跑
--    scripts/etl_v2_users_to_v3.py(幂等,按主键 upsert,约 1 分钟)。
--
--    ⇒ **只允许在「刚导入官方 sql、还没跑 ETL」的库上执行本脚本**
--      (即 CI 建库流程:官方 sql → 本脚本 → awardie-business*.sql → user-domain)。
--      已有 ETL 数据的 dev 库需要清数据时,用 DELETE ... WHERE created_by='etl'
--      之类带条件的语句,不要整表清。
-- ============================================================================

-- ---- 租户:保留默认租户(芋道源码 id=1) ----
DELETE FROM system_tenant WHERE id <> 1;
DELETE FROM system_tenant_package WHERE id <> 1;

-- ---- 用户与角色绑定 ----
DELETE FROM system_user_role WHERE user_id <> 1;
DELETE FROM system_user_post;
DELETE FROM system_users WHERE id <> 1;
-- admin 资料归位 + 项目口令(bcrypt;明文由项目负责人线下持有,不入库)
UPDATE system_users
SET nickname = '系统管理员', remark = 'AwardIE v3 管理员', post_ids = '[]',
    password = '$2b$10$c7xKYlq3/sVg2EgYCxQZEO2T0VruekifBaycjKdBjXuymDJ8HooeG'
WHERE id = 1;

-- ---- 角色:保留超级管理员与普通角色 ----
DELETE FROM system_role WHERE id NOT IN (1, 2);
DELETE FROM system_role_menu WHERE role_id NOT IN (1, 2);

-- ---- 组织与岗位:保留 100(AwardIE 根)→101(总部)→103(研发部门) ----
DELETE FROM system_post;
DELETE FROM system_dept WHERE id NOT IN (100, 101, 103);
UPDATE system_dept SET name = 'AwardIE' WHERE id = 100;
UPDATE system_dept SET name = '总部' WHERE id = 101;

-- ---- 芋道 demo 业务表(清空,表结构保留) ----
DELETE FROM yudao_demo01_contact;
DELETE FROM yudao_demo02_category;
DELETE FROM yudao_demo03_grade;
DELETE FROM yudao_demo03_student;
DELETE FROM yudao_demo03_course;

-- ---- infra 演示配置 ----
DELETE FROM infra_file_config;
DELETE FROM system_sms_channel;
DELETE FROM system_sms_template;
DELETE FROM system_sms_log;
DELETE FROM system_sms_code;
DELETE FROM infra_job;
DELETE FROM infra_job_log;
DELETE FROM infra_codegen_table;
DELETE FROM infra_codegen_column;
DELETE FROM infra_config WHERE id = 12;  -- test3/test5 演示配置(保留初始密码/注册开关/监控地址行)

-- ---- 邮件演示(本系统不用邮件通道) ----
DELETE FROM system_mail_account;
DELETE FROM system_mail_template;
DELETE FROM system_mail_log;

-- ---- 社交登录演示 ----
DELETE FROM system_social_client WHERE id <> 1;
DELETE FROM system_social_user;
DELETE FROM system_social_user_bind;

-- ---- oauth2:保留 default 客户端,删演示 SSO 客户端 ----
DELETE FROM system_oauth2_client WHERE id <> 1;
DELETE FROM system_oauth2_access_token;
DELETE FROM system_oauth2_refresh_token;
DELETE FROM system_oauth2_approve;
DELETE FROM system_oauth2_code;

-- ---- 站内信演示消息 ----
DELETE FROM system_notify_message;

-- ---- quartz 演示任务(引擎表结构保留;按依赖逆序清) ----
DELETE FROM QRTZ_CRON_TRIGGERS;
DELETE FROM QRTZ_SIMPLE_TRIGGERS;
DELETE FROM QRTZ_SIMPROP_TRIGGERS;
DELETE FROM QRTZ_BLOB_TRIGGERS;
DELETE FROM QRTZ_FIRED_TRIGGERS;
DELETE FROM QRTZ_TRIGGERS;
DELETE FROM QRTZ_JOB_DETAILS;

-- ---- 批10:已删前端模块对应的菜单 ----
-- 前端基座只保留 infra/system 两套(24 个示例业务模块已删,见前端 README)。
-- 但芋道种子里这些模块的菜单还在,component 字段指向已不存在的 .vue,
-- 动态路由解析失败 = **点进去白屏**,且管理员侧边栏被十几个死目录塞满。
-- 这里把菜单与对应授权一起清掉。先子后父(无外键,按逻辑顺序)。
-- 保留:id=1 系统管理、id=2 基础设施、3000/3100/3200 三个 AwardIE 目录。
-- 注:MySQL 不允许 DELETE 的目标表出现在自身子查询里,读 system_menu 的
-- 那两条用派生表包一层绕开。
SET @dead_roots := '114,148,272,373,449,480,597,791,860,959,1348,1418,1476,1637,1894,8000,8200,194,347,348';

-- 1) 授权:先删子菜单的,再删根目录的
DELETE FROM system_role_menu WHERE menu_id IN (
  SELECT d.id FROM (
    SELECT id FROM system_menu
    WHERE parent_id IN (SELECT id FROM system_menu WHERE FIND_IN_SET(id, @dead_roots))
  ) d
);
DELETE FROM system_role_menu WHERE menu_id IN (
  SELECT d.id FROM (SELECT id FROM system_menu WHERE FIND_IN_SET(id, @dead_roots)) d
);

-- 2) 菜单:先删子菜单的,再删根目录的
DELETE FROM system_menu WHERE parent_id IN (
  SELECT d.id FROM (SELECT id FROM system_menu WHERE FIND_IN_SET(id, @dead_roots)) d
);
DELETE FROM system_menu WHERE FIND_IN_SET(id, @dead_roots);
