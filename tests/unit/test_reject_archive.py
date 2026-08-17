"""T1 回归测试：驳回打回（FR-APPROVE-07）+ approve 软归档（8.6.4）。

manager 层直测（临时库建最小表），覆盖条件守卫/乐观锁/exclude_archived。
"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

PENDING_DDL = """CREATE TABLE pending_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_type TEXT, achievement_data TEXT,
    submitter_type TEXT, submitter_id INTEGER,
    status TEXT DEFAULT 'pending', version INTEGER DEFAULT 1,
    reviewer_type TEXT, reviewer_id INTEGER, review_comment TEXT, review_time TEXT,
    ext_info TEXT)"""


@pytest.fixture()
def pm(tmp_path):
    db = tmp_path / "t.db"
    # 从真实库反射建表 DDL（保证与 manager SELECT * 全列对齐，永不漂移）
    real = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
    ddl = real.execute("SELECT sql FROM sqlite_master WHERE name='pending_achievements'").fetchone()[0]
    real.close()
    conn = sqlite3.connect(str(db))
    conn.execute(ddl)
    conn.execute("INSERT INTO pending_achievements (achievement_type, achievement_data, submitter_type, submitter_id, status, ext_info) "
                 "VALUES ('award','{}','student',7,'submit','{\"agent_review\":{\"decision\":\"pass\"}}')")
    conn.execute("INSERT INTO pending_achievements (achievement_type, achievement_data, submitter_type, submitter_id, status) "
                 "VALUES ('award','{}','student',8,'pending')")
    conn.commit()
    conn.close()
    from backend.models.pending_achievement import PendingAchievementManager
    return PendingAchievementManager(str(db))


class TestReject:
    def test_reject_submit_ok(self, pm):
        assert pm.reject(1, 'teacher', 5, '证书照片模糊，请重拍') is True
        p = pm.get_pending_by_id(1)
        assert p.status == 'rejected' and p.review_comment == '证书照片模糊，请重拍'
        assert p.reviewer_type == 'teacher' and p.reviewer_id == 5

    def test_reject_non_submit_rejected(self, pm):
        """非 submit 状态（pending 中草稿）不可驳回。"""
        assert pm.reject(2, 'teacher', 5, 'x') is False

    def test_reject_twice_second_fails(self, pm):
        """重复驳回：第二次条件守卫拦截。"""
        assert pm.reject(1, 'teacher', 5, 'a') is True
        assert pm.reject(1, 'teacher', 5, 'b') is False   # 已 rejected

    def test_reject_missing(self, pm):
        assert pm.reject(999, 'teacher', 5, 'x') is False


class TestArchive:
    def test_archive_submit_ok_keeps_row_and_ai(self, pm):
        assert pm.archive(1) is True
        p = pm.get_pending_by_id(1)
        assert p.status == 'archived'
        assert p.version == 2                                   # 乐观锁递增
        assert 'agent_review' in (p.ext_info or '')             # AI 结论保留（8.6.4 核心）

    def test_archive_pending_rejected(self, pm):
        assert pm.archive(2) is False                           # pending 草稿不可归档


class TestSubmitterView:
    def test_exclude_archived_by_default(self, pm):
        assert pm.archive(1) is True
        visible = pm.get_pending_by_submitter('student', 7)
        assert all(p.status != 'archived' for p in visible)      # submissions 页不见 archived
        history = pm.get_pending_by_submitter('student', 7, exclude_archived=False)
        assert any(p.status == 'archived' for p in history)      # 显式查历史可见


def test_old_admin_reject_route_now_real():
    """源码防回退：admin 废弃空转路由已改造为真驳回 API。"""
    src = (PROJECT_ROOT / 'app' / 'routes' / 'admin_review.py').read_text(encoding='utf-8')
    assert '已废弃' not in src
    assert "/api/achievement-review/<int:pending_id>/reject" in src
