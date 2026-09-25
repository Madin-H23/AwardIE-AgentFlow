-- ============================================================================
-- AwardIE 业务菜单(幂等:固定菜单 ID + ON DUPLICATE KEY UPDATE,可重复执行)
-- 来源:芋道 codegen 生成(tableId 210,laboratories 切片),父菜单固定 3000,子菜单/按钮固定 ID
-- 权限说明:芋道无超管绕过,菜单必须显式分配给 super_admin(role_id=1)才会生效
-- 必写 tenant_id=1:RoleMenuDO extends TenantBaseDO,芋道租户拦截器会给 system_role_menu
-- 自动追加 tenant_id=当前租户;不写则落到默认值 0,授权行查不出来(全站 403)
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

-- ---- 批4:pending-achievements 待审成果(菜单 + 3 个按钮权限点) ----
-- 提交走 multipart(POST /submit),查询走 /my-page(按当前用户过滤),撤回走 /withdraw
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3003, 'AwardIE 成果提交', '', 2, 2, 3000, 'pending-achievements', '', 'business/pendingachievement/index', 0, 'PendingAchievement', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 成果提交', updater = 'admin';

INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3031, 'AwardIE 待审成果提交', 'business:pending-achievement:create', 3, 1, 3003, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 待审成果提交', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3032, 'AwardIE 待审成果查询', 'business:pending-achievement:query', 3, 2, 3003, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 待审成果查询', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3033, 'AwardIE 待审成果撤回', 'business:pending-achievement:delete', 3, 3, 3003, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 待审成果撤回', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3034, 'AwardIE 待审成果审核', 'business:pending-achievement:review', 3, 4, 3003, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 待审成果审核', updater = 'admin';

-- ---- 批6:vault 成果库(菜单 + 3 个按钮权限点) ----
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3004, 'AwardIE 成果库', '', 2, 3, 3000, 'vault', '', 'business/vault/index', 0, 'Vault', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 成果库', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3041, 'AwardIE 成果库查询', 'business:vault:query', 3, 1, 3004, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 成果库查询', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3042, 'AwardIE 成果库编辑', 'business:vault:update', 3, 2, 3004, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 成果库编辑', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3043, 'AwardIE 成果库删除', 'business:vault:delete', 3, 3, 3004, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 成果库删除', updater = 'admin';

-- ---- 批7:templates 证书模板(菜单 + 5 个按钮权限点) ----
-- 样本图回显与三个 AI 端点(试测/创建前抽取/生成 prompt)归 query 权限:
-- AI 是模板编辑的辅助动作,单开 AI 权限点会造出"能配不能试"的半残授权态。
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3005, 'AwardIE 证书模板管理', '', 2, 4, 3000, 'templates', '', 'business/template/index', 0, 'Template', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 证书模板管理', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3051, 'AwardIE 证书模板查询', 'business:templates:query', 3, 1, 3005, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 证书模板查询', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3052, 'AwardIE 证书模板创建', 'business:templates:create', 3, 2, 3005, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 证书模板创建', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3053, 'AwardIE 证书模板更新', 'business:templates:update', 3, 3, 3005, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 证书模板更新', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3054, 'AwardIE 证书模板删除', 'business:templates:delete', 3, 4, 3005, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 证书模板删除', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3055, 'AwardIE 证书模板导出', 'business:templates:export', 3, 5, 3005, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 证书模板导出', updater = 'admin';

-- ---- 批8:innovation 大创管理(菜单 + 5 个按钮权限点) ----
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3006, 'AwardIE 大创管理', '', 2, 5, 3000, 'innovations', '', 'business/innovation/index', 0, 'Innovation', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 大创管理', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3061, 'AwardIE 大创查询', 'business:innovation:query', 3, 1, 3006, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 大创查询', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3062, 'AwardIE 大创创建', 'business:innovation:create', 3, 2, 3006, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 大创创建', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3063, 'AwardIE 大创导入', 'business:innovation:import', 3, 3, 3006, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 大创导入', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3064, 'AwardIE 大创更新', 'business:innovation:update', 3, 4, 3006, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 大创更新', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3065, 'AwardIE 大创状态校准', 'business:innovation:calibrate', 3, 5, 3006, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 大创状态校准', updater = 'admin';

