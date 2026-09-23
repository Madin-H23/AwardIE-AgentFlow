-- ============================================================================
-- AwardIE v3 演示数据清理脚本(幂等,可重复执行)
-- 用法:官方 sql(脱敏版)导入 awardie_v3 库后,追加执行本脚本:
--   mysql -u awardie_v3 -p*** awardie_v3 < awardie-cleanup.sql
-- 上游升级流程:重新 archive 新基线 → 重跑 v3_sanitize_sql_secrets.py → 重跑本脚本
--
-- 保留(最小系统集):admin 用户、super_admin/common 角色、总部组织链(100/101/103)、
--   系统菜单/角色菜单/字典/租户默认包/infra_config 功能配置、quartz 引擎表结构
-- 删除:演示用户/角色/组织/岗位、yudao_demo* 业务演示、infra 演示配置
--   (短信/邮件/文件/社交/job)、oauth2 演示客户端、quartz 演示任务
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
