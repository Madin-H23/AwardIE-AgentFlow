# 批9-统计导出日志 Spec(01-spec)

> 2026-09-25 | 依据 `00-需求.md`(R1-R5,事实含 v2/v3 双向取证)

## Problem Statement

批1-8 把 v3 的数据链建起来了,数据在那里躺着没人看。管理员想知道"我们有多少成果、在哪些竞赛、趋势如何",以及"某个学生得了什么、某一年各竞赛的战果如何",还要能把这些导出来发给院里。v2 有这三块功能,v3 一行都没有。

但开干前取证发现,原定范围有三分之一做不了:v2 的年份分析靠 `awards.year`、实验室分析靠 `laboratory_id`、教师维度靠两张关系表和 `granted_role` 字段,而 v3 这三样都没有。硬做只会交付一堆空图表——页面能打开,数字全是 0。

同时 v2 这批功能自身有一批实打实的 bug:学工导出的"学号"列其实是内部数字 ID、教师导出口径与同页 dashboard 不一致、dashboard 的周期筛选其实只影响趋势图、SSE 实时流的续传参数根本不起作用。照抄等于把 bug 搬进 v3。

所以批9 的目标收窄为:**把数据链完整的部分做扎实,把数据链断了的部分明确记为前置债**,不做会交付空数据的端点,也不抄 v2 的缺陷。

## User Stories

1. As a 管理员, I want 分页查看全部成果审核留痕, so that 我能追溯任意一个成果经历过什么。
2. As a 管理员, I want 按成果类型筛选留痕, so that 我能只看某一类成果的处理过程。
3. As a 管理员, I want 按动作码筛选留痕, so that 我能只看提交/通过/驳回/入库中的某一类。
4. As a 管理员, I want 按操作人关键词筛选, so that 我能查某个人的操作记录。
5. As a 管理员, I want 按日期区间筛选, so that 我能导出某段时间的记录。
6. As a 管理员, I want 留痕的动作显示中文标签而不是数字码, so that 我不用背 1/6/7/8 的含义。
7. As a 管理员, I want 看不到其他租户的留痕, so that 多租户之间不互相可见。
8. As a 管理员, I want 看到成果总数/待审数/用户数/竞赛数/白名单竞赛数, so that 我对系统整体规模有概念。
9. As a 管理员, I want 看到五类成果各自的计数, so that 我知道哪类成果多哪类少。
10. As a 管理员, I want 看到竞赛战果 Top, so that 我知道哪些竞赛产出最多。
11. As a 管理员, I want 没有关联竞赛的成果也出现在 Top 里(归入"未关联"), so that 我不会漏掉无主成果。
12. As a 管理员, I want 同数目的竞赛每次看到一样的排序, so that 截图和汇报不会因为随机顺序而反复变。
13. As a 管理员, I want 导出"竞赛 × 年份 × 获奖等级"汇总, so that 我能直接做年度统计表。
14. As a 管理员, I want 汇总导出支持 CSV 和 Excel 两种格式, so that 我能给不同收件人不同格式。
15. As a 管理员, I want CSV 用 Excel 打开中文不乱码, so that 我不用手工改编码。
16. As a 管理员, I want CSV 里的内容不会被 Excel 当成公式执行, so that 恶意或意外的 `=cmd` 类内容不会伤害我的电脑。
17. As a 管理员, I want 导出"学生获奖明细", so that 学工可以拿到学生获奖台账。
18. As a 管理员, I want 学生获奖明细里的"学号"列是真的学号而不是系统内部编号, so that 学工不用二次加工就能用。
19. As a 管理员, I want 导出有明确的行数上限, so that 不会因为数据量暴涨把服务器拖垮。
20. As a 教师, I want 我无法访问统计与导出, so that 统计数据不会被非管理员改动或滥用。
21. As a 学生, I want 我无法访问统计与导出, so that 其他人的数据对我不可见。
22. As a 运维, I want 统计与日志查询走索引而不是全表扫描, so that 数据量增长后响应时间不失控。

## Implementation Decisions

- **命名与边界**:本批交付"业务审计日志查询 + 基础统计 + 两类导出"三块。年份/实验室/教师维度因数据链断裂(见 00-需求 F1/F2/F3)明确不做,记为前置债。

