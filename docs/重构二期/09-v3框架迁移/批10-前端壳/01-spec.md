# 批10-前端壳 Spec(01-spec)

> 2026-09-26 | 依据 `00-需求.md`(R1-R8)与 `CONTEXT.md` 批10 决策 P1-P7
> grilling 产出见 CONTEXT.md 批10 词汇与决策;架构决策见 `docs/adr/0004-前端框架冻结与分层所有权.md`

## Problem Statement

v3 后端做完了九批,用户在浏览器里看不到任何东西。学生提交成果、老师审批、管理员看统计,全无入口。

"做一个界面"有七种做法,差别不在首次工作量(用户明确不是约束),而在**使用效果**与**切流后的维护**。

- 拿芋道通用后台框架:基础设施(布局/权限/表格/119 个系统管理页)现成,但交互是给 ERP/CRM 设计的,不是给"上传奖状→看抽取→审批"设计的。
- 全盘复用 v2 自建前端:交互贴合业务(五批 UX-1),但**没有用户/角色/菜单/字典**这一整块能力,而 v3 后端已迁完整的芋道 system 模块,前端却对不上;还带三个月技术债与 7 个不需要的页面。

各有一半是对的,合起来才是完整答案。

## Solution

**混合方案,分三层,每层所有权不同;框架版本冻结不跟随上游。**

```
框架层 —— 芋道的,不主动改,升级需连带上游
  src/layout  src/components  src/config  src/store  src/router
  src/views/{infra,system}     119 个系统管理页
  → 冻结在 @aab14fb0,不做例行升级

业务层 —— 按 v3 API 重写,完全自主
  src/api/business/**
  src/views/business/**        9 个管理页 + 教师页
  src/views/portal/**          学生门户 + 教师门户
  → 上游变更完全不影响

交互层 —— 从 v2 移植,自定义组件
  PageHeader / TableSkeleton / 150ms 过渡 / 筛选折叠 / --tag-* 色板
  → 放在业务层内,不改框架目录
```

**为什么冻结而不是跟随**(见 ADR-0004):判准是业务稳定性,而**批11 就是切流**。切流前引入"定期拉上游"是纯风险源——框架层一动,119 个系统管理页跟着动,任何回归都要在生产前现场修。芋道后端我们早已深度 fork 且很少同步,前端保持一致。安全补丁通过锁定 `pnpm-lock.yaml` 定向升级依赖解决。

**冻结带来的额外好处**:分层边界的意义从"降低未来同步成本"变成"**清楚哪些代码是我们该维护的**"——所有权清晰本身就是价值,即使永不升级也成立。

## User Stories

1. As a 管理员, I want 登录后看到 AwardIE 侧边栏而非芋道的几十个示例模块, so that 我能立刻找到要的功能。
2. As a 管理员, I want 在实验室页能增删改查实验室, so that 我能维护基础数据。
3. As a 管理员, I want 在竞赛页能增删改查竞赛, so that 我能维护基础数据。
4. As a 管理员, I want 在成果提交页看到待审列表并能审核通过/驳回, so that 我能推进审核流。
5. As a 管理员, I want 在审核详情看到时间线与 AI 建议, so that 我能判断是否通过。
6. As a 管理员, I want 在成果库页按五类切换查看并能行编辑/删除, so that 我能维护已入库成果。
7. As a 管理员, I want 在证书模板页创建模板(带样本图)、试测 AI 抽取、生成 prompt, so that 我能配置抽取规则。
8. As a 管理员, I want 在大创页查看项目、批量校准状态、导入 xlsx, so that 我能维护大创数据。
9. As a 管理员, I want 在统计分析页看到汇总卡片、五类分类、竞赛 Top12, so that 我了解整体规模。
10. As a 管理员, I want 在数据导出页下载 CSV/Excel, so that 我把数据交给院里。
11. As a 管理员, I want 在业务日志页按类型/动作/操作人/日期筛选审核留痕, so that 我能追溯操作。
12. As a 管理员, I want 还能管理用户与角色权限, so that 我控制谁能看到这些页面。
13. As a 教师, I want 登录后侧边栏出现"我的待审"和"我的指导成果", so that 我能完成初审(批5 审核流建立在我身上)。
14. As a 教师, I want 在待审页看到所有待审并能审核, so that 我推进审核。
15. As a 教师, I want 在我的指导成果页看到我指导的获奖, so that 我了解自己的成果。
16. As a 学生, I want 在手机浏览器上提交奖状照片并填信息, so that 我不用电脑也能申报。
17. As a 学生, I want 看到我的提交处于什么状态(待审/通过/驳回), so that 我知道结果。
18. As a 学生, I want 看到被驳回的原因, so that 我知道怎么改。
19. As a 学生, I want 在成果页查看已获得的证书图片, so that 我能保存证明材料。
20. As a 学生, I want 在手机上这些都能做, so that 移动端体验不差。
21. As a 运维, I want 仓库里前端源码能直接构建, so that clone 后不用额外拉取外部仓库。
22. As a 运维, I want 前端升级时只冲突框架目录,业务代码不受影响, so that 维护成本可控。
23. As a 运维, I want 构建、类型检查、lint 都作为门禁, so that 前端质量有底线。

