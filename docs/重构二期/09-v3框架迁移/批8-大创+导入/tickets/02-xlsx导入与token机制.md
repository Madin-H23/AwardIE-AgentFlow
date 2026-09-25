# 02 — xlsx 导入 preview/confirm + preview token 机制

**What to build:** 交付 `POST /business/innovation/import/preview`(multipart)与 `POST /business/innovation/import/confirm`。preview 解析固定十列(项目编号|项目名称|项目类型|起始日期|结束日期|负责人姓名|负责人学号|其他成员|指导教师|经费)、只读第一个 sheet、首行表头**且校验表头文字**、行数上限 1000;逐行校验(项目名称必填、项目类型白名单国家级/省级/院级、经费必须可解析为数字且非法即行错误不静默置 null)。preview 把行数据存服务端缓存并返回随机 token + 行摘要;**confirm 请求体只接受 token,行数据一律从服务端缓存取**——修 v2"伪 sha256 校验 + 信任客户端 rows"的缺陷;token 消费即失效(重复 confirm 报明确错误),缓存设过期时间与容量上限。confirm 整体一个事务,结构性失败整批回滚,行级业务错误按 v2 语义跳过并计入 `skipped` + `errors[]`。返回 `imported/skipped/errors[]`。留痕用芋道 `@OperateLog` 承载操作人与结果摘要。默认 `status='进行中'`、`submitter_type='admin'`、`project_type` 空时默认院级(沿 v2)。用现有 `yudao-spring-boot-starter-excel`(FastExcel),不引 Apache POI。

**Blocked by:** 01(领域模型)

**Status:** ready-for-agent

- [ ] preview 正常路径返回 token + 逐行校验结果
- [ ] confirm 传伪造 rows **无效**(库中只有服务端缓存内容)
- [ ] token 重复使用被拒;过期/超限 token 报"预览已失效"
- [ ] 超 1000 行被拒;坏表头被拒;缺列按空串
- [ ] 非法项目类型/非法日期/非法经费为行级错误
- [ ] 重复编号跳过且计入 skipped
- [ ] 中途结构性失败整批回滚(无半截数据)
- [ ] 写入留痕含操作人与 imported/skipped 摘要
