-- ============================================================
-- 自动归档配置表迁移脚本
-- 创建日期: 2026-01-26
-- 说明: 添加自动归档配置表，支持按成果类型和验证状态配置是否自动归档
-- ============================================================

-- 1. 创建 auto_archive_config 表
CREATE TABLE IF NOT EXISTS auto_archive_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_type TEXT NOT NULL,           -- 'award', 'patent', 'software', 'innovation', 'other'
    validation_status TEXT,                   -- 'valid', 'invalid'（大创/其他为NULL）
    auto_archive_enabled BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(achievement_type, validation_status)
);

-- 2. 插入初始配置数据（默认都不自动归档）
-- 奖状/专利/软著：分为 valid 和 invalid 两个配置
INSERT OR IGNORE INTO auto_archive_config (achievement_type, validation_status, auto_archive_enabled)
VALUES
    ('award', 'valid', 0),
    ('award', 'invalid', 0),
    ('patent', 'valid', 0),
    ('patent', 'invalid', 0),
    ('software', 'valid', 0),
    ('software', 'invalid', 0);

-- 大创/其他：只有 NULL 状态的配置
INSERT OR IGNORE INTO auto_archive_config (achievement_type, validation_status, auto_archive_enabled)
VALUES
    ('innovation', NULL, 0),
    ('other', NULL, 0);

-- 3. 修改 review_logs 表，增加 system 审核人类型
-- 注意：SQLite 不支持直接修改约束，需要重建表
-- 先创建新表
CREATE TABLE IF NOT EXISTS review_logs_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pending_id INTEGER NOT NULL,
    achievement_type TEXT NOT NULL,
    file_hash TEXT,
    file_path TEXT,
    submitter_type TEXT NOT NULL,
    submitter_id INTEGER NOT NULL,
    reviewer_type TEXT NOT NULL,
    reviewer_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    result_type TEXT,
    result_id INTEGER,
    result_file_path TEXT,
    review_comment TEXT,
    operation_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(reviewer_type IN ('teacher', 'admin', 'system'))
);

-- 迁移数据
INSERT OR IGNORE INTO review_logs_new
SELECT * FROM review_logs;

-- 删除旧表，重命名新表
DROP TABLE IF EXISTS review_logs;
ALTER TABLE review_logs_new RENAME TO review_logs;

-- 4. 创建索引（提高查询性能）
CREATE INDEX IF NOT EXISTS idx_auto_archive_config_type_status
ON auto_archive_config(achievement_type, validation_status);

-- 5. 创建触发器（自动更新 updated_at）
CREATE TRIGGER IF NOT EXISTS update_auto_archive_config_timestamp
AFTER UPDATE ON auto_archive_config
FOR EACH ROW
BEGIN
    UPDATE auto_archive_config SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- ============================================================
-- 验证迁移结果
-- ============================================================

-- 验证 auto_archive_config 表
SELECT 'auto_archive_config 表记录数:' AS info, COUNT(*) AS count FROM auto_archive_config;

-- 验证 review_logs 表约束
SELECT 'review_logs 表记录数:' AS info, COUNT(*) AS count FROM review_logs;