## Implementation Decisions

### 1. 冻结前端框架版本(P1,ADR-0004)

- 源码基于 `yudaocode/yudao-ui-admin-vue3@aab14fb0` 同步入库,移除嵌套 .git,README 顶部标注同步点与改造摘要;
- **不做例行上游升级**;安全补丁通过锁定依赖定向升级解决,不整体拉上游;
- 依赖版本锁在 `pnpm-lock.yaml`,提交入库以保证可复现构建。

### 2. 基座改造(R1,已完成)

- 删除 24 个示例业务模块(views + api 双目录),只留 `infra`/`system`;views 25→8 目录,api 20→3,src 文件数 2758→739;
- 清理五处悬空引用(删模块的连带影响):
  - `router/modules/remaining.ts`:删除 282 行起 828 行业务路由,并**补回被截断的 `export default remainingRouter`**;
  - `main.ts`:移除 `@/views/bpm/model/form/PrintTemplate` 的 wangEditor 插件(BPM 整体无用);
  - `layout/components/ToolHeader.vue`:移除 `FmsAccountSetSwitch`(财务科目切换器);
  - `components/AppLinkInput/AppLinkSelectDialog.vue`:商城商品分类选择器 → 通用 `el-input-number` 手填 id + 补确认按钮(无商品中心);
  - `components/DiyEditor/components/mobile/*`:删 6 个商城营销卡片;注册表用 `import.meta.glob` 自动扫描,免维护索引;
- 基线构建全绿:**4.99s**(删模块前 26s)。

### 3. API 层(R2)

- 路径与后端 Controller **逐条核对**(已踩两次凭记忆写错:待审无 get 端点、模板创建是 `/create`);
- 走框架 `request` 封装,`/admin-api` 前缀由 `.env.local` 的 `VITE_API_URL` 提供;
- **下载统一走 `request.download()`**——它会读错误响应;v2 的裸 `<a>` 直链在导出失败时会把错误响应体当文件下载(批9 修好的行数上限报错 `1003009000` 靠这个才能提示到用户)。

### 4. 页面与动态路由机制(R3)

- **前端文件路径由菜单 SQL 的 component 字段决定,不可自选**;配错 → 路由解析失败 → **白屏**;
- 芋道 `generateRoutes()` 读后端菜单,`routerHelper` 把 `business/laboratory/index` 解析为 `@/views/business/laboratory/index.vue`;
- 通用范式:`ContentWrap` + `el-table` + `Pagination` + 表单弹窗;
- 实施顺序按"数据只读 → 简单 CRUD → 复杂交互":统计 → 日志 → 导出 → 实验室 → 竞赛 → 成果库 → 成果提交 → 证书模板 → 大创;
- 每页含:加载态、空态、错误提示、分页、按钮按权限点隐藏。

### 5. 教师端:走菜单不做静态路由特例(P4,业务稳定性)

教师是审核流的执行者(批5 整个审核流建立在教师初审上),无入口即业务断链——这是核心功能,必须做。

但实现上**必须走菜单**,与九个管理页同机制:教师角色 101 已有 `pending-achievement:query` / `review` 权限点,加菜单并授权即由动态路由带出。

**为什么不用静态路由特例**:静态路由是第二条代码路径——权限判定、面包屑、keep-alive、404 兜底都要各维护一遍,是典型的不稳定来源。统一机制比省事更重要。

需新增两菜单:教师待审、教师指导成果;授权 100(admin 顺带能看)+ 101(teacher)。

### 6. 学生端三场景与移动端(R4/R5,P5)

