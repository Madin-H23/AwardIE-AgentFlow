# 批11-迁移切流 01-spec

## 一、方案

**停机窗口内的单向全量迁移**:停 v2 → 备份 → 目标库补 schema → 跑 ETL → 三层对账 →
起 v3 → 冒烟 → 开闸。任一步不过就回滚。

```
[停 v2] → [备份 v2 PG 全量] → [v3 补 schema] → [ETL 15 表]
                                              ↓
                              [对账:行数/id集合/内容哈希]
                                              ↓
                     [起 v3 → 三角色冒烟] → [闸门:用户拍板] → [切流量]
                                              ↓ (不过)
                                    [回滚:v2 恢复服务,数据未动过]
```

**为什么不做双写/灰度**:v2 是 Flask 单体 + 单库,双写要改 v2 写路径(而 v2 已进入
冻结期),灰度要改前端路由;校内单点系统在维护窗口内停 10 分钟可接受,双跑的复杂度
与收益不匹配。**代价**:切流窗口内系统不可用,且回滚粒度是整个窗口。

## 二、关键设计

### 1. 列映射必须是单一事实来源

首版把列名手写在两处(SELECT 一份、INSERT 一份),立刻踩坑:
写 `student_id_no` 而 PG 里叫 `student_id_str`;写 `sort_order` 而实际叫 `display_order`。
**同名写两遍必然漂移**。

改成 `MAPS` 一份定义同时生成 SELECT 与写入列,并用**转换器标记**处理类型:

```python
('submit_time', 'submit_time', 't')    # t=时间转本地 naive / b=布尔→BIT(1) / s=jsonb→字符串 / d=jsonb→dict
```

读源表时列名对不上会**当场抛 UndefinedColumn**,不会变成静默丢列——这是列映射驱动
最大的价值:错误发生在最便宜的时候。

### 2. 「已声明的例外」只写一处

v3 有 NOT NULL 而 v2 可空的列(`pending.submitter_type`、`templates.granted_role`),
必须补值。补值规则写在 ETL 的 `NOTNULL_FALLBACK` / `FILL` 里,**对账工具 import
同一个声明**再算哈希。

不各写一份:各写一份迟早漂移,漂移的表现是对账误报或漏报,都伤闸门的可信度。
补值行会被 `[known]` 段单独上报——**不藏**,处置权留给闸门前的决策者。

### 3. 对账分三层,第三层才是关键

| 层 | 抓什么 | 抓不到什么 |
|---|---|---|
| L1 行数 | 整体漏表 | 行数对但内容错 |
| L2 id 集合差 | 丢行(源有目标无) | id 在但字段写错 |
| **L3 关键字段内容哈希** | **行在、值不对**——列映射写反、jsonb 序列化错、时区偏移 | 选错关键字段时 |

L3 选字段的判据是「业务语义最重 + 映射最容易写错」,不是全字段——全字段会被框架列
(`creator`/`update_time`)和 JSON 键序差异打出假失败。

目标侧多出 v3 自有数据(测试行)时,整体哈希必然不同,此时**降级为按交集核验**并报
`[warn]`,不误判为失败。

**对账工具自己也可能有 bug**:`norm()` 原先用 `if v` 判 `BIT(1)`,而 `b'\x00'`
长度 1 是 truthy,会把 0 和 1 都算成 `'1'` → 218 行竞赛全报假警。已按字节真值修,
并补了单元自验(8 个输入)。**闸门工具自己错了比闸门没跑更危险。**

### 4. 演练库与真实库隔离,且有防呆

演练在 `awardie_v3_rehearsal` 上跑,给所有 v3 脚本加 `AWARDIE_TARGET_DB` 环境变量
(默认仍是 `awardie_v3`)。演练脚本在执行前**先探一次 ETL 实际指向哪个库**,不是演练库
就拒绝执行——首版就因为这层缺失,把 ETL 打到了真实库上。

## 三、数据处置决策(逐条带理由)

| 决策 | 处置 | 理由 |
|---|---|---|
| v2 测试残留(audit_log 1674 行 `is_test=true`) | **不迁** | v2 自己有 `is_test` 标记;迁进来 98.8% 是垃圾 |
| pending 5 行 `submitter_type` NULL(巡检赛/`inspect.png`/`inspect-<随机>` 哈希) | **补 `admin` 值迁入 + `[known]` 上报** | 是测试残留没错,但「像测试数据」不等于「用户确认可删」;补值不丢数,删不删交给闸门 |
| `templates.granted_role`(v2 无,v3 NOT NULL) | 统一补「学生」+ 上报 | 批7 建的模板域默认面向学生;这是默认值不是推断值,故显式声明 |
| pending 与 awards 的 151 条 `file_hash` 重叠 | **不去重** | 两张表两个语义(提交队列 vs 成果库),重叠是 v2 既有状态,保持一致才不篡改历史 |
| `created_at`/`updated_at` | 映射为 `create_time`/`update_time`,**用 v2 原值** | 不取 NOW(),否则历史时间线全变成今天 |
| v2 `users` / `old_user_map` | 不在本脚本处理 | 批2 的 `etl_v2_users_to_v3.py` 已迁 1834 用户 |

## 四、回滚方案

### 4.1 回滚触发条件(任一命中即回滚)

1. 对账三层任一层不过(L2 有丢行 / L3 内容不一致);
2. v3 起服后冒烟不过(三角色登录 / 九管理页 / 学生门户三场景);
3. v3 运行时 5xx 率显著高于 v2 基线。

### 4.2 回滚动作

```
1. 停 v3(48080)
2. 前端 dev/prod 切回 v2(5001 + 18080 + PG 5433)
3. v2 数据未被迁移改动过 —— 它是只读源,ETL 只读不写
   ⇒ 回滚不需要数据回滚,这是单向迁移最大的优势
4. 复验 v2 三角色可登录、可提交
```

**回滚的关键前提:v2 全程只读。** ETL 的连接是 `psycopg2.connect(...)` 且只发
`SELECT`,不写 PG。因此回滚 = 切流量回去,无数据损失。

若迁移过程中**目标库**被写坏(ETL 中途异常),重跑 ETL 即可(幂等 upsert),
或直接 `DROP` 重建后重跑——目标库是从 v2 派生的,没有独立价值。

### 4.3 不可逆点在哪

真正不可逆的只有一处:**v2 停机后若长期不回滚**,期间 v2 的写入会与 v3 分叉。
故切流窗口内:
- 切流前:v2 全量 dump 存档(回滚的最后保险);
- 切流后观察期(建议 ≥3 个工作日)内,v2 保持可启动但不接流量,
  期间**冻结业务写入**(由管理员口头约束),观察期结束再正式下线 v2。

## 五、验证

```bash
# 取口令
export AWARDIE_MYSQL_PASSWORD=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('AWARDIE_MYSQL_PASSWORD','User')")

# 1. schema 完整性(幂等,--check 只查不落)
python scripts/v3_apply_missing_columns.py --check

# 2. 列/表差异扫描(改过目标 schema 后必跑)
python scripts/v3_schema_diff.py

# 3. ETL(先 --dry-run 看清单)
python scripts/etl_v2_business_to_v3.py --dry-run
python scripts/etl_v2_business_to_v3.py

# 4. 对账(退出码 1 = 闸门不能开)
python scripts/v3_reconcile.py

# 5. 全新库演练(一次性库,不碰 awardie_v3)
python scripts/v3_cutover_rehearsal.py
```

## 六、Out of Scope

- 文件二进制迁移(存量证书图搬到 `files/v3/`)——单独立项;
- v2 正式下线与归档;
- 切流后的观察期运营(由用户安排)。