-- ---- 批9:统计分析 / 数据导出 / 业务日志(菜单 + 3 个查询权限点) ----
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3007, 'AwardIE 统计分析', '', 2, 6, 3000, 'stats', '', 'business/stats/index', 0, 'Stats', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 统计分析', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3008, 'AwardIE 数据导出', '', 2, 7, 3000, 'export', '', 'business/export/index', 0, 'Export', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 数据导出', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3009, 'AwardIE 业务日志', '', 2, 8, 3000, 'logs', '', 'business/logs/index', 0, 'Logs', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 业务日志', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3071, 'AwardIE 统计查询', 'business:stats:query', 3, 1, 3007, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 统计查询', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3072, 'AwardIE 导出查询', 'business:export:query', 3, 1, 3008, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 导出查询', updater = 'admin';
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, status, creator, updater)
VALUES (3073, 'AwardIE 日志查询', 'business:logs:query', 3, 1, 3009, 0, 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 日志查询', updater = 'admin';

-- ---- 分配给超级管理员(role_id=1;INSERT IGNORE 幂等) ----
INSERT IGNORE INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 1, id, 'admin', 'admin', 1 FROM system_menu
WHERE id IN (3000, 3001, 3002, 3003, 3004, 3005, 3011, 3012, 3013, 3014, 3015, 3021, 3022, 3023, 3024, 3025, 3031, 3032, 3033, 3034, 3041, 3042, 3043, 3051, 3052, 3053, 3054, 3055, 3006, 3061, 3062, 3063, 3064, 3065, 3007, 3008, 3009, 3071, 3072, 3073);

-- ============================================================================
-- 批10:教师工作台(两个菜单,走动态路由——P4 明确不做静态路由特例)
-- 教师是审核流执行者(批5 整条审核流建立在教师初审上),无入口即业务断链。
-- 菜单 ID 段:3100+(3000 段是管理端,3100 段是教师端,互不重叠)
-- ============================================================================
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3100, 'AwardIE 教师工作台', '', 1, 6, 0, '/teacher', 'ep:user-filled', '', 0, '', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 教师工作台', updater = 'admin';

INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3101, '待审成果', '', 2, 1, 3100, 'pending', '', 'business/teacher/pending/index', 0, 'TeacherPending', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = '待审成果', updater = 'admin';

INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3102, '我的指导成果', '', 2, 2, 3100, 'awards', '', 'business/teacher/awards/index', 0, 'TeacherAwards', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = '我的指导成果', updater = 'admin';

-- ---- 分配给超级管理员(role_id=1) ----
INSERT IGNORE INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 1, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3100, 3101, 3102);

-- ============================================================================
-- 批10:学生门户(三场景,移动端优先)
-- 走菜单而不是静态路由(P4 同理:静态路由是第二条代码路径)。3200 目录的
-- component 指向我们自己的 PortalLayout,让门户有独立壳——框架的 generateRoute
-- 默认给顶级目录硬套后台 Layout,已在 routerHelper.ts 加了「顶级目录填了
-- component 就用它当壳」的分支(存量菜单 component 皆为 '',对它们无影响)。
-- 菜单 ID 段:3200+
-- ============================================================================
INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3200, 'AwardIE 学生门户', '', 1, 7, 0, '/portal', 'ep:medal', 'portal/PortalLayout', 0, 'Portal', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = 'AwardIE 学生门户', component = 'portal/PortalLayout', updater = 'admin';

INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3201, '提交成果', '', 2, 1, 3200, 'submit', '', 'portal/submit/index', 0, 'PortalSubmit', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = '提交成果', updater = 'admin';

INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3202, '我的提交', '', 2, 2, 3200, 'submissions', '', 'portal/submissions/index', 0, 'PortalSubmissions', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = '我的提交', updater = 'admin';

INSERT INTO system_menu (id, name, permission, type, sort, parent_id, path, icon, component, status, component_name, creator, updater)
VALUES (3203, '我的证书', '', 2, 3, 3200, 'certificates', '', 'portal/certificates/index', 0, 'PortalCertificates', 'admin', 'admin')
ON DUPLICATE KEY UPDATE name = '我的证书', updater = 'admin';

-- ---- 分配给超级管理员(role_id=1) ----
INSERT IGNORE INTO system_role_menu (role_id, menu_id, creator, updater, tenant_id)
SELECT 1, id, 'admin', 'admin', 1 FROM system_menu WHERE id IN (3200, 3201, 3202, 3203);
