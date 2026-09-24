# 批7-模板+AI抽取 Spec(01-spec)

> 2026-09-24 | 依据 `00-需求.md`(facts 由 agent 实测,决策按推荐案落地待复核)
> 项目 domain glossary:竞赛(competitions)/实验室(laboratories)/待审成果(pending-achievements)/成果库(vault)/模板(templates)/样本图(sample image)/授予角色(granted role)/物化(materialize)

## Problem Statement

管理员在 v2 里维护证书模板时,只能通过一个把 SQL 直接写在 Controller 里的自建端点组操作:创建、详情、编辑、样本图回显、AI 试测、创建前抽取、生成 prompt。这套东西有三个问题让它无法原样搬进芋道底座:

第一,它没有 Service 分层、没有租户列、没有逻辑删除、没有独立权限点,只有一句 `ROLE_ADMIN` 硬判。芋道的租户拦截器、多租户授权、逻辑删除基础设施在它身上全都用不上,而"竞赛被模板引用就不能删"这条保护规则虽然批3 已在引用清单里预留,却因为表不存在而一直空转。

第二,管理员在详情页编辑关键词时,前端发的是 JSON 字符串、后端要的是 JSON 数组,保存会静默错位;而编辑默认字段还能把授予角色改掉,从而绕过"同竞赛同角色只能有一个模板"的唯一性——这是缺陷不是语义,不该照搬。

第三,也是本批真正的阻塞点:Python AI Worker 提供了 `ExtractTemplate` 与 `GeneratePrompt` 两个 RPC,v2 通过 gRPC 调用它们给管理员做"上传奖状样本图→自动抽取字段→生成 prompt"的辅助流程。但 v3 至今没有接过任何 gRPC——审核流的 AI 建议在 grpc 模式下是硬编码降级("stub 属批7"),模板域的两个 RPC 更是连端点都没有。管理员在 v3 上传样本图,拿不到任何 AI 辅助。

同时还有批4 遗下的一笔账:成果提交是"先落盘再入库",入库失败时磁盘上留下没有任何记录指向的文件。更麻烦的是文件按内容哈希命名,同一个文件可能被别的待审行、物化后的成果、实验室附件共同引用,所以不能想当然地删。

## Solution

在芋道底座上重建证书模板域,并首次把 AwardIE 的 gRPC 客户端建起来。

模板域按芋道分层重建:`templates` 表补齐租户与逻辑删除等基础设施列,授予角色从 JSON 里提为独立列(唯一性因此可索引、也不再能被编辑绕过);五个端点(列表/创建/详情/编辑/样本图回显)加一个逻辑删除端点,统一走权限点与菜单;样本图复用批4 的文件域服务,含三校验与内容去重。批3 预留的竞赛引用保护随着建表自动生效。

gRPC 侧把 proto 与生成物引入 v3 并落到芋道包规范下,建一个参数化、懒连接的 Worker 客户端。模板域三个 AI 端点与审核流的 AI 建议共用同一个模式开关:fake 模式走确定性桩(测试与离线开发不受影响),grpc 模式调真 Worker。因为 Worker 把业务错误码写在响应体里而不是 gRPC 状态码,客户端与调用方一律双层判错;Worker 不可用时模板域返回业务错误码、审核流转人工审核,两种情况都不崩、不挂死。顺带把批5 留下的"审核流 grpc 分支硬编码降级"清偿掉。

文件侧给存储服务补删除能力,并新增一个按路径查引用的检查器:提交流程把去重判断前置到落盘之前(最常见的孤儿场景直接消失),落盘后失败则由事务回滚钩子回收文件,回收前先查是否还有别人引用这个文件——内容寻址下这是唯一安全的做法。模板删除也走同一套引用检查。

## User Stories

