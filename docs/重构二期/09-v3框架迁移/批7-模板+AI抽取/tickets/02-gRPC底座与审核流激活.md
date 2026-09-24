# 02 — gRPC 底座 + AI 建议接真 Worker

**What to build:** 把 Python AI Worker 的 proto 引入 v3(复制契约并追加 `java_package`/`java_outer_classname` 选项,proto 的 `package awardie.ai` 不动以保 wire 兼容),用与 v2 同版本的 protoc 3.25.3 + grpc-java 插件 1.64.0 重新生成 stub(不复制 v2 那两个生成物文件:它们在顶层 `awardie.ai` 包、1.5 万行,不符合 v3 包规范);`yudao-dependencies` 补 grpc/protobuf 版本管理,business 模块用 `grpc-netty-shaded` 隔离芋道自带 Netty;建参数化、懒连接的 Worker 客户端(单 channel + blocking stub + `usePlaintext` + keepAlive,构造不发起连接,Worker 不在线不影响启动)。模式开关统一为单一 `awardie.ai.worker.mode`(fake/grpc,默认 fake),取代批5 的 `ai.review.mode`;审核流 AI 建议的 grpc 分支改为消费 `ExtractAndReview` 流并映射为既有 `Suggestion` 契约,清偿批5"stub 属批7"的硬编码降级挂账。**双层判错**:Worker 业务码在响应体 `code` 内(gRPC transport status 恒 OK),故先判 `resp.getCode()`,再捕获 `StatusRuntimeException` 映射 4003;两条路径都不得冒泡成 500。Worker 不可用时审核流自动转人工审,降级契约与批5 完全一致(含 AI 免责声明)。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] `mvn -q install -DskipTests` 通过;生成物落在 `cn.iocoder.yudao.module.business.framework.grpc.awardie.ai` 下
- [ ] 应用在 Worker 未启动时**正常启动**(懒连接),日志无连接异常堆栈
- [ ] fake 模式下 `ai-suggest` 行为与批5 逐字一致(pass/reject 判定、issuesJson、免责声明)——证明配置合并未破坏既有行为
- [ ] grpc 模式指向不可达端口 → 转人工审 + 4003 + 免责声明仍在,不抛 500、不挂死
- [ ] host/port/三个 deadline 全部可配置且有默认值(120/60/320)
- [ ] `ai.review.mode` 旧键不再被任何代码读取
