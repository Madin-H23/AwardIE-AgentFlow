"""0009: 成果删除留痕去重标记（is_redundant）

背景：防重修复（e82e81b）之前，同一成果可被重复删除并产生多条 action_type=12 留痕
（如 #1194 曾 4 条）。这些是历史脏数据，正式上线前订正。

处理（用户拍板：标记不物理删，尊重 append-only）：
- 新增列 is_redundant INTEGER NOT NULL DEFAULT 0（订正元数据，非业务字段）
- 对每个 (achievement_kind, achievement_id) 的 action12，保留最早一条，其余置 1
- 查询/统计层默认过滤 is_redundant=1；标记列可回退（downgrade 置 0）
"""
from alembic import op

revision = '0009_audit_redundant_flag'
down_revision = '0008_audit_action12'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE achievement_audit_log ADD COLUMN is_redundant INTEGER NOT NULL DEFAULT 0")
    op.execute(
        "UPDATE achievement_audit_log SET is_redundant = 1 "
        "WHERE action_type = 12 AND id NOT IN ("
        "  SELECT MIN(id) FROM achievement_audit_log "
        "  WHERE action_type = 12 GROUP BY achievement_kind, achievement_id)"
    )


def downgrade():
    op.execute("UPDATE achievement_audit_log SET is_redundant = 0")
