# AwardIE-AgentFlow 项目 Wiki

> 由 ZCode Repo-Wiki 生成（基于提交 `ac1352e462`，54 页），导出于 2026-08-21。


## 应用装配与 Web 基础设施

- [01 应用工厂与启动装配](01-应用工厂与启动装配.md) — create_app 的应用装配核心：配置加载、CSRF 全局防护、trace_id 透传、统一异常契约、蓝图注册、静态缓存与日志调度启动  `源码: app/__init__.py`
- [02 配置加载与运行时环境](02-配置加载与运行时环境.md) — 从 config/loader.py、flask.py 和 settings.json 读取系统配置，支持环境变量覆盖、密钥管理与运行时 OCR 配置  `源码: config/loader.py, config/flask.py, config/settings.json`
- [03 统一异常契约与错误码](03-统一异常契约与错误码.md) — AppError 与未预期异常的统一包装，返回 trace_id/code/message/data，并将系统事件落库，是前端错误处理和后端排障的契约  `源码: backend/utils/app_error.py, app/__init__.py`
- [04 认证与会话管理](04-认证与会话管理.md) — 验证用户名/密码、写入 session、角色权限装饰器，以及 users 单表优先 + 旧三表回退的渐进式认证策略  `源码: app/auth.py, app/routes/auth.py`
- [05 密码强度与账号安全](05-密码强度与账号安全.md) — 实现密码复杂度校验、强密码生成、登录限速和账号激活检查，覆盖首次登录强制改密场景  `源码: app/password_policy.py, backend/utils/login_guard.py`
- [06 前端控制台与公共交互](06-前端控制台与公共交互.md) — 控制台启动、深色主题、CSRF 注入、通用工具函数，是前端控制台化和请求安全的基础设施  `源码: app/static/js/console_boot.js, app/static/js/console_theme.js, app/static/js/csrf.js, app/static/js/common.js`

## 角色路由与功能入口

- [07 管理后台基础路由](07-管理后台基础路由.md) — 管理员仪表板、基础设置、人员与活动管理入口，以及所有管理子蓝图的汇总  `源码: app/routes/admin.py`
- [08 成果汇总与文件导入](08-成果汇总与文件导入.md) — 管理端成果汇总页和文件导入的路由逻辑，包括类型统计、状态调整和待审核查询  `源码: app/routes/admin_achievement.py, app/routes/file_import_helpers.py`
- [09 奖状管理](09-奖状管理.md) — 奖状列表、详情、编辑、导入和删除等管理功能，连接奖状模型和处理服务  `源码: app/routes/admin_awards.py`
- [10 实验室管理](10-实验室管理.md) — 实验室 CRUD、成员关联、实验数据分析和页面渲染的管理路由  `源码: app/routes/admin_laboratory.py, backend/services/laboratory_association_service.py`
- [11 大创项目管理](11-大创项目管理.md) — 大学生创新创业项目的管理路由，包括项目成员、指导教师和项目审核  `源码: app/routes/admin_innovation.py`
- [12 专利、软著与其他成果](12-专利、软著与其他成果.md) — 专利、软件著作权和其他文件类成果的管理路由集合，处理多种成果类型的通用导入  `源码: app/routes/admin_patents.py, app/routes/admin_software.py, app/routes/admin_other_files.py`
- [13 审核管理路由](13-审核管理路由.md) — 管理员对成果提交进行审核、驳回、归档的路由，以及相关 helper 的字段标准化  `源码: app/routes/admin_review.py, app/routes/review_helpers.py`
- [14 模板管理](14-模板管理.md) — 管理抽取模板的列表、描点、规则配置，将模板能力暴露给管理员界面  `源码: app/routes/admin_templates.py, app/static/js/templates.js`
- [15 数据导出与报表](15-数据导出与报表.md) — 按条件导出成果数据、生成 Excel/报表并提供下载入口  `源码: app/routes/admin_export.py, backend/utils/export_utils.py, backend/utils/report.py`
- [16 数据分析看板](16-数据分析看板.md) — 获奖数据的统计、筛选和可视化，驱动管理员看板与图表绘制  `源码: app/routes/admin_data_analysis.py, app/static/js/data-analysis.js, app/static/js/dashboard.js`
- [17 操作日志与审计视图](17-操作日志与审计视图.md) — 管理员查看操作日志、审计记录，支持按操作者/时间筛选  `源码: app/routes/admin_log.py, app/static/js/admin_logs.js`
- [18 学生门户](18-学生门户.md) — 学生查看获奖记录、成果提交、个人资料与修改密码的入口  `源码: app/routes/student.py`
- [19 教师门户](19-教师门户.md) — 教师查看指导成果、学生提交审核、数据导出和个人资料管理  `源码: app/routes/teacher.py`
- [20 公共用户信息](20-公共用户信息.md) — 个人资料、头像上传、修改密码等跨学生/教师/管理员的通用用户接口  `源码: app/routes/user_common.py, app/utils/user_routes.py, app/static/js/profile.js`
- [21 API 与辅助接口](21-API 与辅助接口.md) — 统一 /api 蓝图的 JSON 接口和辅助函数，供前端异步调用  `源码: app/routes/api.py, app/routes/api_helpers.py`
- [22 AI 助手聊天接口](22-AI 助手聊天接口.md) — 智能助手对话 HTTP/SSE 路由，将聊天请求接入 Agent 工作流和 RAG 知识库  `源码: app/routes/chat.py`

