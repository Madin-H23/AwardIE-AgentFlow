"""
文档抽取框架综合集成测试

测试抽取框架对不同类型文件的处理能力：
- 普通图片（应返回other）
- zip文件（应返回other）
- 专利图片（应返回patent）
- 软著图片（应返回software）
- 大创xlsx文件（应返回innovation）
"""
import os
import sys
import time
import webbrowser
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# 添加项目根到路径
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import ConfigLoader
from backend.extract import ExtractFramework
from backend.extract.extractors import PatentExtractor, SoftwareExtractor, InnovationExtractor


@dataclass
class TestCase:
    """测试用例定义"""
    name: str
    file_path: Path
    expected_type: str
    description: str


@dataclass
class TestResult:
    """测试结果"""
    name: str
    passed: bool
    message: str
    duration: float = 0.0
    expected_type: str = ""
    actual_type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExtractFrameworkIntegrationTest:
    """抽取框架综合集成测试"""

    def __init__(self):
        """初始化测试器"""
        self.results: List[TestResult] = []
        self.project_root = project_root

        # 加载配置
        self.config_loader = ConfigLoader(project_root)

        # 初始化抽取框架
        self.framework = ExtractFramework.from_config_loader(self.config_loader)

        # 注册抽取器
        self.framework.register(PatentExtractor.from_config_loader(self.config_loader))
        self.framework.register(SoftwareExtractor.from_config_loader(self.config_loader))
        self.framework.register(InnovationExtractor.from_config_loader(self.config_loader))

    def prepare_test_files(self) -> List[TestCase]:
        """准备测试文件"""
        test_cases = []

        # 1. 普通图片（应返回other）
        normal_image_path = self.project_root / "tests" / "test_images" / "other" / "普通图片.jpg"
        if not normal_image_path.exists():
            # 创建一个简单的测试图片
            from PIL import Image, ImageDraw
            normal_image_path.parent.mkdir(parents=True, exist_ok=True)
            img = Image.new('RGB', (400, 200), color='white')
            draw = ImageDraw.Draw(img)
            draw.text((50, 80), "这是一个普通图片，不是证书", fill='black')
            img.save(normal_image_path)

        test_cases.append(TestCase(
            name="普通图片",
            file_path=normal_image_path,
            expected_type="other",
            description="普通图片应返回other类型"
        ))

        # 2. zip文件（应返回other）
        zip_path = self.project_root / "tests" / "test_images" / "other" / "测试文件.zip"
        if not zip_path.exists():
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            # 创建一个包含简单文本的zip文件
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("test.txt", "这是一个测试文件")

        test_cases.append(TestCase(
            name="ZIP文件",
            file_path=zip_path,
            expected_type="other",
            description="不支持zip文件，应返回other"
        ))

        # 3. 专利图片（应返回patent）
        patent_dir = self.project_root / "files" / "patents"
        if patent_dir.exists():
            patent_files = list(patent_dir.glob("*.jpg")) + list(patent_dir.glob("*.png"))
            if patent_files:
                test_cases.append(TestCase(
                    name="专利图片",
                    file_path=patent_files[0],
                    expected_type="patent",
                    description="专利证书应返回patent类型"
                ))

        # 4. 软著图片（应返回software）
        software_dir = self.project_root / "files" / "software"
        if software_dir.exists():
            software_files = list(software_dir.glob("*.jpg")) + list(software_dir.glob("*.png"))
            if software_files:
                test_cases.append(TestCase(
                    name="软著图片",
                    file_path=software_files[0],
                    expected_type="software",
                    description="软著证书应返回software类型"
                ))

        # 5. 大创xlsx文件（应返回innovation）
        innovation_dir = self.project_root / "tests" / "test_images" / "invo"
        if innovation_dir.exists():
            xlsx_files = list(innovation_dir.glob("*.xlsx"))
            if xlsx_files:
                test_cases.append(TestCase(
                    name="大创Excel文件",
                    file_path=xlsx_files[0],
                    expected_type="innovation",
                    description="大创Excel文件应返回innovation类型"
                ))

        return test_cases

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 80)
        print("文档抽取框架综合集成测试")
        print("=" * 80)

        test_cases = self.prepare_test_files()

        if not test_cases:
            print("没有找到任何测试文件！")
            return

        print(f"\n准备测试 {len(test_cases)} 个文件")

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] 测试: {test_case.name}")
            print(f"    文件: {test_case.file_path.name}")
            print(f"    预期: {test_case.expected_type}")

            self.results.append(self._run_single_test(test_case))

    def _run_single_test(self, test_case: TestCase) -> TestResult:
        """运行单个测试"""
        start_time = time.time()

        try:
            # 检查文件是否存在
            if not test_case.file_path.exists():
                return TestResult(
                    name=test_case.name,
                    passed=False,
                    message=f"文件不存在: {test_case.file_path}",
                    duration=time.time() - start_time,
                    expected_type=test_case.expected_type,
                    actual_type="file_not_found"
                )

            # 执行抽取
            result = self.framework.extract(
                str(test_case.file_path),
                use_ocr_cache=True,
                use_llm_cache=True
            )

            duration = time.time() - start_time

            # 验证结果
            actual_type = result.template_type or "unknown"
            passed = (actual_type == test_case.expected_type)

            # 构建返回数据
            data = {}
            if result.data:
                # 只显示前几个关键字段
                if isinstance(result.data, dict):
                    for key in list(result.data.keys())[:5]:
                        value = result.data[key]
                        if value is None:
                            value = "-"
                        elif isinstance(value, list) and len(value) > 0:
                            value = f"[{len(value)}项]"
                        elif isinstance(value, str) and len(value) > 50:
                            value = value[:50] + "..."
                        data[key] = str(value)

            # 获取元数据
            metadata = {}
            if result.metadata:
                if "ocr_cache_hit" in result.metadata:
                    metadata["ocr缓存"] = "命中" if result.metadata["ocr_cache_hit"] else "未命中"
                if "llm_cache_hit" in result.metadata:
                    metadata["llm缓存"] = "命中" if result.metadata["llm_cache_hit"] else "未命中"

            return TestResult(
                name=test_case.name,
                passed=passed,
                message=test_case.description,
                duration=duration,
                expected_type=test_case.expected_type,
                actual_type=actual_type,
                data=data,
                metadata=metadata
            )

        except Exception as e:
            return TestResult(
                name=test_case.name,
                passed=False,
                message=f"测试异常: {e}",
                duration=time.time() - start_time,
                expected_type=test_case.expected_type,
                actual_type="error"
            )

    def generate_html_report(self, output_path: Path) -> None:
        """生成HTML测试报告"""
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if r.passed == False)
        total = len(self.results)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文档抽取框架综合集成测试报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.9; font-size: 0.95em; }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .summary-card .number {{ font-size: 2.5em; font-weight: bold; }}
        .summary-card.passed .number {{ color: #28a745; }}
        .summary-card.failed .number {{ color: #dc3545; }}
        .summary-card.total .number {{ color: #667eea; }}
        .summary-card .label {{ color: #6c757d; font-size: 0.9em; margin-top: 5px; }}
        .test-section {{ padding: 20px 30px; }}
        .test-section h2 {{ margin-bottom: 20px; color: #333; }}
        .test-item {{
            border: 1px solid #e9ecef;
            border-radius: 8px;
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .test-header {{
            display: flex;
            align-items: center;
            padding: 15px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .test-status {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 15px;
        }}
        .test-status.passed {{ background: #28a745; }}
        .test-status.failed {{ background: #dc3545; }}
        .test-title {{ flex: 1; font-weight: 600; color: #333; }}
        .test-duration {{ color: #6c757d; font-size: 0.9em; }}
        .test-body {{ padding: 20px; }}
        .test-row {{ display: grid; grid-template-columns: 150px 1fr; margin-bottom: 10px; }}
        .test-label {{ font-weight: 600; color: #495057; }}
        .test-value {{ color: #6c757d; }}
        .type-comparison {{ display: flex; gap: 20px; margin: 10px 0; }}
        .type-box {{ flex: 1; padding: 15px; border-radius: 6px; text-align: center; }}
        .type-box.expected {{ background: #e3f2fd; }}
        .type-box.actual {{ background: #f3e5f5; }}
        .type-box.correct {{ background: #e8f5e9; }}
        .type-box.wrong {{ background: #ffebee; }}
        .type-box .label {{ font-size: 0.85em; color: #666; margin-bottom: 5px; }}
        .type-box .value {{ font-size: 1.5em; font-weight: bold; }}
        .data-section {{ margin-top: 15px; }}
        .data-title {{ font-weight: 600; color: #495057; margin-bottom: 10px; }}
        .data-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }}
        .data-table th {{ background: #495057; color: white; padding: 10px 8px; text-align: left; font-weight: 600; border: 1px solid #dee2e6; }}
        .data-table td {{ padding: 8px; border: 1px solid #dee2e6; }}
        .data-table tr:nth-child(even) {{ background: #f8f9fa; }}
        .data-table tr:hover {{ background: #e9ecef; }}
        .metadata {{ display: flex; gap: 15px; margin-top: 10px; font-size: 0.9em; color: #6c757d; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>文档抽取框架综合集成测试报告</h1>
            <div class="meta">
                生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
                测试用例数: {total}
            </div>
        </div>

        <div class="summary">
            <div class="summary-card total">
                <div class="number">{total}</div>
                <div class="label">总测试数</div>
            </div>
            <div class="summary-card passed">
                <div class="number">{passed}</div>
                <div class="label">通过</div>
            </div>
            <div class="summary-card failed">
                <div class="number">{failed}</div>
                <div class="label">失败</div>
            </div>
            <div class="summary-card">
                <div class="number">{passed/total*100:.1f}%</div>
                <div class="label">通过率</div>
            </div>
        </div>

        <div class="test-section">
            <h2>测试用例详情</h2>
"""

        # 生成每个测试用例的结果
        for r in self.results:
            status_class = "passed" if r.passed else "failed"

            # 类型比较框的样式
            if r.actual_type == r.expected_type:
                comparison_class = "correct"
            else:
                comparison_class = "wrong"

            html += f"""
            <div class="test-item">
                <div class="test-header">
                    <div class="test-status {status_class}"></div>
                    <div class="test-title">{r.name}</div>
                    <div class="test-duration">{r.duration:.3f}s</div>
                </div>
                <div class="test-body">
                    <div class="test-row">
                        <div class="test-label">测试说明:</div>
                        <div class="test-value">{r.message}</div>
                    </div>

                    <div class="type-comparison">
                        <div class="type-box expected">
                            <div class="label">预期类型</div>
                            <div class="value">{r.expected_type}</div>
                        </div>
                        <div class="type-box {comparison_class}">
                            <div class="label">实际类型</div>
                            <div class="value">{r.actual_type}</div>
                        </div>
                    </div>
"""

            # 显示抽取的数据
            if r.data:
                html += """
                    <div class="data-section">
                        <div class="data-title">抽取的数据:</div>
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>字段</th>
                                    <th>值</th>
                                </tr>
                            </thead>
                            <tbody>
"""

                for key, value in r.data.items():
                    html += f"""
                                <tr>
                                    <td>{key}</td>
                                    <td>{value}</td>
                                </tr>
"""

                html += """
                            </tbody>
                        </table>
                    </div>
"""

            # 显示元数据
            if r.metadata:
                html += """
                    <div class="metadata">
"""
                for key, value in r.metadata.items():
                    html += f"<span>{key}: {value}</span>"
                html += """
                    </div>
"""

            html += """
                </div>
            </div>
"""

        html += """
        </div>
    </div>
</body>
</html>
"""

        # 写入文件
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        print(f"\n报告已保存到: {output_path}")


def main():
    """主程序"""
    tester = ExtractFrameworkIntegrationTest()

    # 运行所有测试
    tester.run_all_tests()

    # 打印结果摘要
    passed = sum(1 for r in tester.results if r.passed)
    total = len(tester.results)
    failed = total - passed

    print()
    print("=" * 80)
    print(f"总计: {total}, 通过: {passed}, 失败: {failed}")
    print("=" * 80)

    # 打印每个测试的结果
    for r in tester.results:
        status = "PASS" if r.passed else "FAIL"
        type_info = f"{r.expected_type} -> {r.actual_type}"
        if r.actual_type != r.expected_type:
            type_info += f" (不匹配!)"
        print(f"{status}: {r.name} - {type_info}")

    # 生成HTML报告
    report_dir = project_root / "tests" / "reports" / "extract" / "集成测试"
    report_path = report_dir / "抽取框架综合集成测试报告.html"
    tester.generate_html_report(report_path)

    # 自动打开浏览器
    print(f"\n正在打开浏览器查看报告...")
    webbrowser.open(str(report_path))

    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
