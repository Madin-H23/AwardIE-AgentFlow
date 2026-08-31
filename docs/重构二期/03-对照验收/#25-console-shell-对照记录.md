# #25 Console Layout Shell 对照记录

> 基调:逐页对照 v1 原模板,布局与设计 1:1 不变,仅换 Element Plus 实现。
> v1 源:`app/templates/layout/base_console.html` + `layout/sidebar.html` + `layout/navbar.html` + `static/css/console_tokens.css`(L56-153 控制台骨架段)。
> v2 落点:`awardie-frontend/src/layouts/ConsoleLayout.vue` + `router/index.ts` children 化 + `styles/tokens.css` 增补。

## 一、v1 区块清单(实现前提取)

### 1. `.console-shell` 容器
min-height 100vh;background var(--bg)。

### 2. `.console-sidebar` 左固定侧边栏
`position:fixed; inset:0 auto 0 0; width:240px; padding:16px 10px; border-right:1px solid var(--sb-line); overflow-y:auto; z-index:1030`

- **admin 菜单结构**(sidebar.html L3-99):
  1. 置顶「数据总览」`.nav-overview`(bi-speedometer2;font-weight 600;letter-spacing .02em;padding 9px 12px;border 1px solid sb-line;图标 brand 色,active 白色)
  2. `hr.sidebar-divider`(margin 10px 8px)
  3. 分组「常用」`.sb-group`(title:.7rem/600/letter-spacing .1em/sb-muted/padding 14px 12px 6px + chevron-down):成果管理(bi-award)/成果审核(bi-clipboard-check)/日志管理(bi-journal-text)
  4. divider
  5. 分组「智能体」:AI 智能体协作(bi-robot)
  6. divider
  7. 分组「基础数据管理」:成果/文件导入(bi-cloud-arrow-up)/奖状模板管理(bi-file-earmark-richtext)/竞赛管理(bi-trophy)/实验室管理(bi-diagram-3)
  8. divider
  9. 分组「用户数据」:学生管理(bi-people)/教师管理(bi-person-badge)/数据分析(bi-bar-chart)/数据导出(bi-download)
  10. divider
  11. 分组「系统设置」:系统设置(bi-gear)
- **teacher 平铺**(L101-111):教师首页(bi-house)/成果展示(bi-folder2)/成果审核(bi-clipboard-check)
- **student 平铺**(L112-120):学生首页(bi-house)/我的成果(bi-folder2)
- **nav-link 通用**:flex gap 10px;padding 8px 12px;radius 6px;font-size .88rem;color sb-ink;hover bg sb-hover;**active bg var(--brand) 白字**;图标 .92rem width 16px
- **折叠交互**:`.sb-group.collapsed` → chevron rotate(-90deg)、body display:none
- **底部账户栏 `.sb-footer`**(sticky bottom;margin-top 12px;padding 12px 10px;border-top sb-line;background sb-foot):
  - `.sb-user`:person-circle 图标(brand 色 1.15rem)+ 用户名 + `.sb-role` 徽标(margin-left auto;.68rem;uppercase;letter-spacing .05em;sb-muted)
  - `.sb-ver`:版本文字(.68rem sb-muted)「AwardIE-AgentFlow 控制台 v1.0 · 管理端」

### 3. `.console-topbar` 顶栏
`position:fixed; top:0; right:0; left:240px; height:52px; background var(--panel); border-bottom 1px solid var(--line); flex align-center gap 12px; padding 0 20px; z-index:1020`

- `.topbar-title`(.95rem/600;块变量,各页覆写,默认「控制台」)
- `.theme-toggle`(margin-left auto;34x30;border line;radius 6px;月亮/太阳 SVG 切换;hover brand)
- `.topbar-user` 下拉(el-dropdown 替代 bootstrap dropdown):
  - 按钮:头像 26px 圆(brand 底白字姓名首字母)+ 姓名(.85rem)+ chevron(.6rem);hover 边框 line
  - 面板:user-head(姓名+role uppercase .72rem)+ divider + 退出登录(bi-box-arrow-right);钉 top 58px right 18px

### 4. `.console-main` 内容区
`margin-left:240px; padding:72px 24px 32px`;顶部 flash 消息区(v2 由 ElMessage 承担,不再渲染 flash 条)。

### 5. navbar.html(旧 base.html 体系)
品牌「成果管理系统」/「回到主页」/欢迎+姓名/登出——已被 base_console 顶栏体系演进覆盖,**不单独复刻**,品牌词并入 shell 的页面标题体系。

## 二、v2 映射表(布局 1:1,菜单只挂 v2 真实路由)

| v1 菜单项 | v2 处置 | 理由 |
|---|---|---|
| 数据总览(bi-speedometer2) | 保留 → `/admin/dashboard`(Odometer) | v2 有 |
| 成果管理(bi-award) | 保留 → `/admin/awards`(Medal) | v2 有 |
| 成果审核(bi-clipboard-check) | 保留 → `/teacher/review`(DocumentChecked) | v2 有,admin 可进 |
| 竞赛管理(bi-trophy) | 保留 → `/admin/competitions`(Trophy) | v2 有 |
| 日志管理/AI 智能体/成果文件导入/奖状模板/实验室/学生/教师/数据分析/数据导出/系统设置 | **不渲染** | v2 纵切面无对应页,渲染即死链 |
| 教师首页(bi-house) | 保留 → `/`(House) | v2 工作台首页 |
| 成果展示(bi-folder2) | 不渲染(v2 教师无独立成果页) | 死链禁挂 |
| 学生首页(bi-house) | 保留 → `/`(House) | 同上 |
| 我的成果(bi-folder2) | 不渲染(v2 在提交页内嵌时间线) | 死链禁挂;学生增挂「提交奖状」→`/submit` |

分组结构保留:admin = 置顶总览 + divider + 「常用」组(成果管理/成果审核)+ divider + 「基础数据管理」组(竞赛管理);teacher/student 平铺(对照 v1)。折叠交互保留(空组不渲染则无折叠,分组保留 chevron)。

## 三、7 页接入 children

`/login`、`/change-password` 不带 shell;其余 7 页(home/submit/teacher-review/profile/admin-awards/admin-competitions/admin-dashboard)挂 `ConsoleLayout` children。守卫逻辑不变。

## 四、E2E 兼容

`.home` 类与各页 heading/testid 不变;E2E 仅依赖 login-account/login-password/login-submit/profile-name 四 testid(已核实)。App.vue 右下角 fixed 主题钮移入顶栏(testid 保留 data-testid="theme-toggle")。

## 五、对照截图

见本目录 `#25-v1-sidebar.png` / `#25-v2-sidebar.png`(v1: 127.0.0.1:5001/admin/dashboard;v2: 127.0.0.1:5199/v2/admin/dashboard)。
