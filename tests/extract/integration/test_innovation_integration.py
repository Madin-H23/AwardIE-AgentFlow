"""
大创抽取器集成测试

测试大创抽取器与框架的集成，使用真实文件进行测试。

测试文件：
- tests/test_images/invo/附件1：2025年学院推荐申报国家级、省级大学生创新创业训练计划项目汇总表.xlsx.xlsx
- tests/test_images/invo/附件2：2023年院级大学生创新创业训练计划项目立项结果及经费划拨.xlsx.xlsx
- tests/test_images/invo/附件3：2024年度大学生国省创项目结题验收结果一览表.xlsx.xlsx

预期结果：
- 附件1：抽取到计算机工程系的国家级/省级项目
- 附件2：抽取到计算机工程系的院级项目
- 附件3：抽取到计算机工程系的结题验收项目（包含验收等级）

测试说明：
1. 大创抽取器基于文件扩展名（.xlsx/.xls）触发，不使用OCR关键词匹配
2. 通过文件名和第一行内容判断是否为大创文件
3. 筛选出目标系别（计算机工程系）的项目
4. 支持多种列名变体和时间格式
"""
import os
import sys
import time
import webbrowser
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# 项目根
project_root = Path(__file__).resolve().parents[3]  # 修正：从integration目录上3级就是项目根
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import ConfigLoader
from backend.extract import ExtractFramework, InnovationExtractor


