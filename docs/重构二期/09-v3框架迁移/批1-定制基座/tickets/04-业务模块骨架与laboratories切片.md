# 04 — 业务模块骨架 + laboratories 首个垂直切片

**What to build:** 新建 `awardie-v3/yudao-module-business`(groupId com.awardie,包 cn.iocoder.yudao.module.business,根 pom 启用),含芋道标准分层(controller/service/mapper/entity/vo/errorcode/convert)+菜单 SQL+模块错误码段。首个垂直切片 **laboratories 实验室域**,用芋道 codegen 生成 CRUD 骨架再定制:建表 `awardie_laboratories`(id/name/description/审计字段,迁移脚本我们维护,芋道不用 Flyway);API=分页列表(关键词模糊)+详情+新增+修改+删除(被业务表引用时拒绝,4009 同构芋道错误码);菜单导入后超管可见"实验室管理",权限点 award:laboratory:*。

**Blocked by:** 03(新模块必须用改后的 groupId,保证 reactor 一致)

**Status:** ready-for-agent

- [ ] 模块编译进 reactor;yudao-server 启动无 bean 冲突
- [ ] MockMvc+Bearer token 测试类(项目 v3 测试范式样板):分页/关键词/增/改/查/删/引用冲突拒绝/非 admin 403 全绿
- [ ] curl 或测试实证:登录→建实验室→列表可见→改名→删除成功
- [ ] codegen 生成物与手写定制的边界记录(哪些文件生成、定制在哪层)入 02-实施.md
- [ ] 测试只在 awardie_v3_test 库跑,不污染 dev 库
