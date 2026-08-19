"""M1 路径A回归：数据层 users.id 引用 + to_users_id 映射桥接。"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from tests.fixtures.schemas import USERS_DDL, PENDING_ACHIEVEMENTS_DDL as PENDING_DDL


@pytest.fixture()
def db(tmp_path):
    d = tmp_path / "m1.db"
    conn = sqlite3.connect(str(d))
    conn.execute(USERS_DDL)
    conn.execute(PENDING_DDL)
    conn.execute("INSERT INTO users (login_code, name, role) VALUES ('T001','张老师','teacher')")
    conn.execute("INSERT INTO users (login_code, name, role) VALUES ('admin','管理员','admin')")
    conn.commit()
    conn.close()
    return str(d)


class TestToUsersId:
    def test_business_code_to_users_id(self, db):
        from backend.utils.users_sync import to_users_id
        assert to_users_id(db, "T001", "teacher") == 1     # users.id 整型
        assert to_users_id(db, "admin", "admin") == 2
        assert to_users_id(db, "NOPE", "teacher") is None  # 不存在
        assert to_users_id(db, "T001", "student") is None  # role 不匹配

    def test_writes_are_users_id(self, db):
        """写入 submitter_id 必须是 users.id（数据层已统一，断言语义）。"""
        from backend.utils.users_sync import to_users_id
        uid = to_users_id(db, "T001", "teacher")
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO pending_achievements (achievement_type, achievement_data, submitter_type, submitter_id, status) "
                     "VALUES ('award','{}','teacher',?,'submit')", (uid,))
        conn.commit()
        row = conn.execute("SELECT submitter_id FROM pending_achievements").fetchone()
        conn.close()
        assert row[0] == uid and isinstance(row[0], int)   # 整型 users.id 落库


class TestRealData:
    def test_real_db_submitters_are_users_ids(self):
        """真实库：10 表 submitter_id 全部落在 users.id 内（零悬空，路径A核心）。"""
        if not (PROJECT_ROOT / "database" / "competitions.db").exists():
            pytest.skip("CI 无真实库")
        conn = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
        bad_total = 0
        for t in ("awards","patents","software_copyrights","other_files","innovation_projects",
                  "pending_achievements","review_logs","laboratory_downloads","laboratory_images","user_photos"):
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
            if "submitter_id" not in cols:
                continue
            bad = conn.execute(f"""SELECT COUNT(*) FROM {t} s
                LEFT JOIN users u ON u.id = s.submitter_id
                WHERE s.submitter_id IS NOT NULL AND u.id IS NULL""").fetchone()[0]
            bad_total += bad
        conn.close()
        assert bad_total == 0, f"存在 {bad_total} 行 submitter_id 无 users 对应"

    def test_wiring_has_imports(self):
        """6 个 admin 路由写入点已接入 to_users_id 且有 import。"""
        for f in ("admin_achievement","admin_other_files","admin_software","admin_patents",
                  "admin_innovation","admin_laboratory"):
            src = (PROJECT_ROOT / "app" / "routes" / f"{f}.py").read_text(encoding='utf-8')
            assert "to_users_id(" in src, f"{f} 未接入映射"
            assert "users_sync import to_users_id" in src, f"{f} 缺 import"
