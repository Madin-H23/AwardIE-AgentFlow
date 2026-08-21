"""AutoArchiveConfigManager 单元测试（pytest 函数式，T31-T34 批次3 转换）。"""
import sqlite3

import pytest

from backend.models.auto_archive_config import AutoArchiveConfigManager

AUDIT_DDL = """
    CREATE TABLE IF NOT EXISTS auto_archive_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        achievement_type TEXT NOT NULL,
        validation_status TEXT,
        auto_archive_enabled BOOLEAN NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(achievement_type, validation_status)
    )
"""


@pytest.fixture()
def manager(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(AUDIT_DDL)
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


def test_initialization(manager):
    assert manager is not None
    assert len(manager.configs) == 8


def test_get_all_configs(manager):
    assert len(manager.get_all_configs()) == 8


def test_get_config_award_valid(manager):
    config = manager.get_config("award", "valid")
    assert config is not None
    assert config.achievement_type == "award"
    assert config.validation_status == "valid"
    assert not config.auto_archive_enabled


def test_get_config_innovation(manager):
    config = manager.get_config("innovation", None)
    assert config is not None
    assert config.achievement_type == "innovation"
    assert config.validation_status is None
    assert not config.auto_archive_enabled


def test_get_config_not_found(manager):
    assert manager.get_config("unknown", "valid") is None


def test_update_config(manager):
    assert manager.update_config("award", "valid", True)
    assert manager.get_config("award", "valid").auto_archive_enabled


def test_is_auto_archive_enabled(manager):
    assert not manager.is_auto_archive_enabled("award", "valid")
    manager.update_config("award", "valid", True)
    assert manager.is_auto_archive_enabled("award", "valid")


def test_should_auto_archive_award_valid(manager):
    assert not manager.should_auto_archive("award", True)
    manager.update_config("award", "valid", True)
    assert manager.should_auto_archive("award", True)


def test_should_auto_archive_award_invalid(manager):
    assert not manager.should_auto_archive("award", False)
    manager.update_config("award", "invalid", True)
    assert manager.should_auto_archive("award", False)


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


def test_batch_update_configs(manager):
    configs = {"award": {"valid": True, "invalid": False},
               "patent": {"valid": True, "invalid": True}}
    assert manager.batch_update_configs(configs)
    assert manager.is_auto_archive_enabled("award", "valid")
    assert not manager.is_auto_archive_enabled("award", "invalid")
    assert manager.is_auto_archive_enabled("patent", "valid")
    assert manager.is_auto_archive_enabled("patent", "invalid")


def test_reset_to_defaults(manager):
    manager.update_config("award", "valid", True)
    manager.update_config("patent", "invalid", True)
    assert manager.reset_to_defaults()
    assert not manager.is_auto_archive_enabled("award", "valid")
    assert not manager.is_auto_archive_enabled("patent", "invalid")
    for config in manager.configs:
        assert not config.auto_archive_enabled


def test_get_stats(manager):
    manager.update_config("award", "valid", True)
    manager.update_config("patent", "invalid", True)
    stats = manager.get_stats()
    assert stats["total_configs"] == 8
    assert stats["enabled_count"] == 2
    assert stats["disabled_count"] == 6
    assert "by_type" in stats


def test_get_validation_status_for_achievement(manager):
    for t in ("award", "patent", "software"):
        assert manager.get_validation_status_for_achievement(t, True) == "valid"
        assert manager.get_validation_status_for_achievement(t, False) == "invalid"
    assert manager.get_validation_status_for_achievement("innovation", True) is None
    assert manager.get_validation_status_for_achievement("innovation", False) is None
    assert manager.get_validation_status_for_achievement("other", True) is None
    assert manager.get_validation_status_for_achievement("other", False) is None
