# 探针 P2 报告:SQLite → PG Python ETL 实跑

**日期**: 2026-08-29 | **状态**: ✅ 完成 | **关联风险**: R-046(由"未知"降为"已量化")

## 环境

- PG 16.9 免安装版:`D:\Develop\tools\pg16-portable`,实例 `127.0.0.1:5433/awardie_probe`(trust 仅限本机 throwaway 探针,勿用于真实数据);启停:`pg16/pgsql/bin/pg_ctl -D pgdata -o "-p 5433" -l pgdata.log start|stop`
- 源库:`database/competitions.db` **副本**(md5 `7936a8cf`,原库零接触)
- 脚本:`etl_sqlite_to_pg.py`(幂等,每次 DROP SCHEMA 重建),`./.venv/Scripts/python etl_sqlite_to_pg.py work/competitions_copy.db "host=127.0.0.1 port=5433 dbname=awardie_probe user=postgres"`
- 盘点:30 表 / 9353 行 / 44 索引 / 21 FK / 18 序列 / 3 视图 / 1 生成列 / 1 BLOB

## 结果:全量迁移成功

行数 30 表全部一致(9353 行)、BLOB md5 回环一致(`b97acf7bd851`)、FK 21/21 建立并通过存量校验、18 序列全部恢复且下一 id 语义正确。

## 真实坑位(P0 spec 必须处理)

1. **混型列(SQLite 宽松类型遗留,最隐蔽)**:`achievement_audit_log.operator_id`、`review_logs.reviewer_id` 声明 INTEGER 却存有 `'admin'` 文本——PG 严格类型直接拒绝。处置:迁移管线必须预扫描 `typeof` 分布;推荐数据清洗(`'admin'`→NULL)而非列降级 TEXT。
2. **JSON 列不能盲转 jsonb**:`awards.llm_response` 有 1/79 行非法 JSON;其余 14 个 JSON 列(`achievement_data`/`validation_result`/`sample_extracted`/`default_fields`/`llm_fields`/`keywords`/`system_event_log.detail`/`evidence` 等)全部合法。处置:逐列 `::jsonb` 试转 + 失败行清单修复,不可一刀切。
3. **日期语义混乱,不能按列名批量升 timestamptz**:`awards.date`(`'2022-05'`)、`competitions.competition_time`(`'10-4月'`、`''`)、`innovation_projects.start_date`(`'2023.5.1'`)列名像日期实为业务文本;而真正的 `created_at`/`updated_at` 类列值全部是合法 ISO 文本,可安全升 timestamptz。映射必须逐列人工确认,启发式不可靠。
4. **生成列翻译(已验证解法)**:`pending_achievements.is_valid = json_extract(validation_result,'$.is_valid')`,且 `is_valid` 值**混有 JSON 布尔与数字**——PG 侧 `->>'is_valid'` 后直接 `::integer` 会在 `false` 上炸。已验证等价表达式(按 `jsonb_typeof` 分支 boolean/number/string,45 行与 SQLite 引擎逐行一致);VIRTUAL→STORED 语义无损;依赖它的 `idx_pending_is_valid` 必须在建列后补建。
5. **序列恢复必须以 `sqlite_sequence` 为准,不能用 max(id)**:`pending_achievements` seq=4269 而实际仅 45 行(删除史);空表(seq=0)需 `setval(seq, 1, false)` 才能让下一 id=1。
6. **BOOLEAN 双面改写**:DDL 的 `DEFAULT 0/1` 与数据行的 `0/1` 都要转换(PG 无 int→bool 隐式转换);`idx_awards_abnormal` 的 partial index 谓词 `=1` 同理需改 `= TRUE`。

## 工具选型结论(回应方案 §8.2 pgloader)

- pgloader 是 Common Lisp 程序,原生不支持 Windows,本机 Docker 不可用即无路可走;但**探针证明 Python ETL 完全可行**,且它天然就是 ADR-0002 要求的"增量补迁脚本"的雏形——布尔改写/序列恢复/混型预扫描逻辑可直接固化进正式迁移管线。
- **建议正式管线顺序**:预扫描(混型列+JSON 审计)→ 建表(FK 后置、VIRTUAL 生成列剥离)→ 装载(布尔适配、BLOB→bytea)→ 索引(谓词布尔改写)→ FK → 序列(sqlite_sequence 为准)→ 生成列翻译补建 → 逐表行数 + BLOB md5 校验。
- 遗留 3 个视图 `students`/`teachers`/`admins` 是 users 三表合并的兼容 shim,v2(JPA 直查 users)可直接废弃。

## 探针工具自身的教训(非业务坑,仅供写正式脚本的人)

- psycopg2 的 `execute()` 返回 None,不可链式 `.fetchone()`
- sqlite3 同一 cursor 嵌套迭代会打断外层循环(预扫描曾因此漏报混型列)
- EDB binaries zip 必须全量解压(unzip 通配符不递归子目录),`share/` 不完整会导致 initdb 失败(`share/timezonesets`)
- SQLite 没有 `chr()`,是 `char()`;LIKE 模式里 `[%]` 是字面量不是字符类
