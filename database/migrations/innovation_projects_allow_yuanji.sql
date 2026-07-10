-- 将 project_type 的 CHECK 约束扩展为包含「院级」
-- SQLite 无法直接修改 CHECK，需重建表

PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS innovation_projects_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_no TEXT UNIQUE,
    project_name TEXT NOT NULL,
    project_type TEXT CHECK(project_type IN ('国家级', '省级',  '院级')),
    start_date TEXT,
    end_date TEXT,
    student_leader_name TEXT,
    student_leader_id TEXT,
    other_members TEXT,
    supervisors TEXT,
    funding_amount REAL,
    status TEXT DEFAULT '进行中' CHECK(status IN ('进行中', '已结题', '终止')),
    submitter_type TEXT CHECK(submitter_type IN ('admin')),
    submitter_id INTEGER,
    submit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    laboratory_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (laboratory_id) REFERENCES laboratories(id) ON DELETE SET NULL
);

INSERT INTO innovation_projects_new (
    id, project_no, project_name, project_type, start_date, end_date,
    student_leader_name, student_leader_id, other_members, supervisors,
    funding_amount, status, submitter_type, submitter_id, submit_time,
    laboratory_id, created_at, updated_at
) SELECT
    id, project_no, project_name, project_type, start_date, end_date,
    student_leader_name, student_leader_id, other_members, supervisors,
    funding_amount, status, submitter_type, submitter_id, submit_time,
    laboratory_id, created_at, updated_at
FROM innovation_projects;

DROP TABLE innovation_projects;

ALTER TABLE innovation_projects_new RENAME TO innovation_projects;

PRAGMA foreign_keys = ON;
