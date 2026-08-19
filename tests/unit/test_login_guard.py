"""P2-25 登录失败锁定单元测试（backend/utils/login_guard.py）。

验证：账号连续失败达阈值锁定 → 锁定期间拒绝 → 登录成功解锁；IP 维度限流独立。
"""
import sqlite3
from datetime import timedelta

import pytest

from backend.utils.login_guard import (
    ACCOUNT_MAX_FAIL, check_login_allowed, record_login_failure,
    record_login_success,
)


@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "login.db")


def _table_count(db):
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM failed_logins").fetchone()[0]
    conn.close()
    return n


class TestAccountLock:
    def test_allowed_before_threshold(self, db):
        for _ in range(ACCOUNT_MAX_FAIL - 1):
            record_login_failure(db, "admin", "10.0.0.1")
            assert check_login_allowed(db, "admin", "10.0.0.1") == (True, None)

    def test_locked_after_threshold(self, db):
        for _ in range(ACCOUNT_MAX_FAIL):
            record_login_failure(db, "admin", "10.0.0.1")
        allowed, retry = check_login_allowed(db, "admin", "10.0.0.1")
        assert allowed is False
        assert retry is not None and retry > 0

    def test_lock_is_per_account(self, db):
        """账号 A 锁定不影响账号 B。"""
        for _ in range(ACCOUNT_MAX_FAIL):
            record_login_failure(db, "admin", "10.0.0.1")
        assert check_login_allowed(db, "student1", "10.0.0.1")[0] is True

    def test_success_clears_lock(self, db):
        for _ in range(ACCOUNT_MAX_FAIL):
            record_login_failure(db, "admin", "10.0.0.1")
        assert check_login_allowed(db, "admin", "10.0.0.1")[0] is False
        record_login_success(db, "admin", "10.0.0.1")
        assert check_login_allowed(db, "admin", "10.0.0.1")[0] is True

    def test_failure_cleared_by_success(self, db):
        """登录成功清空计数：连续 4 次失败后成功，再失败不锁定（计数重置）。"""
        for _ in range(ACCOUNT_MAX_FAIL - 1):
            record_login_failure(db, "s1", "10.0.0.2")
        record_login_success(db, "s1", "10.0.0.2")
        record_login_failure(db, "s1", "10.0.0.2")
        assert check_login_allowed(db, "s1", "10.0.0.2")[0] is True


class TestIpLock:
    def test_ip_threshold_independent(self, db):
        """IP 维度：不同账号同 IP 累计失败触发 IP 锁定。"""
        for i in range(5):  # 每账号 1 次，5 账号同 IP
            record_login_failure(db, f"user{i}", "10.0.0.99")
        # 账号维度未达阈值（各 1 次），IP 维度已达 5 次但阈值 10
        assert check_login_allowed(db, "user0", "10.0.0.99")[0] is True
        for i in range(5):
            record_login_failure(db, f"user{i}", "10.0.0.99")
        # 同 IP 累计 10 次 → IP 锁定
        allowed, retry = check_login_allowed(db, "fresh_user", "10.0.0.99")
        assert allowed is False and retry > 0
