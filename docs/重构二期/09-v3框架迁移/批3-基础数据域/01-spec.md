# 批3-基础数据域 Spec(01-spec)

> 来源:00-需求.md(grilling 3 决策已获用户 2026-09-24 确认) | 2026-09-24

## Problem Statement

v3 业务域里只有批1 的 laboratories 最小切片(无引用检查、无唯一性校验)与批2 的用户域。竞赛域完全缺失,而竞赛是 v2 成果链的根参照(311 条成果全部挂 competition_id,白名单是 BR-1 级别认定的唯一口径)。两域的删除语义也未按 v3 逻辑删除重做——v2 靠 PG 外键冲突报错,在 v3 逻辑删除下永不触发,不显式检查就等于删除无保护。

## Solution

用芋道 codegen 为竞赛域生成标准 CRUD 并定制(全字段 + 名称唯一 + 删除引用检查),实验室域在批1 切片上补齐唯一性校验与引用检查;引用检查做成表清单驱动的骨架,批4-8 成果表陆续建好后无需改代码即自动生效;附 ETL 把 v2 的 218 竞赛 + 5 实验室带 id 迁入 dev 库。

## User Stories

1. As a 管理员, I want 在竞赛管理页增删改查全部字段(名称/官网/主办方/时间/参赛要求/年级类别/简介/别名/白名单/观察名单), so that 竞赛主数据可在 v3 独立维护,批4 提交时可选;
2. As a 管理员, I want 重名竞赛被明确拒绝, so that 成果挂靠不会出现二义参照;
3. As a 管理员, I want 删除被成果引用的竞赛/实验室时被拒绝且告知被哪类成果引用多少条, so that 不会误删导致成果悬空;
4. As a 开发者, I want 引用检查在成果表还没建的阶段不误拒、在表建好后自动生效, so that 批3 不越界建成果表,批4-8 也不用回头改删除逻辑;
5. As a 开发者, I want v2 的 218 竞赛 + 5 实验室连同 id 迁进 dev 库, so that 后续批次开发有真实参照数据,批12 外键迁移保 id;
6. As a 审查者, I want 每处与 v2 的语义差都有书面声明, so that 批10 前端与批12 迁移按 v3 契约开发而非照抄 v2。

## Implementation Decisions

- **表结构**:`awardie_competitions`(id/competition_name VARCHAR(200) UNIQUE/official_website VARCHAR(500)/organizer VARCHAR(200)/competition_time VARCHAR(100)/participant_requirements TEXT/grade_category VARCHAR(50)/brief_description TEXT/alias_list TEXT/white_list BIT(1)/watch_list BIT(1)/is_auto_added BIT(1) + creator/create_time/updater/update_time/deleted/tenant_id),COMMENT 全列必写(codegen 硬要求,F10);TEXT 列在导出 Excel 时不设列宽注解;
- **codegen 路线**:竞赛域走 UI codegen(导表 → moduleName=business/parentMenuId=3000 → preview → 落盘)与批1 同流程;实验室域**不重新生成**(批1 已有,重生成会覆盖手写定制),改为增量改 service/mapper/VO;
- **唯一性**:竞赛名与实验室名均在 service 层前置校验(错误码 `COMPETITIONS_NAME_DUPLICATE` / `LABORATORIES_NAME_DUPLICATE`,update 分支排除自身 id);**两表均不加 DB 唯一索引**——v3 是逻辑删除,唯一索引会让已删同名永久占位(无法按同名重建),且 MyBatis-Plus 的 @TableLogic 使服务层查询自动过滤 deleted 行,出现"服务层放行、DB 抛 DuplicateKey 500"的两层语义打架;竞赛名唯一规则以服务层为唯一真相(ETL 侧另行校验 v2 侧 218 名全唯一);
- **引用检查骨架**:新增 `dal/mysql/reference` 下的 `AchievementReferenceChecker`(Spring 组件,持 `Map<表名, 引用列>` 清单):①先查 `information_schema.TABLES` 判表存在(表不存在→跳过);②存在则 `SELECT COUNT(*) FROM <表> WHERE <列>=? AND deleted=0`(deleted 列不存在时退化为无该条件);③count>0 抛 `ServiceException(域错误码, "存在关联数据:表名 N 条")`;表名与列名是**代码内常量白名单**,不接受外部输入,杜绝注入;
  - 竞赛清单:`awardie_awards.competition_id`、`awardie_templates.competition_id`;
  - 实验室清单:`awardie_awards.laboratory_id`、`awardie_patents.laboratory_id`、`awardie_software_copyrights.laboratory_id`、`awardie_innovation_projects.laboratory_id`、`awardie_other_files.laboratory_id`;实验室关联表(downloads/images/instructors/students/assistants)归批4,届时追加进清单即可;
  - 调用点:`deleteLaboratories` / `deleteLaboratoriesListByIds` / `deleteCompetitions` / `deleteCompetitionsListByIds`,**批量删除逐个校验**(任一被引用则整体拒绝,@Transactional 回滚);
