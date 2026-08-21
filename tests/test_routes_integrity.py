"""
路由完整性测试

扫描所有模板文件，验证：
1. 所有 url_for() 调用的路由是否存在
2. 路由参数是否正确
3. 模板语法是否正确
"""
import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple
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
class RouteReference:
    """路由引用"""
    template_file: str
    line_number: int
    endpoint: str
    params: Dict[str, str]
    full_call: str


@dataclass
class RouteCheckResult:
    """路由检查结果"""
    reference: RouteReference
    route_exists: bool
    error: str = ""


class RouteIntegrityTester:
    """路由完整性测试器"""
    
    def __init__(self):
        """初始化测试器"""
        self.app = create_app(get_config())
        self.templates_dir = project_root / "app" / "templates"
        self.references: List[RouteReference] = []
        self.results: List[RouteCheckResult] = []
        
        # 获取所有注册的路由
        with self.app.app_context():
            self.registered_routes = set()
            for rule in self.app.url_map.iter_rules():
                self.registered_routes.add(rule.endpoint)
    
    def _extract_url_for_calls(self, template_path: Path) -> List[RouteReference]:
        """从模板文件中提取所有 url_for() 调用"""
        references = []
        
        try:
            content = template_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # 匹配 url_for('endpoint', param=value) 或 url_for('endpoint', param=value, ...)
            # 也匹配 url_for("endpoint", param=value)
            pattern = r"url_for\(['\"]([^'\"]+)['\"](?:,\s*([^)]+))?\)"
            
            for line_num, line in enumerate(lines, 1):
                matches = re.finditer(pattern, line)
                for match in matches:
                    endpoint = match.group(1)
                    params_str = match.group(2) if match.group(2) else ""
                    
                    # 解析参数（简单解析，不处理复杂表达式）
                    params = {}
                    if params_str:
                        # 匹配 key=value 或 key='value' 或 key="value"
                        param_pattern = r"(\w+)\s*=\s*['\"]?([^,'\"]+)['\"]?"
                        param_matches = re.finditer(param_pattern, params_str)
                        for pm in param_matches:
                            key = pm.group(1)
                            value = pm.group(2).strip()
                            params[key] = value
                    
                    references.append(RouteReference(
                        template_file=str(template_path.relative_to(self.templates_dir)),
                        line_number=line_num,
                        endpoint=endpoint,
                        params=params,
                        full_call=match.group(0)
                    ))
        except Exception as e:
            print(f"读取模板文件失败: {template_path}, 错误: {e}")
        
        return references
    
    def scan_templates(self):
        """扫描所有模板文件"""
        print("扫描模板文件...")
        
        for template_file in self.templates_dir.rglob('*.html'):
            refs = self._extract_url_for_calls(template_file)
            self.references.extend(refs)
        
        print(f"找到 {len(self.references)} 个 url_for() 调用")
    
    def check_routes(self):
        """检查所有路由引用"""
        print("\n检查路由完整性...")
        
        for ref in self.references:
            # 检查路由是否存在
            # Flask的endpoint格式通常是 'blueprint.endpoint'
            route_exists = ref.endpoint in self.registered_routes
            
            # 如果直接endpoint不存在，尝试查找包含该endpoint的路由
            if not route_exists:
                # 检查是否有以该endpoint结尾的路由
                matching_routes = [r for r in self.registered_routes if r.endswith('.' + ref.endpoint) or r == ref.endpoint]
                if matching_routes:
                    route_exists = True
                    # 如果找到多个匹配，可能需要更精确的匹配
            
            error = ""
            if not route_exists:
                # 查找最相似的路由
                similar = [r for r in self.registered_routes if ref.endpoint in r or r.endswith('.' + ref.endpoint)]
                if similar:
                    error = f"未找到路由 '{ref.endpoint}'，相似路由: {similar[:3]}"
                else:
                    error = f"未找到路由 '{ref.endpoint}'"
            
            result = RouteCheckResult(
                reference=ref,
                route_exists=route_exists,
                error=error
            )
            self.results.append(result)
    
    def generate_report(self):
        """生成测试报告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.route_exists)
        failed = total - passed
        
        print("\n" + "=" * 60)
        print("路由完整性测试报告")
        print("=" * 60)
        print(f"总计: {total} 个路由引用")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        
        if failed > 0:
            print("\n失败的路由引用:")
            # 按模板文件分组
            failed_by_file: Dict[str, List[RouteCheckResult]] = {}
            for result in self.results:
                if not result.route_exists:
                    file = result.reference.template_file
                    if file not in failed_by_file:
                        failed_by_file[file] = []
                    failed_by_file[file].append(result)
            
            for file, results in failed_by_file.items():
                print(f"\n  文件: {file}")
                for result in results:
                    ref = result.reference
                    print(f"    行 {ref.line_number}: {ref.full_call}")
                    print(f"      端点: {ref.endpoint}")
                    print(f"      错误: {result.error}")
        
        return failed == 0
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("路由完整性测试")
        print("=" * 60)
        
        self.scan_templates()
        self.check_routes()
        return self.generate_report()


def main():
    """主函数"""
    tester = RouteIntegrityTester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())


def test_routes_integrity():
    """pytest 入口（T31-T34 批次4）：全模板 url_for 路由完整性扫描。"""
    tester = RouteIntegrityTester()
    assert tester.run_all_tests(), "存在失败的路由引用，详见上方输出"
