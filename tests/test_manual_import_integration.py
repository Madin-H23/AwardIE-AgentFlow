"""
手动导入 API 集成测试

测试手动导入功能的 API 端点。
"""
import os
import sys
import unittest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


class TestManualImportAPI(unittest.TestCase):
    """手动导入 API 集成测试"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化：创建 Flask 应用"""
        # 导入应用工厂
        from app import create_app
        from config.flask import get_config

        # 创建测试配置
        cls.app = create_app(get_config())
        cls.client = cls.app.test_client()

    def _login_as_admin(self):
        """模拟admin用户登录"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['username'] = 'admin'
            sess['user_name'] = 'admin'
            sess['user_type'] = 'admin'

    def test_manual_parse_api_missing_params(self):
        """测试解析 API 缺少参数（需要认证）"""
        # API 需要认证，返回 401
        response = self.client.post('/admin/file-import/manual/parse',
            json={'file_path': '/fake/path.jpg'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)

    def test_manual_parse_api_invalid_type(self):
        """测试解析 API 无效类型（需要认证）"""
        response = self.client.post('/admin/file-import/manual/parse',
            json={
                'achievement_type': 'invalid',
                'file_path': '/fake/path.jpg'
            },
            content_type='application/json'
        )
        # API 需要认证，返回 401
        self.assertEqual(response.status_code, 401)

    def test_manual_parse_api_valid_types(self):
        """测试解析 API 支持的类型（需要认证）"""
        for achievement_type in ['award', 'patent', 'software']:
            response = self.client.post('/admin/file-import/manual/parse',
                json={
                    'achievement_type': achievement_type,
                    'file_path': '/fake/path.jpg'
                },
                content_type='application/json'
            )
            # API 需要认证，返回 401
            self.assertEqual(response.status_code, 401)

    def test_manual_submit_api_missing_params(self):
        """测试提交 API 缺少参数（需要认证）"""
        response = self.client.post('/admin/file-import/manual/submit',
            json={'achievement_data': {}},
            content_type='application/json'
        )
        # API 需要认证，返回 401
        self.assertEqual(response.status_code, 401)

    def test_manual_submit_api_valid_params(self):
        """测试提交 API 参数验证通过（需要认证）"""
        response = self.client.post('/admin/file-import/manual/submit',
            json={
                'achievement_type': 'innovation',
                'achievement_data': {
                    'project_name': '测试大创项目',
                    'project_number': '2026001',
                    'year': 2026
                },
                'submitter_type': 'admin'
            },
            content_type='application/json'
        )
        # API 需要认证，返回 401
        self.assertEqual(response.status_code, 401)


class TestManualImportAPIAuthenticated(unittest.TestCase):
    """手动导入 API 带认证的集成测试"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化：创建 Flask 应用"""
        from app import create_app
        from config.flask import get_config

        cls.app = create_app(get_config())
        cls.client = cls.app.test_client()

    def setUp(self):
        """每个测试前登录"""
        self._login_as_admin()

    def _login_as_admin(self):
        """模拟admin用户登录"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['username'] = 'admin'
            sess['user_name'] = 'admin'
            sess['user_type'] = 'admin'

    def test_manual_parse_api_missing_file_path(self):
        """测试解析 API 缺少 file_path 参数"""
        response = self.client.post('/admin/file-import/manual/parse',
            json={'achievement_type': 'award'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success', False))

    def test_manual_parse_api_invalid_type_authenticated(self):
        """测试解析 API 无效类型（已认证）"""
        response = self.client.post('/admin/file-import/manual/parse',
            json={
                'achievement_type': 'invalid',
                'file_path': '/fake/path.jpg'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success', False))

    def test_manual_parse_api_file_not_found(self):
        """测试解析 API 文件不存在"""
        response = self.client.post('/admin/file-import/manual/parse',
            json={
                'achievement_type': 'award',
                'file_path': '/nonexistent/file.jpg'
            },
            content_type='application/json'
        )
        # 应该返回错误，但可能是200 with success=false，或400/500
        self.assertIn(response.status_code, [200, 400, 404])
        data = response.get_json()
        if data:
            self.assertFalse(data.get('success', True))

    def test_manual_submit_api_missing_achievement_type(self):
        """测试提交 API 缺少 achievement_type"""
        response = self.client.post('/admin/file-import/manual/submit',
            json={
                'achievement_data': {'project_name': '测试'},
                'submitter_type': 'admin'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success', False))

    def test_manual_submit_api_missing_data(self):
        """测试提交 API 缺少 achievement_data"""
        response = self.client.post('/admin/file-import/manual/submit',
            json={
                'achievement_type': 'innovation',
                'submitter_type': 'admin'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success', False))

    def test_manual_submit_api_invalid_innovation_data(self):
        """测试提交 API 大创项目缺少必填字段"""
        response = self.client.post('/admin/file-import/manual/submit',
            json={
                'achievement_type': 'innovation',
                'achievement_data': {
                    'project_number': '2026001'
                    # 缺少 project_name
                },
                'submitter_type': 'admin'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success', False))


if __name__ == '__main__':
    unittest.main()
