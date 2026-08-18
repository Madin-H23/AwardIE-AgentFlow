"""阶段三批G回归：audit_log 补齐动作 9/10/11（源码接线断言 + 端到端落库）。"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestWiring:
    def test_withdraw_wired_both(self):
        for f in ("app/routes/student.py", "app/routes/teacher.py"):
            src = (PROJECT_ROOT / f).read_text(encoding='utf-8')
            assert "audit_log(11," in src, f"{f} 撤回未留痕"

    def test_discard_wired_both(self):
        for f in ("app/routes/student.py", "app/routes/teacher.py"):
            src = (PROJECT_ROOT / f).read_text(encoding='utf-8')
            assert "audit_log(10," in src, f"{f} 放弃未留痕"

    def test_modify_field_diff_wired(self):
        src = (PROJECT_ROOT / "backend" / "services" / "review_service.py").read_text(encoding='utf-8')
        assert "audit_log(9," in src and '"old"' in src and '"new"' in src


class TestEndToEnd:
    def test_withdraw_writes_audit(self, tmp_path, monkeypatch):
        """端到端：撤回动作落 audit_log（临时库）。"""
        db = tmp_path / "a.db"
        real = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
        ddl_p = real.execute("SELECT sql FROM sqlite_master WHERE name='pending_achievements'").fetchone()[0]
        ddl_a = real.execute("SELECT sql FROM sqlite_master WHERE name='achievement_audit_log'").fetchone()[0]
        real.close()
        conn = sqlite3.connect(str(db))
        conn.execute(ddl_p)
        conn.execute(ddl_a)
        conn.execute("INSERT INTO pending_achievements (achievement_type, achievement_data, submitter_type, submitter_id, status) "
                     "VALUES ('award','{}','student',7,'submit')")
        conn.commit()
        conn.close()

        from backend.utils.audit_logger import AuditLogger
        AuditLogger._db_path = str(db)

        # 直调 audit_log 模拟撤回接线（路由层已被源码断言覆盖）
        from backend.utils.audit_logger import audit_log
        assert audit_log(11, 1, "award", operator={"id": 7, "code": "20230001", "user_type": "student"}) is True
        c = sqlite3.connect(str(db))
        row = c.execute("SELECT action_type, operator_role FROM achievement_audit_log").fetchone()
        c.close()
        assert row == (11, 1)

    def test_modify_diff_payload_shape(self, tmp_path):
        """动作9 的 change_detail 结构（field/old/new）。"""
        import json
        db = tmp_path / "b.db"
        real = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
        ddl_a = real.execute("SELECT sql FROM sqlite_master WHERE name='achievement_audit_log'").fetchone()[0]
        real.close()
        conn = sqlite3.connect(str(db))
        conn.execute(ddl_a)
        conn.commit()
        conn.close()
        from backend.utils.audit_logger import AuditLogger
        AuditLogger._db_path = str(db)
        from backend.utils.audit_logger import audit_log
        audit_log(9, 1, "award", operator="AI",
                  change_detail={"field": "award_level", "old": "省级", "new": "国家级"})
        c = sqlite3.connect(str(db))
        detail = json.loads(c.execute("SELECT change_detail FROM achievement_audit_log").fetchone()[0])
        c.close()
        assert detail == {"field": "award_level", "old": "省级", "new": "国家级"}


def test_action_coverage_now_9_of_11():
    """当前已接线动作集合（1/2/6/7/8/9/10/11）——动作5(复核查看)语义价值低暂缓，标注于案。"""
    wired = set()
    for f in ("app/routes/student.py", "app/routes/teacher.py",
              "app/routes/admin_review.py", "backend/services/review_service.py"):
        src = (PROJECT_ROOT / f).read_text(encoding='utf-8')
        for n in (1, 2, 5, 6, 7, 8, 9, 10, 11):
            if f"audit_log({n}," in src:
                wired.add(n)
    assert {1, 2, 6, 7, 8, 9, 10, 11} <= wired
    assert 5 not in wired      # 暂缓（查看动作无决策价值）
