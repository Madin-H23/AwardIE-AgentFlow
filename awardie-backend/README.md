# awardie-backend(v2 后端)

Java 21 + Spring Boot 3.3 + JPA + Flyway + PostgreSQL 16。P0 spec 见仓库 issue #1。

## 本地工具链

| 组件 | 版本/来源 | 说明 |
| --- | --- | --- |
| JDK | 21.0.7 LTS(Oracle),`C:\Program Files\Java\jdk-21` | **系统已装**,`JAVA_HOME` 已指向;注意 PATH 首位是 Oracle javapath 的 JDK 8 shim,`java -version` 显示 1.8 不代表无 21 |
| Maven | 3.8.8(已有),central 走阿里云镜像(`~/.m2/settings.xml`) | PATH |
| PostgreSQL 16.9 | EDB binaries zip | `D:\Develop\tools\pg16-portable`(实例 127.0.0.1:5433,trust 仅限本机开发) |

## 启动/测试

```bash
mvn spring-boot:run          # 启动,JAVA_HOME 已由系统指向 JDK 21,无需手动设置
mvn test                     # 冒烟(需本地 PG 运行且 awardie_dev 库存在)

# PG 实例启停
D:/Develop/tools/pg16-portable/pg16/pgsql/bin/pg_ctl -D D:/Develop/tools/pg16-portable/pgdata -l D:/Develop/tools/pg16-portable/pgdata.log -o "-p 5433" start
```

## 约定

- 统一响应 `ApiResponse{code,message,data,traceId,timestamp}`;成功 code=0;错误码沿 v1 体系(4003=AI 不可用等)
- trace_id:入站 `X-Trace-Id` 复用,否则生成;贯穿 MDC 日志/响应头/响应体
- schema 变更一律走 `src/main/resources/db/migration/`(V1 baseline 由迁移管线 ticket 产出)
