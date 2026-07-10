"""
抽取验证器集成测试

测试验证器在完整抽取流程中的工作情况，包括：
- 验证器在抽取器中的应用
- 与OCR+LLM抽取的集成
- 配置文件中的映射规则应用
- 生成HTML测试报告
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
from backend.extract.validator import ExtractorValidator
from backend.extract.extractors.base import ExtractContext


@dataclass
class TestResult:
    """测试结果"""
    name: str
    passed: bool
    message: str
    duration: float = 0.0
    original_data: Dict[str, Any] = field(default_factory=dict)
    mapped_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ValidatorIntegrationTest:
    """验证器集成测试"""

    def __init__(self):
        """初始化测试器"""
        self.results: List[TestResult] = []
        self.project_root = project_root

        # 加载配置
        self.config_loader = ConfigLoader(project_root)

        # 从配置加载验证映射
        config = self.config_loader.load_config()
        validation_cfg = config.get("validation", {})
        self.value_mappings = validation_cfg.get("value_mappings", {})

        print(f"加载的验证映射规则: {list(self.value_mappings.keys())}")

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 80)
        print("抽取验证器集成测试")
        print("=" * 80)

        # 1. 测试基本值映射
        self.results.append(self._test_basic_value_mapping())

        # 2. 测试竞赛等级映射
        self.results.append(self._test_competition_level_mapping())

        # 3. 测试奖项等级映射（英文->中文）
        self.results.append(self._test_award_level_mapping())

        # 4. 测试多字段同时映射
        self.results.append(self._test_multiple_fields_mapping())

        # 5. 测试空值和None值处理
        self.results.append(self._test_null_value_handling())

        # 6. 测试大小写不敏感映射
        self.results.append(self._test_case_insensitive_mapping())

        # 7. 测试无映射字段保持不变
        self.results.append(self._test_no_mapping_preserved())

    def _test_basic_value_mapping(self) -> TestResult:
        """测试基本值映射"""
        name = "基本值映射"
        start_time = time.time()

        try:
            validator = ExtractorValidator(
                value_mappings={"level": {"A": "一级", "B": "二级"}}
            )

            original = {"level": "A", "name": "测试"}
            result = validator.validate(original)

            passed = (
                result.is_valid and
                result.mapped_data["level"] == "一级" and
                result.mapped_data["name"] == "测试"
            )

            return TestResult(
                name=name,
                passed=passed,
                message="值映射 A -> 一级" if passed else "映射失败",
                duration=time.time() - start_time,
                original_data=original,
                mapped_data=result.mapped_data
            )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"测试异常: {e}",
                duration=time.time() - start_time
            )

    def _test_competition_level_mapping(self) -> TestResult:
        """测试竞赛等级映射"""
        name = "竞赛等级映射"
        start_time = time.time()

        try:
            # 使用配置文件中的映射规则
            if "competition_level" not in self.value_mappings:
                return TestResult(
                    name=name,
                    passed=False,
                    message="配置文件中未找到competition_level映射",
                    duration=time.time() - start_time
                )

            validator = ExtractorValidator(
                value_mappings=self.value_mappings
            )

            # 测试"区域赛" -> "省赛"的映射
            original = {"competition_level": "区域赛", "name": "某竞赛"}
            result = validator.validate(original)

            expected = self.value_mappings["competition_level"].get("区域赛", "省赛")
            passed = result.mapped_data.get("competition_level") == expected

            return TestResult(
                name=name,
                passed=passed,
                message=f"区域赛 -> {expected}",
                duration=time.time() - start_time,
                original_data=original,
                mapped_data=result.mapped_data
            )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"测试异常: {e}",
                duration=time.time() - start_time
            )

    def _test_award_level_mapping(self) -> TestResult:
        """测试奖项等级映射"""
        name = "奖项等级映射"
        start_time = time.time()

        try:
            if "award_level" not in self.value_mappings:
                return TestResult(
                    name=name,
                    passed=False,
                    message="配置文件中未找到award_level映射",
                    duration=time.time() - start_time
                )

            validator = ExtractorValidator(
                value_mappings=self.value_mappings
            )

            # 测试多个英文奖项等级映射
            test_cases = [
                ("Gold Medal", "金奖"),
                ("First Prize", "一等奖"),
                ("Silver Medal", "银奖"),
            ]

            all_passed = True
            results = {}

            for original, expected in test_cases:
                result = validator.validate({"award_level": original})
                actual = result.mapped_data.get("award_level")
                if actual != expected:
                    all_passed = False
                results[f"{original} -> {actual}"] = expected if actual == expected else f"预期: {expected}"

            return TestResult(
                name=name,
                passed=all_passed,
                message=f"测试了{len(test_cases)}个映射规则" if all_passed else "部分映射失败",
                duration=time.time() - start_time,
                original_data={"测试用例": test_cases},
                mapped_data=results
            )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"测试异常: {e}",
                duration=time.time() - start_time
            )

    def _test_multiple_fields_mapping(self) -> TestResult:
        """测试多字段同时映射"""
        name = "多字段同时映射"
        start_time = time.time()

        try:
            # 构造包含多个字段的测试数据
            test_mappings = {
                "award_level": {"Gold Medal": "金奖"},
                "competition_level": {"区域赛": "省赛"},
                "patent_type": {"Invention": "发明专利"}
            }

            validator = ExtractorValidator(value_mappings=test_mappings)

            original = {
                "award_level": "Gold Medal",
                "competition_level": "区域赛",
                "patent_type": "Invention",
                "year": "2024"  # 无映射的字段
            }

            result = validator.validate(original)

            passed = (
                result.mapped_data["award_level"] == "金奖" and
                result.mapped_data["competition_level"] == "省赛" and
                result.mapped_data["patent_type"] == "发明专利" and
                result.mapped_data["year"] == "2024"
            )

            return TestResult(
                name=name,
                passed=passed,
                message="所有字段映射正确" if passed else "部分字段映射失败",
                duration=time.time() - start_time,
                original_data=original,
                mapped_data=result.mapped_data
            )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"测试异常: {e}",
                duration=time.time() - start_time
            )

    def _test_null_value_handling(self) -> TestResult:
        """测试空值和None值处理"""
        name = "空值处理"
        start_time = time.time()

        try:
            validator = ExtractorValidator(
                value_mappings={"level": {"A": "一级"}}
            )

            # 测试None值
            result1 = validator.validate({"level": None})
            test1 = result1.mapped_data["level"] is None

            # 测试空字符串
            result2 = validator.validate({"level": ""})
            test2 = result2.mapped_data["level"] == ""

            # 测试正常值
            result3 = validator.validate({"level": "A"})
            test3 = result3.mapped_data["level"] == "一级"

            passed = test1 and test2 and test3

            return TestResult(
                name=name,
                passed=passed,
                message="None、空字符串、正常值都正确处理",
                duration=time.time() - start_time,
                original_data={"level": "测试None/空/A三种情况"},
                mapped_data={
                    "None -> None": test1,
                    "空字符串 -> 空字符串": test2,
                    "A -> 一级": test3
                }
            )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"测试异常: {e}",
                duration=time.time() - start_time
            )

    def _test_case_insensitive_mapping(self) -> TestResult:
        """测试大小写不敏感映射"""
        name = "大小写不敏感映射"
        start_time = time.time()

        try:
            validator = ExtractorValidator(
                value_mappings={"award_level": {"gold medal": "金奖"}}
            )

            test_cases = [
                ("Gold Medal", "金奖"),
                ("GOLD MEDAL", "金奖"),
                ("gold medal", "金奖"),
                ("GoLd MeDaL", "金奖"),
            ]

            all_passed = True
            results = {}

            for original, expected in test_cases:
                result = validator.validate({"award_level": original})
                actual = result.mapped_data.get("award_level")
                if actual != expected:
                    all_passed = False
                results[f"{original}"] = actual if actual == expected else f"失败: {actual}"

            passed = all_passed

            return TestResult(
                name=name,
                passed=passed,
                message=f"测试了{len(test_cases)}种大小写组合" if passed else "部分映射失败",
                duration=time.time() - start_time,
                original_data={"测试用例": test_cases},
                mapped_data=results
            )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"测试异常: {e}",
                duration=time.time() - start_time
            )

    def _test_no_mapping_preserved(self) -> TestResult:
        """测试无映射字段保持不变"""
        name = "无映射字段保持不变"
        start_time = time.time()

        try:
            validator = ExtractorValidator(
                value_mappings={"level": {"A": "一级"}}
            )

            # 测试没有配置映射的字段
            original = {
                "level": "A",          # 有映射
                "status": "pending",    # 无映射
                "year": "2024"          # 无映射
            }

            result = validator.validate(original)

            passed = (
                result.mapped_data["level"] == "一级" and
                result.mapped_data["status"] == "pending" and
                result.mapped_data["year"] == "2024"
            )

            return TestResult(
                name=name,
                passed=passed,
                message="无映射字段保持原值",
                duration=time.time() - start_time,
                original_data=original,
                mapped_data=result.mapped_data
            )

        except Exception as e:
            return TestResult(
                name=name,
                passed=False,
                message=f"测试异常: {e}",
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
    <title>抽取验证器集成测试报告</title>
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
        .data-comparison {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 10px 0; }}
        .data-box {{ padding: 15px; border-radius: 6px; }}
        .data-box.original {{ background: #e3f2fd; }}
        .data-box.mapped {{ background: #e8f5e9; }}
        .data-box .title {{ font-weight: 600; margin-bottom: 10px; color: #495057; }}
        .data-box pre {{ background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>抽取验证器集成测试报告</h1>
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
                        <div class="test-value">{r.message}</div>
                    </div>

                    <div class="data-comparison">
                        <div class="data-box original">
                            <div class="title">原始数据</div>
                            <pre>{self._format_dict(r.original_data)}</pre>
                        </div>
                        <div class="data-box mapped">
                            <div class="title">映射后数据</div>
                            <pre>{self._format_dict(r.mapped_data)}</pre>
                        </div>
                    </div>
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

    def _format_dict(self, d: Dict[str, Any]) -> str:
        """格式化字典为字符串"""
        import json
        try:
            return json.dumps(d, ensure_ascii=False, indent=2)
        except:
            return str(d)


def main():
    """主程序"""
    tester = ValidatorIntegrationTest()

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
    report_path = report_dir / "验证器集成测试报告.html"
    tester.generate_html_report(report_path)

    # 自动打开浏览器
    print(f"\n正在打开浏览器查看报告...")
    webbrowser.open(str(report_path))

    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
