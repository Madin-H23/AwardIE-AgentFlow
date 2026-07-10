-- 移除 awards 表中的 extract_json 列
-- 执行时间：2026-01-25
-- 说明：extract_json 字段已不再使用，数据已迁移到结构化字段

-- SQLite 不支持直接删除列，需要重建表
BEGIN TRANSACTION;

-- 1. 创建新表（不包含 extract_json 列）
CREATE TABLE awards_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_hash TEXT,
    certificate_id TEXT,
    match_status BOOLEAN,
    ocr_result TEXT,
    llm_prompt TEXT,
    llm_response TEXT,
    
    competition_name_in_file TEXT,
    track TEXT,
    issuer TEXT,
    province TEXT,
    group_name TEXT,
    winner_name TEXT,
    supervisor_name TEXT,
    award_level TEXT,
    competition_level TEXT,
    date TEXT,
    project_title TEXT,
    granted_role TEXT,
    related_student_name TEXT,
    edition INTEGER,
    year INTEGER,
    
    competition_id INTEGER NOT NULL,
    uploaded_by_user_id TEXT,
    match_status_updated_at TIMESTAMP,
    is_abnormal BOOLEAN DEFAULT 0,
    validation_result TEXT,
    submitter_type TEXT,
    submitter_id INTEGER,
    submit_time TEXT,
    laboratory_id INTEGER,
    
    FOREIGN KEY (competition_id) REFERENCES competitions(id)
);

-- 2. 复制数据（排除 extract_json 列）
INSERT INTO awards_new (
    id, image_hash, certificate_id, match_status, ocr_result, llm_prompt, llm_response,
    competition_name_in_file, track, issuer, province, group_name,
    winner_name, supervisor_name, award_level, competition_level,
    date, project_title, granted_role, related_student_name, edition, year,
    competition_id, uploaded_by_user_id, match_status_updated_at,
    is_abnormal, validation_result, submitter_type, submitter_id, submit_time, laboratory_id
)
SELECT 
    id, image_hash, certificate_id, match_status, ocr_result, llm_prompt, llm_response,
    competition_name_in_file, track, issuer, province, group_name,
    winner_name, supervisor_name, award_level, competition_level,
    date, project_title, granted_role, related_student_name, edition, year,
    competition_id, uploaded_by_user_id, match_status_updated_at,
    is_abnormal, validation_result, submitter_type, submitter_id, submit_time, laboratory_id
FROM awards;

-- 3. 删除旧表
DROP TABLE awards;

-- 4. 重命名新表
ALTER TABLE awards_new RENAME TO awards;

-- 5. 重建索引（如果需要）
-- 注意：根据实际数据库结构，可能需要重建其他索引

COMMIT;
