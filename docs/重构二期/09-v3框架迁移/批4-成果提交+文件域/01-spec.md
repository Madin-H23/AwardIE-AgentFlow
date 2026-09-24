# 批4-成果提交+文件域 Spec(01-spec)

> 来源:00-需求.md(grilling 4 决策已获用户 2026-09-24 确认) | 2026-09-24

## Problem Statement

批1-3 让 v3 有了基座、用户与基础数据,但成果提交流整体缺失——v2 里学生提交一张证书走的是"文件三校验 → 五类字段校验 → sha256 去重 → pending 入库"这条纵切面,是三角色全链路的起点。没有它,批5 审核流、批6 物化都无处落脚。文件域同样缺失:v2 的目录存储 + 三校验 + sha256 去重是 v1 以来的业务硬要求,芋道自带文件模块不覆盖后两条。

## Solution

在 business 模块落两件事:①`AwardieFileStorage`——目录存储 + SHA-256 去重 + 三校验 + 路径防护,存储根参数化;②`awardie_pending_achievements` 表 + 提交侧四端点(提交/我的提交/撤回/下载)+ 五类成果字段校验 + pending 状态下的 sha256 去重。顺带把批3 挂账的实验室关联四表与详情/下载端点做完,并把四表接入批3 的删除引用检查清单。

## User Stories

1. As a 学生, I want 上传证书图片/PDF 并填成果表单提交, so that 我的成果进入待审队列(批5 审核的输入);
2. As a 学生, I want 提交后看到字段校验结果(缺什么/格式错), so that 不必等审核退回才知道填错;
3. As a 学生, I want 同一份文件不重复提交, so that 待审列表不被重复件淹没(v2 sha256 去重语义);
4. As a 学生, I want 审核前能撤回自己的提交, so that 传错文件可自行纠正(Fix-E 语义);
5. As a 教师/管理员, I want 下载任意待审文件做初审, so that 审核有据(v2 BR-7:下载一律 attachment);
6. As a 管理员, I want 删实验室时若其下有成员/图片/下载文件则拒绝, so that 不会误删实验室资产(批3 挂账项);
7. As a 开发者, I want 文件存储根可配置、测试写独立目录, so that 测试不污染开发数据、CI 可跑(v2 批3 同教训)。

## Implementation Decisions

- **文件域**:新增 `service/file/AwardieFileStorage`(Spring 组件),构造参数 `@Value("${awardie.file.root:files/v3}")`;方法 `assertAllowed(filename, bytes)`(三校验,顺序=扩展名白名单 → 10MB → 魔术字节,失败抛 `ServiceException(FILE_*)`)、`store(filename, bytes)`(sha256 hex,文件名 `hash[0:16] + "." + ext`,写前 mkdirs)、`resolve(relativePath)`(normalize + startsWith(root) 防越界)、`readAll`、`contentTypeOf`;测试注入 `awardie.file.root=target/test-files`(application-test 约定,不加进 yaml 默认);
- **pending 表**:`awardie_pending_achievements`,列对照 v2 20 列,JSONB→MySQL `JSON`,布尔无;`status` VARCHAR(20) 默认 'pending',`version` INT 默认 1;唯一性:不加 DB 唯一索引(同批3 逻辑删除理由);`file_hash` VARCHAR(64) NOT NULL(去重靠它,但唯一性在 service 层且只对 status=pending 生效,DB 唯一索引会误伤 archived/rejected 行);
- **五类字段校验**:`SubmissionValidator`(纯函数,可直测),按 achievementType 分发——award 必填 competition_name/award_level/winner_name/date + date 四格式且年份 2000-2100;patent 必填 patent_name + application_number 须 CN 开头且长度≥5 + patent_type ∈ {发明专利,实用新型,外观设计};software 必填 software_name + registration_number 须 20 开头 11 位;innovation 必填 project_name;other 必填 title;未知类型抛异常(4000);`is_valid = content 为空 && completeness 为空`;
- **提交 service** `PendingSubmissionService.submit(submitterId, submitterType, achievementType, filename, bytes, dataJson)`:三校验 → 字段校验 → store → sha256+pending 去重(拒则 4001)→ 入库(status=pending,version=1,validation_result=JSON);submitterType 由 controller 从当前登录用户角色推导(学生/教师),不信任前端入参;
- **端点**(挂在 `/business/pending-achievements`):POST `/submit`(multipart:file+achievementType+data)、GET `/my-page`(分页,service 层按当前用户 submitter_id 过滤)、DELETE `/withdraw`(id;仅本人 + status=pending,否则 4009/4030)、GET `/download`(id;本人或 teacher/admin,Content-Disposition attachment + contentTypeOf);
- **实验室关联**:`awardie_laboratory_downloads`(file_path/file_title/file_name/file_size/submitter_*/is_public/display_order)、`awardie_laboratory_images`(image_path/file_name/file_hash/description/display_order/submitter_*)、`awardie_laboratory_instructors`(laboratory_id+teacher_id 联合主键)、`awardie_laboratory_students`(laboratory_id+student_id);端点 GET `/business/laboratories/{id}/detail`(信息+教师+学生+下载数+成果数)与 `/downloads`(下载列表,display_order,id DESC);**awardCount 本批查 awards 表不存在→返回 0 并在代码注释标明批6 补**(不静默假装有数据);
- **引用清单衔接**:四表(仅 downloads/images/instructors/students 持有 laboratory_id 的)追加进 `AchievementReferenceChecker.LABORATORY_REFERENCES`;关联表无 `deleted` 列 → checker 的 columnExists 分支自动退化为不过滤 deleted(已在批3 写好);
- **错误码**:续 1_003_002_000(pending 域)与 1_003_003_000(实验室关联域):`PENDING_ACHIEVEMENT_NOT_EXISTS`、`PENDING_ACHIEVEMENT_DUPLICATE_FILE`、`PENDING_ACHIEVEMENT_NOT_WITHDRAWABLE`、`PENDING_ACHIEVEMENT_FORBIDDEN`、`PENDING_ACHIEVEMENT_TYPE_UNKNOWN`、`FILE_TYPE_NOT_ALLOWED`、`FILE_TOO_LARGE`、`FILE_CONTENT_MISMATCH`、`FILE_PATH_ILLEGAL`;
- **不做**:审计日志表(批5)、时间线、审核动作、物化五表、xlsx 导入、存量迁移。

