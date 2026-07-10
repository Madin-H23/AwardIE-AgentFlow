"""pytest 配置和 fixtures"""
import os
import sys
import sqlite3
import pytest
from pathlib import Path

# 添加项目根到路径
current_file = Path(__file__).resolve()
project_root = current_file.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def temp_db(tmp_path):
    """创建临时测试数据库，包含竞赛和奖状表"""
    db_path = tmp_path / "test_competitions.db"
    conn = sqlite3.connect(str(db_path))

    # 创建竞赛表
    conn.execute("""
        CREATE TABLE competitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_name TEXT NOT NULL,
            alias_list TEXT,
            official_website TEXT,
            organizer TEXT,
            competition_time TEXT,
            participant_requirements TEXT,
            grade_category TEXT,
            brief_description TEXT,
            white_list INTEGER DEFAULT 0,
            watch_list INTEGER DEFAULT 0,
            is_auto_added INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建奖状表
    conn.execute("""
        CREATE TABLE awards (
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
            is_abnormal BOOLEAN DEFAULT 0,
            validation_result TEXT,
            submitter_type TEXT,
            submitter_id INTEGER,
            submit_time TEXT,
            laboratory_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 插入测试数据 - 竞赛
    conn.execute("""
        INSERT INTO competitions (
            competition_name, competition_time, official_website, white_list, grade_category
        ) VALUES
        ('蓝桥杯全国软件和信息技术专业人才大赛', '4-10月', 'http://lanqiao.cn', 1, 'A类'),
        ('全国大学生数学建模竞赛', '9月', 'http://mcm.edu.cn', 1, 'A类'),
        ('互联网+大学生创新创业大赛', '4-10月', 'http://cy.ncss.cn', 1, 'A类'),
        ('全国大学生电子设计竞赛', '7-8月', 'http://nuedc.tsinghua.edu.cn', 0, 'B类'),
        ('ACM程序设计竞赛', '10-12月', 'http://icpc.cn', 1, 'A类')
    """)

    # 插入测试数据 - 奖状
    conn.execute("""
        INSERT INTO awards (
            competition_id, year, date, award_level, competition_level,
            winner_name, supervisor_name, competition_name_in_file
        ) VALUES
        (1, 2023, '2023-06', '一等奖', '省赛', '张三', '李老师', '蓝桥杯'),
        (1, 2023, '2023-06', '二等奖', '省赛', '李四', '李老师', '蓝桥杯'),
        (1, 2024, '2024-06', '一等奖', '国赛', '王五', '李老师', '蓝桥杯'),
        (1, 2024, '2024-05', '二等奖', '省赛', '赵六', '李老师', '蓝桥杯'),
        (1, 2024, '2024-07', '一等奖', '省赛', '钱七', '李老师', '蓝桥杯'),
        (2, 2023, '2023-10', '一等奖', '国赛', '孙八', '周老师', '数学建模'),
        (2, 2023, '2023-10', '二等奖', '国赛', '吴九', '周老师', '数学建模'),
        (3, 2024, '2024-07', '金奖', '国赛', '郑十', '冯老师', '互联网+'),
        (4, 2023, '2023-08', '一等奖', '国赛', '陈一', '卫老师', '电子设计'),
        (5, 2023, '2023-11', '金奖', '区域赛', '楚二', '蒋老师', 'ACM')
    """)

    conn.commit()
    conn.close()
    return str(db_path)
