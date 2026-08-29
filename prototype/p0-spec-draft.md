# P0 Spec:v2 骨架 + Tracer 纵切面可演示

> 决策依据:CONTEXT.md(领域语言)、ADR-0001(作品导向范围收缩)、ADR-0002(双库+路径分流)、立项纪要 2026-08-29、探针报告 `prototype/pg-etl-probe/FINDINGS.md` 与 `prototype/grpc-nginx-probe/FINDINGS.md`。阶段口径:tracer 前置四阶段中的 P0,出口标志 = **tracer 全线可演示**(相对周 1-12)。

## Problem Statement

AwardIE 现在是 Python/Flask + Jinja2 + SQLite 单体:部门主力栈是 Java,前后端耦合无法独立发版,SQLite 无并发能力。我要把它迁移到 Java 21 + Vue 3 + PostgreSQL 16 的现代栈,产出可答辩的全栈作品;但 1800 名学生用户在用,v1 业务不能中断,只能按域绞杀。目前 v2 一行代码都没有,P0 要把新栈骨架立起来,并让第一条纵切面(tracer)全线打通、可以演示。

## Solution

学生用 v2 登录页(Spring Security + PG)登录,上传证书走 Vue 表单提交成果,系统经 gRPC 调 Python AI Worker 产出审核建议,教师确认后成果入库,学生能看到审核时间线。其余功能继续由 v1 服务,Nginx 按路径分流,业务不中断。演示时这一条线覆盖 Java/PG/Vue/gRPC 全部四项选型,是答辩作品的第一块基石。

## User Stories

1. As a 学生, I want 用学号+密码登录 v2 界面, so that 开始使用新系统(首登强制改密,BR-4 沿用)
2. As a 学生, I want 上传证书图片/文件并提交五类成果(奖状/专利/软著/大创/其他), so that 申报我的成果
3. As a 学生, I want 看到提交后成果的审核状态与时间线, so that 知道进展
4. As a 学生, I want 被驳回时看到驳回原因, so that 修改后重新提交(BR-5)
5. As a 教师, I want 看到待审列表并逐条处理, so that 快速完成审核
6. As a 教师, I want 看到每条成果的 AI 审核建议与理由, so that 做最终判断(BR-2:AI 仅辅助)
7. As a 教师, I want 批准/驳回成果, so that 状态机 pending→submit→archived/rejected 正常流转
8. As a 管理员, I want 登录后进入 v2 可用状态, so that 确认管理路径已打通(完整管理台在高频扩展阶段)
9. As a 学生/教师, I want 访问 v1 长尾功能(看板/实验室/门户)不受迁移影响, so that 业务连续
10. As a 作品作者, I want Python ETL 管线把 v1 SQLite 30 表数据迁入 PG, so that v2 有真实数据可演示
11. As a 作品作者, I want Nginx 按路径分流(纵切面→v2,长尾→v1), so that 双系统并存互不干扰
12. As a 作品作者, I want ai_service.proto 契约冻结(extract/review/qa), so that Java 与 Python 并行开发
13. As a 作品作者, I want CI 跑 Java 测试 + 前端构建, so that 回归有护栏
14. As a 作品作者, I want 提交的文件保存并可下载, so that 演示完整业务对象(白名单/大小/魔术字节三校验沿 v1,BR-7 attachment)

## Implementation Decisions

