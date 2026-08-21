# 重构 TODO 索引（CR-11）

> 汇总散落在各文档的"后续/预留/重估"事项，防开发阶段遗忘。按处理阶段分组；完成即勾选并注明落点。
> 依据：需求文档 v1.5 / 设计文档 v1.2 / 交叉审查报告 CR-11。
> **2026-08-19 完成状态回写**：已对照五份实施文档逐一核实——T1/T3/T4/T6/T7/T22 补记完成（证据落点见各行），T2/T8 更新为"就绪未切"，T5/T9 移交二期，T10/T11 标记待核实，T19 建议改挂阶段六。

## 阶段一~三内必办（随路线图任务）

| # | 事项 | 出处 | 触发/时点 |
| --- | --- | --- | --- |
| ~~T1~~ | ~~重开审核驳回路由 + approve 软归档~~ **已完成（阶段二）**：teacher/admin 双 API + 审核页驳回按钮 UI（T1 全闭环）；approve 软归档条件更新保留 AI 结论 + submissions 过滤 | SRS 8.2 阶段二（CR-2 新增） | ✅ |
| T2 | Redis 引入（限流/幂等共享存储）——🔶 基础设施就绪未切：阶段四 compose 双实例+Redis+nginx 已落地（CR-4/5），应用侧切换留上线时（单机 memory:// 可容忍） | 部署 §1 / 安全 §2.4（CR-4） | 上线时 |
| ~~T3~~ | ~~idempotency_keys 表建立与接入~~ **已完成（阶段二）**：SQLite 共享表 + @idempotent 装饰器，批量审核防双击 | API §1.3（CR-4） | ✅ |
| ~~T4~~ | ~~AppError 异常契约 + CI 禁 bare except 门禁~~ **已完成（阶段二/四）**：AppError 契约 + 统一包装 {trace_id,code,message,data} + Retry-After；CI 静态门禁（lint + 禁裸 connect）随阶段四生效 | API §1.4 / 部署 §7（CR-9） | ✅ |
| T5 | status CHECK(pending\|submit\|rejected\|archived) 表重建——阶段五类型重建 0003 未含 CHECK，列 M3 余项（阶段五诚实评估：低优先，无 SQL 过滤需求） | 数据库 §1.5/§3（CR-2 时序声明） | 二期（低） |
| ~~T6~~ | ~~Flask-Migrate baseline 打点（stamp）~~ **已完成（阶段五）**：Alembic baseline 0001 手写安全 stamp（CR-8 交接点落地，commit `3f5bf82`） | 数据库 §7（CR-8） | ✅ |
| ~~T7~~ | ~~每日对账脚本（users 合并验证，须在旧三表转视图前）~~ **已关闭（2026-08-19 反馈）**：对账已随批次执行——阶段三 1832 搬迁对账一致、阶段五迁移 0002 视图化零悬空断言；旧三表已视图化，任务前提失效 | 数据库 §7（CR-7） | ✅ |
| T19 | OCR Provider 禁用自动恢复机制（配置变更后自动重试，防一次性失败永久禁用）——阶段二未实施（阶段一仅修复 secret key 注入+重置运行态），建议随阶段六日志系统重排（OCR 事件监控可观测恢复状态） | 原 P0-1 遗留改进（v1.7 修复时转入） | 建议改挂阶段六 |

## 阶段四（工程化）

| # | 事项 | 出处 |
| --- | --- | --- |
| T8 | 进度存储迁 Redis（P3-4）——🔶 就绪未切：阶段四 compose 已含 Redis，memory:// 单容器可用，切换留上线时 | SRS 8.2 阶段四 |
| T9 | ~~CSS 收敛到 Tailwind 单体系（P3-1）~~ **已完成（2026-08-20，`469d739`）**：由本会话直接执行（原计划交接 DeepSeek-V4-Flash）——54 个 admin 页全量换壳 base_console 控制台体系（card→c-panel、文字按钮、tab 片段/动态 fragment 全链路落 console-shell），17 主页面+5 fragments 冒烟、暗黑双态对位、ruff 通过；执行记录见《2026-08-20_前端重构方案.md》§7；**base.html 体系已无 admin 页使用，待退役（收尾期移除）** | SRS 8.2 / 前端交互设计 §1 |
| T10 | 归档冷库 awards_archive.db 上线 + 演练——**待核实**：阶段四文档未见落地记录，交接摘要已标记待核实 | 需求 5.4 / 数据库 §5 |
| T11 | Celery/RQ 异步队列评估（预留接口已留）——**待核实**：阶段四文档未见落地记录 | 架构 D-1 |