1. As an 管理员, I want 在模板列表里按竞赛和授予角色筛选模板, so that 我能快速定位某个竞赛的学生奖或教师奖配置。
2. As an 管理员, I want 模板列表分页返回总数与行数据, so that 我能知道模板规模并翻页浏览。
3. As an 管理员, I want 创建一个带样本图的模板, so that 我可以为某个竞赛的某种授予角色沉淀一套抽取规则。
4. As an 管理员, I want 创建时样本图必须是合法图片且不超过 10MB, so that 坏文件不会污染文件存储。
5. As an 管理员, I want 同一个竞赛的同一种授予角色不能创建第二个模板, so that 抽取时不会出现规则二义。
6. As an 管理员, I want 创建时指定不存在的竞赛会被明确拒绝, so that 模板不会挂在一个不存在的竞赛上。
7. As an 管理员, I want 创建时授予角色只接受"学生"或"教师", so that 角色枚举不会混入自由文本。
8. As an 管理员, I want 创建时非法 JSON 规则字段被明确拒绝, so that 我能立刻知道哪一栏填错了而不是收到 500。
9. As an 管理员, I want 模板详情返回竞赛名、角色、语言、长度区间、关键词、样本文本、抽取结果、默认字段、LLM 字段和"是否有样本图", so that 我在一个页面看到模板全貌。
10. As an 管理员, I want 详情里的 JSON 字段是可直接解析的结构而不是需要二次解码的字符串, so that 前端不必处理 v2 那套字符串套 JSON 的别扭契约。
11. As an 管理员, I want 在详情页回显样本图原图, so that 我能确认上传的图是对的。
12. As an 管理员, I want 样本图文件丢失时回显给出明确的"不存在"而不是 500, so that 我知道该重新上传。
13. As an 管理员, I want 编辑模板的语言、长度、关键词、样本文本、默认字段与 LLM 字段, so that 我能按试测结果迭代规则。
14. As an 管理员, I want 编辑时不能改授予角色与所属竞赛, so that 唯一性不会被绕过、模板不会漂移到别的竞赛。
15. As an 管理员, I want 编辑不存在的模板得到明确的"不存在", so that 我知道页面上的 id 已失效。
16. As an 管理员, I want 删除一个模板, so that 我能清理不再使用的规则。
17. As an 管理员, I want 删除模板时它的样本图物理文件也被回收, so that 磁盘不会随模板清理而持续增长。
18. As an 管理员, I want 模板被删除后不出现在列表里, so that 我看到的都是有效配置。
19. As an 管理员, I want 还有模板引用的竞赛不能被删除, so that 我不会删掉竞赛却留下悬空模板。
20. As an 管理员, I want 样本图与别的附件内容相同时,删除模板不会误删那个被共享的文件, so that 别人的附件不会因我的操作消失。
21. As an 管理员, I want 上传样本图后点"试测"拿到抽取字段与 OCR 文本, so that 我能验证这套规则是否管用。
22. As an 管理员, I want 在还没保存模板时就能先试抽取, so that 我不用先建一条脏数据再验证。
23. As an 管理员, I want 基于模板规则生成一段抽取 prompt, so that 我能把它用于人工或下游的抽取任务。
24. As an 管理员, I want AI 端点在离线(fake)模式下返回稳定的桩结果, so that 我能在没有 Worker 的环境里演示和开发。
25. As an 管理员, I want AI 端点在 Worker 不可用时返回明确的"AI 服务不可用"业务错误, so that 我知道该等服务恢复而不是看到 500。
26. As an 管理员, I want AI 端点不会因为 Worker 无响应而把请求挂死, so that 页面不会一直转圈。
27. As an 教师, I want 审核待审成果时能拿到 AI 建议, so that 我能更快判断材料是否合规。
28. As a 教师, I want AI 建议不可用时自动转人工审而不是审核流程被卡住, so that AI 故障不影响我的正常工作。
29. As a 教师, I want AI 建议里始终带着"仅辅助参考"的声明, so that 我不会把它当成最终结论。
30. As a 学生, I want 我不能打开模板管理端点, so that 模板配置只能由管理员维护。
31. As a 教师, I want 我不能打开模板管理端点, so that 模板配置只能由管理员维护。
32. As a 学生, I want 重复提交同一个文件时不必担心磁盘被占, so that 我的误操作不会浪费存储。
33. As a 学生, I want 提交过程中即使入库失败,磁盘上也不会留下无人认领的文件, so that 存储不会随着失败尝试无限膨胀。
34. As an 管理员, I want 提交失败时的文件回收不会误删仍被其他记录引用的文件, so that 补偿逻辑不会破坏别人的数据。
35. As a 运维, I want gRPC 目标地址、超时全部可配置, so that 换 Worker 主机或调超时不必改代码。
36. As a 运维, I want Worker 没启动时应用照样能正常启动, so that AI 故障不会拖垮整个服务。
37. As a 运维, I want fake/grpc 用一个开关控制, so that 不会出现两个互相矛盾的配置项。
38. As a 运维, I want 从代码里能看出 gRPC stub 来自哪个 proto 与哪个生成器版本, so that 契约变更时知道该重新生成什么。

