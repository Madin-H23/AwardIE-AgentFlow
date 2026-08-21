"""0007: 审核留痕时间基准统一为应用本地时间（中国时间）

背景：achievement_audit_log.created_at 原依赖 SQLite CURRENT_TIMESTAMP（恒 UTC），
库内排障需心算 +8。配套代码改动：AuditLogger 写入显式传本地时间（datetime.now()），
不再依赖列默认值。本迁移把存量 UTC 行一次性 +8h 对齐新基准。

执行顺序纪律：**先执行本迁移、再部署配套写入代码**（常规 alembic upgrade → 发版顺序天然满足），
避免窗口期新写入的本地时间行被误 +8。

downgrade：-8h 回到 UTC 基准（仅在与旧版代码回滚配套时使用）。
"""
from alembic import op

revision = '0007_audit_localtime'
down_revision = '0006_system_event_log'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE achievement_audit_log "
               "SET created_at = datetime(created_at, '+8 hours') "
               "WHERE created_at IS NOT NULL")


def downgrade():
    op.execute("UPDATE achievement_audit_log "
               "SET created_at = datetime(created_at, '-8 hours') "
               "WHERE created_at IS NOT NULL")
