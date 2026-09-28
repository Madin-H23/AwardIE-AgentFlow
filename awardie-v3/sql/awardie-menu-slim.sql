-- AwardIE 菜单瘦身(批14,用户拍板「管理员日常版」)
-- 目标:把芋道自带的演示/开发工具/单租户用不上的菜单整体隐藏,让管理员侧边栏只剩日常所需。
--
-- ⚠️ 使用纪律:
--   1. 只能在「还没给角色授过自定义菜单」的库上按需重审;重复执行**安全**(幂等,deleted 置 1)。
--   2. 本脚本按**根菜单 id 整子树**隐藏(含目录/页面/按钮三类),恢复 = 把对应行 deleted 置回 0。
--   3. AwardIE 三个目录(3000/3100/3200)与系统管理核心(用户/角色/菜单/部门/岗位/字典/
--      消息中心/审计日志)以及基础设施核心(文件管理/定时任务/API 日志/配置管理)**一律不动**。
--   4. 隐藏 ≠ 卸载:后端接口与前端路由文件都还在,这里只影响菜单可见性。
--
-- 隐藏清单(管理员日常版,2026-09-28 拍板):
--   报表管理(207,含报表/仪表盘/大屏三设计器)        —— 芋道演示,与业务无关
--   代码生成(19)/代码生成案例(83)/数据源配置(195)   —— 框架开发工具
--   表单构建(18)/API 接口(20)/WebSocket(565)        —— 框架开发工具
--   监控中心(773,MySQL/Java/Redis/链路追踪)         —— 本机未部署监控服务,点了也是空
--   租户管理(181)                                   —— AwardIE 单租户固定 tenant=1
--   OAuth 2.0(201)/三方登录(529)                    —— 未接第三方登录
--   地区管理(271)                                   —— 业务未用
-- 保留:用户/角色/菜单/部门/岗位/字典/消息中心/审计日志 + 文件管理/定时任务/API 日志/配置管理

DROP TEMPORARY TABLE IF EXISTS tmp_slim_ids;
CREATE TEMPORARY TABLE tmp_slim_ids (id BIGINT PRIMARY KEY);

-- 递归收集每个根菜单的整棵子树(含按钮)
INSERT INTO tmp_slim_ids (id)
WITH RECURSIVE sub AS (
    SELECT id FROM system_menu
    WHERE id IN (207, 19, 83, 195, 18, 20, 565, 773, 181, 201, 529, 271)
      AND deleted = 0
    UNION ALL
    SELECT c.id
    FROM system_menu c
    JOIN sub s ON c.parent_id = s.id
    WHERE c.deleted = 0
)
SELECT id FROM sub;

UPDATE system_menu m
JOIN tmp_slim_ids t ON m.id = t.id
SET m.deleted = 1;

DROP TEMPORARY TABLE IF EXISTS tmp_slim_ids;
