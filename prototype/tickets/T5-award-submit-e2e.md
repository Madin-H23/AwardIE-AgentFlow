## Parent

#1

## What to build

成果提交端到端——只做奖状(award)一类打穿:学生登录后 Vue 表单填写 + 文件上传(白名单/大小/魔术字节三校验)→ API → PG 入库,下载一律 attachment(BR-7)。表单字段与校验规则与 v1 等价;文件落 v2 独立目录,路径记 PG。窄路径原则:其余四类由后续 ticket 泛化。

## Acceptance criteria

- [ ] 学生提交奖状成功,pending/成果表记录与 v1 字段等价
- [ ] 三校验:超限、非法类型、伪装扩展名均被拒(错误走 CommonResult)
- [ ] 文件下载响应 attachment(BR-7)
- [ ] 提交后列表可见自己提交的记录
- [ ] JUnit 提交/上传/下载/校验拒绝 ~10 例

## Blocked by

-  #6
