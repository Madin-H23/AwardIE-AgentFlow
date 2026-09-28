# 批15 GUI 测试报告:教师提交成果对齐 v1

> 测试时间:2026-09-28 晚|被测:教师工作台「成果提交」新页 + 学生门户回归
> 方法:web-gui-tester 黑盒方法论(纯 GUI 操作、DOM+截图双证据、瞬态 toast 单调用捕获)
> 工具:control-browser(IAB)+ Playwright MCP(上传步骤兜底,原因见「工具限制」)
> 凭据:教师 02110606(黄巧云)/ 学生 212306413(陈品天),均为既有测试约定
> 证据目录:`gui-test-screenshots/`(与本文同仓库,已入库)

## 测试结论总览

| 编号 | 测试点 | 结果 |
|---|---|---|
| T1 | 教师登录 → 工作台菜单出现「成果提交」→ 页面可达且结构完整 | ✅ PASS |
| T2 | 教师上传证明文件 + 必填字段 → 提交成功 → 记录入列、计数+1 | ✅ PASS(修复后) |
| T3 | 校验拦截:无文件时提交禁用;缺必填时警告且不落库 | ✅ PASS |
| T4 | 学生门户回归:重构后薄壳页完整渲染;同文件提交被内容去重正确拒绝 | ✅ PASS |

**抓出并修复的缺陷 2 个**(详见下文):①批10 潜伏的 multipart 请求形态 bug(学生 GUI 提交同样中招);②新页时间列裸时间戳。

## 环境准备(与测试分离)

- 后端 48080(独立进程)、前端 vite 80 均在运行;测试夹具 `t2_fixture.jpg`(330 字节合法 JPEG,FF D8 FF 魔数)预生成
- 测试账号为既有约定;库基线 = 切流迁移的 45 条(全部 archived,0 pending)
- 复现期产生的 API 复现行(id=4256)在 GUI 重测前以 SQL 清除,并声明为环境清理;测试本身全程黑盒

## T1 教师登录与入口(PASS)

教师登录后顶栏只剩「首页 / AwardIE 教师工作台」(无管理目录,角色权限正确);工作台菜单出现**成果提交**,页面 `/teacher/submit` 渲染完整:五类类型切换、上传区、动态必填字段(竞赛名称*/获奖等级*/获奖人*)、右上角「累计提交 0 条」、底部「我的提交(最近 10 条)」空表。

![T1 教师提交页整页](file:///D:/Develop/AI%20应用开发/AI应用开发项目/AwardIE-AgentFlow/gui-test-screenshots/t1_teacher_submit_page.png)

## T2 教师提交主流程(PASS,修复后)

**首轮提交失败(500)** —— 这一失败是本批最大收获,详见「缺陷 1」。修复后重跑:

上传 `t2_fixture.jpg` → 填三项必填 → 提交 → toast **「提交成功,等待审核」** → 表单清空、提交按钮回到禁用态 → 「我的提交」出现记录行(成果=GUI测试竞赛-教师提交链路,类型=奖状,状态=待审核),计数变「累计提交 1 条」。

![T2 提交成功后表单清空+按钮回禁用态](file:///D:/Develop/AI%20应用开发/AI应用开发项目/AwardIE-AgentFlow/gui-test-screenshots/t2_submit_success.png)

修复时间列后记录表最终态(类型/状态徽章、格式化时间均正常):

![T2 记录表终态](file:///D:/Develop/AI%20应用开发/AI应用开发项目/AwardIE-AgentFlow/gui-test-screenshots/t2_record_table_visual.png)

数据库交叉核验:`id=4257, submitter_type='teacher', submitter_id=1797, status='pending'`,与页面展示一致。终态库 = 45 迁移行 + 1 教师测试行(pending),该测试行留在待审队列作为功能证据,可由审核台正常驳回/通过。

## T3 校验拦截(PASS)

- **无文件**:提交按钮 `[disabled]`(DOM 证据 + T1 截图中按钮为灰)
- **有文件缺必填**:toast **「请填写:竞赛名称、获奖等级、获奖人」**,页面不前进、无数据写入(toast 文本在单次调用内捕获;其视觉本体 3 秒消失,截图记录的是点击后的页面状态)

![T3 缺必填警告后的页面状态](file:///D:/Develop/AI%20应用开发/AI应用开发项目/AwardIE-AgentFlow/gui-test-screenshots/t3_required_warning_toast.png)

## T4 学生门户回归(PASS)

- **T4a 重构后薄壳页**:学生陈品天登录 → `/portal/submit` 完整渲染(PortalLayout 底部三 tab + 共享表单五类按钮)——抽组件未破坏学生端

![T4 学生门户提交页(重构后)](file:///D:/Develop/AI%20应用开发/AI应用开发项目/AwardIE-AgentFlow/gui-test-screenshots/t4_portal_submit_refactored.png)

- **T4b 学生提交同内容文件**:请求正常到达后端,被**内容去重正确拒绝**(响应 `1003002001 该文件已在待审列表中(内容重复)`,网络层证据;失败时表单值保留)——既证明学生链路端到端可用,也证明教师测试行未被重复提交污染

![T4 学生端失败时表单保留](file:///D:/Develop/AI%20应用开发/AI应用开发项目/AwardIE-AgentFlow/gui-test-screenshots/t4_student_dedup.png)

## 缺陷记录(均已修复)

### 缺陷 1(高):提交接口 multipart 形态错误 —— 批10 潜伏,双角色同症状

- **现象**:GUI 提交弹「服务器错误」,后端日志 `MultipartException: Current request is not a multipart request`
- **根因**:yudao 的 axios 封装 `request()` 无条件 `Content-Type: headersType || default_headers`,`request.post` 即 application/json;FormData 被当 JSON 序列化发出去。正确路径是 `request.upload`(自带 `headersType: 'multipart/form-data'`,infra 文件上传即此写法)
- **影响面**:`submitPending` 自批10 起就写错了——**学生 GUI 提交同样会 500**,此前只有 MockMvc 级测试(绕过前端请求形态),从未被端到端测过
- **修复**:改走 `request.upload`;学生/教师同函数,一并修复

### 缺陷 2(低):新页提交时间显示裸时间戳

`1790597603000` 直出。修:el-table-column 挂项目标准 `:formatter="dateFormatter"`,字段同时改为语义正确的 `submitTime`。

## 工具限制与偏差(如实记录)

1. **control-browser(IAB)未承担操作性测试**:页面能加载渲染,但合成点击不触发表单行为、截图 surface 超时、登录后无任何错误提示(结合前端直连 `localhost:48080` 的架构,判定为 IAB 对该后端地址的请求挂起,环境级工具限制而非应用缺陷)。同一登录页在 Playwright MCP 浏览器一切正常,教师 API 直连亦正常。测试整体转到 Playwright MCP 执行,IAB 现象留档于此。
2. **文件上传步骤依赖 Playwright MCP**:IAB 明确不支持 file chooser(`capability_unsupported`),故 T2/T4b 的上传经由 Playwright MCP 的 `browser_file_upload` 完成——这属于工具能力互补,非绕过 GUI(点击上传区域、选择文件仍是真实用户路径)。
3. 瞬态 toast 按规范在单次调用内「点击→等待→读文本→截图」;T3 的 toast 视觉本体未及入图(3 秒存活),以同调用内 DOM 文本 + 截图页面状态作双证据,如实说明。

## 控制台错误

测试全程收集 console error:仅 T2 首轮(缺陷 1)与 T4b(去重拒绝,axios 对非 0 code 的预期 reject)各 1 条,修复后归零;无未捕获异常。
