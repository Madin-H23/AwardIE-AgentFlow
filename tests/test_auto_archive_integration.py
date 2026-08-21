"""自动归档集成测试（pytest 函数式，T31-T34 批次3 转换）。"""
import sqlite3

import pytest

from backend.models.auto_archive_config import AutoArchiveConfigManager


@pytest.fixture()
def manager(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auto_archive_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            achievement_type TEXT NOT NULL,
            validation_status TEXT,
            auto_archive_enabled BOOLEAN NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(achievement_type, validation_status)
        )
    """)
    conn.executescript("""
        INSERT OR IGNORE INTO auto_archive_config (achievement_type, validation_status, auto_archive_enabled)
        VALUES
            ('award', 'valid', 0),
            ('award', 'invalid', 0),
            ('patent', 'valid', 0),
            ('patent', 'invalid', 0),
            ('software', 'valid', 0),
            ('software', 'invalid', 0),
            ('innovation', NULL, 0),
            ('other', NULL, 0);
    """)
    conn.commit()
    conn.close()
    return AutoArchiveConfigManager(str(db_path))


# ---------- AutoArchiveConfigManager 集成 ----------

def test_initial_configs(manager):
    configs = manager.get_all_configs()
    assert len(configs) == 8
    for config in configs:
        assert not config.auto_archive_enabled


def test_update_single_config(manager):
    assert manager.update_config("award", "valid", True)
    assert manager.is_auto_archive_enabled("award", "valid")
    assert not manager.is_auto_archive_enabled("award", "invalid")


def test_batch_update(manager):
    configs = {"award": {"valid": True, "invalid": False},
               "patent": {"valid": True, "invalid": True}}
    assert manager.batch_update_configs(configs)
    assert manager.is_auto_archive_enabled("award", "valid")
    assert not manager.is_auto_archive_enabled("award", "invalid")
    assert manager.is_auto_archive_enabled("patent", "valid")
    assert manager.is_auto_archive_enabled("patent", "invalid")


def test_should_auto_archive_award_valid(manager):
    assert not manager.should_auto_archive("award", True)
    manager.update_config("award", "valid", True)
    assert manager.should_auto_archive("award", True)


def test_should_auto_archive_award_invalid(manager):
    assert not manager.should_auto_archive("award", False)
    manager.update_config("award", "invalid", True)
    assert manager.should_auto_archive("award", False)
    # valid 状态不受影响
    assert not manager.should_auto_archive("award", True)


def test_should_auto_archive_innovation(manager):
    assert not manager.should_auto_archive("innovation", True)
    assert not manager.should_auto_archive("innovation", False)
    manager.update_config("innovation", None, True)
    assert manager.should_auto_archive("innovation", True)
    assert manager.should_auto_archive("innovation", False)


def test_get_config_dict(manager):
    manager.update_config("award", "valid", True)
    manager.update_config("patent", "invalid", True)
    config_dict = manager.get_config_dict()
    assert config_dict.get("award_valid")
    assert not config_dict.get("award_invalid")
    assert not config_dict.get("patent_valid")
    assert config_dict.get("patent_invalid")


def test_reset_to_defaults(manager):
    manager.update_config("award", "valid", True)
    manager.update_config("patent", "invalid", True)
    assert manager.reset_to_defaults()
    assert not manager.is_auto_archive_enabled("award", "valid")
    assert not manager.is_auto_archive_enabled("patent", "invalid")


def test_get_stats(manager):
    manager.update_config("award", "valid", True)
    manager.update_config("patent", "invalid", True)
    stats = manager.get_stats()
    assert stats["total_configs"] == 8
    assert stats["enabled_count"] == 2
    assert stats["disabled_count"] == 6


# ---------- ReviewService 集成 ----------

def test_review_service_with_auto_archive_config(manager):
    from backend.services.review_service import ReviewService

    review_service = ReviewService(
        pending_manager=None,
        review_log_manager=None,
        laboratory_manager=None,
        student_manager=None,
        teacher_manager=None,
        auto_archive_config_manager=manager)

    assert review_service.auto_archive_config_manager is manager


def test_should_auto_archive_decision(manager):
    # 奖状
    assert not manager.should_auto_archive("award", True)
    manager.update_config("award", "valid", True)
    assert manager.should_auto_archive("award", True)
    assert not manager.should_auto_archive("award", False)
    manager.update_config("award", "invalid", True)
    assert manager.should_auto_archive("award", False)
    # 专利
    assert not manager.should_auto_archive("patent", True)
    manager.update_config("patent", "valid", True)
    assert manager.should_auto_archive("patent", True)
    # 软著
    assert not manager.should_auto_archive("software", False)
    manager.update_config("software", "invalid", True)
    assert manager.should_auto_archive("software", False)
    # 大创（不区分验证状态）
    assert not manager.should_auto_archive("innovation", True)
    manager.update_config("innovation", None, True)
    assert manager.should_auto_archive("innovation", True)
    assert manager.should_auto_archive("innovation", False)
    # 其他（不区分验证状态）
    assert not manager.should_auto_archive("other", True)
    manager.update_config("other", None, True)
    assert manager.should_auto_archive("other", True)
    assert manager.should_auto_archive("other", False)
