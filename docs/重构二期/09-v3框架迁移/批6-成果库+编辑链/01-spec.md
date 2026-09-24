# 批6-成果库+编辑链 Spec(01-spec)

> 来源:00-需求.md(3 决策按推荐案落地,待用户复核) | 2026-09-24

## Problem Statement

批5 物化到四张最简成果表,但没有"库"——admin 无法浏览/搜索/编辑/删除已入库成果(对照 v2 Fix-C 成果库),四表也缺列表/编辑所需字段(年份、证书号、大创表等)。v2 的成果库是 admin 高频页面,缺它则批7 模板、批9 统计都无数据面。

## Solution

在 business 模块加 `AchievementVaultService` + `AchievementVaultController`:五类(award/patent/software/innovation/other)分页列表 + 行编辑(可编辑列白名单)+ 行删除(引用拒绝);`VaultSpec` 枚举固化表名/名称列/列表列(同 v2 防注入思路)。表结构:四张最简表 ALTER 补列 + 新建大创两表。

## Implementation Decisions

- **VaultSpec 枚举**:type → (表名/名称列/列表列)映射,代码内常量;SQL 只出现枚举里的表名列名,值参数化(v2 同款防注入);
- **列表**:keyword LIKE 名称列 + 分页(1-based,size 上限 100)+ id DESC;`tableExists` 判未建表 → 空列表(不 500);
- **行编辑**:`editableColumns(spec)` 白名单——非白名单列静默忽略(防越权改 image_hash/competition_id 等),无可编辑字段 → 1003005001;
- **行删除**:引用检查复用批3 `AchievementReferenceChecker`——awards 引用 `award_student_winners.award_id`、innovation 引用 `innovation_project_students.project_id`;有引用 → 1003005002;逻辑删除(与 v3 全域一致);
- **权限**:`business:vault:query/update/delete`,授 awardie_admin(100)+super_admin(1);教师/学生不授(防改他人成果);
- **DDL 幂等**:MySQL 8 无 `ADD COLUMN IF NOT EXISTS`;用普通 ALTER + `run_awardie_sql.py` 容忍 1060(已存在),CI 每次全新库天然无重复。

## Testing Decisions

沿用批1-5 范式(MockMvc+Bearer+tenant+test 库+自播种授权 API);AchievementVaultTest 8 例:五类列表各 1 行、keyword 双向、非法 type 1003005000、编辑白名单生效+非白名单不动+不存在 1003005001、删除无引用可删/awards 引用拒/innovation 引用拒、学生 403。

## Out of Scope

pending 聚合视图(v2 `/admin/achievements` JSON 过滤,批4/5 已覆盖待审侧);大创 status 校准(批8);证书文件上传/下载端点(批4 文件域已落地 storage,证书链端点随批6 后续);存量迁移(批12)。

## Further Notes

- 大创本批只建表不物化(物化归批8 Excel 通道,v1/v2 语义);
- 成果库按真实表查(不查 pending JSON),比 v2 的 JSON 过滤更自然,且可用列索引;
- 批9 统计/导出会复用本批的表结构(年份/状态维度已就位)。
