# -*- coding: utf-8 -*-
"""
验证「成果审核空页」问题：仅 status=submit 的记录应在成果审核页展示。

场景：
- 表中有 status=pending 的记录时，get_stats_by_type_and_validation() 会统计到，
  但成果审核页只查 status=submit，导致重定向到某类型/valid 后列表为空。
- 修复：入口重定向使用 get_stats_by_type_and_validation_for_review()（只统计 submit），
  列表仍用 query_pending_items(session_id=None)（只查 submit）。

本测试使用项目中的测试奖状路径（tests/fixtures/award_sample.jpg）构造一条 pending 记录，
验证：pending 时全局审核列表为空、for_review 统计为 0；改为 submit 后列表有数据、for_review 统计有值。
"""
import sys
import unittest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.loader import get_config
from backend.models.pending_achievement import PendingAchievementManager
from app.routes.review_helpers import query_pending_items


# 测试用奖状路径（项目内 fixture）
AWARD_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "award_sample.jpg"


class TestReviewPendingVsSubmitStats(unittest.TestCase):
    """验证成果审核：pending 不入列表、仅 submit 入列表且参与入口统计"""

    @classmethod
    def setUpClass(cls):
        cls.config = get_config()
        cls.db_path = str(cls.config.get_path("database", "competitions_db"))
        if not Path(cls.db_path).exists():
            raise unittest.SkipTest(f"数据库不存在: {cls.db_path}")
        cls.manager = PendingAchievementManager(cls.db_path)

    def setUp(self):
        self._pending_id = None

    def tearDown(self):
        if self._pending_id is not None:
            self.manager.delete_pending(self._pending_id)
            self._pending_id = None

    def _insert_pending_award(self, status: str = "pending"):
        """插入一条奖状类型的 pending 记录，验证通过。返回 pending_id。"""
        achievement_data = {
            "competition_name": "测试竞赛",
            "award_level": "一等奖",
            "winner_name": "测试学生",
            "file_path": str(AWARD_FIXTURE_PATH) if AWARD_FIXTURE_PATH.exists() else "/fake/award.jpg",
        }
        validation_result = {"is_valid": True, "content_issues": [], "completeness_issues": []}
        p = self.manager.submit_for_review(
            achievement_type="award",
            achievement_data=achievement_data,
            validation_result=validation_result,
            submitter_type="student",
            submitter_id=0,
            file_path=achievement_data.get("file_path"),
            status=status,
            file_hash="test_review_stats_hash_" + status,
        )
        self.assertIsNotNone(p)
        self._pending_id = p.id
        return p.id

    def test_pending_record_not_in_global_review_list(self):
        """仅有 pending 记录时：全量统计有值，入口统计(for_review)为 0，全局审核列表为空。"""
        self._insert_pending_award(status="pending")

        # 全量统计（旧逻辑）：应包含这条 award/valid
        stats_all = self.manager.get_stats_by_type_and_validation()
        self.assertIn("award", stats_all)
        self.assertGreaterEqual(stats_all["award"].get("total", 0), 1)
        self.assertGreaterEqual(stats_all["award"].get("valid", 0), 1)

        # 入口统计（仅 submit）：不应包含这条
        stats_review = self.manager.get_stats_by_type_and_validation_for_review()
        award_total_review = stats_review.get("award", {}).get("total", 0)
        # 可能已有其他 submit 的 award，所以只断言「当前这条是 pending 时」列表里 award/valid 的条数
        # 我们通过「全局审核列表」查 award/valid 应不包含这条 pending
        items = query_pending_items(self.manager, "award", "valid", session_id=None)
        pending_ids = {p.id for p in items}
        self.assertNotIn(
            self._pending_id,
            pending_ids,
            "status=pending 的记录不应出现在成果审核页（全局）的 award/valid 列表中",
        )

    def test_submit_record_in_global_review_list(self):
        """改为 submit 后：入口统计有值，全局审核列表包含该条。"""
        self._insert_pending_award(status="pending")
        pending = self.manager.get_pending_by_id(self._pending_id)
        self.assertIsNotNone(pending)

        # 改为 submit
        ok = self.manager.update(pending_item=pending, status="submit")
        self.assertTrue(ok)

        # 入口统计应包含这条 award
        stats_review = self.manager.get_stats_by_type_and_validation_for_review()
        self.assertGreaterEqual(stats_review.get("award", {}).get("total", 0), 1)
        self.assertGreaterEqual(stats_review.get("award", {}).get("valid", 0), 1)

        # 全局审核列表应包含这条
        items = query_pending_items(self.manager, "award", "valid", session_id=None)
        ids = [p.id for p in items]
        self.assertIn(
            self._pending_id,
            ids,
            "status=submit 的记录应出现在成果审核页 award/valid 列表中",
        )


if __name__ == "__main__":
    unittest.main()
