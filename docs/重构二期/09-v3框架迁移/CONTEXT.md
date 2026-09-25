# v3 框架迁移 CONTEXT(grill-with-docs 状态文件)

> 2026-09-22 批1 grilling 两轮后落盘 | 本文件是 v3 工作线的共享词汇与决策记录,spec/tickets/实现都引用它
> 工作线根:`docs/重构二期/09-v3框架迁移/` | 代码:`awardie-v3/`(芋道 master-jdk17 基线 7cab3a7)

## 领域词汇表(domain glossary)

| 术语 | 含义 |
|---|---|
| 上游基线 | 芋道 ruoyi-vue-pro master-jdk17 的入库快照(commit 7cab3a7),我们的改动以它为 diff 基准 |
| 外显三层 | Maven groupId / 应用名与品牌 / 数据库名——批1 唯一允许改的"身份"面 |
| stock 演示数据 | 芋道官方 SQL 带入的演示用户/部门/字典/短信/文件配置等,批1 清理 |
| 业务模块 | `yudao-module-business`(包路径 cn.iocoder.yudao.module.business),装我们全部业务域 |
| 垂直切片 | 贯穿 建表→数据访问→service→REST→测试 的端到端窄片,首个切片=laboratories 实验室 |
| 专用用户 | MySQL 用户 awardie_v3,仅授权 awardie_v3 库,替换 root |
| test 库 | awardie_v3_test,与 dev 库 awardie_v3 隔离,CI 自播种 |
| 脱敏脚本 | scripts/v3_sanitize_sql_secrets.py,官方 sql 的云 Key 演示串→DEMO-REMOVED-BY-AWARDIE |
| 清理脚本 | awardie-v3/sql/awardie-cleanup.sql,官方导入后追加执行,删演示数据留最小集 |
| 三道闸 | 双轴 review(/code-review Standards+Spec)+ OCR(项目纪律)+ security-audit + p3c |
| 五门禁(项目既有) | lint / raw-controls / jdbc-audit / build / 后端测试,v3 CI 等价物 |

## 已落定决策(2026-09-22 grilling,全部按推荐答案)

| # | 决策 | 内容 |
|---|---|---|
| Q1 | 内部包名 | **暂留 cn.iocoder.yudao**,只改外显三层;ADR-0003 承载,稳定期后评估改名 |
| Q2 | 口令注入 | tracked yaml 改 `${AWARDIE_MYSQL_PASSWORD:123456}` 环境变量注入,撤 .git/info/exclude 补丁 |
| Q3 | 清理形态 | 独立 cleanup SQL(官方 sql 原样+我们追加),升级三步:archive→脱敏→清理 |
| Q4 | 首个切片 | laboratories 实验室域(CRUD+关键词筛选+引用计数) |
| Q5 | 业务模块 | yudao-module-business(与上游 module 命名/包路径同构),groupId 改 com.awardie |
| Q6 | CI 触发 | v3 工作流=分支(refactor/v3-yudao-migration)+路径(awardie-v3/**)双过滤;ci-v2 反向排除 |
| Q7 | codegen | 标准 CRUD 用芋道 codegen 生成(前端正好配批10 admin-vue3),审核流/统计/AI 手写 |
| Q8 | 测试库 | 独立 awardie_v3_test,CI 用 MySQL service+官方 sql+cleanup 初始化 |

## 既有事实锚点(不再重新论证)

- 环境:MySQL 8.0.41(3306)/Redis 5.0.14.1 便携(6379)/yudao-server 48080/admin 口令 admin123;
- 上游约束:默认装配仅 system+infra;yudao-ui 五前端是 submodule 占位(批10 初始化 admin-vue3);PG 有脚本但非默认路径,v3 走 MySQL;
- GH013:官方 sql 演示云 Key 会被 push protection 拦,脱敏脚本已处置,上游升级后必须重跑;
- 磁盘:D 盘余量是硬约束(曾打满),大提交/amend 前先 df -h,构建产物随删。

## 流程(用户 2026-09-22 规定)

需求梳理(grilling+本文档)→ to-spec → to-tickets → 实现(每 ticket /implement 驱动 /tdd)→ 自测 → 三道闸(双轴 review+OCR+security-audit+p3c)→ 截图验收+清理测试文件+commit。spec/tickets 无外部 tracker,落本工作线文档目录。

---

## 批10 词汇补充(2026-09-26 grilling)

| 术语 | 含义 |
|---|---|
| 框架层 | 芋道前端自带的 src/layout、src/components、src/config、src/store、src/router 与 src/views/{infra,system}(119 个系统管理页)。**不属于我们,升级需连带上游** |
| 业务层 | 我们按 v3 后端 API 重写的 src/api/business、src/views/business、src/views/portal。**完全自主,上游变更不影响** |
| 交互层 | 从 v2 移植的 UX-1 资产(PageHeader/TableSkeleton/150ms 路由过渡/筛选折叠/--tag-* 徽章色板),作自定义组件放在业务层内 |
| 动态路由 | 芋道机制:侧边栏来自后端菜单表,`routerHelper` 把菜单 component 字段(如 `business/laboratory/index`)解析为 `@/views/.../index.vue`。**前端文件路径由菜单 SQL 决定,不可自选;配错会白屏** |
| 门户 | 学生/教师端页面,走独立布局不用管理端侧边栏,但**路由仍走菜单**(不搞静态路由特例) |
| 同步点 | 前端源码的上游来源 commit,批10 同步自 `yudaocode/yudao-ui-admin-vue3@aab14fb0`,README 顶部标注 |

## 批10 决策(2026-09-26 grilling,按「业务稳定性」尺子)

| # | 决策 | 内容 | 稳定性理由 |
|---|---|---|---|
| P1 | 框架长期策略 | **冻结在当前版本,不跟随上游升级** | 批11 即切流;切流前引入"定期拉上游"是纯风险源。框架层一动,119 个系统管理页跟着动。代价(安全补丁手动定向升)可控 |
| P2 | 方案选型 | **混合方案**:框架层不动 + 业务层重写 + 交互层移植 | 用户明确"仓库体积与首次工作量不是约束,尺子是使用效果+维护"。芋道补 v2 缺失的 用户/角色/菜单/字典 整块;v2 提供照业务长出来的交互 |
| P3 | 源码入库方式 | **源码入库 + README 标同步点** | 后端已深度 fork 入库(8657 文件),前端保持一致;构建可用性最简单(clone 即可 build,CI 无需处理子模块) |
| P4 | 教师端入口 | **要做,且走菜单不做静态路由特例** | 教师是审核流执行者(批5 整个审核流建立在其上),无入口即业务断链。但必须统一机制:教师角色 101 已有 pending-achievement:query/review 权限点,加菜单授权即由动态路由带出。静态路由特例 = 多一条代码路径 = 权限/面包屑/keep-alive 各维护一遍 = 不稳定来源 |
| P5 | 移动端适配范围 | **375px 为验证基线 + 验到 430px,不做平板** | 375 比 430 更窄,375 成立则 430 通常成立(空间更多);真风险是反向(按 430 设计却在 375 崩)。平板 768px 是新功能不是稳定性要求 |
| P6 | 验证深度 | **必须实际启动应用逐功能点验证** | 构建只验静态 import,查不出动态路由与运行时解析;学生端白屏是灾难性的。清单:登录→侧边栏→九个菜单逐个点→教师菜单→系统管理几页→页面装修器打开(DiyEditor 我们改过) |
| P7 | 小程序 | **不做 uniapp,网页端移动端适配覆盖** | 用户 2026-09-25 拍板;uniapp 是独立 submodule,多一条前端构建链 |