## 二期 / 条件重估（不在本轮）

| # | 事项 | 出处 | 重估触发条件 |
| --- | --- | --- | --- |
| T12 | 用户头像补齐或下线 | 取舍 D4（user_photos 0 行） | 二期需要时 |
| T13 | 三类零使用成果管理页合并（-28 路由） | 取舍 D2 | 任一类型年入库 ≥20 条 |
| T14 | 报告生成模块下线评估 | 取舍 D3 | 院系确认无人使用 |
| T15 | 门户改登录可见（方案 A） | 取舍 D1 重估条件 | 院系放弃对外展示 |
| T16 | 数据库迁移 MySQL/PostgreSQL | 非目标 N7 / 架构 D-2 | 阶段四后并发或数据量超 SQLite 边界 |
| T17 | 等保定级 / 告知同意等上线合规事项 | 需求 4.9 说明 | 正式上线前 |
| T18 | 移动端适配解冻（FR-UI-03，恢复响应式/相机调用设计） | 取舍 D6（v1.6 拍板：只做 Web 端） | 二期移动使用占比明确 |
| T21 | ~~存量测试环境隔离修复~~ **已完成（2026-08-19）**：test_llm_adapter fixture 隔离 apikey.json（load_config 会注入真实 key 覆盖 patch env，且真实 key 曾泄漏进失败输出）；test_data_analysis temp_db 补 4 张关联表（award_teacher_winners/award_supervisors/teachers/laboratories）。5 例存量失败清零，311 全绿 | 全量回归 2026-08-17 发现 | ✅ |
| ~~T22~~ | ~~admin.py 4 处"重置为默认密码"改造为随机强密码一次性下发~~ **已完成（阶段二）**：admin 4 处重置改随机强密码 + needs_password_change 标记（配合首登强制改密），**默认密码引用清零** | P2-28 配套 | ✅ |
| T23 | ~~存量 F821 未定义名清账~~ **已完成（2026-08-18）**：38 处全清——其中 20+ 处是 L3 批量替换事故残留真 bug（conn 未定义/return 短路/外键 pragma 死码）+ 2 处笔误 bug（ext_info/matched_template）+ 6 处字符串注解误报（TYPE_CHECKING 根治）；CI 豁免已转正 | ruff 全量 CI 抓出 2026-08-18 | ✅ |
| T24 | 存量代码全量覆盖率提升（当前 12.85%；核心模块已 86%——存量路由/服务测试补齐后逐步提升全量指标） | CI cov 收窄 2026-08-18 | 二期 |

## 新增待办编排（阶段五收官 → 阶段六，2026-08-19 起）

> 阶段五关键路径已收官（实施文档 🔶 阶段性版，M1 后半全部完成）。此后新增待办按企业级开发流程的任务推进顺序编排：
> **文档补齐（已随阶段五完成）→ 测试套件清理（阶段六前置·质量基线）→ 文档整理（阶段六前置·文档基线）→ 阶段六（日志系统·开发主线）**。
> 排序依据：进入新特性开发前 CI 必须是可信信号（质量门禁前置）；产出新文档前先治理文档体系（单一真源原则）。各节头标注定位与完成标志，完成即在对应任务行勾选并注明落点。