- **后端骨架**:Java 21 + Spring Boot 3.3 + JPA + Flyway,单模块包内分层(controller/service/repository/dto 严格分离);CommonResult 统一包装(借鉴 it-ops-service ApiResponse 5 字段);GlobalExceptionHandler + TraceId 直通沿用 v1 语义。
- **前端骨架**:Vue 3 + Vite 5 + Pinia + Element Plus + TypeScript;路由按纵切面组织(登录/提交/审核/时间线);Element Plus 双主题适配现有设计 token。
- **数据库**:PG 16(pgvector 预埋);schema = 30 表,由 **Python ETL 管线**从 v1 SQLite 迁入,顺序按探针 P2 已验证管线:预扫描(混型列+JSON 审计)→ 建表(FK 后置、VIRTUAL 生成列剥离)→ 装载(BOOLEAN 0/1 适配、BLOB→bytea)→ 索引(谓词 =1/=0 改布尔)→ FK → 序列(**以 sqlite_sequence 为准**,空表 setval(1,false))→ 生成列翻译(jsonb_typeof 分支表达式,探针已逐行验证)→ 逐表行数 + BLOB md5 校验。
- **数据清洗**(探针 P2 发现):`achievement_audit_log.operator_id`/`review_logs.reviewer_id` 的 `'admin'` 文本→NULL;JSON 列逐列试转 jsonb,`awards.llm_response` 1/79 非法行修复后转;`created_at`/`updated_at` 类升 timestamptz,`awards.date`/`competitions.competition_time`/`innovation_projects.start_date` 保留 TEXT(值非日期语义)。
- **登录**:Spring Security + 会话;兼容 v1 存量口令哈希验证,登录成功透明重哈希;BR-4 首登强制改密;BR-6 密码强度沿用。
- **状态机与业务规则**:BR-1~7 全量沿用;pending→submit→rejected/archived 状态机与 v1 等价,驳回必须可重新提交(BR-5)。
- **gRPC 契约**:ai_service.proto 覆盖 extract/review/qa(review 与 qa 为 server-streaming);Python Worker 复用 v1 LangGraph 编排(N1 不重写算法);**Nginx 配置硬条目(探针 P1)**:`grpc_read_timeout ≥300s` + `grpc_send_timeout 3600s` + `grpc_socket_keepalive on`;client 对 `INTERNAL: Stream removed` 映射为重试/降级。
- **分流**:Nginx 路径分流——v2 前端静态资源 + `/api/v2/*`→ Java(8080),其余→ v1 Flask(5001);文件上传存 v2 独立目录,路径记 PG。
- **测试库口径(本机 Docker 不可用)**:本地用免安装 PG 16.9 专用实例(127.0.0.1:5433,探针同款),CI 用 GitHub Actions `services: postgres`;Testcontainers 列为 Docker 修复后可选替换,不阻塞。

## Testing Decisions

- **唯一行为测试 seam = HTTP API**:Spring Boot 测试对真实 PG(上述实例)黑盒驱动,只测外部行为;v1 的 942 例 pytest HTTP 层测试是语义基线,P0 翻译 tracer 链路相关子集(登录/改密/提交/审核/时间线,目标 40-60 例)为 JUnit。
- **gRPC**:Java 侧一律注入 fake stub 做 service 层单测;真实 AI Worker 联调仅 P0 收尾 1 条冒烟(提交→AI 建议→时间线全通)。
- **E2E**:Playwright ≤3 条,只护 tracer 演示主线(登录→提交→看时间线),答辩演示的回归护栏。
- **前端**:Vitest 组件测试 P0 不强制;ESLint + build 通过作为门禁。

## Out of Scope

- 成果导出(FR-ACH/POI)→ P1 纵切面补全(用户故事见 ADR-0001 纵切面定义)
- 双库影子比对与写路径窗口制切换 → P1(P0 仅路径分流共存)
- 高频扩展队列(admin 五类成果管理/个人资料/竞赛管理)→ P2
- 长尾域(看板/实验室/门户/管理台子域)→ 永不迁移,v1 只读并存
- 性能验收(P95≤30ms、压测)→ P2 末;SkyWalking 链路追踪 → P1+
- AI 算法重写、微服务、移动端(N1/N3/N5 非目标)
- 生产部署(部门服务器)→ P0 以本地/单机演示环境为出口口径

## Further Notes

- 里程碑:P0 出口即答辩作品 M1'(tracer 可演示);无硬日期,相对周制,延期以事实复盘。
- 答辩叙事资产:双库绞杀架构(ADR-0002)、gRPC 双进程、探针先行方法论(两份 FINDINGS 即证据)。
- Spec 用词遵循 CONTEXT.md glossary(纵切面/Tracer/探针/长尾并存/窗口制切换/双库影子比对/稳态收束)。
- 后续 `/to-tickets` 依 wayfinding 约定:本 issue 为 map,child issues 为 tickets。
