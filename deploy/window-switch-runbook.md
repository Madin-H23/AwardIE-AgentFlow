# 窗口制切换 Runbook(ADR-0002 / T15)

> 适用:某业务域从 v1(SQLite)切到 v2(PG)写路径。口径:按域二值切换,分钟级冻结,不按流量比例。
> 前置:该域 v2 功能已验收;影子比对(`scripts/shadow_compare.py`)确认纵切面域差异可由增量补迁覆盖。

## 四步流程(以"成果提交域"为例)

### 1. 冻结(约 1 分钟)
- Nginx 置维护页:`location /achievement-submit { return 503; }`(v1 域路由),`nginx -s reload`
- 通知口径:系统维护中,预计 X 分钟
- **验证**:curl v1 提交端点 → 503

### 2. 增量补迁(分钟级)
```bash
# 全量重跑管线(幂等,分钟级);大库时改用增量(按 updated_at 水位)
D:/venvs/awardie/Scripts/python scripts/v2_migrate.py --skip-baseline
```
- 注意:`--skip-baseline` 跳过 DDL 重生成,仅重灌数据;**V1 baseline 已入库勿动**
- 纵切面域行数核对:SQLite COUNT vs PG COUNT(冻结期内数字应一致)

### 3. 接管
- Nginx 移除维护页,`/achievement-submit` 走 v2(纵切面已在 /api/v2 下,无路由改动)
- **验证**:浏览器提交一笔真实成果 → PG 出现新 pending 行 + audit action_type=1

### 4. 回退(一条命令)
- 若 v2 接管后异常:`nginx -s reload` 恢复维护页 → v1 路由解冻 → 流量回 v1
- 数据回退:v2 接管期产生的 PG 行**保留**(增量补迁工具天然支持下次再切),v1 侧无脏数据

## 演练记录(2026-08-30)

- 演练范围:数据层影子比对全量(30 表)+ 纵切面行数核对
- 报告:`scripts/shadow_report_2026-08-30.txt`
- 结果:行数分叉全部可解释(测试物化 +4 awards/提交 +118 pending/v1 服务期增量 +80 system_event_log);
  内容指纹差异为类型映射规范化噪声(jsonb/timestamptz/BOOLEAN 的文本表示),比对工具规范化策略列 P1 迭代
- 冻结/接管步骤:dev 环境按本 runbook 走通(nginx 维护页→补迁→浏览器真实提交→PG 新行)
- 回退:Nginx upstream 恢复验证 ✓

## P3 触发监控(#23)

```bash
D:/venvs/awardie/Scripts/python scripts/tail_traffic_report.py
```
解析 nginx 8090 access.log,输出 v2/v1 长尾分类统计与 Top 路径。**P3 触发观测口径**:v1 长尾占比持续 ~0% 且绝对量趋零(建议按周观察)→ 再评估稳态收束。

## 已知边界

- 增量补迁当前实现为**全量重灌**(幂等),分钟级;大库需改水位增量(P2 优化)
- 影子比对 API 层(双发 JSON 对比)待 v1/v2 出现同构端点后启用;当前数据层比对已满足切换 assurance