- **提交成果**:五类选择 + 动态表单 + 文件上传(multipart 对齐批4 `POST /business/pending-achievements/submit`);
- **查进度**:我的提交列表(`GET /my-page`)+ 状态 + 时间线(`/{id}/timeline`);
- **证书查看**:已入库成果的证书图片(批4 物化带 `certificate_path`);
- 学生端走门户布局,但**路由仍走菜单**(同 P4 的理由);
- 移动端:**375px 为验证基线,验到 430px,不做平板**。375 比 430 更窄,375 成立则 430 通常成立;真风险是反向(按 430 设计在 375 崩)。平板 768px 是新功能不是稳定性要求;
- 侧边栏小屏折叠为抽屉;表格小屏转卡片式;弹窗小屏全屏;触控目标 ≥ 44x44。

### 7. UX-1 交互移植(R6)

移植五项(记忆实证五批投入):`PageHeader`、`TableSkeleton`、150ms 路由过渡、筛选折叠、`--tag-*` 徽章色板。**放在 `src/views/business/components/` 下,不改框架目录**(保证上游变更时只冲突框架 7 目录,且冻结后这层边界只用于所有权标识)。

### 8. 验证深度:必须实际启动(P6)

构建只验静态 import,查不出动态路由与运行时解析;**学生端白屏是灾难性的**。

验证清单(P6):
1. 登录 → 侧边栏渲染(验动态路由机制,配错会白屏)
2. 九个管理菜单逐个点开
3. 教师菜单(待审/指导成果)可见可用
4. 学生端三场景
5. 系统管理几页(用户/角色/菜单/字典)
6. **页面装修器能打开**(DiyEditor 我们改过,删过 6 个商城卡片)
7. 375px 与 430px 两个宽度下学生端三场景截图

### 9. 质量门禁与 CI(R7)

- `pnpm build:local` —— **唯一硬门禁**;
- `pnpm ts:check`(上游自带 vue-tsc);
- `pnpm lint:eslint` / `lint:style`(上游自带配置);
- E2E(Playwright)覆盖:登录 → 九管理页 → 教师页 → 学生端三场景 → 375/430px;
- `ci-v3.yml` 现有 `backend-v3` 需加 `frontend-v3` job。**注意 CI 跑 Linux**,与本地 Windows 有差异,尤其 `rolldown` 原生模块的平台包需验证。

## Testing Decisions

- **主门禁是构建**:前端不像后端有 101 个单测兜底,`build` 绿是底线;
- **类型检查必须过**:`ts:check` 拦"页面写错字段名/调错 API"这类静默错误;
- **运行时验证不可省**(P6):构建查不出动态路由,必须实际启动逐功能点;
- **API 路径逐条对照后端 Controller**:已踩两次记忆写错的坑,列为 ticket 验收项;
- **移动端截图**:375px 与 430px 双宽度下学生端三场景必须完整可用。

## Out of Scope

- 小程序/uniapp(P7,用户 2026-09-25 拍板:网页端移动端适配优先)
- 平板专门布局(P5:新功能非稳定性要求)
- AI 对话页面(v2 `ChatView`,批7 走 gRPC)
- 自动归档配置页(v2 `AdminSettingsView`,死配置)
- 实验室数据分析页(依赖批9 已阻塞的实验室维度统计)
- 前端国际化(芋道有多语言,本项目只做中文)
- 复杂图表(趋势图待批9 前置债解决)
- 框架层跟随上游升级(P1 冻结)

## Further Notes

- **冻结的隐含要求**:框架层代码要"可读可改"而不是"不敢动"——我们虽不升级,但遇到框架 bug 仍需能改(改了就脱离上游,这是冻结的代价,要接受)。README 需写清这一点。
- **上游 HEAD 自身构建不过**:`aab14fb0` 的 `oa/attendance` 引用不存在的 `@/views/oa/utils/constants`,我们靠删 OA 绕过。下次若解冻并升级上游,先查这一条。
- **中文路径不是本次构建的根因**:初遇 rolldown 的"找不到指定路径"曾怀疑中文路径(批7 的 protoc 确是该根因),但复制到纯 ASCII 路径重装依赖后报同样错,已排除。相似症状不同根因,必须实测对照。
- **新会话起手点**:T01 已完成待落盘,新会话从 T02(补齐 API)或 T03(九个页面)开始,详见 `tickets/`。
