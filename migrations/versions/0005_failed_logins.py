"""P2-25：登录失败锁定表 failed_logins（落库版限流，不依赖 Redis）。

安全设计 §2.4：failed_logins 表做账号级锁定兜底（多 worker 共享计数）。
代码层 backend/utils/login_guard.py 含 CREATE TABLE IF NOT EXISTS 兜底（老库首次调用自动建表）；
本迁移显式建表保持 Alembic 迁移链完整。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '0005_failed_logins'
down_revision: Union[str, Sequence[str], None] = '0004_teacher_fk_relink'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("""CREATE TABLE IF NOT EXISTS failed_logins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login_code TEXT NOT NULL DEFAULT '',
        ip TEXT NOT NULL DEFAULT '',
        fail_count INTEGER NOT NULL DEFAULT 0,
        first_fail_at TEXT NOT NULL,
        lock_until TEXT,
        updated_at TEXT NOT NULL
    )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_failed_logins_code ON failed_logins(login_code)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS failed_logins"))
