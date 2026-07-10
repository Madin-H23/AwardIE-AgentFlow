"""竞赛等级缺失视为异常的检测逻辑单元测试"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
from backend.extract.validation import AwardValidator


class TestCompetitionLevelValidation:
    """竞赛等级必填 -> 缺失算异常"""

    def test_has_competition_level_valid(self):
        v = AwardValidator()
        r = v.validate({
            "competition_id": 1,
            "winner_name": "张三",
            "year": 2024,
            "award_level": "一等奖",
            "granted_role": "学生",
            "supervisor_name": "老师",
            "competition_level": "国赛",
        })
        assert r.is_valid
        assert not any(e.code == "COMPETITION_LEVEL_MISSING" for e in r.content_issues)

    def test_missing_competition_level_invalid(self):
        v = AwardValidator()
        r = v.validate({
            "competition_id": 1,
            "winner_name": "李四",
            "year": 2024,
            "award_level": "二等奖",
            "granted_role": "学生",
            "supervisor_name": "老师",
            "competition_level": "",
        })
        assert not r.is_valid
        issues = [e for e in r.content_issues if e.code == "COMPETITION_LEVEL_MISSING"]
        assert len(issues) == 1
        assert "竞赛等级" in issues[0].message

    def test_no_competition_level_key_invalid(self):
        v = AwardValidator()
        r = v.validate({
            "competition_id": 1,
            "winner_name": "王五",
            "year": 2024,
            "award_level": "三等奖",
            "granted_role": "学生",
            "supervisor_name": "老师",
        })
        assert not r.is_valid
        issues = [e for e in r.content_issues if e.code == "COMPETITION_LEVEL_MISSING"]
        assert len(issues) == 1
