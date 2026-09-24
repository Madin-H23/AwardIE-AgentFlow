# 批2-用户与角色域 Spec(01-spec)

> 来源:00-需求.md(grilling 4 决策按推荐案落地,标注待复核)| 2026-09-24

## Problem Statement

v3 目前只有芋道 stock 的最小用户集(1 个清理后的 admin),v2 的 1834 个真实用户、三角色语义、scrypt 口令体系都不在。后续每个业务批(提交/审核/成果)都挂在用户与角色上,没有真实用户域,批 3 之后全部空转。

## Solution

把 v2 用户域迁入 v3:三角色 RBAC 新建、scrypt 口令兼容+登录升级 BCrypt、1834 用户 ETL(显式保 v2 id,为批12 外键迁移铺路)、v2 资料扩展字段落扩展表。登录字段天然对齐(都是 login_code/username)。

## User Stories

1. As a 迁移负责人, I want 一条幂等脚本把 1834 个 v2 用户连同角色/资料字段迁到 v3, so that 不手工建号、可重复执行;
2. As a 学生, I want 用 v2 的同一账号口令直接登录 v3, so that 无感知迁移、不需要改密;
3. As a 系统, I want 用户首次登录后口令自动升级为 BCrypt, so that 逐步收敛到上游安全栈;
4. As a 开发者, I want v2 的 student/teacher/admin 三角色在 v3 可区分可授权, so that 业务权限点按角色授予;
5. As a 批12 负责人, I want v2 用户 id 在 v3 一一保留, so that 成果表 submitter_id 外键原样迁移、免映射表;
6. As a 开发者, I want v2 的专业/年级/职称等资料字段有着落, so that 学生/教师门户批(批10)有数据可用。

## Implementation Decisions

- **口令编码器**:业务模块新增 `AwardiePasswordEncoder`(@Primary PasswordEncoder):`scrypt:` 前缀→BouncyCastle SCrypt 逐参复算(参数从哈希串解析);其余→委托 BCryptPasswordEncoder。移植自 v2 `WerkzeugCompatPasswordEncoder`(去掉其 bcrypt 历史兜底分支之外的逻辑不变);依赖 `org.bouncycastle:bcprov-jdk18on:1.78.1`(与 v2 同版本);
- **登录升级**:`AuthenticationSuccessEvent` 监听器,认证成功后若该用户口令仍为 scrypt 前缀,用 encoder.encode(原始口令) 重编码并 UPDATE system_users(原始口令从事件的 Authentication credentials 取,Spring Security 6 ProviderManager 先 publish 后 eraseCredentials——实现时以测试实证为准,若 credentials 已被清空则回退"仅兼容不升级"并在文档挂账);
- **角色**:SQL 建三角色(code=awardie_admin/awardie_teacher/awardie_student,name=管理员/教师/学生);laboratory 四权限点菜单(3011-3015)授 awardie_admin;ETL 按 v2 role 关联 system_user_role;
- **ETL 脚本** `scripts/etl_v2_users_to_v3.py`(venv python,psycopg2+pymysql):PG awardie_dev → MySQL awardie_v3;两表(system_users+awardie_user_profile);显式 id;username ON DUPLICATE KEY UPDATE 幂等;末尾 ALTER TABLE ... AUTO_INCREMENT=max(id)+1;校验输出(行数/id 集合差/hash 前缀分布);
- **扩展表** `awardie_user_profile`(user_id BIGINT PK、major、grade、title、qq、skills、profile_is_public BIT 默认 1),DDL 入 `awardie-v3/sql/awardie-business.sql`;
- **v2 admin 覆盖 stock admin**:id=1 同行覆盖(口令变为 v2 admin 的),批1 的 LaboratoriesControllerTest 解耦对此的依赖(见 Testing Decisions);
- **不做**:部门树、注册、OAuth2、v1 哈希同步(v1 独立 SQLite,不碰)。

## Testing Decisions

- 只测外部行为(HTTP 契约+DB 终态);
- **Prefactor(先做)**:批1 LaboratoriesControllerTest 当前依赖 cleanup 后的 admin 口令——ETL 会覆盖该口令导致其本地必挂。改为测试自播种用户(mapper 直插 bcrypt 已知口令+角色),与环境状态解耦;
- **新集成测试** `UserMigrationAuthTest`(yudao-server/src/test 同范式):①mapper 播种一个 scrypt 哈希用户(哈希用 v2 同构参数现场生成)→ MockMvc 登录成功 → DB 中断言该用户口令已升级为 `$2` 前缀 → 再次登录成功;②三角色关联各取一样本;③匿名登录 401;
- **ETL 验证**(CI 无 PG,本地手动+记录):对 awardie_v3 实跑→计数 1834/1834、id 保真抽查、hash 前缀 scrypt 保留、二次跑幂等(计数不变)、AUTO_INCREMENT 已抬;记录入 03-测试.md;
- prior art:批1 LaboratoriesControllerTest 的登录/租户/断言范式。

## Out of Scope

部门/岗位树;用户注册;社交登录;学生教师门户页(批10);成果数据外键迁移(批12,本仅保 id 保真);v1 SQLite 侧任何改动。

## Further Notes

- 若 AuthenticationSuccessEvent 拿不到原始口令(credentials 已清),回退方案=保持 scrypt 永久兼容并在批1 文档同款挂账,升级改期;
- 芋道 username 唯一性:ETL 前需确认 PG login_code 无重复(1834 条唯一,脚本内置校验,有重复则报错中止);
- admin 覆盖后,本地 dev 库 admin 口令=v2 的(Mayy123 系),批1 测试自播种后不受影响。
