## Parent

#1

## What to build

Nginx 路径分流共存(ADR-0002 落地):统一入口下 v2 前端静态资源 + `/api/v2/*`→ Java(8080),其余路径→ v1 Flask(5001);长尾域(看板/实验室/门户)业务不中断。配置含探针 P1 的 grpc 超时硬条目。

## Acceptance criteria

- [ ] 同一端口访问:纵切面走 v2,看板/实验室/门户走 v1
- [ ] v1 核心路由抽 10 条回归冒烟通过(分流后行为不变)
- [ ] 跨域会话口径与 ADR-0002 一致(接受重新登录,无共享会话魔法)
- [ ] nginx 配置入库(含 grpc_read_timeout ≥300s / send_timeout / keepalive)
- [ ] 分流开关注释完整,切回 v1 全量只改 upstream 一处

## Blocked by

-  #6