| 顺序 | 阶段锚点 | 任务组 | 边界 | 优先级 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 1 | 阶段五·收尾 | 文档补齐（流程规范）T29/T30 | 仅流程规范类；功能设计归各阶段 SDD | — | ✅ 已完成 |
| 2 | 阶段六·前置 | 测试套件清理（重构前遗留）T31-T34 | 只动 tests/ 根级遗留文件；CI 28 文件与冻结模块逻辑不动 | 高（批次1-3）/ 中 / 低 | 待执行 |
| 3 | 阶段六·前置 | 文档整理（体系治理）T35-T37 | 只动 docs/ 目录与归档，零代码改动 | 高 | 待 hewj 确认 |
| 4 | 阶段六 | 日志系统 T26-T28、T38-T43 | 按日志系统设计 L1-L6 依赖链；不动 AuditLogger 契约 | 功能主线 | 待执行 |

> **并行窗口**：测试清理批次 4/5（中/低优先级）可与文档整理 P0/P1 交叉执行；日志系统 L1 数据层可在测试清理批次 1+2 完成后提前启动（冲突测试已消除）。

---

## 阶段五·收尾（文档补齐·流程规范）✅

> 定位：补全开发流程规范文档，确保完整性与可追溯性。完成标志：文档流程合规度 B/C 级缺口清零——2026-08-19 达成，本节仅作完成留痕。

| # | 事项 | 出处 | 触发/时点 |
| --- | --- | --- | --- |
| ~~T29~~ | ~~独立测试方案文档~~ **已完成（2026-08-19，v1.1 补充提示词框架与适用性评估）**：`设计/2026-08-19_测试方案.md`——15 章节全覆盖：测试分层策略 / 覆盖率目标分解 / 准入准出标准 / 测试环境隔离 8 规则 / 12 条测试纪律 / CI 集成 / 编码修复铁律 9+5 条 / 冻结模块清单 / 提示词模板库 A-F / 测试报告规范 / 测试选择决策树 / 测试套件适用性评估与清理计划 | 文档流程合规度评估 B 级缺口 | ✅ |
| ~~T30~~ | ~~风险登记册~~ **已完成（2026-08-19）**：`风险登记册.md`——23 条风险集中登记（18 技术风险 R-001~R-018 + 5 流程性风险 R-019~R-023），每条含编号/描述/概率/影响/缓解措施/当前状态/关联阶段。15 条已缓解，5 条部分缓解，1 条条件就绪 | 文档流程合规度评估 C 级缺口 | ✅ |

## 阶段六·前置（测试套件清理·重构前遗留）

> 定位：清理重构前遗留测试，移除过时或无效用例，建立可信质量基线——必须在阶段六新增 ~60 用例前完成，否则开发期失败无法归因、覆盖率分母失真。边界：只动 tests/ 根级遗留文件；CI 跟踪的 28 文件不动；冻结模块（extract/ocr）逻辑零改动。完成标志：根级 24 文件全部处置完毕，每批后全量回归基线不回退。
> 2026-08-19 评估结论：CI 跟踪的 28 个文件全部适用；根级 24 个文件仅 1 个直接适用。详见 `设计/2026-08-19_测试方案.md` §15。

| # | 事项 | 出处 | 触发/时点 |
| --- | --- | --- | --- |
| T31 | 批次 1+2：删除 4 个过时测试（test_password_config / test_files_commit / verify_data_analysis / test_lab_association_feature），移走 5 个非测试脚本到 tests/tools/ 或 scripts/ | 测试方案 §15.3 | 高 |
| T32 | 批次 3：8 个 unittest.TestCase 转 pytest 函数式（admin_settings / config_loader / auto_archive×2 / manual_import×3 / review_pending_vs_submit_stats），登录模拟适配 users 认证 | 测试方案 §15.3 | 高 |
| T33 | 批次 4：4 个脚本式测试重写为 pytest（test_files / test_main_services / test_page_rendering / test_routes_integrity），改造后拉入 CI 清单 | 测试方案 §15.3 | 中 |
| T34 | 批次 5：冻结模块测试评估（extract/unit 7 个、extract/integration 6 个、ocr/ 4 个），需 API key 的标注 skipif | 测试方案 §15.3 | 低 |

## 阶段六·前置（文档整理·体系治理）