@dataclass
class ItemResult:
    """测试结果"""
    name: str
    passed: bool
    message: str
    duration: float = 0.0
    expected: str = ""
    actual: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class InnovationIntegrationTest:
    """大创抽取器集成测试"""

    def __init__(self):
        """初始化测试器"""
        self.results: List[ItemResult] = []
        self.project_root = project_root

        # 测试文件路径
        self.test_dir = self.project_root / "tests" / "test_images" / "invo"

        # 测试文件列表
        self.test_files = [
            {
                "name": "附件1 - 国家级/省级项目汇总表",
                "path": self.test_dir / "附件1：2025年学院推荐申报国家级、省级大学生创新创业训练计划项目汇总表.xlsx.xlsx",
                "description": "2025年国家级/省级大创项目，包含起讫时间格式",
                "expected_count": ">= 1",
                "expected_level": ["国家级", "省级"]
            },
            {
                "name": "附件2 - 院级项目立项结果",
                "path": self.test_dir / "附件2：2023年院级大学生创新创业训练计划项目立项结果及经费划拨.xlsx.xlsx",
                "description": "2023年院级大创项目，包含立项年份格式",
                "expected_count": ">= 1",
                "expected_level": ["院级"]
            },
            {
                "name": "附件3 - 结题验收结果",
                "path": self.test_dir / "附件3：2024年度大学生国省创项目结题验收结果一览表.xlsx.xlsx",
                "description": "2024年结题验收项目，包含验收等级",
                "expected_count": ">= 0",  # 可能没有计算机工程系的数据
                "expected_level": None
            },
        ]

    def run_all_tests(self) -> None:
        """运行所有测试"""
        print("=" * 80)
        print("大创抽取器集成测试")
        print("=" * 80)
        print()

        # 1. 测试框架初始化
        self.results.append(self._test_framework_init())

        # 2. 测试大创文件识别
        for file_info in self.test_files:
            if file_info["path"].exists():
                self.results.append(self._test_file_recognition(file_info))
            else:
                self.results.append(ItemResult(
                    name=f"文件识别 - {file_info['name']}",
                    passed=False,
                    message=f"测试文件不存在: {file_info['path']}",
                    duration=0
                ))

        # 3. 测试数据抽取
        for file_info in self.test_files:
            if file_info["path"].exists():
                self.results.append(self._test_data_extraction(file_info))

        # 4. 测试非大创文件处理
        self.results.append(self._test_non_innovation_file())

        # 5. 测试不支持扩展名
        self.results.append(self._test_unsupported_extension())

    def _test_framework_init(self) -> ItemResult:
        """测试框架初始化"""
        name = "框架初始化"
        start_time = time.time()

        try:
            config_loader = ConfigLoader(self.project_root)
            framework = ExtractFramework.from_config_loader(config_loader)

            # 创建并注册大创抽取器
            innovation_extractor = InnovationExtractor.from_config_loader(config_loader)
            framework.register(innovation_extractor)

            duration = time.time() - start_time

            # 验证抽取器已注册
            if innovation_extractor.name in [e.name for e in framework._extractors]:
                return ItemResult(
                    name=name,
                    passed=True,
                    message="框架初始化成功，大创抽取器已注册",
                    duration=duration,
                    expected="大创抽取器已注册",
                    actual="大创抽取器已注册",
                    details={"extractor_count": len(framework._extractors)}
                )
            else:
                return ItemResult(
                    name=name,
                    passed=False,
                    message="大创抽取器未注册",
                    duration=duration,
                    expected="大创抽取器已注册",
                    actual="大创抽取器未注册"
                )

        except Exception as e:
            return ItemResult(
                name=name,
                passed=False,
                message=f"框架初始化失败: {e}",
                duration=time.time() - start_time
            )

    def _test_file_recognition(self, file_info: Dict) -> ItemResult:
        """测试文件识别"""
        name = f"文件识别 - {file_info['name']}"
        start_time = time.time()

        try:
            config_loader = ConfigLoader(self.project_root)
            framework = ExtractFramework.from_config_loader(config_loader)
            innovation_extractor = InnovationExtractor.from_config_loader(config_loader)
            framework.register(innovation_extractor)

            result = framework.extract(str(file_info["path"]))

            duration = time.time() - start_time

            # 验证是否识别为大创文件
            is_innovation = result.template_type == "innovation"

            if is_innovation:
                return ItemResult(
                    name=name,
                    passed=True,
                    message=f"正确识别为大创文件",
                    duration=duration,
                    expected="template_type=innovation",
                    actual=f"template_type={result.template_type}",
                    details={"file_name": file_info["path"].name}
                )
            else:
                return ItemResult(
                    name=name,
                    passed=False,
                    message=f"未能识别为大创文件: {result.data.get('note', '')}",
                    duration=duration,
                    expected="template_type=innovation",
                    actual=f"template_type={result.template_type}, note={result.data.get('note', '')}"
                )

        except Exception as e:
            return ItemResult(
                name=name,
                passed=False,
                message=f"文件识别失败: {e}",
                duration=time.time() - start_time
            )

    def _test_data_extraction(self, file_info: Dict) -> ItemResult:
        """测试数据抽取"""
        name = f"数据抽取 - {file_info['name']}"
        start_time = time.time()

        try:
            config_loader = ConfigLoader(self.project_root)
            framework = ExtractFramework.from_config_loader(config_loader)
            innovation_extractor = InnovationExtractor.from_config_loader(config_loader)
            framework.register(innovation_extractor)

            result = framework.extract(str(file_info["path"]))

            duration = time.time() - start_time

            # 验证结果
            if result.template_type != "innovation":
                return ItemResult(
                    name=name,
                    passed=False,
                    message=f"未识别为大创文件: {result.data.get('note', '')}",
                    duration=duration
                )

            projects = result.data.get("projects", [])
            count = result.data.get("count", 0)

            # 检查项目数量
            if file_info["expected_count"].startswith(">="):
                min_count = int(file_info["expected_count"][2:])
                if count < min_count:
                    return ItemResult(
                        name=name,
                        passed=False,
                        message=f"项目数量不足: 期望至少{min_count}个，实际{count}个",
                        duration=duration,
                        expected=f"count >= {min_count}",
                        actual=f"count = {count}"
                    )

            # 检查项目级别（如果配置了）
            if file_info.get("expected_level"):
                found_levels = set()
                for p in projects:
                    level = p.get("project_level")
                    if level:
                        found_levels.add(level)

                expected_levels = set(file_info["expected_level"])
                if not found_levels.intersection(expected_levels):
                    return ItemResult(
                        name=name,
                        passed=False,
                        message=f"项目级别不符合预期: 期望{expected_levels}，实际{found_levels}",
                        duration=duration,
                        expected=f"level in {expected_levels}",
                        actual=f"levels = {found_levels}"
                    )

            # 检查项目数据完整性
            details = {
                "count": count,
                "file_name": file_info["path"].name,
                "projects": []
            }

            for i, p in enumerate(projects[:3]):  # 只显示前3个项目
                details["projects"].append({
                    "project_number": p.get("project_number"),
                    "project_name": p.get("project_name"),
                    "start_date": p.get("start_date"),
                    "end_date": p.get("end_date"),
                    "project_level": p.get("project_level"),
                    "acceptance_level": p.get("acceptance_level"),
                    "leader_name": p.get("leader_name"),
                    "leader_student_id": p.get("leader_student_id"),
                    "supervisors": p.get("supervisors", []),
                    "members": p.get("members", []),
                    "department": p.get("department"),
                    "project_description": p.get("project_description")
                })

            return ItemResult(
                name=name,
                passed=True,
                message=f"成功抽取{count}个项目",
                duration=duration,
                expected=f"抽取到{file_info['expected_count']}个项目",
                actual=f"抽取到{count}个项目",
                details=details
            )

        except Exception as e:
            return ItemResult(
                name=name,
                passed=False,
                message=f"数据抽取失败: {e}",
                duration=time.time() - start_time
            )

    def _test_non_innovation_file(self) -> ItemResult:
        """测试非大创文件处理"""
        name = "非大创文件处理"
        start_time = time.time()

        try:
            # 创建一个临时的非大创Excel文件
            import tempfile
            from openpyxl import Workbook

            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
                temp_path = f.name

            try:
                wb = Workbook()
                ws = wb.active
                ws.append(["普通数据表"])
                ws.append(["姓名", "年龄"])
                ws.append(["张三", "20"])
                wb.save(temp_path)

                config_loader = ConfigLoader(self.project_root)
                framework = ExtractFramework.from_config_loader(config_loader)
                innovation_extractor = InnovationExtractor.from_config_loader(config_loader)
                framework.register(innovation_extractor)

                result = framework.extract(temp_path)

                duration = time.time() - start_time

                # 应该返回other
                if result.template_type == "other":
                    return ItemResult(
                        name=name,
                        passed=True,
                        message="正确返回other类型",
                        duration=duration,
                        expected="template_type=other",
                        actual=f"template_type={result.template_type}"
                    )
                else:
                    return ItemResult(
                        name=name,
                        passed=False,
                        message=f"应返回other类型，实际返回{result.template_type}",
                        duration=duration
                    )

            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            return ItemResult(
                name=name,
                passed=False,
                message=f"测试失败: {e}",
                duration=time.time() - start_time
            )

    def _test_unsupported_extension(self) -> ItemResult:
        """测试不支持扩展名"""
        name = "不支持扩展名"
        start_time = time.time()

        try:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                temp_path = f.name

            try:
                config_loader = ConfigLoader(self.project_root)
                framework = ExtractFramework.from_config_loader(config_loader)
                innovation_extractor = InnovationExtractor.from_config_loader(config_loader)
                framework.register(innovation_extractor)

                result = framework.extract(temp_path)

                duration = time.time() - start_time

                # 应该返回other（不支持的扩展名）
                if result.template_type == "other":
                    note = result.data.get("note", "")
                    if "扩展名" in note:
                        return ItemResult(
                            name=name,
                            passed=True,
                            message="正确拒绝不支持的扩展名",
                            duration=duration,
                            expected="返回other，提示扩展名不支持",
                            actual=f"返回other，note={note}"
                        )

                return ItemResult(
                    name=name,
                    passed=False,
                    message="未正确处理不支持的扩展名",
                    duration=duration,
                    expected="返回other，提示扩展名不支持",
                    actual=f"template_type={result.template_type}"
                )

            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            return ItemResult(
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
    <title>大创抽取器集成测试报告</title>
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
        .project-section {{ margin-top: 15px; }}
        .project-section-title {{ font-weight: 600; color: #495057; margin-bottom: 10px; }}
        .project-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }}
        .project-table th {{ background: #495057; color: white; padding: 10px 8px; text-align: left; font-weight: 600; border: 1px solid #dee2e6; }}
        .project-table td {{ padding: 8px; border: 1px solid #dee2e6; }}
        .project-table tr:nth-child(even) {{ background: #f8f9fa; }}
        .project-table tr:hover {{ background: #e9ecef; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>大创抽取器集成测试报告</h1>
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
            status_icon = "✓" if r.passed else "✗"

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
                        <div class="test-value">{status_icon} {r.message}</div>
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

            # 显示项目详情
            if r.details.get("projects"):
                projects = r.details["projects"]
                html += """
                    <div class="project-section">
                        <div class="project-section-title">抽取到的项目 ({})</div>
                        <table class="project-table">
                            <thead>
                                <tr>
                                    <th>项目编号</th>
                                    <th>项目名称</th>
                                    <th>开始日期</th>
                                    <th>结束日期</th>
                                    <th>负责人</th>
                                    <th>负责人学号</th>
                                    <th>成员</th>
                                    <th>指导教师</th>
                                    <th>项目级别</th>
                                    <th>验收级别</th>
                                    <th>系别</th>
                                </tr>
                            </thead>
                            <tbody>
""".format(len(projects))

                for p in projects:
                    # 辅助函数：处理None值显示
                    def fmt(val):
                        return val if val not in (None, '', 'None') else '-'

                    # 处理成员列表
                    members = p.get('members', [])
                    members_str = '; '.join(members) if members else '-'

                    # 处理指导教师列表
                    supervisors = p.get('supervisors', [])
                    supervisors_str = '; '.join(supervisors) if supervisors else '-'

                    html += f"""
                                <tr>
                                    <td>{fmt(p.get('project_number'))}</td>
                                    <td>{fmt(p.get('project_name'))}</td>
                                    <td>{fmt(p.get('start_date'))}</td>
                                    <td>{fmt(p.get('end_date'))}</td>
                                    <td>{fmt(p.get('leader_name'))}</td>
                                    <td>{fmt(p.get('leader_student_id'))}</td>
                                    <td>{members_str}</td>
                                    <td>{supervisors_str}</td>
                                    <td>{fmt(p.get('project_level'))}</td>
                                    <td>{fmt(p.get('acceptance_level'))}</td>
                                    <td>{fmt(p.get('department'))}</td>
                                </tr>
"""

                html += """
                            </tbody>
                        </table>
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
    tester = InnovationIntegrationTest()

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
    report_path = report_dir / "大创抽取器集成测试报告.html"
    tester.generate_html_report(report_path)

    # 自动打开浏览器
    print(f"\n正在打开浏览器查看报告...")
    webbrowser.open(str(report_path))

    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
