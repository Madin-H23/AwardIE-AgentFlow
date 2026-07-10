"""
首页渲染测试

验证首页可以正常渲染，包括实验室列表和封面图片显示。
"""
import os
import sys
from pathlib import Path

# 设置项目根目录
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.chdir(project_root)

from flask import Flask
from app import create_app


def test_index_page_renders():
    """测试首页可以正常渲染"""
    app = create_app()
    
    with app.test_client() as client:
        # 访问首页
        response = client.get('/')
        
        # 验证响应状态码
        assert response.status_code == 200, f"首页返回状态码 {response.status_code}，期望 200"
        
        # 验证响应内容包含关键元素
        html_content = response.get_data(as_text=True)
        
        # 验证包含实验室展示标题
        assert '实验室展示' in html_content or '实验室' in html_content, "首页应包含实验室相关内容"
        
        # 验证没有模板错误（不应该包含错误信息）
        assert 'BuildError' not in html_content, "首页不应包含路由构建错误"
        assert 'laboratory_cover_image' not in html_content or 'admin.laboratory_image_file' in html_content or 'auth.laboratory_file_access' in html_content, "封面图片路由应使用正确的路由"
        
        print("[PASS] 首页渲染测试通过")


if __name__ == '__main__':
    test_index_page_renders()
    print("所有测试通过！")
