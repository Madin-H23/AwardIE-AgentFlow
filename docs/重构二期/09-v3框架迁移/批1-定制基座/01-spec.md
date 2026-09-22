# 批1-定制基座 Spec(01-spec)

> 来源:00-需求.md + CONTEXT.md(grilling 两轮 8 决策)| 2026-09-22 | 基线:5346ap33

## Problem Statement

芋道 stock 骨架虽已跑通,但当前是"上游原装"状态:品牌坐标是 cn.iocoder/ruoyi-vue-pro、库里是 15 个演示用户和全套演示业务数据、本地开发用 MySQL root 明文口令、v3 分支没有 CI、我们自己的业务域没有一个落脚模块。后续 12 个业务批次如果从这个状态起跑,每一批都要先和上游形态搏斗一圈,演示数据还会污染交付与统计。

## Solution

把底座改造成 AwardIE v3 的定制基座,一次性做完五件事:外显三层改名(坐标/品牌/库名)、演示数据清理脚本化、MySQL 专用用户+环境变量口令、v3 分支 CI、以及一个经过端到端验证的业务模块骨架(yudao-module-business,以 laboratories 实验室域作为首个垂直切片,并用芋道 codegen 生成以验证生成器路线)。

## User Stories

1. As a 开发者, I want 仓库坐标/应用名/库名是 awardie 体系, so that 交付物对外身份统一、不与上游混淆;
2. As a 开发者, I want 一条命令把官方 SQL 导入后清理成最小系统集, so that 新环境初始化不残留演示数据、升级上游后可重复;
3. As a 开发者, I want 应用只用专用 MySQL 用户且口令经环境变量注入, so that 凭据不落库、团队 clone 即用;
4. As a 开发者, I want 推 v3 分支自动跑 CI(编译+测试+门禁), so that 每批改动有质量闸门,v2 流水不空跑;
5. As a 开发者, I want 一个装全部业务域的模块骨架和首个端到端切片, so that 后续 12 批直接照范式长,不重复探路;
6. As a 开发者, I want 芋道 codegen 在标准 CRUD 上被验证可用, so that 后续 CRUD 批走生成器、复杂域手写的策略有实证;
7. As a 审查者, I want 上游基线提交与我们的改造提交在 git log 中可区分, so that 升级上游时 diff 边界清晰。

## Implementation Decisions

- **外显三层**:Maven groupId `cn.iocoder.boot`→`com.awardie`(根 pom+dependencies+各 module pom,约 25 处);Spring `spring.application.name` 与 server 模块品牌标识改 AwardIE v3;数据库 `ruoyi-vue-pro`→`awardie_v3`(重建库+重灌脱敏 SQL+重跑清理);**内部包名 cn.iocoder.yudao 不动**(ADR-0003);
- **清理脚本**:`awardie-v3/sql/awardie-cleanup.sql`,官方(脱敏)SQL 导入后追加;保留最小集=admin 用户、super_admin/common 角色、系统菜单与权限、基础字典类型结构;删除其余 stock 演示用户/部门/岗位/短信通道/文件配置/codegen 演示等;幂等(可重复执行);
- **凭据**:`application-local.yaml` 数据源改 `password: ${AWARDIE_MYSQL_PASSWORD:123456}`;建 MySQL 用户 `awardie_v3`(仅 awardie_v3 库授权);撤 .git/info/exclude 补丁;全仓 grep 确认无其他明文口令入库;
- **CI**:新增 `.github/workflows/ci-v3.yml`——触发=push/PR 到 `refactor/v3-yudao-migration` 且 paths=`awardie-v3/**`;job=MySQL 8 service+Redis service+建 awardie_v3_test 库+官方 sql+cleanup+`mvn -B test`(awardie-v3 目录);`ci-v2.yml` 加 branches 过滤排除 v3 分支;前端门禁待批10 submodule 初始化后接入;
- **业务模块**:新建 `awardie-v3/yudao-module-business`(groupId com.awardie,包 cn.iocoder.yudao.module.business),根 pom 启用;含 controller/service/mapper/entity/vo/errorcode/convert 标准分层+菜单 SQL+模块错误码段;
- **首个切片 laboratories**:表 `awardie_laboratories`(id/name/description/创建审计字段,迁移脚本由我们维护,不放 Flyway——芋道不用 Flyway,SQL 脚本即真相);API=分页列表(关键词)+详情+新增+修改+删除(删除前引用检查:被业务表引用时 4009 同构芋道错误码);**用芋道 codegen 生成 CRUD 骨架再定制**,验证生成器路线;
- **菜单与权限**:切片菜单 SQL 导入后超级管理员可见"实验室管理",权限点 `award:laboratory:*` 三件套;
- **提交规范**:上游基线类提交信息以 `chore(v3-upstream):` 起头,我们的改造以 `feat(v3):`/`fix(v3):`,git log 可区分(需求 R6)。

## Testing Decisions

- 只测外部行为(HTTP 契约+DB 终态),不测实现细节——与项目既有纪律一致;
- **Seam 选择(1 个)**:业务模块的 REST 接口层,经 Spring `MockMvc`+独立 test 库 `awardie_v3_test` 直测;芋道上游代码不补测试(其自身几无测试,不为上游补);
- 切片测试覆盖:分页/关键词/增改查/删除/引用冲突拒绝/权限(非 admin 403)/菜单导入后权限面含新权限点;
- prior art:v2 的 BaseIntegrationTest 范式(TestRestTemplate+cookie/XSRF)在 v3 不适配——芋道是 token 认证无 CSRF cookie,v3 测试范式=MockMvc+Bearer token,本批建立样板;
- CI 中跑模块测试;本地 `mvn -B test`(awardie-v3)等价。

## Out of Scope

前端 submodule 初始化与任何 UI(批10);laboratories 之外的业务域(批2 起);v2 数据 ETL(批12);AI Worker 对接(批5/7);内部包名 rename(ADR-0003 挂稳定期);芋道其他 module(bpm/ai/mp/pay/mall)的启用。

## Further Notes

- 芋道错误码体系:业务错误码按 module 分段(如 award 模块 1-0400-0000 段),切片遵循芋道 ErrorCode 惯例,不新造体系;
- codegen 生成物与手写定制的边界要记录(哪些文件是生成的、定制改在哪些层),便于后续批复用;
- 演示数据清理后,admin 口令 admin123 建议在清理脚本里一并改密为项目口令(需求 R2 最小集的一部分,spec 落定:清理脚本含 admin 口令更新)。