## Implementation Decisions

- **模块**:改动 `yudao-module-business`(芋道业务模块),新增模板域包 `controller/admin/template`、`service/template`、`dal/dataobject/template`、`dal/mysql/template`、`framework/grpc`、`service/reference`;依赖管理改 `yudao-dependencies`(新增 grpc/protobuf 版本管理);业务模块 pom 新增 gRPC 客户端依赖。

- **gRPC 契约引入方式**:把 Worker 的 proto 复制进 v3 并**追加 `java_package` / `java_outer_classname` 选项**,使生成物落到 `cn.iocoder.yudao.module.business.framework.grpc.awardie.ai`,然后用与 v2 相同版本的 protoc 与 grpc-java 插件重新生成。**不复制 v2 已入库的生成物文件**(它们在顶层 `awardie.ai` 包且体量 1.5 万行,不符合 v3 包规范)。proto 的 `package awardie.ai` 不动——wire 契约包名一变,现有 Python Worker 就对不上。生成物目录固定、不参与 IDE 索引以外的人工编辑,并在生成脚本旁记录工具版本。

- **gRPC 版本**:grpc-java 1.64.0、protobuf-java 3.25.3(与 v2 生成时的 protoc 版本一致,避免升级生成物带来的行为漂移);传输用 `grpc-netty-shaded`,避免与芋道自身 Netty 依赖抢版本。

- **客户端形态**:单 `ManagedChannel` + blocking stub,`usePlaintext` + keepAlive(与 v2 范式一致),实现 `AutoCloseable` 由 Spring 调 `close()`;**懒连接**——构造 channel 不发起连接,Worker 不在线不影响应用启动;每次调用用 `withDeadlineAfter` 施加超时。

- **配置项**(新增,全部有默认值):
  - `awardie.ai.worker.mode`:`fake` | `grpc`,默认 `fake`;
  - `awardie.ai.worker.host` / `port`:默认 `127.0.0.1` / `50060`;
  - `awardie.ai.worker.extract-timeout-seconds`(抽取,默认 120) / `prompt-timeout-seconds`(prompt,默认 60) / `review-timeout-seconds`(审核流,默认 320)。
  - 批5 遗留的 `ai.review.mode` **被 `awardie.ai.worker.mode` 取代**,审核 AI 建议与模板 AI 端点读同一开关;旧键不再保留(两个开关必然分叉成互相矛盾的配置)。

- **错误处理契约(双层判错)**:Worker 把业务码写在响应体 `code` 字段内(gRPC transport status 恒 OK),因此调用方必须先判 `resp.getCode()`(0 成功,4000 规则非法,4003 AI 依赖不可用,4004 图片不可读/抽取失败,5xxx 内部错误),再捕获 `StatusRuntimeException`(连接失败/超时/序列化失败)并映射为 4003。两条路径都不得冒泡成 500。

