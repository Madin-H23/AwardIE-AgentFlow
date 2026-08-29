## Parent

#1

## What to build

AI Worker gRPC 化(Python 侧独立推进,与 Java 完全并行):ai_service.proto 契约定稿并冻结(extract/review/qa;review、qa 为 server-streaming),Python gRPC server 壳包住 v1 LangGraph 编排(N1:算法不重写,仅接口层),入参传数据、Worker 无状态。

## Acceptance criteria

- [ ] ai_service.proto 冻结入库(extract/review/qa 三方法,流式口径与探针 P1 一致)
- [ ] Python gRPC server 可启动,健康检查可见
- [ ] review 用真实样例证书走通 OCR+LLM 链路,流式返回审核建议(沿 v1 LLM 配置)
- [ ] 直连冒烟脚本(python client)通过;BR-2 语义:输出含"仅辅助参考"标注字段
- [ ] Worker 不可用时熔断降级语义在 proto 错误码中可表达(4003 沿 v1)

## Blocked by

None — can start immediately
