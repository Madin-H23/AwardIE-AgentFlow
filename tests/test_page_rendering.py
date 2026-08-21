"""
页面渲染测试

验证所有关键页面可以正常渲染，包括：
1. 模板语法正确性（url_for调用）
2. 路由存在性
3. 页面渲染无异常
"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

# 设置项目根目录
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.chdir(project_root)

from flask import Flask
from app import create_app
from config.flask import get_config


@dataclass
class PageTestResult:
    """页面测试结果"""
    route: str
    method: str
    status_code: int
    passed: bool
    error: str = ""
    has_template_error: bool = False
    template_errors: List[str] = None
    
    def __post_init__(self):
        if self.template_errors is None:
            self.template_errors = []


class PageRenderingTester:
    """页面渲染测试器"""
    
    def __init__(self):
        """初始化测试器"""
        self.app = create_app(get_config())
        self.client = self.app.test_client()
        self.results: List[PageTestResult] = []
    
    def _login_as_admin(self):
        """模拟admin用户登录"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['username'] = 'admin'
            sess['user_name'] = 'admin'
            sess['user_type'] = 'admin'
    
    def _login_as_teacher(self, teacher_id: str = 'T001'):
        """模拟teacher用户登录"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = teacher_id
            sess['role'] = 'teacher'
            sess['username'] = teacher_id
            sess['user_name'] = '测试教师'
            sess['user_type'] = 'teacher'
    
    def _login_as_student(self, student_id: str = '2021001'):
        """模拟student用户登录"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = student_id
            sess['role'] = 'student'
            sess['username'] = student_id
            sess['user_name'] = '测试学生'
            sess['user_type'] = 'student'
    
    def test_page(self, route: str, method: str = 'GET', 
                  login_func=None, **kwargs) -> PageTestResult:
        """
        测试单个页面渲染
        
        Args:
            route: 路由路径
            method: HTTP方法
            login_func: 登录函数（如果需要登录）
            **kwargs: 路由参数（如 id=1）
        """
        # 如果需要登录
        if login_func:
            login_func()
        
        # 发送请求（捕获异常，避免一个页面错误导致整个测试停止）
        try:
            if method == 'GET':
                response = self.client.get(route, **kwargs)
            elif method == 'POST':
                response = self.client.post(route, **kwargs)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
        except Exception as e:
            # 如果请求本身抛出异常（如模板渲染错误），捕获并返回错误结果
            import traceback
            error_msg = f"请求异常: {str(e)}"
            result = PageTestResult(
                route=route,
                method=method,
                status_code=500,
                passed=False,
                error=error_msg,
                has_template_error=True,
                template_errors=[type(e).__name__]
            )
            self.results.append(result)
            return result
        
        # 分析响应
        status_code = response.status_code
        html_content = response.get_data(as_text=True)
        
        # 检查模板错误
        template_errors = []
        has_template_error = False
        
        error_keywords = [
            'BuildError',
            'TemplateNotFound',
            'UndefinedError',
            'jinja2.exceptions',
            'werkzeug.routing.exceptions',
        ]
        
        for keyword in error_keywords:
            if keyword in html_content:
                has_template_error = True
                template_errors.append(keyword)
        
        # 检查是否有异常堆栈
        if 'Traceback' in html_content or 'Exception:' in html_content:
            has_template_error = True
            template_errors.append('Exception')
        
        # 判断是否通过
        # 允许200（成功）和302（重定向），但不允许模板错误
        passed = (
            status_code in [200, 302] and 
            not has_template_error
        )
        
        error_msg = ""
        if not passed:
            if status_code != 200:
                error_msg = f"HTTP状态码错误: {status_code}"
            if has_template_error:
                error_msg += f" 模板错误: {', '.join(template_errors)}"
        
        result = PageTestResult(
            route=route,
            method=method,
            status_code=status_code,
            passed=passed,
            error=error_msg,
            has_template_error=has_template_error,
            template_errors=template_errors
        )
        
        self.results.append(result)
        return result
    
    def test_public_pages(self):
        """测试公开页面"""
        print("\n=== 测试公开页面 ===")
        
        # 首页
        result = self.test_page('/')
        print(f"{'[PASS]' if result.passed else '[FAIL]'} GET / - {result.status_code}")
        if not result.passed:
            print(f"  错误: {result.error}")
        
        # 登录页
        result = self.test_page('/login')
        print(f"{'[PASS]' if result.passed else '[FAIL]'} GET /login - {result.status_code}")
        if not result.passed:
            print(f"  错误: {result.error}")
    
    def test_admin_pages(self):
        """测试管理员页面"""
        print("\n=== 测试管理员页面 ===")
        
        # 仪表板
        result = self.test_page('/admin/dashboard', login_func=self._login_as_admin)
        print(f"{'[PASS]' if result.passed else '[FAIL]'} GET /admin/dashboard - {result.status_code}")
        if not result.passed:
            print(f"  错误: {result.error}")
        
        # 列表页
        list_pages = [
            '/admin/awards',
            '/admin/patents',
            '/admin/software',
            '/admin/laboratories',
            '/admin/students',
            '/admin/teachers',
            '/admin/achievement-review',  # 审核页面（实际路由）
        ]
        
        for page in list_pages:
            result = self.test_page(page, login_func=self._login_as_admin)
            print(f"{'[PASS]' if result.passed else '[FAIL]'} GET {page} - {result.status_code}")
            if not result.passed:
                print(f"  错误: {result.error}")
    
    def test_teacher_pages(self):
        """测试教师页面"""
        print("\n=== 测试教师页面 ===")
        
        # 仪表板
        result = self.test_page('/teacher/dashboard', login_func=self._login_as_teacher)
        print(f"{'[PASS]' if result.passed else '[FAIL]'} GET /teacher/dashboard - {result.status_code}")
        if not result.passed:
            print(f"  错误: {result.error}")
    
    def test_student_pages(self):
        """测试学生页面"""
        print("\n=== 测试学生页面 ===")
        
        # 仪表板
        result = self.test_page('/student/dashboard', login_func=self._login_as_student)
        print(f"{'[PASS]' if result.passed else '[FAIL]'} GET /student/dashboard - {result.status_code}")
        if not result.passed:
            print(f"  错误: {result.error}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("页面渲染测试")
        print("=" * 60)
        
        try:
            self.test_public_pages()
            self.test_admin_pages()
            self.test_teacher_pages()
            self.test_student_pages()
        except Exception as e:
            import traceback
            print(f"\n测试执行异常: {e}")
            traceback.print_exc()
        
        # 统计结果
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        print("\n" + "=" * 60)
        print(f"测试完成: {passed}/{total} 通过, {failed} 失败")
        print("=" * 60)
        
        # 显示失败详情
        if failed > 0:
            print("\n失败详情:")
            for result in self.results:
                if not result.passed:
                    print(f"  {result.method} {result.route}")
                    print(f"    状态码: {result.status_code}")
                    print(f"    错误: {result.error}")
                    if result.template_errors:
                        print(f"    模板错误: {', '.join(result.template_errors)}")
        
        return failed == 0


def main():
    """主函数"""
    tester = PageRenderingTester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())


def test_page_rendering_all_routes():
    """pytest 入口（T31-T34 批次4）：关键页面渲染无异常。"""
    from tests.fixtures.schemas import require_real_db
    require_real_db()   # 页面渲染依赖真实库数据
    tester = PageRenderingTester()
    assert tester.run_all_tests(), "存在渲染失败的页面，详见上方输出"
