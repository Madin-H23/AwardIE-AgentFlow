"""M1 后半①：审核写入切 ORM（_update_status / approve_pending / reject_pending）回归。

验证：ORM 写路径落库正确 + 状态机前置校验不回归（裸 SQL 语义等价）。
"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.schemas import PENDING_ACHIEVEMENTS_DDL as PENDING_DDL


@pytest.fixture(autouse=True)
def _reset_engine():
    import backend.orm.base as b
    b.reset_engine()
    yield
    if b._engine is not None:
        b._engine.dispose()
    b.reset_engine()


@pytest.fixture()
def pending_db(tmp_path):
    """带 submit/pending 两态记录的 pending 库（is_valid 生成列已含）。"""
    db = tmp_path / "p.db"
    conn = sqlite3.connect(str(db))
    conn.execute(PENDING_DDL)
    conn.execute(
        "INSERT INTO pending_achievements (achievement_type, achievement_data, status, submitter_type, submitter_id)"
        " VALUES ('award', '{}', 'submit', 'student', 1)")
    conn.execute(
        "INSERT INTO pending_achievements (achievement_type, achievement_data, status, submitter_type, submitter_id)"
        " VALUES ('award', '{}', 'pending', 'student', 2)")
    conn.commit()
    conn.close()
    return str(db)


def _make_manager(db):
    """构造 Manager（读缓存走测试库）并注入 ORM engine（写路径同库）。"""
    from backend.models.pending_achievement import PendingAchievementManager
    import backend.orm.base as b
    b._engine = b.build_engine(db)
    b._SessionLocal = None
    return PendingAchievementManager(db)


def _row(db, pending_id):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status, reviewer_id, reviewer_type, review_comment, review_time"
        " FROM pending_achievements WHERE id=?", (pending_id,)).fetchone()
    conn.close()
    return row


class TestApproveRejectOrm:
    def test_approve_pending_writes_reviewer(self, pending_db):
        mgr = _make_manager(pending_db)
        assert mgr.approve_pending(1, reviewer_id=5, reviewer_type='admin',
                                   review_comment='通过') is True
        row = _row(pending_db, 1)
        assert row['reviewer_id'] == 5
        assert row['reviewer_type'] == 'admin'
        assert row['review_comment'] == '通过'
        assert row['review_time'] is not None
        assert row['status'] == 'submit'        # 只写审核人信息，状态由调用方推进

    def test_approve_wrong_status_rejected(self, pending_db):
        mgr = _make_manager(pending_db)
        assert mgr.approve_pending(2, reviewer_id=5, reviewer_type='admin') is False
        assert _row(pending_db, 2)['reviewer_id'] is None

    def test_approve_missing_pending(self, pending_db):
        mgr = _make_manager(pending_db)
        assert mgr.approve_pending(999, reviewer_id=5, reviewer_type='admin') is False

    def test_reject_pending_writes_reviewer(self, pending_db):
        mgr = _make_manager(pending_db)
        assert mgr.reject_pending(1, reviewer_id=7, reviewer_type='teacher',
                                  review_comment='材料不全') is True
        row = _row(pending_db, 1)
        assert row['reviewer_id'] == 7
        assert row['reviewer_type'] == 'teacher'
        assert row['review_comment'] == '材料不全'

    def test_reject_requires_comment(self, pending_db):
        mgr = _make_manager(pending_db)
        assert mgr.reject_pending(1, reviewer_id=7, reviewer_type='teacher', review_comment='') is False


class TestUpdateStatusOrm:
    def test_update_status_writes(self, pending_db):
        mgr = _make_manager(pending_db)
        assert mgr._update_status(2, 'submit', reviewer_id=3, comment='提审') is True
        row = _row(pending_db, 2)
        assert row['status'] == 'submit'
        assert row['reviewer_id'] == 3
        assert row['review_comment'] == '提审'

    def test_update_status_wrong_status(self, pending_db):
        mgr = _make_manager(pending_db)
        assert mgr._update_status(1, 'submit', reviewer_id=3, comment='x') is False
        assert _row(pending_db, 1)['status'] == 'submit'   # 原状态保持

    def test_update_status_missing_pending(self, pending_db):
        mgr = _make_manager(pending_db)
        assert mgr._update_status(999, 'submit', reviewer_id=3, comment='x') is False
