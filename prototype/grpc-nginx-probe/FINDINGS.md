# 探针 P1 报告:gRPC server-streaming 经 Nginx 透传

**日期**: 2026-08-29 | **状态**: ✅ 完成 | **关联风险**: R-045(由"未知"降为"已量化,含解法")

## 环境

- nginx 1.28.0 Windows 免安装版:`D:\Develop\tools\nginx-win\nginx-1.28.0`(conf 已替换为本探针配置)
- 探针:`prototype/grpc-nginx-probe/` —— `streamer.proto`(StreamDeltas 快流 / StreamSlow 慢流)+ `server.py`(50051)+ `client.py`(测 delta 到达间隔)
- 端口:50051 直连 / 50052 nginx 默认配置 / 50053 nginx 调优配置(`grpc_read_timeout 3600s + grpc_send_timeout 3600s + grpc_socket_keepalive on`)
- 复跑:`server.py 50051` → `nginx.exe`(在 nginx 目录)→ `client.py <target> deltas|slow <count> <interval_ms>`;停止:`client` 自退、`nginx -s stop`
- **口径偏差**:handoff 原定"Java gRPC client",实际用 Python client(grpcio 1.83.1)。理由:透传行为发生在 HTTP/2 与 Nginx 配置层,与 client 语言实现无关;Java/netty 侧差异留 P0 骨架首次联调确认(风险低)。JDK 本机为 1.8,亦不足以代表 v2 的 Java 21 目标栈。

## 结果矩阵

| 场景 | 路径 | 条件 | 结果 |
| --- | --- | --- | --- |
| A 基线 | 直连 50051 | 快流 20 delta / 200ms | ✓ 20/20,间隔中位数 203ms |
| B 默认 | nginx 50052 | 快流同上 | ✓ 20/20,203ms —— **默认配置无缓冲** |
| C 调优 | nginx 50053 | 快流同上 | ✓ 20/20,203ms |
| D1 断流 | nginx 默认 50052 | 慢流 idle 65s > 60s | ✗ **1/2 后流被切**:`RST_STREAM (error code 2)`,即 60s `grpc_read_timeout` 到期 |
| D2 解法 | nginx 调优 50053 | 慢流同上 | ✓ 2/2,idle 65s 完整通过 |
| E 对照 | 直连 50051 | 慢流同上 | ✓ 2/2,server 自身无超时切断 |

## 结论(P0 部署 spec 硬性条目)

1. **缓冲担忧排除**:nginx `grpc_pass` 默认逐条透传 server-streaming delta,快流间隔曲线与直连完全一致,无需额外关闭缓冲的配置。
2. **断流风险确认+解法**:默认 `grpc_read_timeout 60s` 会在"两次读操作间隔 >60s"时 RST 流。v2 的 AI 审核/问答链路中,LLM 长推理可能产生 >60s 的无输出间隙——**v2 生产 nginx 必须显式配置**:`grpc_read_timeout ≥ 300s`(按 LLM 最长推理时间定,建议留 5 倍裕度)+ `grpc_send_timeout 3600s` + `grpc_socket_keepalive on`。
3. 该配置已随探针 `nginx.conf` 固化,P0 的 Nginx 双 upstream 配置可直接抄。
4. `RST_STREAM code 2` 在 client 侧表现为 `INTERNAL: Stream removed`——P0 的 Java client 错误处理要把这个映射为"重试/降级"而非"AI 不可用"。

## 教训

- nginx Windows 版解压即用(2.1MB zip),conf 覆盖到 `conf/nginx.conf` 最省事;`listen 50052; http2 on;` 是 1.25.1+ 新语法(旧写法 `listen 50052 http2` 已弃用)。
- Python 探针 venv 装 `grpcio`+`grpcio-tools`(清华镜像),`grpc_tools.protoc -I. --python_out=. --grpc_python_out=. streamer.proto` 生成 stub。
