"""0011: sqlite_sequence 去重修复（0010 遗留缺陷）

背景：0010 迁移 `_restore_seqs` 用 INSERT OR REPLACE 恢复自增计数，但
sqlite_sequence 是 SQLite 内部表、无唯一索引——OR REPLACE 找不到冲突行时
变成普通 INSERT，为同一表插入重复行（实测 awards 出现 (1193,1195) 两行）。

后果（严重）：AUTOINCREMENT 机制读 sqlite_sequence 时取第一行 seq=1193，
新插入行 id 恒为 1194；首次 INSERT 成功（lastrowid=1194），下一次再插 1194
主键冲突，异常被业务层吞掉 → awards 表行数不再增长甚至长期为空（P1-P3
测试入库全假绿、成果管理看不到新数据）。该缺陷同样会咬生产库。

处理：删除每个表名除最新 rowid（=最新 seq）外的重复行，保留最大值。
downgrade：不可还原（被删重复行的信息无法重构），回退依赖迁移前备份；
与 0010 downgrade no-op 策略一致。
"""
from alembic import op

revision = '0011_sqlite_seq_dedup'
down_revision = '0010_typization_finish'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "DELETE FROM sqlite_sequence "
        "WHERE rowid NOT IN (SELECT MAX(rowid) FROM sqlite_sequence GROUP BY name)"
    )


def downgrade():
    """去重不可还原；回退靠迁移前备份（与 0010 同策略）。"""
    pass