"""0010 迁移回归：类型规范收尾（14 表短字段 TEXT→VARCHAR/TIMESTAMP，建新替旧）。

背景：0010 是声明一致性收尾——users 时间戳、awards.submit_time、
patents/software_copyrights 短字段、audit.operator_ip 等 TEXT → 定长类型；
长文本保持 TEXT。重建前抓 sqlite_sequence、重建后恢复（防自增 id 复用）。
策略：对缺失表跳过——测试库只建代表性子集即可全逻辑覆盖。
断言：up 后类型变更正确、数据保留、sqlite_sequence 恢复、视图重建可用、行数一致；
down 为 no-op（单向改进），不报错且版本回退。
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def _alembic(db, *args):
    env = dict(os.environ)
    env["ALEMBIC_DB"] = str(db)
    r = subprocess.run(
        [sys.executable, "-m", "alembic"] + list(args),
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"alembic 失败: {r.stderr[-2000:]}"


@pytest.fixture()
def typ_db(tmp_path):
    """0009 状态库：0010 涉及的代表性表（TEXT 形态）+ 视图 + sqlite_sequence。"""
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, login_code TEXT UNIQUE,"
                 " name TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT)")
    conn.execute("CREATE TABLE awards (id INTEGER PRIMARY KEY AUTOINCREMENT, submit_time TEXT,"
                 " winner_name TEXT, extract_json TEXT)")
    conn.execute("CREATE TABLE patents (id INTEGER PRIMARY KEY AUTOINCREMENT, application_number TEXT,"
                 " patentee TEXT, description TEXT)")
    conn.execute("CREATE TABLE software_copyrights (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                 " registration_number TEXT, registration_date TEXT, source_code TEXT)")
    conn.execute("CREATE TABLE achievement_audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                 " operator_ip TEXT, change_detail TEXT)")
    # 视图（0010 先删后建）
    conn.execute("CREATE VIEW students AS SELECT id, login_code FROM users WHERE login_code LIKE '2%'")
    # 数据 + 自增计数（含"删除历史"形态：seq 大于行数）
    for i in range(2):
        conn.execute("INSERT INTO users (login_code, name) VALUES (?, 'u')", (f"2{i:06d}",))
    conn.execute("INSERT INTO awards (submit_time, winner_name) VALUES ('2026-08-21', 'x')")
    conn.execute("INSERT INTO patents (application_number, patentee) VALUES ('CN1', 'p')")
    conn.execute("INSERT INTO software_copyrights (registration_number, registration_date) VALUES ('RS1', '2026-01-01')")
    conn.execute("INSERT INTO achievement_audit_log (operator_ip, change_detail) VALUES ('10.0.0.1', '{}')")
    # 手动造 seq=1195（模拟删除历史残留）与 users seq；sqlite_sequence 无唯一索引，
    # OR REPLACE 不生效会插重复行，须先 DELETE 再 INSERT（0011 已修复重复行形态）
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('awards', 'users')")
    conn.execute("INSERT INTO sqlite_sequence VALUES ('awards', 1195)")
    conn.execute("INSERT INTO sqlite_sequence VALUES ('users', 1834)")
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('0009_audit_redundant_flag')")
    conn.commit()
    conn.close()
    return db


def _col_type(db, table, col):
    conn = sqlite3.connect(str(db))
    r = conn.execute(f"PRAGMA table_info({table})").fetchall()
    conn.close()
    for row in r:
        if row[1] == col:
            return row[2]
    return None


def _count(db, table):
    conn = sqlite3.connect(str(db))
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return n


class Test0010:
    def test_upgrade_typization_and_everything_kept(self, typ_db):
        # 升级到 head（0011_sqlite_seq_dedup 一并执行）：真实链 0010→0011 顺序，
        # 0011 修复 0010 的 sqlite_sequence 重复行缺陷后再断言 seq 恢复形态
        _alembic(typ_db, "upgrade", "0011_sqlite_seq_dedup")
        # 类型变更（区分大小写不敏感比较：SQLite 返回声明的类型原文）
        assert _col_type(typ_db, "users", "created_at").upper() == "TIMESTAMP"
        assert _col_type(typ_db, "users", "updated_at").upper() == "TIMESTAMP"
        assert _col_type(typ_db, "awards", "submit_time").upper() == "TIMESTAMP"
        assert _col_type(typ_db, "patents", "application_number").upper() == "VARCHAR(50)"
        assert _col_type(typ_db, "software_copyrights", "registration_number").upper() == "VARCHAR(50)"
        assert _col_type(typ_db, "achievement_audit_log", "operator_ip").upper() == "VARCHAR(45)"
        # 长文本保留 TEXT
        assert _col_type(typ_db, "awards", "extract_json").upper() == "TEXT"
        # 数据保持
        assert _count(typ_db, "users") == 2
        assert _count(typ_db, "awards") == 1
        assert _count(typ_db, "patents") == 1
        # 视图重建可用
        conn = sqlite3.connect(str(typ_db))
        assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 2
        # sqlite_sequence 恢复（防自增 id 复用）：0011 去重后单行 1195
        seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='awards'").fetchone()[0]
        conn.close()
        assert seq == 1195, f"awards seq 应恢复为 1195，实际 {seq}"
        # 自增延续：0010 恢复的 seq 生效（1195 后的新行 id=1196。若存在重复行，
        # 取第一条的语义与 0011 修复后一致——链上 0011 已落地则单行 1195）
        conn = sqlite3.connect(str(typ_db))
        cur = conn.execute("INSERT INTO awards (submit_time) VALUES ('2026-08-22')")
        conn.commit()
        conn.close()
        assert cur.lastrowid == 1196

    def test_downgrade_noop_and_rollback(self, typ_db):
        _alembic(typ_db, "upgrade", "0010_typization_finish")
        _alembic(typ_db, "downgrade", "0009_audit_redundant_flag")
        # down no-op：类型保持（单向改进），版本回退
        assert _col_type(typ_db, "awards", "submit_time").upper() == "TIMESTAMP"
        assert _count(typ_db, "users") == 2
        conn = sqlite3.connect(str(typ_db))
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0009_audit_redundant_flag"
        conn.close()