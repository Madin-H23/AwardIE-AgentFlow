"""审核留痕操作人/动作展示解析回归（M1 后 users.id 快照 → 学号+姓名）：
- AuditLogger._resolve_operator：dict 传 users.id（code=数字且无 name）→ 解析 login_code+name 快照
- LogQueryService.query_audit_logs：行加工 action_label 中文 + operator_display（数字历史数据解析）
- 容错：无 users 表/未命中不抛、非数字快照原样保留
"""
import sqlite3

import pytest

from backend.utils.audit_logger import AuditLogger
from backend.services.log_query_service import LogQueryService

AUDIT_DDL = """
CREATE TABLE achievement_audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  achievement_id INTEGER, achievement_kind TEXT, trace_id TEXT,
  action_type INTEGER CHECK(action_type BETWEEN 1 AND 12), action_result INTEGER,
  operator_id INTEGER, operator_code TEXT, operator_name TEXT, operator_role INTEGER,
  ai_batch_id TEXT, change_detail TEXT, remark TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
"""
USERS_DDL = "CREATE TABLE users (id INTEGER PRIMARY KEY, login_code TEXT, name TEXT)"


@pytest.fixture
def db(tmp_path):
    p = str(tmp_path / "audit_disp.db")
    conn = sqlite3.connect(p)
    conn.execute(AUDIT_DDL)
    conn.execute(USERS_DDL)
    conn.execute("INSERT INTO users (id, login_code, name) VALUES (1370, '212306413', '陈品天')")
    conn.execute("INSERT INTO users (id, login_code, name) VALUES (2, '02114818', '王老师')")
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def audit_path(db, monkeypatch):
    old = AuditLogger._db_path
    AuditLogger._db_path = db
    yield db
    AuditLogger._db_path = old


def test_resolve_users_id_to_login_code_and_name(audit_path):
    op = AuditLogger._resolve_operator({"id": 1370, "code": "1370", "user_type": "student"})
    assert op["code"] == "212306413"
    assert op["name"] == "陈品天"
    assert op["role"] == 1


def test_resolve_keeps_explicit_name(audit_path):
    op = AuditLogger._resolve_operator({"id": 1, "code": "admin", "name": "管理员", "role": 4})
    assert op["name"] == "管理员" and op["code"] == "admin"


def test_resolve_tolerates_missing_users_table(tmp_path, monkeypatch):
    p = str(tmp_path / "empty.db")
    sqlite3.connect(p).close()
    old = AuditLogger._db_path
    AuditLogger._db_path = p
    try:
        op = AuditLogger._resolve_operator({"id": 999, "code": "999", "user_type": "student"})
        assert op["code"] == "999" and op["name"] == "999"   # 回退原快照，不抛
    finally:
        AuditLogger._db_path = old


def _insert_audit(db, **kw):
    conn = sqlite3.connect(db)
    cols = {"achievement_id": 3709, "achievement_kind": "award", "action_type": 1,
            "operator_name": kw.pop("operator_name", "1370"), "operator_role": 1}
    cols.update(kw)
    keys = ",".join(cols)
    conn.execute(f"INSERT INTO achievement_audit_log ({keys}) VALUES ({','.join('?' * len(cols))})",
                 tuple(cols.values()))
    conn.commit()
    conn.close()


def test_query_audit_logs_labels_and_display(db):
    _insert_audit(db, operator_name="1370", action_type=1)          # 历史：users.id 数字
    _insert_audit(db, operator_name="AI智能审核", action_type=2)     # AI 快照：非数字
    result = LogQueryService.query_audit_logs(db_path=db, per_page=10)
    items = {it["operator_name"]: it for it in result["items"]}
    assert items["1370"]["action_label"] == "提交"
    assert items["1370"]["operator_display"] == "212306413 陈品天"
    assert items["AI智能审核"]["action_label"] == "AI 审核"
    assert items["AI智能审核"]["operator_display"] == "AI智能审核"



def test_query_audit_logs_created_at_local(db):
    # 库内即应用本地时间：写入走 _local_now_str，查询不再转换
    import sqlite3
    from datetime import datetime
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO achievement_audit_log (achievement_id, achievement_kind, action_type,"
        " operator_name, operator_role, created_at) VALUES (1194,'award',8,'2',2,'2026-08-21 06:55:51')")
    conn.commit(); conn.close()
    r = LogQueryService.query_audit_logs(db_path=db, per_page=5)
    it = [x for x in r["items"] if x["action_type"] == 8][0]
    assert it["created_at"] == "2026-08-21 06:55:51"           # 原样返回，无任何时区转换

def test_audit_log_writes_local_time(audit_path):
    import sqlite3
    from datetime import datetime
    assert AuditLogger.log(6, 999, "award", operator={"id": 2, "code": "2", "user_type": "teacher"})
    conn = sqlite3.connect(audit_path)
    row = conn.execute("SELECT created_at FROM achievement_audit_log WHERE achievement_id=999").fetchone()
    conn.close()
    assert row is not None
    assert abs((datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") - datetime.now()).total_seconds()) < 30


def test_resolve_display_names_by_login_code(db):
    # 历史快照存业务号(02114818 教师 users.id=1794 不在现有集合) → login_code 兜底命中
    import sqlite3
    conn = sqlite3.connect(db)
    r = AuditLogger.resolve_display_names(conn, {"02114818", "1370"})
    conn.close()
    assert r["1370"] == "212306413 陈品天"           # 按 id
    assert r["02114818"] == "02114818 王老师"        # 按 login_code 兜底


def test_query_audit_logs_teacher_name_via_login_code(db):
    _insert_audit(db, operator_name="02114818", operator_role=2, action_type=8)
    r = LogQueryService.query_audit_logs(db_path=db, per_page=10)
    it = [x for x in r["items"] if x["operator_name"] == "02114818"][0]
    assert it["operator_display"] == "02114818 王老师"


def test_action12_delete_label_and_display(audit_path):
    db = audit_path
    # 成果删除(动作12)：写入成功 + 中文标签 + 操作人展示
    assert AuditLogger.log(12, 1194, "award",
                           operator={"id": 1794, "code": "02114818", "user_type": "teacher"},
                           remark="成果删除")
    r = LogQueryService.query_audit_logs(db_path=db, per_page=10)
    it = [x for x in r["items"] if x["action_type"] == 12][0]
    assert it["action_label"] == "成果删除"
    assert it["operator_display"] == "02114818 王老师"
    assert it["remark"] == "成果删除"
