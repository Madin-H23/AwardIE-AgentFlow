## Parent

#1

## What to build

迁移管线从探针固化为可重跑工具:一条命令从 `database/competitions.db` 副本重建 v2 库——产出 Flyway `V1__baseline.sql`(30 表 PG 方言 DDL,schema 进版本控制)+ 数据装载 + 数据清洗 + 校验报告。管线顺序按探针 P2 已验证八步;schema 后续演进一律走 Flyway V2+。

## Acceptance criteria

- [ ] 一条命令幂等重建(drop/create schema→migrate→ETL→校验)
- [ ] 清洗执行:混型列 `'admin'`→NULL;JSON 列逐列试转 jsonb(`awards.llm_response` 非法行修复);`created_at`/`updated_at` 升 timestamptz;`awards.date`/`competition_time`/`start_date` 保留 TEXT
- [ ] 生成列 `pending_achievements.is_valid` 按探针已验证表达式建立(STORED),`idx_pending_is_valid` 补建
- [ ] 序列以 sqlite_sequence 为准恢复(空表 setval(1,false));BOOLEAN 默认值与数据双面改写
- [ ] 校验报告:30 表行数一致、BLOB md5 一致、FK 21/21 通过
- [ ] `V1__baseline.sql` 入库;三个 legacy 视图(students/teachers/admins)不迁移(决策记录)

## Blocked by

-  #2
