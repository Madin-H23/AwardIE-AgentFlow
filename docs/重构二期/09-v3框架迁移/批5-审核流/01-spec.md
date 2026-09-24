# 批5-审核流 Spec(01-spec)

> 来源:00-需求.md(4 决策按推荐案落地,待用户复核) | 2026-09-24

## Problem Statement

批4 的提交流只把成果送进 pending 队列,没有出口:教师看不到队列、批不了、批完不物化、无留痕。v2 的审核闭环有完整状态机(pending→archived/rejected)、按类型物化到四张成果表、每步留痕、AI 辅助建议。缺这些,批4 的提交就是死路,批6 的成果库也无数据来源。

## Solution

在 business 模块落三件事:①`ReviewService`——状态机(approve/reject + 非 pending 守卫 + 驳回必填原因)+ 审计留痕(action_type 1/6/7/8)+ 时间线;②物化入库——approve 时按类型分发到 awards/patents/software_copyrights/other_files(本批建四张最简表),竞赛按名自动建,幂等靠业务事实(file_hash)而非审计留痕;③AI 建议——fake/grpc 双模式,Worker 不可用优雅降级不阻塞审核。

## User Stories

1. As a 教师, I want 看待审队列(含提交者姓名)与详情, so that 我能据此初审;
2. As a 教师, I want 批准后成果自动入库到对应成果表, so that 审核有即时结果(不用二次录入);
3. As a 教师, I want 驳回必须写原因, so that 学生知道改什么;
4. As a 审核人, I want 已审记录不能再审(状态机守卫), so that 不会出现重复入库;
5. As a 审核人, I want 每步留痕并能看时间线, so that 争议时可追溯;
6. As a 教师, I want AI 给出辅助建议(字段完整性/白名单), so that 审核更快;但 AI 不可用时审核仍能继续;
7. As a 学生, I want 我的提交被驳回后能改后重提, so that 不被一次驳回卡死(去重只对 pending 生效,批4 已实现)。

## Implementation Decisions

- **状态机**:`ReviewService.approve(id, operator, comment)` / `reject(...)`;守卫 `status == pending` 否则抛 `REVIEW_ILLEGAL_STATE_TRANSITION`;驳回空原因抛 `REVIEW_COMMENT_REQUIRED`;审核人/时间/意见落 pending 的 reviewer_id/review_time/review_comment;
- **审计表** `awardie_achievement_audit_log`(对照 v2 18 列取用):achievement_id/achievement_kind/action_type(1 提交/6 通过/7 驳回/8 物化)/action_result/operator_id/operator_code/operator_name/change_detail(JSON)/created_at + 逻辑删除/租户;操作人取芋道登录用户(昵称作 operator_name,username 作 operator_code);
- **物化四表最简 DDL**:
  - `awardie_awards`:image_hash/certificate_id/certificate_path/competition_name_in_file/track/issuer/province/group_name/winner_name/supervisor_name/award_level/competition_level/date/project_title/competition_id/submitter_type/submitter_id/submit_time + 审计列 + tenant;
  - `awardie_patents`:patent_name/patent_type/application_number(UNIQUE)/inventor/patentee/certificate_file/submitter_*/laboratory_id + 审计列;
  - `awardie_software_copyrights`:software_name/software_version/registration_number(UNIQUE)/copyright_owner/certificate_file/submitter_*/laboratory_id + 审计列;
  - `awardie_other_files`:file_name/file_path(UNIQUE)/file_hash/description/submitter_*/laboratory_id + 审计列;
  - 批6 在四表上补编辑链字段(组别/学生关联/证书链等),本批只建物化所需;
  - **学生获奖关联** `awardie_award_student_winners`(award_id/student_id)——v2 物化 award 时关联 submitter(学生),成果库页"我的获奖"依赖它,本批一并建;
