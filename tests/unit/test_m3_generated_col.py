"""M3 起点回归：pending is_valid 生成列 + 索引（JSON 高频字段提列）。"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def _real_db():
    from tests.fixtures.schemas import require_real_db
    require_real_db()   # R-028 升级：文件存在且 users 表存在，否则 skip
    return PROJECT_ROOT / "database" / "competitions.db"


class TestGeneratedColumn:
    def test_is_valid_column_exists_and_auto(self):
        """is_valid 生成列存在，且由 validation_result 自动推导（含更新跟随）。"""
        db = _real_db()
        conn = sqlite3.connect(str(db))
        # SQLite 生成列不在 table_info（只显示普通列），须查 table_xinfo
        cols = [r[1] for r in conn.execute("PRAGMA table_xinfo(pending_achievements)")]
        assert "is_valid" in cols, "is_valid 生成列缺失"
        # 且确认它是生成列（hidden=2 表示 VIRTUAL 生成列）
        gen = conn.execute("PRAGMA table_xinfo(pending_achievements)").fetchall()
        gen_col = [r for r in gen if r[1] == "is_valid"][0]
        # xinfo: (cid,name,type,notnull,dflt,pk,hidden)——hidden 在索引 6
        assert gen_col[6] == 2, f"is_valid 应为 VIRTUAL 生成列(hidden=2)，实际 hidden={gen_col[6]}"
        # 生成列自动推导（含更新跟随）：自建临时行驱动，不依赖真库数据形态
        vr_a = '{"is_valid": true, "reason": "t75"}'
        vr_b = '{"is_valid": false, "reason": "t75-update"}'
        conn.execute(
            """INSERT INTO pending_achievements
               (achievement_type, achievement_data, status, submitter_type,
                submitter_id, file_hash, session_id, validation_result)
               VALUES ('award', '{"t": "m3-probe"}', 'pending', 'admin',
                       1, 'hash-m3-probe', 'm3-session', ?)""",
            (vr_a,))
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        try:
            row = conn.execute(
                "SELECT is_valid, json_extract(validation_result,'$.is_valid') "
                "FROM pending_achievements WHERE id=?", (pid,)).fetchone()
            assert row == (1, True), f"生成列初值不一致: {row}"
            # 更新跟随：validation_result 变更后生成列同步
            conn.execute("UPDATE pending_achievements SET validation_result=? WHERE id=?",
                         (vr_b.replace("false", "true").replace("true", "false"), pid))
            row = conn.execute("SELECT is_valid FROM pending_achievements WHERE id=?", (pid,)).fetchone()
            assert row[0] in (0, False), f"更新后生成列未跟随: {row}"
        finally:
            conn.execute("DELETE FROM pending_achievements WHERE id=?", (pid,))
            conn.commit()
        conn.close()

    def test_index_present(self):
        db = _real_db()
        conn = sqlite3.connect(str(db))
        idx = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_pending_is_valid'").fetchone()
        conn.close()
        assert idx, "idx_pending_is_valid 索引缺失"

    def test_generated_auto_follows_update(self, tmp_path):
        """VIRTUAL 生成列在 validation_result 更新后自动跟随。"""
        from tests.fixtures.schemas import PENDING_ACHIEVEMENTS_DDL as DDL
        db = tmp_path / "g.db"
        conn = sqlite3.connect(str(db))
        conn.execute(DDL)   # 共享 DDL 已含 is_valid 生成列（2026-08-19 同步）
        conn.execute("INSERT INTO pending_achievements (achievement_type, achievement_data, validation_result, status) "
                     "VALUES ('award','{}','{\"is_valid\": false}','pending')")
        conn.commit()
        assert conn.execute("SELECT is_valid FROM pending_achievements").fetchone()[0] == 0
        conn.execute("UPDATE pending_achievements SET validation_result='{\"is_valid\": true}'")
        conn.commit()
        assert conn.execute("SELECT is_valid FROM pending_achievements").fetchone()[0] == 1   # 自动跟随
        conn.close()

    def test_idempotency_table_in_prod(self):
        """生产主库 idempotency_keys 已建（幂等护栏落地）。"""
        db = _real_db()
        conn = sqlite3.connect(str(db))
        t = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='idempotency_keys'").fetchone()
        conn.close()
        assert t, "生产 idempotency_keys 表缺失"
