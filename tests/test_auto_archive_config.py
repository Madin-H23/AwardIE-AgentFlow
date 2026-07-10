"""
Auto Archive Config Manager 单元测试

测试自动归档配置管理模块的功能。
"""
import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.models.auto_archive_config import AutoArchiveConfigManager, AutoArchiveConfig


class TestAutoArchiveConfigManager(unittest.TestCase):
    """AutoArchiveConfigManager 单元测试"""

    def setUp(self):
        """测试前准备：创建临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test.db")

        # 创建表结构
        import sqlite3
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()

        # 创建 auto_archive_config 表
        cursor.execute("""
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

        # 插入初始数据
        cursor.executescript("""
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

        # 初始化 Manager
        self.manager = AutoArchiveConfigManager(self.test_db_path)

    def tearDown(self):
        """测试后清理：删除临时数据库"""
        shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.manager)
        self.assertEqual(len(self.manager.configs), 8)  # 8条初始配置

    def test_get_all_configs(self):
        """测试获取所有配置"""
        configs = self.manager.get_all_configs()
        self.assertEqual(len(configs), 8)

    def test_get_config_award_valid(self):
        """测试获取奖状-验证通过配置"""
        config = self.manager.get_config('award', 'valid')
        self.assertIsNotNone(config)
        self.assertEqual(config.achievement_type, 'award')
        self.assertEqual(config.validation_status, 'valid')
        self.assertFalse(config.auto_archive_enabled)

    def test_get_config_innovation(self):
        """测试获取大创配置（无验证状态）"""
        config = self.manager.get_config('innovation', None)
        self.assertIsNotNone(config)
        self.assertEqual(config.achievement_type, 'innovation')
        self.assertIsNone(config.validation_status)
        self.assertFalse(config.auto_archive_enabled)

    def test_get_config_not_found(self):
        """测试获取不存在的配置"""
        config = self.manager.get_config('unknown', 'valid')
        self.assertIsNone(config)

    def test_update_config(self):
        """测试更新配置"""
        # 启用奖状-验证通过的自动归档
        result = self.manager.update_config('award', 'valid', True)
        self.assertTrue(result)

        # 验证更新成功
        config = self.manager.get_config('award', 'valid')
        self.assertTrue(config.auto_archive_enabled)

    def test_is_auto_archive_enabled(self):
        """测试判断是否启用自动归档"""
        # 默认不启用
        self.assertFalse(self.manager.is_auto_archive_enabled('award', 'valid'))

        # 启用后判断
        self.manager.update_config('award', 'valid', True)
        self.assertTrue(self.manager.is_auto_archive_enabled('award', 'valid'))

    def test_should_auto_archive_award_valid(self):
        """测试奖状-验证通过的自动归档判断"""
        # 默认不自动归档
        self.assertFalse(self.manager.should_auto_archive('award', True))

        # 启用后自动归档
        self.manager.update_config('award', 'valid', True)
        self.assertTrue(self.manager.should_auto_archive('award', True))

    def test_should_auto_archive_award_invalid(self):
        """测试奖状-验证失败的自动归档判断"""
        # 默认不自动归档
        self.assertFalse(self.manager.should_auto_archive('award', False))

        # 启用 invalid 状态
        self.manager.update_config('award', 'invalid', True)
        self.assertTrue(self.manager.should_auto_archive('award', False))

    def test_should_auto_archive_innovation(self):
        """测试大创的自动归档判断（不区分验证状态）"""
        # 默认不自动归档
        self.assertFalse(self.manager.should_auto_archive('innovation', True))
        self.assertFalse(self.manager.should_auto_archive('innovation', False))

        # 启用后，两种状态都自动归档
        self.manager.update_config('innovation', None, True)
        self.assertTrue(self.manager.should_auto_archive('innovation', True))
        self.assertTrue(self.manager.should_auto_archive('innovation', False))

    def test_get_config_dict(self):
        """测试获取配置字典"""
        # 更新一些配置
        self.manager.update_config('award', 'valid', True)
        self.manager.update_config('patent', 'invalid', True)

        config_dict = self.manager.get_config_dict()

        # 验证字典内容
        self.assertTrue(config_dict.get('award_valid'))
        self.assertFalse(config_dict.get('award_invalid'))
        self.assertFalse(config_dict.get('patent_valid'))
        self.assertTrue(config_dict.get('patent_invalid'))

    def test_batch_update_configs(self):
        """测试批量更新配置"""
        configs = {
            'award': {'valid': True, 'invalid': False},
            'patent': {'valid': True, 'invalid': True},
        }

        result = self.manager.batch_update_configs(configs)
        self.assertTrue(result)

        # 验证更新成功
        self.assertTrue(self.manager.is_auto_archive_enabled('award', 'valid'))
        self.assertFalse(self.manager.is_auto_archive_enabled('award', 'invalid'))
        self.assertTrue(self.manager.is_auto_archive_enabled('patent', 'valid'))
        self.assertTrue(self.manager.is_auto_archive_enabled('patent', 'invalid'))

    def test_reset_to_defaults(self):
        """测试重置为默认值"""
        # 先启用一些配置
        self.manager.update_config('award', 'valid', True)
        self.manager.update_config('patent', 'invalid', True)

        # 重置
        result = self.manager.reset_to_defaults()
        self.assertTrue(result)

        # 验证全部重置为 False
        self.assertFalse(self.manager.is_auto_archive_enabled('award', 'valid'))
        self.assertFalse(self.manager.is_auto_archive_enabled('patent', 'invalid'))
        for config in self.manager.configs:
            self.assertFalse(config.auto_archive_enabled)

    def test_get_stats(self):
        """测试获取统计信息"""
        # 启用一些配置
        self.manager.update_config('award', 'valid', True)
        self.manager.update_config('patent', 'invalid', True)

        stats = self.manager.get_stats()

        self.assertEqual(stats['total_configs'], 8)
        self.assertEqual(stats['enabled_count'], 2)
        self.assertEqual(stats['disabled_count'], 6)
        self.assertIn('by_type', stats)

    def test_get_validation_status_for_achievement(self):
        """测试获取成果验证状态"""
        # 奖状/专利/软著：返回 'valid' 或 'invalid'
        self.assertEqual(self.manager.get_validation_status_for_achievement('award', True), 'valid')
        self.assertEqual(self.manager.get_validation_status_for_achievement('award', False), 'invalid')
        self.assertEqual(self.manager.get_validation_status_for_achievement('patent', True), 'valid')
        self.assertEqual(self.manager.get_validation_status_for_achievement('patent', False), 'invalid')
        self.assertEqual(self.manager.get_validation_status_for_achievement('software', True), 'valid')
        self.assertEqual(self.manager.get_validation_status_for_achievement('software', False), 'invalid')

        # 大创/其他：返回 None
        self.assertIsNone(self.manager.get_validation_status_for_achievement('innovation', True))
        self.assertIsNone(self.manager.get_validation_status_for_achievement('innovation', False))
        self.assertIsNone(self.manager.get_validation_status_for_achievement('other', True))
        self.assertIsNone(self.manager.get_validation_status_for_achievement('other', False))


def run_tests():
    """运行测试"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAutoArchiveConfigManager)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