> 定位：对现有文档体系梳理治理，统一结构与命名规范，为阶段六实施文档建立挂载点。边界：只动 docs/ 目录与归档，零代码改动；`docs/重构/` 权威体系不动；全部 git mv 保证可回滚。完成标志：docs/ 根层仅剩 README.md + 分类目录（`find docs -maxdepth 1 -type f` 为空）。
> 推进顺序：T35（P0 归档 + P1 归位 + 总索引）→ T36（P2 去重）→ T37（CHANGELOG）。

| # | 事项 | 出处 | 触发/时点 |
| --- | --- | --- | --- |
| T35 | 文档体系整理执行：按《文档整理计划》P0 归档（3 批 ~60 文件）+ P1 根层散落文件归位 + 创建 docs/README.md 总索引；全部 git mv，批间验证 | `重构/2026-08-19_文档整理文档.md` §7 / 整理计划 | 待 hewj 确认（高） |
| T36 | 文档去重 4 组：flask_api 清单双份 / 测试方案双份 / database 两份结构说明 / README vs guide（P2，需 hewj 决策） | 文档整理文档 §5.2 | P0-P1 完成后（中） |
| T37 | CHANGELOG.md 建立（按阶段汇总变更） | 文档整理文档 §5.1 | 建议 P2 时（低） |

## 阶段六（日志系统）

> 定位：管理员后台日志系统——查看（四源统一）/ 分析（看板+告警）/ 行动计划。边界：不动 AuditLogger append-only 契约；不引入 ELK/Loki/Prometheus server 等外部组件。完成标志：日志系统设计 §9.3 验收 DoD 全绿，测试基线 224 → ~284。
> 总纲：按 L1→L6 依赖链实施，预计 ~60 新增测试用例。设计依据：`设计/2026-08-19_日志系统设计.md`（SDD·第八章）。

### 设计要点摘要

| 维度 | 规划 |
| --- | --- |
| 日志级别 | `system_event_log.event_level` 五级：debug / info / warning / error / critical；事件分类 8 类（ocr/llm/breaker/auth/upload/db/security/system） |
| 输出格式 | app.log：`%(asctime)s - %(levelname)s [%(name)s] [tid:%(trace_id)s] %(message)s`；TraceIdFilter 注入 trace_id（请求头 X-Trace-Id 或 uuid 前 12 位） |
| 存储策略 | app.log RotatingFile 10MB×5；system_event_log 表（SQLite，append-only，独立连接不阻塞主业务），定时清理 90 天前记录；metrics_snapshot 保留 30 天 |
| 实时性 | SSE 推送延迟 ≤2s；每管理员并发 SSE 连接 ≤2，超限 429 |
| 脱敏 | 写入前 `_sanitize()`：身份证 → `****`、手机号 → `138****5678`、完整学号 → `2024****01`；password/secret/token 自动掩码 |

### 任务清单（L1-L6 依赖链，T25 拆分）