## 数据模型与 ORM

- [23 ORM 基座与仓库层](23-ORM 基座与仓库层.md) — SQLAlchemy ORM 基类、仓库模式、以及 awards/pending/users 等核心表的访问封装  `源码: backend/orm/base.py, backend/orm/repositories.py`
- [24 用户体系数据映射](24-用户体系数据映射.md) — 合并后的 users 单表与旧 admins/students/teachers 三表之间的映射，login_code 到 users.id 的写入转换  `源码: backend/orm/users.py, backend/utils/users_sync.py`
- [25 奖状与待审核成果模型](25-奖状与待审核成果模型.md) — 奖状记录和待审核成果的领域模型，包含识别字段、审核状态、导入状态及关联关系  `源码: backend/models/award.py, backend/models/pending_achievement.py`
- [26 竞赛与大创项目模型](26-竞赛与大创项目模型.md) — 竞赛目录、等级、时间字段解析，以及大创项目及其成员/指导教师的 ORM 模型  `源码: backend/models/competition.py, backend/models/innovation_project.py, backend/utils/competition_time_parser.py`
- [27 实验室与师生模型](27-实验室与师生模型.md) — 实验室、学生、教师、用户照片等基础数据模型，支撑门户和管理端展示  `源码: backend/models/laboratory.py, backend/models/student.py, backend/models/teacher.py, backend/models/user_photo.py`
- [28 专利/软著/其他文件模型](28-专利-软著-其他文件模型.md) — 专利、软件著作权和其他文件类成果的数据模型，统一承载多类型成果的元数据  `源码: backend/models/patent.py, backend/models/software_copyright.py, backend/models/other_file.py`

## 文件与导入管线

- [29 批量导入进度与手动导入](29-批量导入进度与手动导入.md) — 跨请求共享的导入进度存储，以及手动填写成果表单后的数据组装、校验与落库  `源码: app/import_progress_store.py, backend/services/manual_import_service.py, app/routes/manual_import_helpers.py`
- [30 统一文件管理服务](30-统一文件管理服务.md) — 文件上传、路径规划、类型识别、删除与关联的中央文件服务，是文件安全与流转的统一边界  `源码: backend/services/unified_file_manager.py, backend/services/file_upload_service.py, backend/services/file_deletion_service.py, backend/services/file_exceptions.py`
- [31 奖状处理流水线](31-奖状处理流水线.md) — 从上传文件到 OCR/抽取、校验、审核、入库的奖状处理服务编排  `源码: backend/services/award_processing_service.py`
- [32 成果审核服务](32-成果审核服务.md) — 审核任务创建、提交、批准/驳回、归档的完整状态机，覆盖多角色多成果类型的审核流  `源码: backend/services/review_service.py, backend/models/review_log.py, backend/models/auto_archive_config.py`

## OCR 与文档抽取

- [33 OCR 引擎与供应商抽象](33-OCR 引擎与供应商抽象.md) — 多 OCR 供应商的统一接入、工厂创建、注册表与动态故障转移，是 OCR 能力的可扩展边界  `源码: backend/ocr/core/ocr_engine.py, backend/ocr/core/provider_factory.py, backend/ocr/core/providers.py, backend/ocr/core/provider_registry.py, backend/utils/pdf_to_image.py`
- [34 OCR 缓存与状态](34-OCR 缓存与状态.md) — OCR 请求缓存、供应商健康状态、熔断指标和运行时配置  `源码: backend/ocr/core/cache_db.py, backend/ocr/core/provider_status.py, backend/ocr/config.py, config/ocr_runtime.json`
- [35 抽取框架与类型系统](35-抽取框架与类型系统.md) — 定义抽取器接口、字段类型、识别结果结构和异常体系，是模板抽取与 LLM 抽取的共同基座  `源码: backend/extract/framework.py, backend/extract/types.py, backend/extract/exceptions.py`
- [36 奖状抽取器](36-奖状抽取器.md) — 针对奖状/证书的模板与 LLM 混合抽取，识别竞赛名称、奖项、学生、指导教师等字段  `源码: backend/extract/extractors/award.py`
- [37 证书与其他文档抽取器](37-证书与其他文档抽取器.md) — 证书、成绩单及其他非结构化文档的专用抽取逻辑  `源码: backend/extract/extractors/certificate.py, backend/extract/extractors/other.py, backend/extract/extractors/base.py`
- [38 大创项目抽取器](38-大创项目抽取器.md) — 从大创项目文档中抽取项目信息、成员、指导教师、级别等结构化数据  `源码: backend/extract/extractors/innovation.py`
- [39 LLM 引擎与缓存](39-LLM 引擎与缓存.md) — 封装不同 LLM Provider 的调用、Prompt 解析和重试，并基于数据库缓存响应  `源码: backend/extract/llm/llm_engine.py, backend/extract/llm/provider.py, backend/extract/llm/cache_db.py, backend/agent/llm_adapter.py, backend/extract/prompts/default_prompt.json`
- [40 模板匹配与管理](40-模板匹配与管理.md) — 从预置模板中匹配文档版式，提取字段映射规则并支持模板 CRUD  `源码: backend/extract/template/manager.py, backend/extract/template/matcher.py, backend/extract/template/template.py, backend/extract/template/competition.py, backend/extract/config/type_rules.json`
- [41 抽取结果校验](41-抽取结果校验.md) — 校验抽取结果的完整性和合法性，识别竞赛等级、字段类型等错误  `源码: backend/extract/validator.py, backend/extract/validation/award_validator.py, backend/extract/validation/models.py, backend/extract/validation/rules.py`

