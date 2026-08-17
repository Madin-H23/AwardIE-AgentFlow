"""
Auto Archive Config Management Module

Manages auto-archive configuration for different achievement types and validation statuses.
自动归档配置管理模块。
"""
import sqlite3
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class AutoArchiveConfig:
    """Auto Archive Configuration data model"""
    id: Optional[int] = None
    achievement_type: str = ""  # 'award', 'patent', 'software', 'innovation', 'other'
    validation_status: Optional[str] = None  # 'valid', 'invalid' (NULL for innovation/other)
    auto_archive_enabled: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __str__(self) -> str:
        """String representation"""
        status_str = self.validation_status or "all"
        return f"{self.achievement_type}/{status_str}: {self.auto_archive_enabled}"


class AutoArchiveConfigManager:
    """Manages auto-archive configuration data operations"""

    def __init__(self, db_path: str):
        """
        Initialize AutoArchiveConfigManager

        Args:
            db_path: Database file path
        """
        self.db_path = db_path
        self.configs: List[AutoArchiveConfig] = []
        self._load_all_from_db()
        logger.info(f"AutoArchiveConfigManager initialized with db_path: {self.db_path}")

    def _get_db_connection(self):
        """Get database connection"""
        from backend.utils.db_connection import get_connection

        return get_connection(self.db_path)
        return conn

    def _load_all_from_db(self):
        """Load all configs from database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM auto_archive_config ORDER BY achievement_type, validation_status")
            rows = cursor.fetchall()
            conn.close()

            self.configs = [self._row_to_config(row) for row in rows]
            logger.info(f"Loaded {len(self.configs)} auto-archive configs from database")
        except Exception as e:
            logger.error(f"Failed to load auto-archive configs: {e}")
            self.configs = []

    def _row_to_config(self, row: sqlite3.Row) -> AutoArchiveConfig:
        """Convert database row to AutoArchiveConfig object"""
        data = dict(row)
        # Convert INTEGER to BOOLEAN for auto_archive_enabled
        if 'auto_archive_enabled' in data:
            data['auto_archive_enabled'] = bool(data['auto_archive_enabled'])
        return AutoArchiveConfig(**data)

    def get_all_configs(self) -> List[AutoArchiveConfig]:
        """
        获取所有配置

        Returns:
            所有配置列表
        """
        return list(self.configs)

    def get_config(
        self,
        achievement_type: str,
        validation_status: Optional[str] = None
    ) -> Optional[AutoArchiveConfig]:
        """
        获取指定类型和验证状态的配置

        Args:
            achievement_type: 成果类型 ('award', 'patent', 'software', 'innovation', 'other')
            validation_status: 验证状态 ('valid', 'invalid')，大创/其他为 None

        Returns:
            配置对象，如果未找到则返回 None
        """
        for config in self.configs:
            if config.achievement_type == achievement_type and config.validation_status == validation_status:
                return config
        return None

    def is_auto_archive_enabled(
        self,
        achievement_type: str,
        validation_status: Optional[str] = None
    ) -> bool:
        """
        判断指定类型和验证状态是否启用自动归档

        Args:
            achievement_type: 成果类型
            validation_status: 验证状态

        Returns:
            是否启用自动归档，默认为 False
        """
        config = self.get_config(achievement_type, validation_status)
        return config.auto_archive_enabled if config else False

    def update_config(
        self,
        achievement_type: str,
        validation_status: Optional[str],
        auto_archive_enabled: bool
    ) -> bool:
        """
        更新配置

        Args:
            achievement_type: 成果类型
            validation_status: 验证状态
            auto_archive_enabled: 是否启用自动归档

        Returns:
            是否成功
        """
        config = self.get_config(achievement_type, validation_status)
        if not config:
            logger.warning(f"找不到配置: {achievement_type}/{validation_status}")
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE auto_archive_config
                SET auto_archive_enabled = ?
                WHERE achievement_type = ? AND validation_status IS ?
            """, (1 if auto_archive_enabled else 0, achievement_type, validation_status))

            conn.commit()
            conn.close()

            # 更新内存对象（无需重新加载，因为已经更新了）
            config.auto_archive_enabled = auto_archive_enabled
            logger.info(f"更新配置: {achievement_type}/{validation_status} -> {auto_archive_enabled}")
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"更新配置失败: {e}")
            return False

    def batch_update_configs(self, configs: Dict[str, Dict[str, bool]]) -> bool:
        """
        批量更新配置

        Args:
            configs: 配置字典，格式:
                {
                    'award': {'valid': True, 'invalid': False},
                    'patent': {'valid': False, 'invalid': False},
                    'software': {'valid': True, 'invalid': False},
                    'innovation': {None: False},
                    'other': {None: False}
                }

        Returns:
            是否全部成功
        """
        all_success = True
        for achievement_type, status_configs in configs.items():
            for validation_status, enabled in status_configs.items():
                if not self.update_config(achievement_type, validation_status, enabled):
                    all_success = False
        return all_success

    def get_config_dict(self) -> Dict[str, Dict[str, bool]]:
        """
        获取配置字典（用于 API 返回）

        Returns:
            配置字典，格式:
            {
                'award_valid': True,
                'award_invalid': False,
                'patent_valid': False,
                ...
            }
        """
        result = {}
        for config in self.configs:
            # 构建键名，如 'award_valid', 'innovation'（无状态）
            if config.validation_status:
                key = f"{config.achievement_type}_{config.validation_status}"
            else:
                key = config.achievement_type
            result[key] = config.auto_archive_enabled
        return result

    def should_auto_archive(
        self,
        achievement_type: str,
        is_valid: bool
    ) -> bool:
        """
        判断是否应该自动归档

        根据成果类型和验证状态判断是否启用自动归档。
        对于奖状/专利/软著，区分 valid 和 invalid 状态。
        对于大创/其他，不区分验证状态。

        Args:
            achievement_type: 成果类型
            is_valid: 是否通过验证

        Returns:
            是否应该自动归档
        """
        # 奖状/专利/软著：区分验证状态
        if achievement_type in ('award', 'patent', 'software'):
            validation_status = 'valid' if is_valid else 'invalid'
            return self.is_auto_archive_enabled(achievement_type, validation_status)

        # 大创/其他：不区分验证状态
        if achievement_type in ('innovation', 'other'):
            return self.is_auto_archive_enabled(achievement_type, None)

        # 默认不自动归档
        return False

    def get_validation_status_for_achievement(
        self,
        achievement_type: str,
        is_valid: bool
    ) -> Optional[str]:
        """
        获取成果的验证状态（用于查询配置）

        Args:
            achievement_type: 成果类型
            is_valid: 是否通过验证

        Returns:
            验证状态字符串，或不区分状态时返回 None
        """
        if achievement_type in ('award', 'patent', 'software'):
            return 'valid' if is_valid else 'invalid'
        return None

    def reset_to_defaults(self) -> bool:
        """
        重置所有配置为默认值（全部不自动归档）

        Returns:
            是否成功
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE auto_archive_config
                SET auto_archive_enabled = 0
            """)
            conn.commit()
            conn.close()

            # 重新加载数据
            self._load_all_from_db()
            logger.info("重置所有配置为默认值")
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"重置配置失败: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取配置统计信息

        Returns:
            统计信息字典
        """
        total = len(self.configs)
        enabled = sum(1 for c in self.configs if c.auto_archive_enabled)

        # 按类型统计
        by_type = {}
        for config in self.configs:
            if config.achievement_type not in by_type:
                by_type[config.achievement_type] = {'total': 0, 'enabled': 0}
            by_type[config.achievement_type]['total'] += 1
            if config.auto_archive_enabled:
                by_type[config.achievement_type]['enabled'] += 1

        return {
            'total_configs': total,
            'enabled_count': enabled,
            'disabled_count': total - enabled,
            'by_type': by_type
        }