| # | 事项 | 依赖 | 产出 | 预计用例 | 触发/时点 |
| --- | --- | --- | --- | --- | --- |
| T38 | ~~L1 数据层~~ **已完成（2026-08-20，`cc91a8a`）**：迁移 0006 + ORM 模型 + SystemEventLogger（PII 脱敏/不阻塞/from_exception）+ 接入点 4/8 类（breaker/errorhandler/auth 锁定/启动；ocr 属冻结模块经调用方包装、llm/upload/db 留 L2+）+ conftest 全局隔离 + 15 单测（335 全绿） | 无 | migrations/0006 + backend/orm/system_event_log.py + backend/utils/system_event_logger.py | ✅15 | ~~高~~ ✅ |
| T39 | ~~L2 查询层~~ **已完成（2026-08-20，`8e16f09`）**：LogQueryService（audit/system/review 三源 + 跨源合并）+ LogFileReader（tail/search/stream + tid 解析，旧格式兼容）+ MetricsSnapshot（collect/archive）+ trace_id 补齐（T26 同步闭环：before_request + TraceIdFilter，**修复 `app._current_trace_id` 从未赋值、响应恒 None 的存量缺陷**）+ 12 单测（347 全绿） | L1 | backend/services/log_query_service.py 等 3 个 | ✅12 | ~~高~~ ✅ |
| T40 | ~~L3 分析层~~ **已完成（2026-08-20，`1953b40`）**：LogAnalyzer（动作分布/错误趋势/审核瓶颈/活跃度/AI 健康/留痕健康/每日摘要 7 类）+ AlertEngine（A001-A006 六规则 evaluate/归档/缺表容错）+ PlanGenerator（告警转计划/状态机 open→acknowledged→resolved/每日报告）+ 16 单测（363 全绿） | L2 | backend/services/log_analyzer.py 等 3 个 | ✅16 | ~~高~~ ✅ |
| T41 | ~~L4 路由层~~ **已完成（2026-08-20，`d353fde`）**：admin_log 蓝图 19 接口（四源查询+分析5+指标/日报+告警/计划+SSE 并发≤2）；顺带修复 require_role_api_json 漏判 /admin/api/ 前缀（302→401）；SSE 前端自动重连留 L5；13 单测（376 全绿）。**同批暴露并处置 R-027 分支假推送事故**（37 提交 ff 合并回 main） | L2+L3 | app/routes/admin_log.py | ✅13 | ~~高~~ ✅ |
| T42 | ~~L5 前端~~ **已完成（2026-08-20，`13bd08d`）**：控制台新体系地基（base_console 双主题基类）+ 首个落地页——3 Tab（行式日志流+severity 竖条/六 ECharts 看板+vitals 体征带/计划流转）+ SSE 重连提示 + 侧边栏导航；playwright 冒烟全通（含亮暗切换）。方案见《2026-08-20_前端重构方案.md》；**T9 批量迁移已由本会话直接执行**（`469d739`，见 T9 行） | L4 | console_logs.html + base_console + 2 宏 + 2 JS | ✅GUI 冒烟 | ~~中~~ ✅ |
| T44 | ~~AI 助手页分端+DeepSeek 风格~~ **已完成（2026-08-20）**：chat.html 拆 3 partial + 双壳（chat_console/chat_portal）+ 路由按角色选壳；**DeepSeek 网页端对话风格**（顶部模式 pill/圆角气泡/26px 大圆角输入条/圆发钮/推荐 chips）；调研结论：官方 deepseek-harness 为 Agent 编排 UI 非对话页，落地采用 chat.deepseek.com 对话界面共识；三角色 playwright 验证；顺带修 L6 log_scheduler 参数 bug | 前端实施记录 §5 | 双壳+风格 | ✅三角色 | ~~中~~ ✅ |
| T43 | ~~L6 收尾~~ **已完成（2026-08-20，`bc4d684`）**：行动计划持久化（action_plans 落库：generate 合并/transition 写库/load）+ 日志定时线程（metrics 5min 归档 + 每日 09:00 窗口[90天清理 + ignored 7 天重开 + 每日报告留痕]）+ 6 测试 + 阶段六实施文档 §9-§10；T28 定时归档随 L6 完成 | L5 | log_scheduler.py + plan_generator 落库 | ✅6+ | ~~中~~ ✅ |
| T26 | trace_id 全链路贯通（run.py TraceIdFilter + LogFileReader 解析 + DB 留痕串联） | 随 L2 | 含于 T39 | 含于 T39 | 高 |
| T27 | SystemEventLogger 接入点矩阵全量落地（OCR/LLM/熔断/认证/上传/DB/安全 7 类事件） | 随 L1 | 含于 T38 | 含于 T38 | 高 |
| T28 | metrics_snapshot 定时归档（5 分钟快照）+ daily_report 推送 | 随 L6 | 含于 T43 | 含于 T43 | 中 |
| T45 | ~~AI 助手恢复 V2 外观~~ **已完成（2026-08-21，`fc66e9a`）**：撤销 343a8ec 回退（chat 3 partials + 双壳 + 按 role 选壳），叠加 CSS v6 修复保留；三角色 playwright 验证（admin=console/student=portal+DeepSeek UI+暗黑 token 成对） | 08-21 实施记录 | — | ✅GUI | 中 |
| T46 | ~~网络出站直连~~ **已完成（2026-08-21，`b656b7d`）**：run.py 剥 HTTP(S)_PROXY + llm_adapter `httpx.Client(trust_env=False)`——LLM/OCR 不再被本地代理(3067)劫持，代理开/关均正常访问；实测无代理直连+页面问答正常 | 08-21 实施记录 §3 | — | ✅ | 高 |
| T47 | ~~AI 助手三模式体验（markdown 排版+独立窗口+全流式）~~ **已完成（2026-08-21，`35a9840`/`68f41b2`/`982eb1d`）**：①renderMarkdown 安全渲染（先转义后渲染/白名单/逐行状态机，支持 ol/ul/表格/标题/引用/注入防护）；②三模式独立对话窗口（modeHistories 快照+专属欢迎语+生成中禁切+清空只当窗）；③multi_agent/single_agent 分片流式（_answer_pieces 逐 delta，tools 138 片/auto 进度3+8 片，零重复 LLM 调用）；新增测试 5 例 | 08-21 实施记录 §4 | — | ✅16测试 | 中 |
| T48 | ~~5001 端口误判澄清 + 三端并行测试手法~~ **已完成（2026-08-21，memory/文档）**：实测 5001 可用（切回默认端口）；`*.localhost` 三端并行（cookie 按 host 隔离、端口不参与；坑=系统代理吞 .localhost 回 502） | 08-21 实施记录 §5 | — | ✅实测 | 中 |
| T49 | 三模式**生成期真流式**（非分片）：auto 改 LangGraph QA 节点透出 chunk / tools 用 create_agent `stream_mode=messages` | 08-21 实施记录 §7 | T47 分片版基础上 | 视测试 | 可选/用户确认 |
| T50 | 三端并行 Playwright 自动化冒烟示例（补 hosts 后三 context 并行） | 08-21 实施记录 §7 | T48 | 待定 | 可选 |
| T51 | ~~审核留痕展示与删除体系~~ **已完成（2026-08-21，5501f25/698924d/ac1352e/e82e81b/1d100e7）**：操作人按 users.id 或 login_code 双路解析"学号 姓名"；编号阶段语义（入库=成果#/待审=待审成果#）；audit 时间写入层统一本地（0007）；成果删除留痕 动作12（0008 扩 CHECK）+防重+历史重复标记（0009 is_redundant，查询默认过滤） | 08-21 实施记录 §8.1 | 迁移 0007-0009 | ✅72 | 高 |
| T52 | ~~LLM 指标与日志链路~~ **已完成（2026-08-21，105c612/26483a8/089b673/2afc1da）**：LLM 成功率恒 0 三重根因修复（打点回调/collect 0.26 兼容/ai_health 键匹配）；应用日志 tail、系统事件展示本地、实时流阻塞修复、每日报告键名对齐 | 08-21 实施记录 §8.2 | — | ✅ | 高 |
| T53 | ~~测试资产治理~~ **已完成（2026-08-21，6b1312b/cdafb79/97fa7e0）**：数据库结构说明文档；完整回归实测三档（CI 192/unit 365/根级 61+11 挂）；CI 清单补全 5 新测试；CI YAML 字面 \n 事故修复（run 88009233372） | 08-21 实施记录 §8.3 | — | ✅217 | 高 |
| T54 | ~~数据库结构说明文档~~ **已完成（2026-08-21，6b1312b）**：`设计/2026-08-21_数据库结构说明.md`（31 表/迁移链 0001-0009/核心约定/排查命令） | 08-21 实施记录 §8.3 | — | ✅ | 中 |
| T55 | system_event_log 时间统一（写入层 UTC→本地，连带 90 天清理/每日 09:00 报告窗口基准评估） | 数据库结构文档 §4 待办 | T52 展示层已转本地 | 评估后 | 上线前 |