- **审计日志端点**:`GET /business/logs/audit`,分页 + 四种筛选(成果类型 / 动作码 / 操作人关键词 / 日期区间)。复用现有 `awardie_achievement_audit_log` 与 `AchievementAuditLogMapper`,**不新建表**——v3 审核流已在写 action 1/6/7/8,数据链完整,缺的只是查询面。响应字段:id / achievementId / achievementKind / actionType / actionLabel / actionResult / operatorCode / operatorName / remark / createTime。动作码字典只含 1 提交 / 6 审核通过 / 7 驳回 / 8 物化入库(v2 前端也只有这四个;历史 2-5/9-12 在 v2 Java 里从未产出,不迁)。

- **审计索引**:给 `awardie_achievement_audit_log` 加 `achievement_id` 与 `create_time` 索引——现有按 `achievement_id` 查时间线的路径(批5 时间线端点已在用)就是全表扫,批9 的全量分页会放大这个问题。

- **统计端点**:`GET /business/stats/overview` 返回 `summary`(awardsTotal / pendingSubmit / usersTotal / competitionsTotal / whitelist)+ `category`(award / patent / software / innovation / other);`GET /business/stats/by-competition` 返回 Top12。全部 SQL **显式 `deleted = b'0' AND tenant_id = ?`**——JdbcTemplate 不经 MyBatis-Plus 租户拦截器(批8 已实证并修过同款问题),这是硬要求不是风格问题。计数用 `Long` 而非 v2 的 `Integer`(大表溢出)。

- **竞赛 Top 的两个修正**:`LEFT JOIN competitions` + `COALESCE(competition_name, '未关联')` 保留无主成果(v2 已如此,保留);**加 `name ASC` 二级排序**——v2 只有 `ORDER BY total DESC LIMIT 12`,同数时行序随机,截图与对账会漂。这是修 v2 缺陷,不是发明语义。

- **不做的统计维度**:年份趋势(靠 `awards.year`,v3 物化不写该列;且趋势图属前端批10)、实验室维度(同 F2)、教师证书拆分(靠 `granted_role`,v3 awards 表无此列)。这三项在 00-需求 F1/F2/F3 已列为前置债。

- **导出(两类)**:
  - `GET /business/export/competition-summary(.csv|.xlsx)`:竞赛 × 年份 × 获奖等级汇总。竞赛关联在 v3 是完整的(`awardie_awards.competition_id` 有值),故可做;
  - `GET /business/export/student-affairs(.csv|.xlsx)`:学生获奖明细,走 `awardie_award_student_winners` join `system_users`。**"学号"列取 `system_users.username`**——v3 的 username 就是学号(批2 ETL 把 v2 `login_code` 映射过来,实测 1792 个纯数字账号),这修掉了 v2 选 `users.id` 导致"学号列是内部数字 ID"的 bug。

- **CSV 三项修正**:
  1. **不用 `row.values()` 顺序假设**——v2 导出依赖 JDBC Map 的迭代顺序对应 SELECT 列序,无列名映射,换驱动或加别名就错列。v3 走显式 DTO;
  2. **防公式注入**——单元格以 `=` / `+` / `-` / `@` 开头时前置单引号转义(v2 只做 RFC 引号转义,这类内容会被 Excel 当公式执行);
  3. **行数上限**——两类默认上限 10000(可配),超出报错而非静默截断。v2 只有年度明细 `LIMIT 500`,其余无上限。

- **XLSX**:用已有 `yudao-spring-boot-starter-excel`(FastExcel)写单 sheet,不复刻 v2 的 Apache POI 内存双 sheet;`@ApiAccessLog(operateType = EXPORT)` 标注导出动作。CSV 保留 UTF-8 BOM(v2 已有,Excel 打开中文不乱码的前提)。

- **权限与菜单**:菜单 3007 统计分析 / 3008 数据导出 / 3009 业务日志;权限点 `business:stats:query` / `business:export:query` / `business:logs:query`(按批7-8 的 ID 规律取 3071-3073)。全部 admin 专属,`system_role_menu` INSERT 必写 `tenant_id=1`。三角色 403 由集成测试锁。

- **错误码**:本批取 `1_003_009_XXX` 段(1_003_000~008 已占完)。