## Testing Decisions

- 沿用批1-3 范式:`yudao-server/src/test/java/cn/iocoder/yudao/server/business/`,MockMvc + Bearer + tenant-id 1 + test 库,只测外部行为(HTTP + DB 终态 + 文件落盘终态);
- **文件域单测**(新建 `AwardieFileStorageTest`,纯 JUnit,用 target/test-files):三校验各一拒(`.txt` 扩展名 / 11MB / 内容与扩展名不符)+ 合法 PDF 落盘 + 同内容再存一次命中同路径(去重)+ resolve 越界(`../`)拒绝 + contentTypeOf 映射;
- **提交流集成测试**(`PendingSubmissionControllerTest`):五类成果各提交一条(用真实魔术字节构造 jpg/png/pdf 夹具,不用默认假文件——"断言前自问是否因默认值巧合通过")+ 字段校验结果断言(缺 winner_name → is_valid=false + issues 非空)+ 同 hash 重复提交 → 1003002001 + 撤回(仅本人/仅 pending/非本人各一)+ 下载 attachment(本人 OK,他人学生 4030)+ 教师提交 submitter_type=teacher;
- **实验室关联测试**(`LaboratoryAssetsTest` 或并入批3 测试类):详情聚合返回教师/学生/下载数 + 引用表建临时行后删实验室被拒(复用批3 `ReferenceCheckTest` 的建表/删表模式);
- 临时文件清理:测试类 `@AfterEach` 递归清 target/test-files;
- dev 端到端:venv requests 走"登录→提交→我的提交→撤回→下载"五步(中文表单,不用 curl)。

## Out of Scope

审核动作与时间线(批5);awards/patents/software/innovation/other 五表与物化(批6);templates 与 AI 抽取(批7);achievement_audit_log 表(批5);xlsx 导入(批8);统计导出(批9);前端页面(批10);小程序(批11);588 条 pending 与 30MB 文件实体迁移(批12);芋道 infra 文件模块的改造或删除。

## Further Notes

- 提交端点是 multipart,测试用 MockMvc `multipart()` 构造;中文文件名在 Windows 控制台 curl 会 GBK 变形,测试与验收一律 venv python;
- sha256 去重只查 `status=pending`:驳回后重提同一文件应允许(v2 语义:驳回后修改可重新提交,新行);
- `store()` 同 hash 同扩展名直接覆盖写入(REPLACE_EXISTING),内容一致故无副作用;不同扩展名同内容会存两份(hash 前 16 位相同但扩展名不同)—沿 v2 行为,不额外收敛;
- 实验室关联表无 tenant_id?——**必须有**(芋道多租户拦截器对无 tenant_id 表会跳过追加,导致跨租户可见;批3 两表都有),建表时带 tenant_id;
- 撤回用逻辑删除(BaseDO),v2 是物理删;逻辑删除后 sha256 去重不再命中(查 pending 状态时自动过滤 deleted),与"撤回后可重新提交"一致。