- **审核流 grpc 分支**:改为消费 `ExtractAndReview` 的 server-streaming,读到 `final` 事件后映射为现有 `Suggestion` record(decision / issues_json / suggestion / code);流中断、超时、无 `final` 事件一律走既有降级路径(转人工审 + 4003 + AI 免责声明),**降级契约与批5 完全一致**。

- **模板域表结构**:新建 `awardie_templates`,字段 = v2 语义字段 + 芋道标准列(`tenant_id`、`creator`、`create_time`、`updater`、`update_time`、`deleted` 逻辑删除)。`granted_role` 从 `default_fields` JSONB 提为独立 `VARCHAR` 列(唯一性因此可走列比较);`competition_id` 建索引;四个规则字段(`keywords` / `sample_extracted` / `default_fields` / `llm_fields`)用 MySQL `JSON` 类型(与批4/6 已用的 `validation_result` / `other_members` 一致)。**不加 `name` / `status` / 业务编号**——v2 无此语义、无存量值可回填。

- **唯一性语义**:保留 v2 表达的意图"同竞赛 + 同授予角色 + 未删除只允许一个模板",改为对独立列做应用层校验(沿用项目既定纪律"业务唯一性不加 DB 索引",逻辑删除下唯一索引也会误伤已删行),冲突抛业务错误码。

- **编辑白名单**:编辑只接受语言、长度区间、关键词、样本文本、默认字段、LLM 字段、是否翻译;**`granted_role` 与 `competition_id` 不在白名单**(v2 能改 `default_fields` 从而绕过唯一性,是缺陷,明确修掉)。非白名单键静默忽略(与批6 成果库行编辑口径一致)。

- **删除语义**:逻辑删除(`deleted=1`),不建 DB 外键(逻辑删除下 FK 永不触发,与批3-6 一致);模板无下游业务引用(成果提交/审核链都不查模板),故不做引用拒绝;删行成功后在同一流程内回收样本图物理文件,回收前走引用检查。

- **文件引用检查器**:新增 `FileReferenceChecker`,按"表名 → 路径列"配对清单驱动,口径与既有 `AchievementReferenceChecker` 完全一致——表不存在则跳过(逐批建表期)、有 `deleted` 列则 `deleted=0` 才算引用、标识符正则白名单、值全部参数化。清单覆盖所有存路径的表(共 8 张):待审成果 `file_path`、实验室下载 `file_path`、实验室图片 `image_path`、成果证书 `certificate_path`、专利 `certificate_file`、软著 `certificate_file`、其他文件 `file_path`、模板 `sample_image_path`(列名不一致,故按表:列配对;专利/软著两列是 OCR 审查补上的,初稿漏了它们)。

- **文件存储能力扩展**:`AwardieFileStorage` 增 `delete(relativePath)`(幂等,文件不存在不报错)与 `deleteIfUnreferenced(relativePath)`(先查引用再删,无引用才删)。落盘/读取/解析/Content-Type/三校验等既有行为不动。

- **孤儿文件补偿**:`PendingSubmissionService.submit()` 的顺序调整为 三校验 → 字段校验 → **算 sha256 → 去重查询** → 落盘 → insert → 留痕(去重前置:哈希可由字节直接算出,不必落盘就知道是否重复,这消灭了最常见的孤儿场景);落盘之后若 insert/留痕失败,由 `TransactionSynchronization` 在事务 `afterCompletion` 回滚时触发 `deleteIfUnreferenced`。已知边界:补偿本身失败会留残留文件,按可接受处理,不引入事务代理重写。