- **不做 SSE 实时流**:v2 那版有六处实缺陷(`afterId` 入参被当前 MAX(id) 覆盖导致无法续传、暂停期间丢消息且不补发、无心跳、无自动重连、每连接一线程无并发上限、手拼 JSON 用单引号替换双引号会篡改内容)。重做需设计游标 + 心跳 + 重连 + 限流,应单独排,不在本批。

- **不聚合芋道 infra/system 日志**:v3 的 `infra_api_access_log` / `system_operate_log` 与 v2 的 `system_event_log` 不是对位关系(前者是框架层访问/操作日志,后者是业务事件分类日志)。v3 无 `system_event_log` 对位表,硬凑四套日志的聚合视图会让语义混淆。需要时按"日志中心"单独排。

## Testing Decisions

- **原则**:只测外部可观察行为(端点契约、数据库终态、文件字节内容),不测实现细节;断言前自问"是否因默认值巧合通过"。

- **测试水平的一个硬要求**:**用固定数据夹具逐条锁 SQL 数值口径**。v2 的 `AdminStatsTest` 只验响应结构不验聚合数值(取证确认:无固定 awards/年份/教师/innovation 夹具),这种水平不能继承——v3 的测试必须种入已知数据后断言确切数字(如"种 3 条 awards 2 条 patent,category.award 必须等于 3")。

- **审计查询集成测试**:分页(总数/页内容/越界页)、按类型筛、按动作码筛、按操作人关键词筛、日期区间边界(含当天)、空表返回空、动作码中文标签、租户隔离(种 tenant 2 的行,tenant 1 查不到)。

- **统计集成测试**:summary 五项与 category 五项的确切数值(固定夹具)、竞赛 Top12 的排序正确性(**含构造同数值的两条竞赛,断言 name 升序**)、"未关联"桶存在、租户隔离、空表全零。

- **导出集成测试**:两类 × CSV/XLSX;CSV 断言**字节级**内容(BOM 存在、表头精确、列序正确、行序正确、学号列是 username 而非数字 id、含逗号/引号/换行的字段被正确转义、公式前缀被转义);XLSX 断言 magic + 行数;行数上限触发;空结果导出只有表头;越权 403。

- **纯单测**:CSV 单元格转义(逗号/引号/换行/CRLF/公式前缀四类/空值/null)、动作码字典映射(含未知码兜底)。

- **测试纪律(沿批7/批8)**:清理用**物理 DELETE**(逻辑删除残留会让"取第一条"拿到历史行);只改用户→角色绑定(禁用 `assignRoleMenu`);本地复跑前先 `redis-cli -n 1 FLUSHDB`。

- **静态门禁**:p3c 仅扫本批改动 Java 文件;推前本地复刻 CI 建库后跑全量(批4/6/7/8 四次证明有效)。

## Out of Scope

- 年份 / 实验室 / 教师维度的统计与分析(数据链断裂,前置债)
- 教师个人导出(缺教师关系表,前置债)
- 学生个人门户导出(属批10 学生端)
- SSE 实时流(六处 v2 缺陷,需重新设计)
- 芋道 infra/system 日志的聚合视图
- 导出图片 ZIP(v2 也未实现)
- 物化补 `year`/`laboratory_id`、教师关系表(审核流行为变更,需单独批)
- 前端页面(属批10)

## Further Notes

- **本批最容易做错的地方是"照抄 v2 端点"**:v2 的分析 SQL 依赖 PostgreSQL 的 `date_trunc`/`to_char`/`interval` 与主键函数依赖,MySQL 下 `date_trunc` 不存在、`GROUP BY c.id` 在 `ONLY_FULL_GROUP_BY` 下直接报错。本批虽不做时间聚合,但所有新 SQL 必须按 MySQL 方言写,且显式 GROUP BY 全部非聚合列。
- **数据链断裂是系统性的**:F1/F2/F3 三个硬阻塞同源——v2 的很多维度依赖"审核物化时写入关系行与派生字段",而 v3 的物化只写核心文本字段。这不是本批能补的(属审核流行为变更),但它决定了批9 只能交付三分之一的范围。已明确记为前置债,批10 之前必须解决,否则统计维度永远是空的。
- **审计表字段够用但不完整**:v3 审计表无 `trace_id` / `operator_role` / `operator_ip`,故本批日志查询**不能**按 trace 搜。若要 trace 关联,需给表加列并在写入层透传(芋道 trace 走 MDC),属另一件事,本批不做。
