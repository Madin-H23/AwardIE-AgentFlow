"""
Auto Archive Integration Tests

自动归档功能集成测试（简化版）
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

from backend.models.auto_archive_config import AutoArchiveConfigManager


class TestAutoArchiveConfigIntegration(unittest.TestCase):
    """自动归档配置集成测试"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test.db")

        # 创建数据库表
        self._create_database()

        # 初始化 manager
        self.manager = AutoArchiveConfigManager(self.test_db_path)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def _create_database(self):
        """创建数据库表结构"""
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

        # 插入初始配置
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

    def test_initial_configs(self):
        """测试初始配置"""
        configs = self.manager.get_all_configs()
        self.assertEqual(len(configs), 8)

        # 所有配置默认为 False
        for config in configs:
            self.assertFalse(config.auto_archive_enabled)

    def test_update_single_config(self):
        """测试更新单个配置"""
        result = self.manager.update_config('award', 'valid', True)
        self.assertTrue(result)

        # 验证配置已更新
        self.assertTrue(self.manager.is_auto_archive_enabled('award', 'valid'))
        self.assertFalse(self.manager.is_auto_archive_enabled('award', 'invalid'))

    def test_batch_update(self):
        """测试批量更新配置"""
        configs = {
            'award': {'valid': True, 'invalid': False},
            'patent': {'valid': True, 'invalid': True},
        }

        result = self.manager.batch_update_configs(configs)
        self.assertTrue(result)

        # 验证配置已更新
        self.assertTrue(self.manager.is_auto_archive_enabled('award', 'valid'))
        self.assertFalse(self.manager.is_auto_archive_enabled('award', 'invalid'))
        self.assertTrue(self.manager.is_auto_archive_enabled('patent', 'valid'))
        self.assertTrue(self.manager.is_auto_archive_enabled('patent', 'invalid'))

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

        # 验证 valid 状态不受影响
        self.assertFalse(self.manager.should_auto_archive('award', True))

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

    def test_reset_to_defaults(self):
        """测试重置为默认值"""
        # 启用一些配置
        self.manager.update_config('award', 'valid', True)
        self.manager.update_config('patent', 'invalid', True)

        # 重置
        result = self.manager.reset_to_defaults()
        self.assertTrue(result)

        # 验证全部重置为 False
        self.assertFalse(self.manager.is_auto_archive_enabled('award', 'valid'))
        self.assertFalse(self.manager.is_auto_archive_enabled('patent', 'invalid'))

    def test_get_stats(self):
        """测试获取统计信息"""
        # 启用一些配置
        self.manager.update_config('award', 'valid', True)
        self.manager.update_config('patent', 'invalid', True)

        stats = self.manager.get_stats()

        self.assertEqual(stats['total_configs'], 8)
        self.assertEqual(stats['enabled_count'], 2)
        self.assertEqual(stats['disabled_count'], 6)


class TestReviewServiceIntegration(unittest.TestCase):
    """ReviewService 集成测试"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test.db")

        # 创建数据库表
        self._create_database()

        # 初始化 managers
        self.auto_archive_config_manager = AutoArchiveConfigManager(self.test_db_path)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def _create_database(self):
        """创建数据库表结构"""
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

        # 插入初始配置
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

    def test_review_service_with_auto_archive_config(self):
        """测试 ReviewService 集成 AutoArchiveConfigManager"""
        from backend.services.review_service import ReviewService

        # 创建 ReviewService（最小参数）
        review_service = ReviewService(
            pending_manager=None,  # 不需要
            review_log_manager=None,  # 不需要
            laboratory_manager=None,  # 不需要
            student_manager=None,  # 不需要
            teacher_manager=None,  # 不需要
            auto_archive_config_manager=self.auto_archive_config_manager
        )

        # 验证 manager 已正确集成
        self.assertIsNotNone(review_service.auto_archive_config_manager)
        self.assertEqual(
            review_service.auto_archive_config_manager,
            self.auto_archive_config_manager
        )

    def test_should_auto_archive_decision(self):
        """测试自动归档决策逻辑"""
        # 测试奖状-验证通过
        self.assertFalse(self.auto_archive_config_manager.should_auto_archive('award', True))
        self.auto_archive_config_manager.update_config('award', 'valid', True)
        self.assertTrue(self.auto_archive_config_manager.should_auto_archive('award', True))

        # 测试奖状-验证失败
        self.assertFalse(self.auto_archive_config_manager.should_auto_archive('award', False))
        self.auto_archive_config_manager.update_config('award', 'invalid', True)
        self.assertTrue(self.auto_archive_config_manager.should_auto_archive('award', False))

        # 测试专利-验证通过
        self.assertFalse(self.auto_archive_config_manager.should_auto_archive('patent', True))
        self.auto_archive_config_manager.update_config('patent', 'valid', True)
        self.assertTrue(self.auto_archive_config_manager.should_auto_archive('patent', True))

        # 测试软著-验证失败
        self.assertFalse(self.auto_archive_config_manager.should_auto_archive('software', False))
        self.auto_archive_config_manager.update_config('software', 'invalid', True)
        self.assertTrue(self.auto_archive_config_manager.should_auto_archive('software', False))

        # 测试大创（不区分验证状态）
        self.assertFalse(self.auto_archive_config_manager.should_auto_archive('innovation', True))
        self.auto_archive_config_manager.update_config('innovation', None, True)
        self.assertTrue(self.auto_archive_config_manager.should_auto_archive('innovation', True))
        self.assertTrue(self.auto_archive_config_manager.should_auto_archive('innovation', False))

        # 测试其他（不区分验证状态）
        self.assertFalse(self.auto_archive_config_manager.should_auto_archive('other', True))
        self.auto_archive_config_manager.update_config('other', None, True)
        self.assertTrue(self.auto_archive_config_manager.should_auto_archive('other', True))
        self.assertTrue(self.auto_archive_config_manager.should_auto_archive('other', False))


def run_tests():
    """运行测试"""
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAutoArchiveConfigIntegration))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestReviewServiceIntegration))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
