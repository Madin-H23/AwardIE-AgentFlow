"""0008: 扩展审核留痕动作枚举至 12（成果删除）

背景：补"成果删除留痕"需 action_type=12，但表 CHECK 约束为 BETWEEN 1 AND 11。
SQLite 无法 ALTER 约束 → 按标准三步重建表（rename→create→copy→drop→重命名）。
说明：Alembic 默认 batch 模式下以文本重建 SQLite 表，会自动保留原表数据与索引；
此处使用显式重建以精确控制（含 CHECK 扩为 1..12）。
"""
from alembic import op

revision = '0008_audit_action12'
down_revision = '0007_audit_localtime'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE achievement_audit_log RENAME TO achievement_audit_log_old')
    op.execute('''
        CREATE TABLE achievement_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            achievement_id INTEGER NOT NULL,
            achievement_kind TEXT CHECK(achievement_kind IN ('award','patent','software','innovation','other')),
            trace_id VARCHAR(64), action_type INTEGER NOT NULL CHECK(action_type BETWEEN 1 AND 12),
            action_result INTEGER NOT NULL DEFAULT 0 CHECK(action_result IN (0,1,2)),
            operator_id INTEGER, operator_code VARCHAR(50) NOT NULL, operator_name VARCHAR(50) NOT NULL,
            operator_role INTEGER CHECK(operator_role IN (1,2,3,4)), operator_ip TEXT,
            ai_batch_id VARCHAR(50), change_detail TEXT, remark TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)
    ''')
    op.execute('''
        INSERT INTO achievement_audit_log
            (id, achievement_id, achievement_kind, trace_id, action_type, action_result,
             operator_id, operator_code, operator_name, operator_role, operator_ip,
             ai_batch_id, change_detail, remark, created_at)
        SELECT id, achievement_id, achievement_kind, trace_id, action_type, action_result,
               operator_id, operator_code, operator_name, operator_role, operator_ip,
               ai_batch_id, change_detail, remark, created_at
        FROM achievement_audit_log_old
    ''')
    op.execute('DROP TABLE achievement_audit_log_old')


def downgrade():
    op.execute('ALTER TABLE achievement_audit_log RENAME TO achievement_audit_log_old')
    op.execute('''
        CREATE TABLE achievement_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            achievement_id INTEGER NOT NULL,
            achievement_kind TEXT CHECK(achievement_kind IN ('award','patent','software','innovation','other')),
            trace_id VARCHAR(64), action_type INTEGER NOT NULL CHECK(action_type BETWEEN 1 AND 11),
            action_result INTEGER NOT NULL DEFAULT 0 CHECK(action_result IN (0,1,2)),
            operator_id INTEGER, operator_code VARCHAR(50) NOT NULL, operator_name VARCHAR(50) NOT NULL,
            operator_role INTEGER CHECK(operator_role IN (1,2,3,4)), operator_ip TEXT,
            ai_batch_id VARCHAR(50), change_detail TEXT, remark TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)
    ''')
    op.execute('''
        INSERT INTO achievement_audit_log
            (id, achievement_id, achievement_kind, trace_id, action_type, action_result,
             operator_id, operator_code, operator_name, operator_role, operator_ip,
             ai_batch_id, change_detail, remark, created_at)
        SELECT id, achievement_id, achievement_kind, trace_id, action_type, action_result,
               operator_id, operator_code, operator_name, operator_role, operator_ip,
               ai_batch_id, change_detail, remark, created_at
        FROM achievement_audit_log_old
    ''')
    op.execute('DROP TABLE achievement_audit_log_old')
