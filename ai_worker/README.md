# ai_worker(v2 AI Worker)

Python gRPC 进程:v1 LangGraph 编排 1:1 保留(N1 非目标,仅接口层 gRPC 化),供 Java 后端经 gRPC 调用。契约:`protos/ai_service.proto`。

## 启动(D:\venvs\awardie,与 v1 Flask 同环境)

```bash
# 编译 stub(改 proto 后重跑)
D:/venvs/awardie/Scripts/python -m grpc_tools.protoc -I ai_worker/protos \
  --python_out=ai_worker/protos --grpc_python_out=ai_worker/protos \
  ai_worker/protos/ai_service.proto

# 启动(默认 127.0.0.1:50060,独立进程;依赖 config/settings.json + .env 的 OCR/LLM 配置)
D:/venvs/awardie/Scripts/python ai_worker/server.py 50060

# 冒烟(Health/Extract/ExtractAndReview/Ask,真实样例+真实链路)
D:/venvs/awardie/Scripts/python ai_worker/client_smoke.py 50060 files/agent_upload/14094a2d_--.jpg
```

## 契约要点

| 方法 | 形态 | v1 映射 |
| --- | --- | --- |
| Extract | unary | `ToolContext().extract_framework.extract(file_path, ...)` |
| ExtractAndReview | server-streaming(node/delta/final 事件) | `MultiAgentWorkflow.run_stream(task_type="extract_and_review")` |
| Ask | server-streaming(delta 逐段) | `MultiAgentWorkflow.run_stream(task_type="qa")` |
| Health | unary | langgraph 可用性 |

- 错误码沿 v1:0 成功;**4003=AI 不可用(降级为 OCR-only/人工审)**;5xxx 内部
- BR-2:每个 final 事件带 `disclaimer`(AI 建议仅辅助参考)
- 无状态:入参传数据/文件路径,Worker 不读业务库;进程内 workflow 单例(构建成本高,双检锁)
- 流式口径:经 Nginx 需 `grpc_read_timeout ≥300s`(探针 P1 结论,见 prototype/grpc-nginx-probe/FINDINGS.md)
- Worker 无 Pydantic/Flask 依赖,纯 v1 环境即可运行;Java 侧集成在 T8
