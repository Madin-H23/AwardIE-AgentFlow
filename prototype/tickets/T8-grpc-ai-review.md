## Parent

#1

## What to build

Java gRPC client 接线 + 教师审核侧 AI 建议展示:service 层注入可切换的 gRPC stub(fake/真实 worker),教师待审列表展示,AI 建议流式渲染(打字机);Nginx grpc 超时硬条目落地(探针 P1 结论)。BR-2 语义:UI 明示 AI 仅辅助。

## Acceptance criteria

- [ ] 教师角色可见待审列表(来自 T5/T6 提交的数据)
- [ ] AI 建议流式渲染(经真实 worker 一次走通;开发态可切 fake)
- [ ] fake stub 单测覆盖 service 层(成功/流式中断/降级三态)
- [ ] nginx 配置含 `grpc_read_timeout ≥300s` + `grpc_send_timeout 3600s` + `grpc_socket_keepalive on` 并经慢流场景验证(idle >60s 不断)
- [ ] client 对 `INTERNAL: Stream removed` 映射为重试/降级而非报错抛给用户
- [ ] AI 不可用时降级为"OCR-only"或"无建议可人工审"(4003 语义)

## Blocked by

-  #6、 #4
