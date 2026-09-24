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

-- ---- awardie_admin 授予业务菜单权限(批1 laboratories;批3 competitions;批4 待审成果) ----
-- 说明:芋道无超管绕过,权限全走 system_role_menu;super_admin(id=1)已在批1 菜单 SQL 授予
INSERT IGNORE INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 100, id, 'admin', 'admin', 1 FROM system_menu
WHERE id IN (3000, 3001, 3002, 3003, 3004, 3011, 3012, 3013, 3014, 3015, 3021, 3022, 3023, 3024, 3025, 3031, 3032, 3033, 3034, 3041, 3042, 3043);

-- ---- 批4:学生/教师也必须有提交流权限(v2 语义:学生提交、教师可代提) ----
-- 菜单(3003)不给(门户侧边栏由批10 前端壳决定),但三个操作权限点必须给,
-- 否则学生提交直接 403——v2 里学生门户的提交入口是主链路,不能被权限挡死
INSERT IGNORE INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 101, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3031, 3032, 3033, 3034);
INSERT IGNORE INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 102, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3031, 3032, 3033, 3034);

-- ---- 批6:成果库是 admin 主责域(教师不授,避免学生/教师越权改他人成果) ----
INSERT IGNORE INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 100, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3041, 3042, 3043);

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