- **错误码**:business 段续 1_003_000_001 起 —— `LABORATORIES_NAME_DUPLICATE`、`LABORATORIES_IN_USE`、`COMPETITIONS_NOT_EXISTS`(1_003_001_000)、`COMPETITIONS_NAME_DUPLICATE`、`COMPETITIONS_IN_USE`;
- **分页排序**:竞赛 `ORDER BY id DESC`(v2 口径);实验室沿用批1 `id DESC`;
- **is_auto_added**:建档恒 false(codegen VO 不暴露该字段于 SaveReqVO 的必填,service 强制置 false),RespVO 保留只读输出——v2 同(INSERT 写死 FALSE,列表页只展示"自动建/手工"标签);
- **ETL**:`scripts/etl_v2_competitions_laboratories_to_v3.py`(venv python,psycopg2+pymysql,环境变量 `AWARDIE_MYSQL_PASSWORD`/`PGPASSWORD`);显式 id;竞赛全字段 + 布尔→BIT;实验室 name/description(cover_image 不迁,批4);前置清 dev 库批1 测试遗留(deleted=1 的 11 行,物理 DELETE);ON DUPLICATE KEY UPDATE 幂等;末尾 `ALTER TABLE AUTO_INCREMENT=max+1`;输出计数/id 差/hash 无关校验;dev 实跑并记录;
- **菜单 SQL**:`awardie-business-menus.sql` 追加 competitions 父菜单 3002 + 5 权限点 3021-3025(固定 ID 幂等);`awardie-user-domain.sql` 的 awardie_admin 授权 ID 列表扩到含 3002/3021-3025;
- **不做**:前端页面(批10);实验室成员/图片/下载端点(批4);成果五表建表(批6);templates 建表(批7);竞赛与实验室的相互关联(v2 无此关系,不动)。

## Testing Decisions

- 沿用批1 建立的范式:`yudao-server/src/test/java/cn/iocoder/yudao/server/business/`,`@SpringBootTest(classes=YudaoServerApplication.class)` + dynamic-datasource master 键覆盖到 `awardie_v3_test` + 自播种用户真登录 token + tenant-id: 1,只测外部行为(HTTP 契约 + DB 终态);
- **竞赛**(新 `CompetitionsControllerTest`):create/get/page(q 命中与未命中)/update 全字段/delete 成功 + 删后再查 null + 更新已删报 `COMPETITIONS_NOT_EXISTS`;重名 create 报 `COMPETITIONS_NAME_DUPLICATE`;未登录 401;
- **引用检查**(新 `ReferenceCheckTest`,纯 service 层 + MockMvc 双证):
  1. 建临时引用表 `awardie_awards`(测试内建、测试后删)插一行 competition_id=X → 删竞赛 X 报 `COMPETITIONS_IN_USE` 且消息含表名与行数;同法验实验室四张表各自触发;
  2. 引用行 `deleted=1` → 删除放行(逻辑删除不阻断);
  3. 引用表不存在(用清单外的表名场景:本批 dev 无成果表)→ 删除放行,不误拒;
- **实验室补全**(扩 `LaboratoriesControllerTest`):重名 create 拒绝;引用存在时 delete 拒绝;现有 3 例不回归;
- **ETL**:dev 库实跑记录入 03-测试.md(计数 218/5、id 保真抽查、二跑幂等、AUTO_INCREMENT);CI 无 PG 不纳入 CI;
- 断言前自问"是否因默认值巧合通过":引用检查三例均用**非默认表名与非默认 id**,deleted 位显式置 1/0,不用缺省。

## Out of Scope

前端(批10);实验室成员/图片/下载三表与详情聚合端点(批4);成果五表与 templates 表建表(批6/7);成果与竞赛/实验室的数据关联迁移(批12);v2 `laboratory_assistants` 等无 FK 保护的历史关系(批4 一并处置)。

## Further Notes

- v3 是逻辑删除,引用检查是删除保护的唯一防线(无 FK 兜底),因此该组件的错误码与消息必须稳定可诊断——批4-6 建表后要复核清单是否覆盖齐全,记入批4 出口条件;
- `information_schema` 查询每次 delete 只走一次(表存在性缓存于组件首次调用,单请求内有效),不做全局缓存,避免热改表后陈旧;
- 批1 遗留的 11 行 deleted=1 实验室行在 ETL 中物理清理;CI test 库每次全新初始化,无此问题;
- 竞赛 218 条名称全唯一 → ETL 的 ON DUPLICATE KEY UPDATE 幂等键为 id + 名称双保障;
- ETL 脚本内不得出现明文口令,一律环境变量(与批2 ETL 同纪律)。
