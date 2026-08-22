"""0012: 审计留痕测试噪音打标（is_test）

背景：本地开发期 pytest 全量回归 / gui_smoke / 覆盖率跑批在真实库产生了大量
自动化留痕（截至 2026-08-23 共 1297 行中约 1290 行为测试产物），污染
admin/logs 默认视图与审计统计的取证价值。

处理原则（用户 goal 定稿：宁可漏标不可误标，标记不物理删，尊重 append-only）：
- 新增列 is_test INTEGER NOT NULL DEFAULT 0（订正元数据，非业务字段）
- 满足任一保守特征即标 1：
  ① 深夜时段（02:00-06:59）——自动化跑批窗口，人工操作从不发生；
  ② 合成/测试操作者：'0'（无会话回退值）、'AI'（自动审核）、'1370'
    （users.id 数字快照遗留）、'212206095'（种子学生陶雅轩）、
    '212306413'（gui_smoke 学生陈品天）；
  ③ 分钟级突发：同一 (分钟, 操作者, 动作) ≥5 条——机器指纹；
  ④ 教师 02110606（gui_smoke 教师账号黄巧云）指向已不存在实体的行。
- 刻意保留（漏标）：#1194/#1195 的删除留痕史（用户亲历的重复删除事件证据）
  与 08-21 白天的教师入库留痕。
- 查询/统计层默认过滤 is_test=1；include_tests 显式可查全量；downgrade 置 0 可回退。
"""
from alembic import op

revision = '0012_audit_test_flag'
down_revision = '0011_sqlite_seq_dedup'
branch_labels = None
depends_on = None

_MARK_SQL = """
UPDATE achievement_audit_log SET is_test = 1 WHERE id IN (
    SELECT l.id FROM achievement_audit_log l
    WHERE CAST(substr(l.created_at, 12, 2) AS INTEGER) BETWEEN 2 AND 6
       OR l.operator_code IN ('0', 'AI', '1370', '212206095', '212306413')
       OR l.id IN (
            SELECT l2.id FROM achievement_audit_log l2
            JOIN (SELECT substr(created_at, 1, 16) m, operator_code oc, action_type at_
                  FROM achievement_audit_log
                  GROUP BY 1, 2, 3 HAVING COUNT(*) >= 5) b
              ON substr(l2.created_at, 1, 16) = b.m
             AND l2.operator_code = b.oc AND l2.action_type = b.at_)
       OR (l.operator_code = '02110606'
           AND l.achievement_id NOT IN (SELECT id FROM awards))
)
"""


def upgrade():
    op.execute("ALTER TABLE achievement_audit_log ADD COLUMN is_test INTEGER NOT NULL DEFAULT 0")
    op.execute(_MARK_SQL)


def downgrade():
    op.execute("UPDATE achievement_audit_log SET is_test = 0")
