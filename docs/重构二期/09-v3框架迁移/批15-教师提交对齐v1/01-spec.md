# 批15 01-spec:教师提交成果对齐 v1

## Problem

用户实测:v3 只有学生能提交成果。v1 的教师有完整提交能力
(`/teacher/achievement-submit`:上传 + 表单 + 提交记录),v3 教师工作台只有
「待审成果」「我的指导成果」两个菜单,没有任何提交入口。

## 现状核查(实测)

- **后端已就绪,零改动**:`POST /business/pending-achievements/submit` 只挂
  `business:pending-achievement:create`,教师角色已授权;
  `SubmitterTypeResolver` 对教师返回 `teacher`;
  既有测试 `teacherSubmissionUsesTeacherType` 断言 `submitter_type='teacher'` 通过。
- **缺口纯在前端**:无教师提交页、无菜单。

## Solution

1. **抽取共享表单组件** `business/components/PendingSubmitForm.vue`
   (自学生门户 submit 页抽出,258 行;含五类动态字段/必填拦截/上传区)。
   组件只负责「填表 → 提交 → emit('submitted')」,提交后的导航由宿主页决定
   ——学生跳「我的提交」,教师留在本页刷记录,两种语义不写死在组件里。
2. **学生门户页变薄壳**(行为不变,提交后仍跳 `/portal/submissions`)。
3. **新增教师页** `business/teacher/submit/index.vue`:共享表单 +
   「我的提交(最近 10 条)」概览表(对齐 v1 `submissions.html` 的形态:
   最近 10 条作概览 + 累计计数;完整分页/撤回/进度已有教师待审台与门户承载)。
4. **菜单 3103** 写入 `awardie-business-menus.sql`(3100 段,sort=3 追加) +
   `awardie-user-domain.sql` 授权集(100/101)+ 生产库直接执行。

## 关键决策

- **追加 sort=3 而非插到第一位**:不打乱教师现有菜单顺序;要调整可在菜单管理里拖。
- **记录概览只放最近 10 条**:与 v1 一致;撤回/时间线/分页不在此页重复建设
  (门户「我的提交」已有,教师待审台已有)。
- **v1 的异步进度轮不搬**:v3 的提交模型是同步落库(v1 的 OCR/LLM 异步提取在 v3
  由审核侧 AI 建议承接),「对齐」对齐的是能力面(教师可提交 + 有记录),不是逐像素复刻。

## Out of Scope

- **v1 admin 的批量导入向导**(file-import 系列,~2800 行)是另一个大功能,不属
  「教师提交」对齐范围;如需要单独立项。
- 教师提交后的**自我审核**治理问题(教师同时有 review 权限,可审自己的提交)——
  v1 同样存在此语义(assigned_reviewer 机制),维持现状,如需回避另立票。
