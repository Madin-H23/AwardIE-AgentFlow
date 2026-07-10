-- 创建大创项目学生关联表
-- 用于存储项目与学生之间的关联关系，支持负责人和成员两种角色
-- 创建日期: 2026-01-26

-- 创建关联表
CREATE TABLE IF NOT EXISTS innovation_project_students (
    project_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('leader', 'member')),  -- 角色：负责人或成员
    student_name TEXT,                                        -- 原始姓名（用于显示）
    student_id_str TEXT,                                       -- 原始学号（用于匹配）
    match_type TEXT,                                          -- 匹配类型：student_id_exact, name_only, id_not_found, id_name_mismatch, unmatched
    PRIMARY KEY (project_id, student_id),
    FOREIGN KEY (project_id) REFERENCES innovation_projects(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- 创建索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_innovation_project_students_student 
    ON innovation_project_students(student_id);
CREATE INDEX IF NOT EXISTS idx_innovation_project_students_project 
    ON innovation_project_students(project_id);
