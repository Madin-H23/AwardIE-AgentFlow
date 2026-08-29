## Parent

#1

## What to build

Java 侧骨架立起来(prefactor 层,尚无业务表):Spring Boot 3.3 + Java 21 单模块工程,连本地免安装 PG 16.9(127.0.0.1:5433,探针同款),Flyway 可执行迁移,统一响应包装与全局异常处理就位。借鉴 it-ops-service 四件:CommonResult(ApiResponse 5 字段)、GlobalExceptionHandler、TraceIdFilter、自动填充。

## Acceptance criteria

- [ ] JDK 21 免安装版就位(本机现仅 JDK 8),构建/运行用 Java 21,README 记录工具链来源与启动命令
- [ ] `/actuator/health` 返回 UP,数据源指向 5433 本地 PG
- [ ] Flyway migrate 空跑成功(flyway_schema_history 生成)
- [ ] 任意未知路径/异常返回 CommonResult 统一结构(含 trace_id)
- [ ] JUnit 冒烟(health 断言)本地通过;Maven 构建通过

## Blocked by

None — can start immediately