- **权限模型**:五个权限点 `business:templates:query|create|update|delete|export`,菜单 3005 + 权限点 3051-3055(已核实官方 `system_menu` 该段完全空闲);授权 super_admin 与 awardie_admin,**`system_role_menu` 的 INSERT 必写 `tenant_id=1`**(批6 头号缺陷:租户拦截器会自动追加租户条件,漏写则落到默认值 0,全新库上全站 403);学生/教师不授权。样本图回显与三个 AI 端点归 `query` 权限(AI 是模板编辑的辅助动作,单开 AI 权限点会造出"能配不能试"的半残态)。

- **错误码**:模板域取 `1_003_006_XXX` 段(1_003_000~005 已由实验室/竞赛/待审/文件/审核/成果库占完);沿用批4 文件域既有错误码(类型不允许/超限/魔术字节不符/路径非法)。

- **API 契约风格**:沿批3-6 既有风格(`/admin-api/business/templates` + `CommonResult`,`@PreAuthorize("@ss.hasPermission(...)")` + `security:ss`);分页用芋道 `PageParam`/`PageResult`。JSON 字段出入参为**结构化对象**(关键词为字符串数组),不再套 JSON 字符串——这是对 v2 前端/后端契约错位的修正。

- **审计与操作人**:芋道 token 认证下 `getAuthentication().getName()` 返回 token 字符串本身,操作人信息一律按登录用户 id 查用户表取(批2 起的纪律);创建/更新/删除的 `creator`/`updater` 由芋道 `BaseDO` 自动填充。

## Testing Decisions

- **原则**:只测外部可观察行为(端点 HTTP 契约、数据库终态、文件系统的实际存在与否),不测实现细节;断言前自问"是否因默认值而巧合通过",关键用例用非默认输入;键名即契约(Map 型响应必须断言键名——Fix-G 批立的纪律)。

- **测试接缝**:最高层接缝 = HTTP 端点(MockMvc + 真实登录 token + 真实 MySQL `awardie_v3_test` + 真实 Redis 库 1),沿用批3-6 既有 8 个集成测试类的范式;纯函数层(唯一性判定、引用清单、文件删除幂等、JSON 规则字段序列化)下沉到 business 模块单测;gRPC 层用**不可达端口**与桩响应测双层判错与降级,**测试不得依赖真 Worker 在线**(CI 无 Worker)。

- **既有测试范式(prior art)**:集成测试类统一 `@SpringBootTest(classes = YudaoServerApplication.class, properties = {...})` 注入测试库 URL/用户名与 `spring.data.redis.database=1`(权限缓存键不含库标识,与 dev 服务隔离);登录走 `/admin-api/system/auth/login` 真实换 token;请求带 `tenant-id: 1` 头;用户与角色绑定只用 `assignUserRole`,**禁止 `assignRoleMenu`**(全量替换语义会抹掉其他测试依赖的授权);角色菜单归属由 SQL 负责,测试只断言权限点存在;前后清理业务表(文件测试额外清 `target/test-files/...`);无 `@Sql`、无测试 resources——schema 与菜单由外部 SQL 初始化链提供。

- **模块覆盖与用例**:
  - 模板域集成测试(≥12 例):分页列表 + 竞赛过滤 + 角色过滤双向命中;创建成功(含样本图落盘与 `tenant_id` 落库断言);重复创建被拒;非法角色 / 非法 JSON / 不存在竞赛 / 空文件 / 魔术字节不符;详情键名契约;编辑白名单生效且非白名单键被忽略(用非默认值验证不巧合通过);编辑不存在;删除后列表不再出现且样本图文件消失;竞赛删除被模板引用拒绝(**首次实证批3 预留的引用保护**);样本图回显字节往返 + 文件失存 + 路径越界;教师与学生访问全端点 403。
  - AI 端点:fake 模式三端点桩契约(键名/字段);grpc 模式指向不可达端口 → 4003 且**快速返回**(不挂死);模板无样本图时试测的明确错误。
  - 审核流回归:现有 `ReviewFlowTest` 的 fake 建议用例必须在模式开关改名后仍绿(证明配置合并未破坏批5 行为);补一条"grpc 模式不可达 → 转人工审 + 免责声明仍在"的用例。
  - 文件域单测:`delete` 幂等(不存在不抛);`deleteIfUnreferenced` 在"有引用时保文件、无引用时删文件"两个方向都成立;引用清单覆盖六张表(逐表构造引用行验证至少抽查 pending/其他文件/模板三处,因为列名不同)。
  - 孤儿补偿:重复提交**不产生新文件**(用文件系统目录清单断言,而非只看 DB);落盘后入库失败 → 文件被回收,且与另一条记录同内容时**不误删**(构造"同 hash 两行"场景)。

