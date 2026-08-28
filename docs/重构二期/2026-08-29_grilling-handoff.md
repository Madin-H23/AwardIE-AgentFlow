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

## 3. 四个 Gap（grilling 第一轮必答，答案落 CONTEXT.md）

1. **项目目的的权重排序**：学习 Java 栈 / 真的上线替换 v1 / 面试（答辩）作品——三者比例是多少？
   - 影响：ticket 切法。面试作品 → tracer bullet 选"能展示全栈纵切面"的切片；真上线 → 数据迁移链路先跑通；学习 → 关键模块亲手写、agent 只做脚手架。
2. **真实时间预算**：实习期每周实际可投入小时数？单人还是能拉到帮手？
   - 影响：28 周路线图按 2-3 人全职排的；若实际是 1 人 × 业余时间，节奏需重排（P0 可能拉长到 6-8 周）。
3. **立项流程的真实性**：方案里"评审委员会答辩 / 部门周报 / 资源审批"6 节点是推断的流程，你的真实环境是否有这套组织流程？
   - 影响：若无，立项 6 节点简化为"导师知会 + 周报备案"两步；若有，按方案走。
4. **M4（v1 下线）硬度**：2027-02 下线 v1 是硬 deadline 还是软目标？
   - 影响：硬 → P2/P3 缓冲策略保守化；软 → 可按"见好就收"动态收束。

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

- [ ] 四个 Gap 全部有明确答案，落 `CONTEXT.md`
- [ ] P0 阶段（第 1-4 周）范围经逐项确认（不是方案原文复读，是确认过的范围）
- [ ] 决策如有修订：新 ADR 落 `docs/adr/`（编号从 0001 起），方案文档暂不改版（等 P0 收官统一升 v2.0）
- [ ] 第一张 tracer-bullet ticket 的方向已定（选哪个纵切面先打通）