- **竞赛自动建**:物化 award 时按 competition_name 查 `awardie_competitions`,查不到则插入(competition_name + is_auto_added=true),返回 id(与 v2 F9 同);
- **幂等(F3 教训)**:v2 靠"审计有 action_type=8"判幂等,但 v2 存量 164 条 archived 无该留痕——不可靠。v3 改**查业务事实**:award/other 按 file_hash 查对应表,patent/software 按 application_number/registration_number 或 file_path 查;命中则跳过物化(仍记 action_type=8 留痕);
- **空串转 NULL**:`nullable()` 兜底(UNIQUE 约束防撞,同 v2 F10);
- **innovation 不物化**(v1/v2 语义,大创限 admin Excel 通道,批8 处理),approve 时记 action_type=8 + change_detail `{"message":"入库","ref":"skipped"}`;
- **AI 建议(fake/grpc)**:新增 `AiReviewService`(模式 `ai.review.mode` 默认 fake)。fake:返回确定性建议对象(decision=pass、issues 空、suggestion 含免责声明);grpc:调 Worker `ExtractAndReview`(复用 v2 生成的 `AiServiceGrpc` stub 思路——v3 需生成/引入 stub,见 tickets);**任何 gRPC 异常 → 降级(decision=need_manual + code 4003),不抛给用户**;响应固定带 BR-2 免责声明;
- **端点**:`POST /business/pending-achievements/{id}/review`(action=approve/reject)、`GET /business/pending-achievements/{id}/timeline`、`GET /business/pending-achievements/{id}/ai-suggest`、`GET /business/pending-achievements/teacher-pending-list`(join 提交者姓名);权限点 `business:pending-achievement:review`(教师+admin 授),列表/详情复用 query;
- **时间线可见性**:本人/teacher/admin(与 v2 D4);越权返回 FORBIDDEN;
- **不做**:五表编辑链(批6);大创物化(批8);Worker stub 的 gRPC 真连测试(CI 无 Worker,fake 模式覆盖,grpc 路径靠本地手工 smoke)。

## Testing Decisions

- 沿用批1-4 范式(MockMvc + Bearer + tenant 1 + test 库 + 自播种用户,播种走 assignRoleMenu/assignUserRole 避缓存);
- **状态机**:approve→archived;reject→rejected;非 pending(直插 archived)再审 → 1003004002;驳回空 comment → 1003004003;
- **物化**:award/patent/software/other 各 approve 一条 → 对应表 1 行 + audit action_type=8;竞赛自动建(提交时 competition_name 不存在 → approve 后 competitions 多 1 行且 is_auto_added=true);innovation approve → 不物化但 code 0;**重复 approve 同一 pending(重置 status 后再 approve)→ 成果表仍 1 行(幂等)**;
- **审计**:approve 后 audit 表含 action_type 6 与 8 两行;reject 含 7;时间线按 created_at 升序;他人看时间线 → 1003004004;
- **AI 建议**:fake 模式 → 200 + decision 非空 + 免责声明;mode=grpc 但 Worker 不可达 → 降级 decision=need_manual(不 500);
- 断言前自问默认值巧合:用非默认类型/非默认字段组合。

## Out of Scope

五表编辑链与 Fix-C/Fix-R/Fix-T 对应端点(批6);templates/ExtractTemplate/GeneratePrompt(批7);xlsx 导入与大创 status(批8);统计导出(批9);前端(批10);小程序(批11);存量迁移(批12);Worker gRPC 真实连通性测试(无 Worker 环境)。

## Further Notes

- gRPC stub:Worker proto 见 `ai_worker/protos/ai_service.proto`;v2 已生成 Java stub(`com.awardie.ai`)。v3 若引入需 protoc 生成或复用 v2 stub 二进制,属批7(模板+AI 抽取)一并处理;**本批 AI 建议默认 fake,grpc 路径以"Worker 不可达→降级"为测试口径**,不强依赖 stub;
- 物化在 approve 的同一事务内:成果表写失败 → 整个 approve 回滚(pending 状态不变),避免"已审未物化";
- 幂等查业务事实时,file_hash 在 awards/other_files 都有;patent/software 用唯一键(空值则按 certificate_file/file_path),与 v2 nullable 兜底配合;
- 批6 接管后,本批的四张最简表要扩列(ALTER)并补编辑链,届时的字段以批6 spec 为准。
