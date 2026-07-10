"""
手动导入页面 UI 测试

测试手动导入页面的 UI 元素和渲染。
"""
import os
import sys
import unittest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


class TestManualImportUI(unittest.TestCase):
    """手动导入页面 UI 测试"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化：创建 Flask 应用"""
        from app import create_app
        from config.flask import get_config

        cls.app = create_app(get_config())
        cls.client = cls.app.test_client()

    def test_file_import_page_requires_auth(self):
        """测试文件导入页面需要登录"""
        response = self.client.get('/admin/file-import')
        # 未登录应该重定向到登录页
        self.assertIn(response.status_code, [302, 303])
        self.assertIn('/login', response.location)

    def test_manual_api_endpoints_exist(self):
        """测试手动导入 API 端点存在（需要认证）"""
        # 测试解析端点
        response = self.client.post('/admin/file-import/manual/parse',
            json={'achievement_type': 'award', 'file_path': '/fake/path.jpg'},
            content_type='application/json'
        )
        # 未登录应该返回 401 或 403
        self.assertIn(response.status_code, [401, 403])

        # 测试提交端点
        response = self.client.post('/admin/file-import/manual/submit',
            json={'achievement_type': 'innovation', 'achievement_data': {}},
            content_type='application/json'
        )
        # 未登录应该返回 401 或 403
        self.assertIn(response.status_code, [401, 403])

    def test_manual_import_template_exists(self):
        """测试手动导入模板文件存在"""
        template_path = project_root / 'app' / 'templates' / 'admin' / 'file_import' / 'upload.html'
        self.assertTrue(template_path.exists(), "upload.html 模板文件应该存在")

        # 读取模板内容，验证包含手动导入相关元素
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查模式切换选项卡（使用Bootstrap原生tabs）
        self.assertIn('importModeTabs', content)
        self.assertIn('autoModeTab', content)
        self.assertIn('manualModeTab', content)
        self.assertIn('data-bs-toggle="tab"', content)

        # 检查手动导入相关元素（模板中 id 为 manualTypeAward 等）
        self.assertIn('manualImportContent', content)
        self.assertTrue('typeAward' in content or 'manualTypeAward' in content, "缺少奖状类型选项")
        self.assertTrue('typePatent' in content or 'manualTypePatent' in content, "缺少专利类型选项")
        self.assertTrue('typeSoftware' in content or 'manualTypeSoftware' in content, "缺少软著类型选项")

    def test_manual_import_service_exists(self):
        """测试手动导入服务模块存在"""
        service_path = project_root / 'backend' / 'services' / 'manual_import_service.py'
        self.assertTrue(service_path.exists(), "manual_import_service.py 应该存在")


if __name__ == '__main__':
    unittest.main()
