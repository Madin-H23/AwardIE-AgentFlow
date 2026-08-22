"""T57 停写切换测试（M4）：review_logs 冻结为历史只读。

断言：
1. create_log 调用即 no-op——review_logs 行数不变；
2. 同一审核动作周期内 achievement_audit_log 正常增长（新留痕体系接管）；
3. 历史数据经只读路径（query_logs/get_recent_logs）继续可查。
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fixtures.schemas import AUDIT_LOG_DDL  # noqa: E402

REVIEW_LOGS_DDL = """CREATE TABLE review_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pending_id INTEGER NOT NULL,
    achievement_type VARCHAR(20) NOT NULL,
    file_hash VARCHAR(64),
    file_path VARCHAR(500),
    submitter_type VARCHAR(20) NOT NULL,
    submitter_id INTEGER NOT NULL,
    reviewer_type VARCHAR(20) NOT NULL,
    reviewer_id INTEGER NOT NULL,
    action_type VARCHAR(20) NOT NULL,
    result_type VARCHAR(20),
    result_id INTEGER,
    result_file_path VARCHAR(500),
    review_comment TEXT,
    operation_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(reviewer_type IN ('teacher', 'admin', 'system'))
)"""


@pytest.fixture()
def frozen_db(tmp_path):
    """临时库：review_logs（含 1 条历史行）+ achievement_audit_log。"""
    db = tmp_path / "freeze.db"
    conn = sqlite3.connect(str(db))
    conn.execute(REVIEW_LOGS_DDL)
    conn.execute(
        "INSERT INTO review_logs (pending_id, achievement_type, submitter_type, submitter_id,"
        " reviewer_type, reviewer_id, action_type) VALUES (1, 'award', 'student', 1370,"
        " 'teacher', 1795, 'approved')")
    conn.execute(AUDIT_LOG_DDL)
    conn.commit()
    conn.close()
    return db


def _counts(db):
    conn = sqlite3.connect(str(db))
    rl = conn.execute("SELECT COUNT(*) FROM review_logs").fetchone()[0]
    al = conn.execute("SELECT COUNT(*) FROM achievement_audit_log").fetchone()[0]
    conn.close()
    return rl, al


def test_create_log_is_noop_after_freeze(frozen_db):
    from backend.models.review_log import ReviewLogManager
    mgr = ReviewLogManager(str(frozen_db))
    before, _ = _counts(frozen_db)

    result = mgr.create_log(
        pending_id=2, achievement_type="award", submitter_type="student",
        submitter_id=1370, reviewer_type="teacher", reviewer_id=1795,
        action_type="rejected", review_comment="信息有误")

    assert result is None  # no-op 返回
    after, _ = _counts(frozen_db)
    assert after == before == 1  # review_logs 行数不变


def test_new_action_writes_audit_not_review_logs(frozen_db, monkeypatch):
    """同一审核动作周期：audit_log 增长、review_logs 不变。"""
    from backend.models.review_log import ReviewLogManager
    from backend.utils.audit_logger import audit_log
    from backend.utils import audit_logger as al
    monkeypatch.setattr(al.AuditLogger, "_db_path", str(frozen_db))
    mgr = ReviewLogManager(str(frozen_db))
    rl0, al0 = _counts(frozen_db)

    # 模拟一次"审核通过"动作的新留痕路径
    mgr.create_log(pending_id=3, achievement_type="award", submitter_type="student",
                   submitter_id=1370, reviewer_type="teacher", reviewer_id=1795,
                   action_type="approved")
    audit_log(6, 3, "award", operator={"id": 1795, "code": "1795", "user_type": "teacher"},
              change_detail={"target_table": "award"})

    rl1, al1 = _counts(frozen_db)
    assert rl1 == rl0  # 旧表停写
    assert al1 == al0 + 1  # 新表接管


def test_history_still_readable(frozen_db):
    from backend.models.review_log import ReviewLogManager
    mgr = ReviewLogManager(str(frozen_db))
    logs = mgr.query_logs(action_type="approved")
    assert len(logs) == 1
    assert logs[0].pending_id == 1
    assert len(mgr.get_recent_logs(limit=10)) == 1