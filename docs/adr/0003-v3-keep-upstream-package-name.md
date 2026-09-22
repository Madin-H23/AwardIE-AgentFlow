---
status: accepted
date: 2026-09-22
---

# v3 底座:内部 Java 包名暂留 cn.iocoder.yudao,只改坐标/品牌/库名

v3 以芋道 ruoyi-vue-pro(master-jdk17)为底座,基线 8657 文件已入库 awardie-v3/。问题:内部包名是否改为 com.awardie 体系?

决策:**暂留 cn.iocoder.yudao**。改造只碰三层外显:Maven groupId(cn.iocoder.boot→com.awardie)、应用名/品牌标识、数据库名(ruoyi-vue-pro→awardie_v3)。内部包路径、目录结构、上游 module 命名保持原样。

## Considered Options

- **暂留上游包名(选定)**:8657 文件的机械改名会让每次上游合并都产生包名冲突,芋道 fork 的常规做法;稳定期(数据迁移切流后)可评估 expand-contract 式改名,彼时有完整测试网可接;
- **现在全量改名**:对外展示最干净(与 v2 的 com.awardie 一致),但一次触碰全部源文件,且与上游的 diff 面永久扩大,13 个业务批次全程背着合并冲突;
- **expand-contract 渐进改名**:新包名与旧形式并存、按 blast radius 分批迁移,CI 每批保持绿。最稳健但把成本摊到最多批次,当前阶段不值得。

## Consequences

- 代码里出现 cn.iocoder.yudao 是有意的,不是漏改;新业务模块同样遵循(yudao-module-business ↔ cn.iocoder.yudao.module.business);
- 上游基线升级流程(重新 archive→脱敏→清理)不受包名干扰,三步保持简单;
- 若未来答辩/交付要求包名品牌化,按 expand-contract 单独立项,不在 13 批路线内。
