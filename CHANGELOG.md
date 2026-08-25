# CHANGELOG · AwardIE-AgentFlow 变更史

> 一页式阶段汇总；逐日细节见 `docs/重构/实施记录/` 各篇。
> 本文件由 T37 于 2026-08-24 建立，此后重大变更按阶段追加。

## 2026-08-25 · 重构全景总结 + CI 补漏 + 数据库快照整理

- 重构全景总结成文（1f55a73）：七阶段时间线 / 八大域资产对照 / 十事故诚实复盘 / 八条方法论，全部事实溯源至实施记录与 git 历史
- fix(ci)：data_export 500 根因=requirements-test 缺 pandas——export_utils 顶层 import 致蓝图导入期 ImportError，CI 最小依赖集补 `pandas>=2.0.0`
- parse_students 缺陷修复配套收尾（cb7ed72）：真库守卫用例去数据化（自建探针行驱动），破坏性入口加门控
- database 存量清理：两旧版结构说明删除入归档；54 个 bak.* 快照（含 -wal/-shm）整理入 `database/snapshots/`（整目录 gitignore），restore_awards_history / archive_dead_drafts 脚本路径同步
- docs 路由与根 README 对齐现状：端口 5001 / CPU 依赖与 RAG 补装 / 测试账号 / 破坏性回归纪律

## 2026-08-24 · 冻结期收官（T35-T37 / T75 收尾 / parse_students 缺陷修复）

- 文档体系整理：docs 根层 12 散文件归位（用户指南/运维指南），设计文档 41+plans 15+database 两旧版
  入 归档/，wiki→架构解读，新建 docs/README.md 路由索引与本文件
- T75 全清账：certificate_extractor 按签认契约解冻（12 例构造修复+18 例转正收编 CI）；
  extract 系 140 例冻结测试全部恢复常驻防线
- parse_students 双缺陷修复（hewj 授权 F3 唯一豁免点）：兜底正则排除全角括号 +
  循环三元组化修 P3 分组错位；存量 other_members 零污染

## 2026-08-23~24 · 「见好就收」三阶段 goal（70483a5…cdba139）

- **P0 可用性收口**：CDN 外链清零（11 模板切本地 vendor）；/student/activities 坏页下线；
  断网模拟外部请求 0 个
- **P1 审计流卫生**：迁移 0012_audit_test_flag——历史噪音打标 1290 条/保留 7 条真实删除史；
  AuditLogger pytest 运行态自动标记；查询层默认过滤；登录 410ms=scrypt 结案归档
- **P2 六批**：models 覆盖率 44%→60%（护栏 43 例）；39 条死草稿归档清零；
  skip 零头清理；get_config 单语义收敛；app.utils 单一真源收敛（_core.py）；
  T74 双壳决策落档（user_base=师生门户基类，保留不迁）

## 2026-08-21~22 · AI 助手体验与数据资产保护

- AI 助手 V2：三模式独立窗口、markdown 排版、分片流式（T45-T48）
- 出站直连修复（trust_env=False，代理开关均可用）
- P0 数据资产保护：R-031 写路径缺 commit 致 awards 不落库（恢复 195 行历史成果）、
  R-032 sqlite_sequence 去重（迁移 0011）、R-033 备份 WAL 一致性；
  log_scheduler 每日窗口自动备份 + restore_awards_history 幂等恢复脚本

## 2026-08-20 · 阶段六日志系统 L1-L6 + 管理端控制台化

- 日志系统 L1-L6 全量落地（system_event_log/trace_id/分析告警/admin_log 蓝图/前端看板）
- T9：54 个 admin 页换壳 base_console 控制台新体系 + 数据总览看板首页
- 白屏根因 P19（console_tokens.css 损坏）等前端稳定性系列修复

## 2026-08-17 ~ 08-19 · 二期与测试体系奠基

- M1 users 引用重写（10 表 submitter_id → users.id）+ ORM 化 + Alembic 迁移链起点
- M2 路由去重（上传链路参数化）；M3 pending is_valid 生成列
- 阶段六前置：测试方案 v1.1 / 风险登记册 / TODO 索引三权威文档建立
- CI 质量门全绿（最小依赖集/F821 硬门禁/覆盖率门禁）

## 2026-08-14 ~ 08-16 · 四阶段重构（stage1-stopbleed → stage4-engineering 四 tag）

- 阶段一止血：P0×10 清零（debug 门控/DB 连接工厂/竖图旋转/上传白名单等）
- 阶段二加固：CSRF/IDOR/幂等键/AppError 契约/熔断/SSE 骨架（15/15 闭环）
- 阶段三重构：决策公共模块/RAG 统一检索/users 三表合并数据层/QA 流式/审核时间线
- 阶段四工程化：Dockerfile/compose/nginx/metrics/backup.py/CI 流水线
- SRS v1.8（业务需求章+根因复盘）+ SDD 六篇 + 交叉审查 CR-1~12 全修

## 2026-08-14 之前 · 初始化

- Flask 3 + SQLite(WAL) + LangGraph 多智能体 + ChromaDB RAG + 百度 OCR 成果管理系统初版