- **静态门禁**:p3c 仅扫本批改动的 Java 文件,增量违例清零;SQL 脱敏检查沿用 CI 既有 job;与 v2 前端相关的门禁(lint/raw-controls/jdbc-audit/build)本批不涉及(v3 前端属批10)。

- **推前纪律**:任何"本地全绿"的批次,推之前先本地复刻 CI 建库流程(全新 `awardie_v3_test` + CI 同款六脚本顺序 `ruoyi-vue-pro.sql → quartz.sql → awardie-cleanup.sql → awardie-business.sql → awardie-business-menus.sql → awardie-user-domain.sql`,collation `utf8mb4_bin`)再跑全量——批4/批6 两次证明旧库会掩盖"缺角色/缺授权/tenant_id 落 0/表列缺失"。

## Out of Scope

- 模板接入运行时抽取匹配链(v2 也没有;Worker 侧 `template_rule_json` 当前不消费,固定走默认 award prompt)——挂账,等 Worker 扩规则化抽取。
- 模板名称、状态、导出、批量操作、模板版本管理、样本图替换等 v2 没有或未验证的能力。
- Worker 侧(Python)任何改动:requirements 缺 `grpcio` 声明、host/port 硬编码不可配、`Health` 语义弱——均为 Worker 资产问题,登记为部署前风险。
- v2 → v3 的 templates 数据 ETL 与样本图跨库搬迁(属批12 统一 ETL)。
- 前端页面实现(属批10);本批只保证端点契约可用 + swagger 可验。
- 批6 遗留的大创只建表(物化)与批5 的物化时机、成果表最小集、时间线可见性等既有挂账——本批不动,等批8 统一处置。

## Further Notes

- **proto 契约的两条硬事实**:一是 proto 的 `package awardie.ai` 不能改(改了 Python Worker 的完整方法路径就对不上,现存 Worker 是按这个契约实现的);二是 Java 侧的 `java_package` 可以改(纯 Java 包名,不影响 wire),所以本批用"复制 proto + 加 java_package 选项 + 重生成"而不是"直接搬 v2 生成物"。
- **Worker 可用性不能用 Health 判定**:它只检查 langgraph 能否 import,恒返回 ok;OCR/LLM 故障要到第一次业务调用才暴露。因此 fake 模式是开发与 CI 的默认姿态,grpc 模式是接入真 Worker 后的姿态。
- **历史坑位对本批的直接影响**:授权 SQL 必写 `tenant_id`(批6);测试与 dev 的 Redis 必须分库(批6);测试禁改共享角色授权(批6);MySQL 8 无 `ADD COLUMN IF NOT EXISTS`,幂等靠 SQL runner 容忍"已存在"错误码(批6);SQL 注释里不能放分号(runner 按分号切语句);JSON 列不要手工拼 `?::jsonb`(那是 PG 语法,v3 走 MySQL)。
- **风险登记**:grpc-java 与芋道自带 Netty 之间的传递依赖冲突是引入 gRPC 的首要风险,故用 `grpc-netty-shaded` 隔离;protobuf-java 版本若被 Spring Boot BOM 托管,需在 `yudao-dependencies` 显式声明版本以保证生成物与运行期一致。
