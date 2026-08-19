"""orm baseline——当前 schema 即起点（M1 后半③③，CR-8 交接点）。

本迁移不执行任何 DDL（现库已是权威 baseline）；后续增量迁移在 versions/ 追加。
注意：autogenerate 会把未建模表视为 DROP——**新增迁移一律手写**，禁用 autogenerate。
"""
from typing import Sequence, Union

revision: str = '0001_orm_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op：现库 schema 即 baseline。"""


def downgrade() -> None:
    """No-op。"""
