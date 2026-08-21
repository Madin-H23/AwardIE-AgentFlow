"""T61 修复测试：PendingAchievementManager.reload_from_db 读库刷新。

背景：异步自动归档线程读内存缓存可能陈旧（多 worker/并发直连写库后），
曾致教师奖状入库时 granted_role 偶发旧值'学生'。reload_from_db 强制回源
DB 并替换缓存，后续 approve_single 内部 get_pending_by_id 读到一致新数据。
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fixtures.schemas import PENDING_ACHIEVEMENTS_DDL  # noqa: E402

from backend.models.pending_achievement import (  # noqa: E402
    PendingAchievementManager,
)


@pytest.fixture()
def manager(tmp_path):
    """临时库上的 PendingAchievementManager（共享 DDL，不依赖真实库）。"""
    db_path = tmp_path / "pending_reload.db"
    conn = sqlite3.connect(db_path)
    conn.execute(PENDING_ACHIEVEMENTS_DDL)
    conn.commit()
    conn.close()
    return PendingAchievementManager(str(db_path))


def _insert_row(conn, pending_id, granted_role, status="submit"):
    conn.execute(
        "INSERT INTO pending_achievements (id, achievement_type, achievement_data,"
        " status, file_hash) VALUES (?, ?, ?, ?, '')",
        (pending_id, "award", json.dumps({"granted_role": granted_role}), status),
    )
    conn.commit()


def _fetch_granted_role(conn):
    row = conn.execute("SELECT achievement_data FROM pending_achievements WHERE id = 1")
    return json.loads(row.fetchone()[0])["granted_role"]


def test_reload_from_db_returns_fresh_data_and_replaces_cache(manager):
    """缓存陈旧（'学生'）而 DB 已是'教师'时，reload 返回新值且缓存被替换。"""
    # 初始：直连插入后先 reload 让缓存就位（与库一致为'学生'）
    _insert_row(manager._get_db_connection(), 1, "学生")
    assert manager.reload_from_db(1).get_achievement_data()["granted_role"] == "学生"

    # 模拟他进程/线程直连写库：granted_role 改为'教师'，Manager 缓存不知情
    conn = manager._get_db_connection()
    conn.execute(
        "UPDATE pending_achievements SET achievement_data = ? WHERE id = 1",
        (json.dumps({"granted_role": "教师"}),),
    )
    conn.commit()
    conn.close()
    # 缓存仍是旧值（复现 T61 症状）
    assert manager.get_pending_by_id(1).get_achievement_data()["granted_role"] == "学生"

    fresh = manager.reload_from_db(1)
    assert fresh is not None
    assert fresh.get_achievement_data()["granted_role"] == "教师"
    # 缓存对象已被替换——后续 get_pending_by_id 读到一致新值
    assert manager.get_pending_by_id(1).get_achievement_data()["granted_role"] == "教师"
    assert fresh.id == 1


def test_reload_missing_record_removes_from_cache_and_returns_none(manager):
    """记录被并发删除后 reload 返回 None 且缓存在剔除。"""
    _insert_row(manager._get_db_connection(), 1, "学生")
    assert manager.reload_from_db(1) is not None  # 缓存就位
    assert manager.get_pending_by_id(1) is not None

    conn = manager._get_db_connection()
    conn.execute("DELETE FROM pending_achievements WHERE id = 1")
    conn.commit()
    conn.close()

    assert manager.reload_from_db(1) is None
    assert manager.get_pending_by_id(1) is None


def test_reload_cache_miss_append_keeps_visible(manager):
    """缓存未命中（他进程新建）时 reload 补入缓存，get_pending_by_id 可见。"""
    _insert_row(manager._get_db_connection(), 1, "学生")
    assert manager.get_pending_by_id(1) is None  # 新记录未在缓存（直连插入绕过 Manager）

    fresh = manager.reload_from_db(1)
    assert fresh is not None
    assert manager.get_pending_by_id(1).id == 1


def test_async_auto_archive_uses_reload_from_db(monkeypatch):
    """_auto_archive_pending_async 必须走 pending_manager.reload_from_db（T61 修复点）而非缓存读。"""
    from backend.services.review_service import ReviewService

    svc = ReviewService.__new__(ReviewService)
    called = {}

    class FakePendingManager:
        def reload_from_db(self, pending_id):
            called["reloaded"] = pending_id
            return None  # 第一次：记录不存在，直接 return

        def get_pending_by_id(self, pending_id):
            called["cache_read"] = pending_id  # 若被调用即为回归（证明未走读库）

    svc.pending_manager = FakePendingManager()

    def fake_approve(pending_id, reviewer, force=False):
        called["approved"] = pending_id
        return type(
            "R", (), {"success": True, "target_id": 7, "action": "approved", "error": None}
        )()

    monkeypatch.setattr(svc, "approve_single", fake_approve)

    # reload 返回 None（记录已不存在）时应直接 return，不进入 approve_single
    svc._auto_archive_pending_async(123)
    assert called == {"reloaded": 123}
    assert "cache_read" not in called

    # reload 返回记录时应继续 approve_single
    class FakePending:
        id = 123
        achievement_type = "award"

    class FakePendingManager2(FakePendingManager):
        def reload_from_db(self, pending_id):
            called["reloaded"] = pending_id
            return FakePending()

    svc.pending_manager = FakePendingManager2()
    svc._auto_archive_pending_async(123)
    assert called["approved"] == 123
    assert "cache_read" not in called