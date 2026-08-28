# v2 重构 Grilling Handoff（新 session 起点材料）

| 项目 | 内容 |
| --- | --- |
| **日期** | 2026-08-29 |
| **用途** | 供新 session 运行 `/grill-with-docs` 时作为起点输入；本文件固化当前上下文，避免访谈从零开始 |
| **前置状态** | 立项方案已入库（commit 9f00fa9）、skills 前置配置已完成（docs/agents/ 三件 + CLAUDE.md Agent skills 段） |
| **预期产物** | `CONTEXT.md`（repo 根）+ ADRs（docs/adr/，仅在决策修订时）+ P0 阶段 spec 素材 |

---

## 1. 访谈入口（新 session 第一句话）

```
/grill-with-docs
```

提醒 agent：本文件是起点材料，按阶段切片喂入方案文档（先 §2/§4/§10/§14，即 P0 相关章节），不要一次吞 1707 行。

## 2. 已拍板层（访谈中不需重谈，除非新证据推翻）

| # | 决策 | 来源 |
| --- | --- | --- |
| D1 | 后端：Spring Boot 3.3 + Java 21 + JPA | 2026-08-25 对话拍板 |
| D2 | 前端：Vue 3 + Vite 5 + Pinia + Element Plus + TypeScript | 同上 |
| D3 | 数据库：PostgreSQL 16 + Flyway + pgvector | 同上 |
| D4 | AI 进程：Python 保留，gRPC 暴露给 Java | 同上 |
| D5 | 迁移策略：Strangler Fig + Nginx 切流 + 方案 A 起步（Flask 写主 + Java 影子读） | 同上 |
| D6 | 业务范围：v1 全部功能 1:1 复刻（265 端点 / 30 表 / BR-1~7 不变） | 立项方案 §3/§4 |
| D7 | 不引入：WebFlux / MyBatis-Plus 主路径 / Nacos / Kafka / 微服务（v2 范围内） | 立项方案 §5.7 |

## 3. 四个 Gap（✅ 2026-08-29 已全部回答，grilling 跳过第一轮）

| # | Gap | 答案 | 影响 |
| --- | --- | --- | --- |
| 1 | 项目目的权重 | **面试/答辩作品优先** | tracer bullet 选"能打通全栈纵切面"的切片；里程碑对齐答辩节奏；265 端点全量复刻降级为非必须（见 §8-1） |
| 2 | 时间预算 | **5-10h/周**（含 agent 杠杆） | 核心链路约 7-9 个月；范围 = 纵切面 + 60-70% 高频页面，长尾留 v1 |
| 3 | 立项流程真实性 | **无，直接开工**（个人项目） | 立项 6 节点（答辩/周报/资源审批/Kickoff）全部取消，grilling 完直接进 to-spec |
| 4 | M4 硬度 | **软目标** | P4"v1 下线"改为"P4 稳态收束"（可选）：写操作切 v2 后 v1 只读存档并存，见好就收随时可停 |

## 8. 答案的直接影响（grilling 时需正式确认的改写）

1. **范围改写（最大影响）**：方案 §4.1"P0 = v1 全部功能 1:1 复刻（265 端点）"在作品导向下降级——**核心纵切面 30-50 端点（登录→成果提交→AI 审核→入库→AI 助手问答）是 P0-P2 的真范围**；答辩考的是"核心链路全栈真实现 + 可讲的设计故事"（Strangler 灰度 / gRPC 双进程 / 影子同步机制），不是全量端点数。88 模板中约 60-70% 高频页面 Vue 化，长尾（报表/实验室/门户边角）留 v1 只读并存。
2. **节奏改写**：28 周（2-3 人全职）→ **单人 + agent、约 6-9 个月**（范围收缩对冲了单人缺口）；每阶段 DoD 数值不变，但阶段数量与内容按 §8-1 收缩。
3. **流程改写**：无立项仪式 → to-spec 直接跟在 grilling 后；部门周报改为面向导师的结论式汇报（沿用去黑话格式），仅作同步不作审批。
4. **tracer bullet 候选方向**（grilling 确认第一张 ticket）："登录（Java Security + PG）→ 成果上传提交（Vue 表单 + Flask 影子读对照）→ AI 审核（gRPC 调 Python Worker）→ 入库 + 时间线展示"——一条线吃满四项选型，是作品叙事的最短路径。

## 4. 探针问题（prototype 候选，纸面定不了）

| # | 问题 | 关联风险 | 探针形态 |
| --- | --- | --- | --- |
| P1 | gRPC server-streaming 经 Nginx 透传是否稳定（缓冲/断流行为） | R-045 | throwaway：Java gRPC client + Python server + Nginx 配置，curl 观察 delta 间隔 |
| P2 | pgloader 迁移 v1 SQLite（jsonb/生成列/BLOB）真实坑位 | R-046 | throwaway：对 database/competitions.db 副本实跑 pgloader，记录失败清单 |
| P3 | 虚拟线程 + JPA 在真实负载下的 P95 | R-041 | 可推迟到 P0 脚手架后测，不必前置 |

纪律：探针代码放 `prototype/<name>` 分支，答案折进真实设计后 prototype 保留为 primary source（v1"探针先行定案"方法论同构）。

## 5. 输入材料指针

| 材料 | 路径 | 用途 |
| --- | --- | --- |
| 立项方案 v1.0 | `docs/重构二期/2026-08-25_二次重构方案.md` | 访谈主输入（按章节切片） |
| 审查报告 | `docs/重构二期/评审报告/2026-08-25_方案审查报告.md` | 已修补项清单 |
| v1 SRS | `docs/重构/2026-08-14_需求分析文档.md` | 业务基线 |
| v1 风险登记册 | `docs/重构/风险登记册.md` | 28 条历史风险（R-031 教训等） |
| v1 数据库结构说明 | `docs/重构/设计/2026-08-21_数据库结构说明.md` | 30 表权威结构 |
| v1 全景总结 | `docs/重构/2026-08-25_重构全景总结.md` | 方法论沉淀（探针先行/goal 制/契约签认） |
| CLAUDE.md Agent skills 段 | `CLAUDE.md` | issue tracker / triage labels / domain docs 约定 |

## 6. Context Hygiene 纪律

- **grilling → /to-spec → /to-tickets 必须在同一未中断的 context window**（约 150k tokens 内）；本 handoff + 方案切片是初始输入。
- /to-tickets 产出后：每张 ticket 单独新开 session 跑 /implement，ticket 间 /clear。
- 探针任务（第 4 节）在 grilling 完成后、to-spec 前执行；探针结论折入 spec。
- 若 session 在 to-tickets 前接近 context 上限：在最近的 phase boundary /compact，不硬撑。

## 7. Grilling 目标（验收口径）

- [x] 四个 Gap 全部有明确答案（✅ 2026-08-29 本 session 完成，见 §3/§8）
- [ ] P0 阶段范围经逐项确认（按 §8-1 收缩后的"纵切面+高频页面"口径，不是方案原文复读）
- [ ] 决策如有修订：新 ADR 落 `docs/adr/`（编号从 0001 起，首条建议 ADR-0001"作品导向范围收缩"），方案文档暂不改版（等 P0 收官统一升 v2.0）
- [ ] 第一张 tracer-bullet ticket 的方向已定（候选见 §8-4）
