# -*- coding: utf-8 -*-
"""验证「成果审核空页」问题：仅 status=submit 的记录应在成果审核页展示。

场景：
- 表中有 status=pending 的记录时，get_stats_by_type_and_validation() 会统计到，
  但成果审核页只查 status=submit，导致重定向到某类型/valid 后列表为空。
- 修复：入口重定向使用 get_stats_by_type_and_validation_for_review()（只统计 submit），
  列表仍用 query_pending_items(session_id=None)（只查 submit）。

pytest 函数式（T31-T34 批次3 转换）；无库环境自动 skip。
"""
from pathlib import Path

import pytest

from config.loader import get_config_loader
from backend.models.pending_achievement import PendingAchievementManager
from app.routes.review_helpers import query_pending_items

AWARD_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "award_sample.jpg"


@pytest.fixture(scope="module")
def manager():
    config = get_config_loader()
    db_path = str(config.get_path("database", "competitions_db"))
    if not Path(db_path).exists():
        pytest.skip(f"数据库不存在: {db_path}")
    return PendingAchievementManager(db_path)


@pytest.fixture()
def cleanup_pending(manager):
    created = []
    yield created
    for pid in created:
        manager.delete_pending(pid)


def _insert_pending_award(manager, created, status="pending"):
    achievement_data = {
        "competition_name": "测试竞赛",
        "award_level": "一等奖",
        "winner_name": "测试学生",
        "file_path": str(AWARD_FIXTURE_PATH) if AWARD_FIXTURE_PATH.exists() else "/fake/award.jpg",
    }
    validation_result = {"is_valid": True, "content_issues": [], "completeness_issues": []}
    p = manager.submit_for_review(
        achievement_type="award",
        achievement_data=achievement_data,
        validation_result=validation_result,
        submitter_type="student",
        submitter_id=0,
        file_path=achievement_data.get("file_path"),
        status=status,
        file_hash="test_review_stats_hash_" + status,
    )
    assert p is not None
    created.append(p.id)
    return p.id


def test_pending_record_not_in_global_review_list(manager, cleanup_pending):
    """仅有 pending 记录时：全量统计有值，入口统计(for_review)为 0，全局审核列表为空。"""
    pending_id = _insert_pending_award(manager, cleanup_pending, status="pending")

    stats_all = manager.get_stats_by_type_and_validation()
    assert "award" in stats_all
    assert stats_all["award"].get("total", 0) >= 1
    assert stats_all["award"].get("valid", 0) >= 1

    items = query_pending_items(manager, "award", "valid", session_id=None)
    pending_ids = {p.id for p in items}
    assert pending_id not in pending_ids,         "status=pending 的记录不应出现在成果审核页（全局）的 award/valid 列表中"


def test_submit_record_in_global_review_list(manager, cleanup_pending):
    """改为 submit 后：入口统计有值，全局审核列表包含该条。"""
    pending_id = _insert_pending_award(manager, cleanup_pending, status="pending")
    pending = manager.get_pending_by_id(pending_id)
    assert pending is not None

    ok = manager.update(pending_item=pending, status="submit")
    assert ok

    stats_review = manager.get_stats_by_type_and_validation_for_review()
    assert stats_review.get("award", {}).get("total", 0) >= 1
    assert stats_review.get("award", {}).get("valid", 0) >= 1

    items = query_pending_items(manager, "award", "valid", session_id=None)
    ids = [p.id for p in items]
    assert pending_id in ids, "status=submit 的记录应出现在成果审核页 award/valid 列表中"
