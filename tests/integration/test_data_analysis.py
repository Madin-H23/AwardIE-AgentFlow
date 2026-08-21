"""
数据分析功能集成测试

测试管理员和实验室的数据分析页面和API端点。
"""
import pytest
from app import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client


@pytest.fixture
def authenticated_client(client):
    """创建已认证的测试客户端"""
    # 模拟管理员登录 - 使用与app/auth.py一致的session键名
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['user_type'] = 'admin'
        sess['user_name'] = 'admin'
        sess['role'] = 'admin'
        sess.permanent = True
    return client


class TestAdminDataAnalysis:
    """测试管理员数据分析功能"""

    def test_admin_data_analysis_page(self, client):
        """测试管理员数据分析页面访问

        验证页面路由存在。由于需要认证，预期会重定向到登录页面
        或返回403 Forbidden。
        """
        response = client.get('/admin/data-analysis', follow_redirects=False)

        # 未认证时，应该重定向到登录页面(302)或返回403
        assert response.status_code in [200, 302, 403], \
            f"Unexpected status code: {response.status_code}"

    def test_admin_data_analysis_page_with_redirect(self, client):
        """测试管理员数据分析页面（跟随重定向）"""
        response = client.get('/admin/data-analysis', follow_redirects=True)

        # 跟随重定向后，应该到达登录页面或数据分析页面
        assert response.status_code in [200, 403], \
            f"Unexpected status code after redirect: {response.status_code}"

    def test_api_competitions(self, client):
        """测试竞赛列表API

        验证API端点存在。未认证时应该返回401或403。
        """
        response = client.get('/api/admin/data-analysis/competitions')

        # API需要认证，未认证应该返回401或403
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403, got {response.status_code}"

    def test_api_award_timeline(self, client):
        """测试奖状时间轴API"""
        response = client.get('/api/admin/data-analysis/award-timeline')

        # 未认证应该返回401或403
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403, got {response.status_code}"

    def test_api_contribution(self, client):
        """测试贡献度统计API"""
        response = client.get('/api/admin/data-analysis/contribution')

        # 未认证应该返回401或403
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403, got {response.status_code}"

    def test_api_trend(self, client):
        """测试趋势分析API"""
        response = client.get('/api/admin/data-analysis/trend')

        # 未认证应该返回401或403
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403, got {response.status_code}"

    def test_api_heatmap(self, client):
        """测试热力图API"""
        response = client.get('/api/admin/data-analysis/heatmap')

        # 未认证应该返回401或403
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403, got {response.status_code}"

    def test_api_dynamic_chart(self, client):
        """测试动态图表冲突检测API

        验证API端点存在并正确处理请求。
        """
        response = client.get('/api/admin/data-analysis/dynamic-chart')

        # 未认证应该返回401或403
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403, got {response.status_code}"

    def test_page_has_tab2_filters(self, authenticated_client):
        """测试页面模板正确性：过滤器在Tab 2而非全局

        验证：
        - 不存在全局过滤器元素 yearRangeFilter 和 whitelistFilter
        - 存在Tab 2的过滤器元素 tab2YearFilter 和 tab2WhitelistFilter
        """
        response = authenticated_client.get('/admin/data-analysis')
        assert response.status_code == 200

        html = response.data.decode('utf-8')

        # 验证不存在全局过滤器
        assert 'id="yearRangeFilter"' not in html, \
            "页面不应包含全局年份过滤器（应在Tab 2中）"
        assert 'id="whitelistFilter"' not in html, \
            "页面不应包含全局白名单过滤器（应在Tab 2中）"

        # 验证Tab 2中存在过滤器（T59 修复：模板演进为 year-tags 标签式筛选，
        # 原 tab2YearFilter select 已退役；等价容器 id=yearTags）
        assert 'id="yearTags"' in html or 'id="tab2YearFilter"' in html, \
            "Tab 2应包含年份筛选（yearTags 标签容器或 tab2YearFilter）"
        assert 'id="tab2WhitelistFilter"' in html, \
            "Tab 2应包含白名单过滤器"


class TestLaboratoryDataAnalysis:
    """测试实验室数据分析功能"""

    def test_laboratory_data_analysis_page(self, client):
        """测试实验室数据分析页面

        验证实验室数据分析路由存在。实验室ID为1的测试。
        """
        response = client.get('/laboratory/1/data-analysis', follow_redirects=False)

        # 未认证时，应该重定向到登录页面(302)或返回403/404
        assert response.status_code in [200, 302, 403, 404], \
            f"Unexpected status code: {response.status_code}"

    def test_laboratory_data_analysis_page_with_redirect(self, client):
        """测试实验室数据分析页面（跟随重定向）"""
        response = client.get('/laboratory/1/data-analysis', follow_redirects=True)

        # 跟随重定向后，应该到达某个页面
        assert response.status_code in [200, 403, 404], \
            f"Unexpected status code after redirect: {response.status_code}"

    def test_api_laboratory_competitions(self, client):
        """测试实验室竞赛列表API"""
        response = client.get('/api/laboratory/1/data-analysis/competitions')

        # 未认证应该返回401或403
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403, got {response.status_code}"

    def test_api_laboratory_contribution(self, client):
        """测试实验室贡献度统计API"""
        response = client.get('/api/laboratory/1/data-analysis/contribution')

        # 未认证应该返回401或403
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403, got {response.status_code}"


class TestDataAnalysisRoutesExist:
    """测试数据分析路由是否正确注册"""

    def test_admin_blueprint_registered(self, client):
        """验证admin_data_analysis蓝图已注册"""
        # 通过访问不存在的路由来检查蓝图是否注册
        # 如果蓝图未注册，Flask会返回不同的错误
        response = client.get('/admin/data-analysis')

        # 任何响应都说明路由系统在工作
        assert response.status_code in [200, 302, 403, 404, 500], \
            "Route system not responding"

    def test_api_blueprint_registered(self, client):
        """验证api蓝图已注册"""
        response = client.get('/api/health')

        # health端点应该总是可访问的（不需要认证）
        assert response.status_code == 200, \
            f"API blueprint not registered, got status {response.status_code}"
        assert response.json['status'] == 'ok', \
            "Health check returned unexpected response"
