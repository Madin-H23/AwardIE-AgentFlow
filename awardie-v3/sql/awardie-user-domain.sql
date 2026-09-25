-- ============================================================================
-- AwardIE 批2:三角色 + 用户资料扩展表(幂等:固定 ID + ON DUPLICATE KEY UPDATE,可重复执行)
-- 用法:官方 sql + awardie-cleanup.sql 之后执行
-- 角色 ID 段:100/101/102(避开芋道 stock 的 1/2 与演示段)
-- ============================================================================

-- ---- 三角色(v2 student/teacher/admin → 芋道 RBAC,code 与 v2 role 值语义对齐) ----
INSERT INTO system_role (id, name, code, sort, data_scope, data_scope_dept_ids, status, type, remark, creator, updater, tenant_id)
VALUES (100, '管理员', 'awardie_admin', 1, 1, '', 0, 2, 'AwardIE 系统管理员(v2 admin 映射)', 'admin', 'admin', 1)
ON DUPLICATE KEY UPDATE name = '管理员', code = 'awardie_admin', updater = 'admin';
INSERT INTO system_role (id, name, code, sort, data_scope, data_scope_dept_ids, status, type, remark, creator, updater, tenant_id)
VALUES (101, '教师', 'awardie_teacher', 2, 1, '', 0, 2, 'AwardIE 教师(v2 teacher 映射)', 'admin', 'admin', 1)
ON DUPLICATE KEY UPDATE name = '教师', code = 'awardie_teacher', updater = 'admin';
INSERT INTO system_role (id, name, code, sort, data_scope, data_scope_dept_ids, status, type, remark, creator, updater, tenant_id)
VALUES (102, '学生', 'awardie_student', 3, 1, '', 0, 2, 'AwardIE 学生(v2 student 映射)', 'admin', 'admin', 1)
ON DUPLICATE KEY UPDATE name = '学生', code = 'awardie_student', updater = 'admin';

-- ---- 业务菜单授权统一口径(批10 起) ----
-- 幂等性说明:system_role_menu 主键是自增 id,无 (role_id, menu_id) 唯一约束,
-- 所以 INSERT IGNORE 永远不会去重(实测重跑 6 次即 6 份重复)。改为
-- 「先 DELETE 该角色在这批菜单上的旧关联,再 INSERT」——既幂等,又能让
-- 授权清单的收窄(如学生去掉 3034)对已存在的库真正生效。
DELETE FROM system_role_menu WHERE role_id = 100
  AND menu_id IN (3000,3001,3002,3003,3004,3005,3006,3007,3008,3009,3011,3012,3013,3014,3015,3021,3022,3023,3024,3025,3031,3032,3033,3034,3041,3042,3043,3051,3052,3053,3054,3055,3061,3062,3063,3064,3065,3071,3072,3073);
-- awardie_admin 授予业务菜单权限(批1 laboratories;批3 competitions;批4 待审成果;批6 成果库;批7 模板;批8 大创;批9 统计导出日志)
-- 说明:芋道无超管绕过,权限全走 system_role_menu;super_admin(id=1)已在批1 菜单 SQL 授予
INSERT INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 100, id, 'admin', 'admin', 1 FROM system_menu
WHERE id IN (3000, 3001, 3002, 3003, 3004, 3005, 3006, 3007, 3008, 3009, 3011, 3012, 3013, 3014, 3015, 3021, 3022, 3023, 3024, 3025, 3031, 3032, 3033, 3034, 3041, 3042, 3043, 3051, 3052, 3053, 3054, 3055, 3061, 3062, 3063, 3064, 3065, 3071, 3072, 3073);

-- ---- 批4:学生/教师也必须有提交流权限(v2 语义:学生提交、教师可代提) ----
-- 菜单(3003)不给(门户侧边栏由批10 前端壳决定),但操作权限点必须给,
-- 否则学生提交直接 403——v2 里学生门户的提交入口是主链路,不能被权限挡死。
--
-- 批10 更正:教师给 3031/3032/3033/3034(可代提、需审核);学生只给
-- 3031/3032/3033,**不给 3034(business:pending-achievement:review)**。
-- 原稿注释写"三个操作权限点"却实际授了四个。review 的唯一服务端门是
-- @PreAuthorize,没有 hasStaffRole 兜底(其兄弟端点 download/timeline/ai-suggest
-- 都有 owner||staff 校验),批10 库内实测确认学生角色确实持有该权限——
-- 等于任一学生可审核任意待审成果,approve 还会触发物化写入成果库。
DELETE FROM system_role_menu WHERE role_id = 101 AND menu_id IN (3031, 3032, 3033, 3034);
INSERT INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 101, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3031, 3032, 3033, 3034);

DELETE FROM system_role_menu WHERE role_id = 102 AND menu_id IN (3031, 3032, 3033, 3034);
INSERT INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 102, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3031, 3032, 3033);

-- ---- 批6:成果库是 admin 主责域(教师不授,避免学生/教师越权改他人成果) ----
-- 3041/3042/3043 已含在上面 admin 的授权清单里,教师与学生均不在其中。
-- 批10 例外:教师授 **3041 查询**——「我的指导成果」页唯一的可用数据源就是
-- GET /business/vault/award(批9 遗留:无教师关系表,没法按教师 id 查),
-- 页面再按 supervisor_name 含当前用户姓名在前端过滤。
-- 只授 query 不授 update(3042)/delete(3043),保持"教师能看不能改"。

-- ---- 批10:教师工作台两菜单(菜单 SQL 在 awardie-business-menus.sql 的 3100 段) ----
DELETE FROM system_role_menu WHERE role_id IN (100, 101) AND menu_id IN (3100, 3101, 3102);
INSERT INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 100, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3100, 3101, 3102);
INSERT INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 101, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3100, 3101, 3102);

-- 教师补成果库只读权限(见上「批6 例外」说明)
DELETE FROM system_role_menu WHERE role_id = 101 AND menu_id = 3041;
INSERT INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 101, id, 'admin', 'admin', 1 FROM system_menu WHERE id = 3041;

-- ---- 批10:学生门户三菜单(菜单 SQL 在 awardie-business-menus.sql 的 3200 段) ----
-- 走菜单而非静态路由(P4 同理)。3200 目录的 component 指向我们自己的 PortalLayout,
-- 学生登录后侧边栏只剩门户三项,不会再看到管理端的实验室/竞赛/成果库那些。
DELETE FROM system_role_menu WHERE role_id = 102 AND menu_id IN (3200, 3201, 3202, 3203);
INSERT INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 102, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3200, 3201, 3202, 3203);

-- ---- 用户资料扩展表(芋道 system_users 装不下 v2 的 major/grade/title/qq/skills/profile_is_public) ----
CREATE TABLE IF NOT EXISTS awardie_user_profile (
    user_id          BIGINT       PRIMARY KEY COMMENT '用户ID(system_users.id)',
    major            VARCHAR(50)  DEFAULT NULL COMMENT '专业',
    grade            VARCHAR(50)  DEFAULT NULL COMMENT '年级',
    title            VARCHAR(50)  DEFAULT NULL COMMENT '职称(教师)',
    qq               VARCHAR(50)  DEFAULT NULL COMMENT 'QQ',
    skills           TEXT         DEFAULT NULL COMMENT '技能',
    profile_is_public BIT         DEFAULT b'1' NOT NULL COMMENT '资料是否公开',
    creator          VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time      DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater          VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 用户资料扩展表';
