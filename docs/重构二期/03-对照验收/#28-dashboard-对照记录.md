# #28 admin dashboard 五区块重做 对照记录

> 基调:逐页对照 v1 `app/templates/admin/dashboard.html`(113 行)+ `app/static/js/dashboard.js`(174 行)+ console_tokens.css 生命体征带/筛选栏/提示条样式段。
> 取代 #21 交付(自由发挥版);#21 已留"交付定性修正"评论。

## 一、v1 区块清单(实现前提取)

1. **页面头+提示条**:h1「成果数据总览」(1.35rem/600)+ `.page-alert`(brand 6% 底、info 圆点、「数据实时统计;成果分类以奖状/专利/软著/其他四类统计,最终口径以人工审核归档数据为准。」)
2. **资产条 `.vitals`**(grid 4 列 gap 14px,卡=panel 底/line 边框/radius 8/padding 14 16):
   - 成果总数:值=五类合计;副行「奖状 X · 专利 Y · 软著 Z · 大创 W · 其他 V」
   - 待审核(pulse-dot 红):值=pending_submit;副行「需人工处理/无积压」;>0 时值加 `.alarming` 红色脉冲
   - 白名单竞赛:副行「占 N% 竞赛」
   - 成果·竞赛密度:值=(五类合计/竞赛数).toFixed(1);副行「共 N 个竞赛」
3. **汇总卡 `.c-panel`**:左 1/3 大数字「本周期成果新增(2026 年至今)」+副行「待审核 X · 白名单竞赛 Y / 本月新增 A · 上月 B · 环比 ▲C%」;右 2/3 分类计数 5 行(虚线下划线 item)+公式行「新增 = 奖状 + 专利 + 软著 + 大创 + 其他」+口径注脚「奖状口径:全量 A(其中教师证书 T;管理/学生视角 M)」
4. **工具条+竞赛战果 Top**:filter-bar(周期 select 近6月/近12月/全部+导出按钮)+表格(竞赛/获奖总数/占比,占比行内 5px brand 进度条),数据=awards LEFT JOIN competitions GROUP BY name ORDER BY total DESC LIMIT 12,'未关联' 兜底
5. **趋势卡**:panel-head「成果入库趋势」+ECharts 320px 平滑折线(月补零连续)

## 二、v2 落法与偏差声明

- **状态词迁移**:v1 待审=`status='submit'`(SQLite 库);v2 状态机(#11)=`status='pending'`。语义同位。
- **死控件不搬**:v1 `dimSelect`(按时间/按竞赛)与 `trendSelect`(按月/按年度)在前端均无事件绑定(v1 dashboard.js 仅绑定 periodSelect)。v2 处置:周期 select 真接 `months` 参数;趋势卡的按月/按年由后端 `gran` 参数**真实现**(v1 死选项补全为活功能);维度 select 不渲染(渲染即撒谎)。
- **导出按钮**:v2 无数据导出纵切面,渲染 disabled 按钮+title「导出纵切面待接入」,不留死链。
- **后端**:`GET /api/v2/admin/stats/overview?months=&gran=month|year` 一次聚合(summary/category/trend/compare/byCompetition);原 `/stats` 保留(AdminStatsTest 兼容)。环比=本月 vs 上月 awards 新增,`deltaPct` 保留 1 位。
- **前端**:AdminDashboardView 按 v1 DOM 结构重写;select→el-select、table→el-table、button→el-button(门禁);pulse-dot/alarming/进度条 CSS 原样移植进 tokens.css dashboard 段。

## 三、验收

AdminStatsTest 补 overview 断言(五类计数/环比字段/Top 表排序);E2E 看板断言「成果总数」继续可见;并排截图留档。
