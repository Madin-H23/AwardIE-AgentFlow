"""pytest 配置和 fixtures"""
import os
import sys
import sqlite3
import pytest
from pathlib import Path

# 添加项目根到路径
# __file__ = tests/extract/template/conftest.py
# 需要向上找到项目根目录
current_file = Path(__file__).resolve()
# tests/extract/template -> tests/extract -> tests -> project_root
project_root = current_file.parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def test_db_path(tmp_path):
    """创建临时测试数据库"""
    db_path = tmp_path / "test_templates.db"
    conn = sqlite3.connect(str(db_path))
    # 创建测试表结构
    conn.execute("""
        CREATE TABLE templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_type TEXT NOT NULL,
            min_length INTEGER DEFAULT 0,
            max_length INTEGER DEFAULT 0,
            keywords TEXT,
            sample_text TEXT,
            sample_extracted TEXT,
            default_fields TEXT,
            llm_fields TEXT,
            language TEXT DEFAULT 'zh',
            need_translate INTEGER DEFAULT 0,
            is_manual_edited INTEGER DEFAULT 0,
            sample_image_blob BLOB,
            competition_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture
def sample_template_data():
    """示例模板数据"""
    return {
        "type": "award",
        "keywords": ["蓝桥杯", "省赛"],
        "min_length": 50,
        "default_fields": {
            "competition_name": "蓝桥杯",
            "granted_role": "学生"
        },
        "sample_text": "蓝桥杯全国软件和信息技术专业人才大赛获奖证书获得者：张三",
        "sample_extracted": '{"winner_name": "张三", "award_level": "一等奖"}'
    }


@pytest.fixture
def sample_templates_data():
    """多个示例模板数据"""
    return [
        {
            "type": "award",
            "keywords": ["蓝桥杯", "省赛"],
            "min_length": 30,  # 降低最小长度要求
            "default_fields": {"competition_name": "蓝桥杯", "granted_role": "学生"}
        },
        {
            "type": "award",
            "keywords": ["蓝桥杯", "优秀指导教师"],
            "min_length": 30,  # 降低最小长度要求
            "default_fields": {"competition_name": "蓝桥杯", "granted_role": "教师"}
        },
        {
            "type": "award",
            "keywords": ["数据安全"],
            "min_length": 20,  # 降低最小长度要求
            "default_fields": {"competition_name": "数据安全竞赛", "granted_role": "学生"}
        }
    ]


@pytest.fixture
def ocr_text_samples():
    """OCR 文本样本"""
    return {
        "蓝桥杯省赛": "蓝桥杯全国软件和信息技术专业人才大赛省赛获奖证书获得者：李明，获得一等奖",
        "蓝桥杯教师": "蓝桥杯全国软件和信息技术专业人才大赛优秀指导教师获奖证书：陈老师，指导学生获得一等奖",
        "数据安全": "数据安全竞赛省赛二等奖获奖者：王芳",
        "无匹配": "这是一段普通的文本，不包含任何竞赛关键词"
    }


@pytest.fixture
def config_dir():
    """配置目录路径"""
    return str(project_root / "backend" / "extract" / "config")
