# 02 — API 层补齐

**What to build:** 补齐 `src/api/business/**` 剩余端点:学生端(我的提交分页/时间线/下载/提交)、模板 AI 三端点(试测/创建前抽取/生成 prompt)、大创导入(preview/confirm)与校准、实验室/竞赛详情。**每条路径必须与后端 Controller 逐条核对**——已踩过两次凭记忆写错的坑(待审成果无 get 端点、模板创建是 /create)。下载统一走 `request.download()`(会读错误响应,v2 裸 `<a>` 不会)。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] 所有路径与后端 Controller 逐条核对一致
- [ ] 三个文件(`basic/achievement/index.ts`)路径无偏差
- [ ] 下载用 `request.download()` 而非裸 `<a>`
- [ ] ts:check 绿
