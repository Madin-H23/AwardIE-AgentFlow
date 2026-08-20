"""阶段六 L1：system_event_log 表（日志系统设计 §3.1，编号顺延——0004/0005 已用）。

应用层关键事件（OCR 失败/熔断翻转/异常捕获/认证失败等）从非结构化 app.log
升级为结构化 DB 记录。类型按 G8 规范（枚举 VARCHAR，message/detail 长文本 TEXT）。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '0006_system_event_log'
down_revision: Union[str, Sequence[str], None] = '0005_failed_logins'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("""CREATE TABLE IF NOT EXISTS system_event_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        event_category  VARCHAR(20) NOT NULL CHECK(event_category IN (
                            'ocr', 'llm', 'breaker', 'auth', 'upload',
                            'db', 'security', 'system')),
        event_level     VARCHAR(10) NOT NULL CHECK(event_level IN (
                            'debug', 'info', 'warning', 'error', 'critical')),
        event_message   TEXT NOT NULL,
        trace_id        VARCHAR(64),
        operator_id     INTEGER REFERENCES users(id),
        operator_code   VARCHAR(50),
        detail          TEXT,
        source_module   VARCHAR(100),
        source_file     VARCHAR(200),
        source_line     INTEGER,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP
    )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_category "
                      "ON system_event_log(event_category, created_at)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_level "
                      "ON system_event_log(event_level, created_at)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_trace "
                      "ON system_event_log(trace_id) WHERE trace_id IS NOT NULL"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_time "
                      "ON system_event_log(created_at)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS system_event_log"))
