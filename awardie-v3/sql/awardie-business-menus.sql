-- ============================================================================
-- AwardIE 业务菜单(幂等:固定菜单 ID + ON DUPLICATE KEY UPDATE,可重复执行)
-- 来源:芋道 codegen 生成(tableId 210,laboratories 切片),父菜单固定 3000,子菜单/按钮固定 ID
-- 权限说明:芋道无超管绕过,菜单必须显式分配给 super_admin(role_id=1)才会生效
-- 用法:官方 sql + cleanup + awardie-business.sql 之后执行
-- ============================================================================

-- ---- 父菜单:AwardIE 业务管理 ----
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, status, creator, updater)
VALUES (3000, 'AwardIE 业务管理', '', 1, 5, 0, '/business', 'ep:collection', 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 业务管理', updater = 'admin';

-- ---- 批1:laboratories 实验室(菜单 + 5 个按钮权限点) ----
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3001, 'AwardIE 实验室管理', '', 2, 0, 3000, 'laboratories', '', 'business/laboratory/index', 0, 'Laboratories', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 实验室管理', updater = 'admin';

INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3011, 'AwardIE 实验室查询', 'business:laboratories:query', 3, 1, 3001, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 实验室查询', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3012, 'AwardIE 实验室创建', 'business:laboratories:create', 3, 2, 3001, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 实验室创建', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3013, 'AwardIE 实验室更新', 'business:laboratories:update', 3, 3, 3001, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 实验室更新', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3014, 'AwardIE 实验室删除', 'business:laboratories:delete', 3, 4, 3001, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 实验室删除', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3015, 'AwardIE 实验室导出', 'business:laboratories:export', 3, 5, 3001, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 实验室导出', updater = 'admin';

-- ---- 批3:competitions 竞赛(菜单 + 5 个按钮权限点) ----
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3002, 'AwardIE 竞赛管理', '', 2, 1, 3000, 'competitions', '', 'business/competition/index', 0, 'Competitions', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 竞赛管理', updater = 'admin';

INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3021, 'AwardIE 竞赛查询', 'business:competitions:query', 3, 1, 3002, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 竞赛查询', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3022, 'AwardIE 竞赛创建', 'business:competitions:create', 3, 2, 3002, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 竞赛创建', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3023, 'AwardIE 竞赛更新', 'business:competitions:update', 3, 3, 3002, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 竞赛更新', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3024, 'AwardIE 竞赛删除', 'business:competitions:delete', 3, 4, 3002, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 竞赛删除', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3025, 'AwardIE 竞赛导出', 'business:competitions:export', 3, 5, 3002, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 竞赛导出', updater = 'admin';

-- ---- 分配给超级管理员(role_id=1;INSERT IGNORE 幂等) ----
INSERT IGNORE INTO system_role_menu (role_id, menu_id, creator, updater)
SELECT 1, id, 'admin', 'admin' FROM system_menu WHERE id IN (3000, 3001, 3002, 3011, 3012, 3013, 3014, 3015, 3021, 3022, 3023, 3024, 3025);