## Agent 与 AI 能力

- [42 Agent 工作流编排](42-Agent 工作流编排.md) — 多智能体图（supervisor/extract/review/qa）的状态图定义、节点连接和主循环，是 Agent 系统的中枢  `源码: backend/agent/graph/workflow.py, backend/agent/graph/supervisor.py`
- [43 Agent 节点实现](43-Agent 节点实现.md) — 抽取、审核、QA 三个 Agent 节点如何在工作流中执行各自的工具调用和结果回写  `源码: backend/agent/graph/extraction_agent.py, backend/agent/graph/review_agent.py, backend/agent/graph/qa_agent_node.py, backend/agent/qa_agent.py`
- [44 Agent 工具集](44-Agent 工具集.md) — 暴露给智能体的查询、抽取、统计、导出和上下文工具，是 Agent 与业务模型交互的边界  `源码: backend/agent/tools/query_tools.py, backend/agent/tools/extract_tools.py, backend/agent/tools/stats_tools.py, backend/agent/tools/export_tools.py, backend/agent/tools/context.py, backend/agent/tools/__init__.py`
- [45 Agent 状态与服务入口](45-Agent 状态与服务入口.md) — 对话状态结构、Agent 服务入口与上下文决策，将用户请求路由到合适的子 Agent  `源码: backend/agent/state.py, backend/agent/service.py, backend/agent/decision.py`
- [46 RAG 知识库](46-RAG 知识库.md) — 文档索引、向量化、检索和向量库实现的 RAG 链路，为 QA Agent 提供知识来源  `源码: backend/rag/indexer.py, backend/rag/embeddings.py, backend/rag/retriever.py, backend/rag/vectorstore.py`
- [47 数据分析与指标](47-数据分析与指标.md) — 数据聚合、指标快照、热力图和趋势分析，供看板与 Agent stats 工具使用  `源码: backend/managers/data_analysis_manager.py, backend/utils/metrics.py, backend/services/heatmap_service.py, backend/services/metrics_snapshot.py`

## 日志、审计与运维

- [48 审计日志与系统事件](48-审计日志与系统事件.md) — 操作审计和系统事件的记录、查询、异常落库，结合 trace_id 贯穿全链路  `源码: backend/utils/audit_logger.py, backend/utils/system_event_logger.py, backend/orm/audit_log.py, backend/orm/system_event_log.py`
- [49 日志查询与分析](49-日志查询与分析.md) — 日志文件读取、查询服务和分析器，支撑管理后台日志检索  `源码: backend/services/log_query_service.py, backend/services/log_analyzer.py, backend/services/log_file_reader.py`
- [50 定时任务与日志调度](50-定时任务与日志调度.md) — 后台日志调度、指标归档与容量清理任务，避免长期运行内存/日志膨胀  `源码: backend/utils/log_scheduler.py`
- [51 幂等与熔断](51-幂等与熔断.md) — 防止重复提交的幂等控制、外部服务调用的熔断器与降级策略  `源码: backend/utils/idempotency.py, backend/utils/circuit_breaker.py`
- [52 数据库迁移链](52-数据库迁移链.md) — Alembic 迁移链：从旧库到 ORM 视图、类型化重建、教师外键重连、审计字段扩展  `源码: migrations/env.py, migrations/versions/0001_orm_baseline.py, migrations/versions/0002_legacy_tables_to_views.py, migrations/versions/0003_typization_rebuild.py, migrations/versions/0004_teacher_fk_relink.py`
- [53 初始化与种子数据](53-初始化与种子数据.md) — 初始管理员账号、种子竞赛数据和基础数据导入，用于新环境初始化  `源码: backend/utils/seed.py, scripts/init_system.py`
- [54 备份与清理脚本](54-备份与清理脚本.md) — 数据库备份和过期文件清理等运维脚本  `源码: scripts/backup.py, scripts/cleanup_files.py`
