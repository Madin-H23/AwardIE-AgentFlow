"""FR-INIT 回归测试：种子灌入幂等 + 默认管理员创建。"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.seed import ensure_default_admin, seed_competitions

COMPETITIONS_DDL = """
CREATE TABLE competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_name TEXT, official_website TEXT, organizer TEXT,
    competition_time TEXT, participant_requirements TEXT, grade_category TEXT,
    brief_description TEXT, alias_list TEXT,
    white_list INTEGER, watch_list INTEGER, is_auto_added INTEGER
)"""
ADMINS_DDL = "CREATE TABLE admins(username TEXT PRIMARY KEY, name TEXT, password_hash TEXT, user_activated INTEGER DEFAULT 1)"


@pytest.fixture()
def empty_db(tmp_path):
    import sqlite3
    db = tmp_path / "seed.db"
    conn = sqlite3.connect(str(db))
    conn.execute(COMPETITIONS_DDL)
    conn.execute(ADMINS_DDL)
    conn.commit()
    conn.close()
    return db


def test_seed_into_empty_db(empty_db):
    n = seed_competitions(str(empty_db))
    assert n > 50, f"种子应灌入 84 条左右（实际 {n}）"
    import sqlite3
    c = sqlite3.connect(str(empty_db))
    assert c.execute("SELECT COUNT(*) FROM competitions WHERE white_list=1").fetchone()[0] == n


def test_seed_idempotent(empty_db):
    first = seed_competitions(str(empty_db))
    second = seed_competitions(str(empty_db))      # 非空跳过
    assert first > 0 and second == 0
    import sqlite3
    c = sqlite3.connect(str(empty_db))
    assert c.execute("SELECT COUNT(*) FROM competitions").fetchone()[0] == first  # 无重复


def test_default_admin_created_with_policy_password(empty_db, tmp_path):
    out = tmp_path / "admin_pwd.txt"
    pwd = ensure_default_admin(str(empty_db), out_txt=out)
    assert pwd is not None
    from app.password_policy import validate_password_strength
    assert validate_password_strength(pwd, is_admin=True)[0], "初始密码必须满足管理员策略"
    assert out.exists() and pwd in out.read_text(encoding="utf-8")
    # 可登录验证：hash 能校验通过
    import sqlite3
    from werkzeug.security import check_password_hash
    c = sqlite3.connect(str(empty_db))
    h = c.execute("SELECT password_hash FROM admins WHERE username='admin'").fetchone()[0]
    assert check_password_hash(h, pwd)


def test_default_admin_idempotent(empty_db, tmp_path):
    ensure_default_admin(str(empty_db), out_txt=tmp_path / "a.txt")
    assert ensure_default_admin(str(empty_db), out_txt=tmp_path / "b.txt") is None  # 已存在不重建


def test_seed_json_is_deploy_asset():
    """种子 JSON 必须在库内（部署资产，FR-INIT-01 依赖它）。"""
    p = PROJECT_ROOT / "database" / "seed_competitions.json"
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert len(data) >= 50 and all(r.get("white_list") == 1 for r in data)
