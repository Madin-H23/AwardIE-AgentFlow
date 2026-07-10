"""
专利和软著抽取器集成测试

使用真实的证书文件测试PatentExtractor和SoftwareExtractor。
"""
import os
import sys
import time
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# 添加项目根到路径
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import ConfigLoader
from backend.ocr import OCREngine
from backend.extract.llm import LLMEngine
from backend.extract import ExtractFramework, PatentExtractor, SoftwareExtractor
from backend.extract.extractors.base import ExtractContext


@dataclass
class TestResult:
    """测试结果"""
    name: str
    passed: bool
    message: str
    duration: float = 0.0
    expected: str = ""
    actual: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class CertificateIntegrationTest:
    """专利和软著抽取器集成测试"""

    def __init__(self):
        """初始化测试器"""
        self.results: List[TestResult] = []
        self.project_root = project_root

        # 测试文件目录
        self.patent_dir = self.project_root / "files" / "patents"
        self.software_dir = self.project_root / "files" / "software"

        # 加载配置
        self.config_loader = ConfigLoader(project_root)

        # 初始化OCR引擎
        self.ocr_engine = OCREngine.from_config_loader(self.config_loader)

        # 初始化LLM引擎
        self.llm_engine = LLMEngine.from_config_loader(self.config_loader)

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 80)
        print("专利和软著抽取器集成测试")
        print("=" * 80)

        # 1. 测试框架初始化
        self.results.append(self._test_framework_init())

        # 2. 测试专利抽取
        if self.patent_dir.exists():
            patent_files = list(self.patent_dir.glob("*"))
            if patent_files:
                print(f"\n找到 {len(patent_files)} 个专利证书文件")
                for i, file_path in enumerate(patent_files[:5]):  # 最多测试5个
                    self.results.append(self._test_patent_extraction(file_path, i))
            else:
                print("\n未找到专利证书文件")
        else:
            print(f"\n专利目录不存在: {self.patent_dir}")

        # 3. 测试软著抽取
        if self.software_dir.exists():
            software_files = list(self.software_dir.glob("*"))
            if software_files:
                print(f"\n找到 {len(software_files)} 个软著证书文件")
                for i, file_path in enumerate(software_files[:5]):  # 最多测试5个
                    self.results.append(self._test_software_extraction(file_path, i))
            else:
                print("\n未找到软著证书文件")
        else:
            print(f"\n软著目录不存在: {self.software_dir}")

        # 4. 测试非证书文件
        self.results.append(self._test_non_certificate_file())

    def _test_framework_init(self) -> TestResult:
        """测试框架初始化"""
        name = "框架初始化"
        start_time = time.time()

        try:
            # 创建抽取框架
            framework = ExtractFramework.from_config_loader(self.config_loader)

            # 注册抽取器
            patent_extractor = PatentExtractor.from_config_loader(self.config_loader)
            software_extractor = SoftwareExtractor.from_config_loader(self.config_loader)

            framework.register(patent_extractor)
            framework.register(software_extractor)

            duration = time.time() - start_time

            # 验证注册成功 - 通过检查抽取器是否可用
            if (patent_extractor.name == "patent" and
                software_extractor.name == "software"):
                return TestResult(
                    name=name,
                    passed=True,
                    message=f"框架初始化成功，已注册抽取器: patent, software",
                    duration=duration,
                    expected=f"已注册: patent, software",
                    actual=f"已注册: patent, software"
                )
            else:
                return TestResult(
                    name=name,
                    passed=False,
                    message=f"抽取器注册不完整",
                    duration=duration
                )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"框架初始化失败: {e}",
                duration=time.time() - start_time
            )

    def _test_patent_extraction(self, file_path: Path, index: int) -> TestResult:
        """测试专利抽取"""
        name = f"专利抽取 - {file_path.name}"
        start_time = time.time()

        try:
            # 创建抽取器
            extractor = PatentExtractor.from_config_loader(self.config_loader)

            # 创建上下文
            ctx = ExtractContext(
                file_path=str(file_path),
                ocr_text=None,
                use_ocr_cache=True,
                use_llm_cache=True,
                ocr_engine=self.ocr_engine,
                llm_engine=self.llm_engine
            )

            # 执行抽取
            result = extractor.extract(ctx)
            duration = time.time() - start_time

            # 验证结果
            if result.template_type == "patent":
                data = result.data

                # 检查关键字段
                required_fields = ["patent_name", "patent_type"]
                missing_fields = [f for f in required_fields if not data.get(f)]

                if missing_fields:
                    return TestResult(
                        name=name,
                        passed=False,
                        message=f"缺少必要字段: {', '.join(missing_fields)}",
                        duration=duration,
                        details={"data": data}
                    )

                return TestResult(
                    name=name,
                    passed=True,
                    message=f"成功抽取专利: {data.get('patent_name')}",
                    duration=duration,
                    details={
                        "data": data,
                        "ocr_cache_hit": result.metadata.get("ocr_cache_hit", False),
                        "llm_cache_hit": result.metadata.get("llm_cache_hit", False)
                    }
                )
            elif result.template_type == "other":
                return TestResult(
                    name=name,
                    passed=False,
                    message=f"未识别为专利证书: {result.data.get('note', '')}",
                    duration=duration
                )
            else:
                return TestResult(
                    name=name,
                    passed=False,
                    message=f"识别类型不正确: {result.template_type}",
                    duration=duration
                )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"专利抽取失败: {e}",
                duration=time.time() - start_time
            )

    def _test_software_extraction(self, file_path: Path, index: int) -> TestResult:
        """测试软著抽取"""
        name = f"软著抽取 - {file_path.name}"
        start_time = time.time()

        try:
            # 创建抽取器
            extractor = SoftwareExtractor.from_config_loader(self.config_loader)

            # 创建上下文
            ctx = ExtractContext(
                file_path=str(file_path),
                ocr_text=None,
                use_ocr_cache=True,
                use_llm_cache=True,
                ocr_engine=self.ocr_engine,
                llm_engine=self.llm_engine
            )

            # 执行抽取
            result = extractor.extract(ctx)
            duration = time.time() - start_time

            # 验证结果
            if result.template_type == "software":
                data = result.data

                # 检查关键字段
                required_fields = ["software_name", "registration_number"]
                missing_fields = [f for f in required_fields if not data.get(f)]

                if missing_fields:
                    return TestResult(
                        name=name,
                        passed=False,
                        message=f"缺少必要字段: {', '.join(missing_fields)}",
                        duration=duration,
                        details={"data": data}
                    )

                return TestResult(
                    name=name,
                    passed=True,
                    message=f"成功抽取软著: {data.get('software_name')}",
                    duration=duration,
                    details={
                        "data": data,
                        "ocr_cache_hit": result.metadata.get("ocr_cache_hit", False),
                        "llm_cache_hit": result.metadata.get("llm_cache_hit", False)
                    }
                )
            elif result.template_type == "other":
                return TestResult(
                    name=name,
                    passed=False,
                    message=f"未识别为软著证书: {result.data.get('note', '')}",
                    duration=duration
                )
            else:
                return TestResult(
                    name=name,
                    passed=False,
                    message=f"识别类型不正确: {result.template_type}",
                    duration=duration
                )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"软著抽取失败: {e}",
                duration=time.time() - start_time
            )

    def _test_non_certificate_file(self) -> TestResult:
        """测试非证书文件处理"""
        name = "非证书文件处理"
        start_time = time.time()

        try:
            # 创建临时文本文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("这是一段普通文本，不是证书文件")
                temp_path = f.name

            try:
                extractor = PatentExtractor.from_config_loader(self.config_loader)

                ctx = ExtractContext(
                    file_path=temp_path,
                    ocr_text=None,
                    use_ocr_cache=True,
                    use_llm_cache=True,
                    ocr_engine=self.ocr_engine,
                    llm_engine=self.llm_engine
                )

                result = extractor.extract(ctx)
                duration = time.time() - start_time

                # 应该返回other（不支持的扩展名）
                if result.template_type == "other":
                    return TestResult(
                        name=name,
                        passed=True,
                        message="正确拒绝不支持的文件类型",
                        duration=duration
                    )
                else:
                    return TestResult(
                        name=name,
                        passed=False,
                        message=f"应返回other类型，实际返回{result.template_type}",
                        duration=duration
                    )

            finally:
                import os
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"测试失败: {e}",
                duration=time.time() - start_time
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
    <title>专利和软著抽取器集成测试报告</title>
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
        .data-section {{ margin-top: 15px; }}
        .data-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }}
        .data-table th {{ background: #495057; color: white; padding: 10px 8px; text-align: left; font-weight: 600; border: 1px solid #dee2e6; }}
        .data-table td {{ padding: 8px; border: 1px solid #dee2e6; }}
        .data-table tr:nth-child(even) {{ background: #f8f9fa; }}
        .data-table tr:hover {{ background: #e9ecef; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>专利和软著抽取器集成测试报告</h1>
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

            html += f"""
            <div class="test-item">
                <div class="test-header">
                    <div class="test-status {status_class}"></div>
                    <div class="test-title">{r.name}</div>
                    <div class="test-duration">{r.duration:.3f}s</div>
                </div>
                <div class="test-body">
                    <div class="test-row">
                        <div class="test-label">测试结果:</div>
                        <div class="test-value">{'✓' if r.passed else '✗'} {r.message}</div>
                    </div>
"""

            if r.expected:
                html += f"""
                    <div class="test-row">
                        <div class="test-label">预期结果:</div>
                        <div class="test-value">{r.expected}</div>
                    </div>
"""

            if r.actual:
                html += f"""
                    <div class="test-row">
                        <div class="test-label">实际结果:</div>
                        <div class="test-value">{r.actual}</div>
                    </div>
"""

            # 显示抽取的数据
            if r.details.get("data"):
                data = r.details["data"]
                html += """
                    <div class="data-section">
                        <div style="font-weight: 600; color: #495057; margin-bottom: 10px;">抽取的数据:</div>
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>字段</th>
                                    <th>值</th>
                                </tr>
                            </thead>
                            <tbody>
"""

                for key, value in data.items():
                    html += f"""
                                <tr>
                                    <td>{key}</td>
                                    <td>{value if value not in (None, '') else '-'}</td>
                                </tr>
"""

                html += """
                            </tbody>
                        </table>
                    </div>
"""

            # 显示缓存信息
            if r.details.get("ocr_cache_hit") is not None:
                html += f"""
                    <div class="test-row">
                        <div class="test-label">OCR缓存:</div>
                        <div class="test-value">{'命中' if r.details['ocr_cache_hit'] else '未命中'}</div>
                    </div>
"""
            if r.details.get("llm_cache_hit") is not None:
                html += f"""
                    <div class="test-row">
                        <div class="test-label">LLM缓存:</div>
                        <div class="test-value">{'命中' if r.details['llm_cache_hit'] else '未命中'}</div>
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
    tester = CertificateIntegrationTest()

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
        print(f"{status}: {r.name} - {r.message}")

    # 生成HTML报告
    report_dir = project_root / "tests" / "reports" / "extract" / "集成测试"
    report_path = report_dir / "专利软著抽取器集成测试报告.html"
    tester.generate_html_report(report_path)

    # 自动打开浏览器
    print(f"\n正在打开浏览器查看报告...")
    webbrowser.open(str(report_path))

    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
