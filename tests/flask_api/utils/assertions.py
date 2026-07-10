"""
测试断言工具
提供丰富的断言方法，记录详细的错误信息
"""
import logging
from typing import Any, List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TestAssertion:
    """测试断言"""

    def __init__(self, description: str, actual: Any, expected: Any,
                 passed: bool, error_msg: str = ""):
        self.description = description
        self.actual = actual
        self.expected = expected
        self.passed = passed
        self.error_msg = error_msg
        self.timestamp = datetime.now()


class AssertionContext:
    """断言上下文，收集所有断言结果"""

    def __init__(self, test_case_id: str):
        self.test_case_id = test_case_id
        self.assertions: List[TestAssertion] = []
        self.current_step = 0
        self.steps = []

    def add_step(self, step_name: str):
        """添加测试步骤"""
        self.current_step += 1
        self.steps.append({
            'step_num': self.current_step,
            'step_name': step_name,
            'timestamp': datetime.now()
        })
        logger.info(f"[Step {self.current_step}] {step_name}")

    def assert_equals(self, description: str, actual: Any, expected: Any,
                      context: str = "") -> bool:
        """断言相等"""
        passed = (actual == expected)
        error_msg = ""

        if not passed:
            error_msg = f"Expected: {expected}, but got: {actual}"
            if context:
                error_msg = f"[{context}] {error_msg}"
            logger.error(f"Assertion failed: {description} - {error_msg}")

        assertion = TestAssertion(description, actual, expected, passed, error_msg)
        self.assertions.append(assertion)

        return passed

    def assert_true(self, description: str, condition: Any,
                    context: str = "") -> bool:
        """断言为真"""
        passed = bool(condition)
        error_msg = "" if passed else f"Expected True, but got: {condition}"
        if context and not passed:
            error_msg = f"[{context}] {error_msg}"

        if not passed:
            logger.error(f"Assertion failed: {description} - {error_msg}")

        assertion = TestAssertion(description, condition, True, passed, error_msg)
        self.assertions.append(assertion)

        return passed

    def assert_in(self, description: str, item: Any, container: Any,
                  context: str = "") -> bool:
        """断言包含"""
        passed = (item in container)
        error_msg = "" if passed else f"Expected {item} in {container}"
        if context and not passed:
            error_msg = f"[{context}] {error_msg}"

        if not passed:
            logger.error(f"Assertion failed: {description} - {error_msg}")

        assertion = TestAssertion(description, item, container, passed, error_msg)
        self.assertions.append(assertion)

        return passed

    def assert_status_code(self, response_status: int, expected_status: int,
                           endpoint: str = "") -> bool:
        """断言HTTP状态码"""
        passed = (response_status == expected_status)
        error_msg = ""
        if not passed:
            error_msg = f"Expected status {expected_status}, got {response_status}"
            if endpoint:
                error_msg = f"{endpoint} - {error_msg}"

        assertion = TestAssertion(
            f"Status code check",
            response_status,
            expected_status,
            passed,
            error_msg
        )
        self.assertions.append(assertion)

        return passed

    def assert_has_key(self, description: str, data: Dict, key: str) -> bool:
        """断言字典包含键"""
        passed = (key in data)
        error_msg = f"Key '{key}' not found in data"
        if not passed:
            logger.error(f"Assertion failed: {description} - {error_msg}")

        assertion = TestAssertion(
            f"Has key: {key}",
            list(data.keys()),
            key,
            passed,
            error_msg
        )
        self.assertions.append(assertion)

        return passed

    def get_failed_assertions(self) -> List[TestAssertion]:
        """获取所有失败的断言"""
        return [a for a in self.assertions if not a.passed]

    def get_summary(self) -> Dict[str, Any]:
        """获取断言摘要"""
        total = len(self.assertions)
        passed = len([a for a in self.assertions if a.passed])
        failed = total - passed

        return {
            'test_case_id': self.test_case_id,
            'total_assertions': total,
            'passed_assertions': passed,
            'failed_assertions': failed,
            'success_rate': f"{(passed/total*100):.1f}%" if total > 0 else "0%",
            'steps': self.steps
        }


class BugReport:
    """BUG报告"""

    def __init__(self):
        self.bugs = []

    def add_bug(self, test_case_id: str, assertion: TestAssertion,
                step_info: Dict, api_info: Dict, test_data: Dict):
        """添加BUG记录"""
        bug = {
            'bug_id': f"BUG-{len(self.bugs) + 1:03d}",
            'test_case_id': test_case_id,
            'timestamp': assertion.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'severity': self._determine_severity(assertion),
            'status': 'Open',
            'title': self._generate_title(assertion, step_info),
            'description': assertion.error_msg,
            'step': step_info,
            'api': api_info,
            'test_data': test_data,
            'expected': assertion.expected,
            'actual': assertion.actual,
            'assertion_type': assertion.description
        }
        self.bugs.append(bug)

    def _determine_severity(self, assertion: TestAssertion) -> str:
        """根据断言类型确定严重程度"""
        critical_keywords = ['login', 'authentication', 'authorization']
        high_keywords = ['database', 'data loss', 'corruption']

        desc_lower = assertion.description.lower()

        if any(kw in desc_lower for kw in critical_keywords):
            return 'Critical'
        elif any(kw in desc_lower for kw in high_keywords):
            return 'High'
        else:
            return 'Medium'

    def _generate_title(self, assertion: TestAssertion, step_info: Dict) -> str:
        """生成BUG标题"""
        step_name = step_info.get('step_name', 'Unknown Step')
        return f"{step_name}: {assertion.description}"

    def export_to_markdown(self, output_file: str):
        """导出BUG清单到Markdown"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# BUG清单\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"BUG总数: {len(self.bugs)}\n\n")

            # 严重程度统计
            severity_stats = {}
            for bug in self.bugs:
                severity_stats[bug['severity']] = severity_stats.get(bug['severity'], 0) + 1

            f.write("## 严重程度统计\n\n")
            f.write("| 严重程度 | 数量 |\n")
            f.write("|----------|------|\n")
            for severity, count in sorted(severity_stats.items()):
                f.write(f"| {severity} | {count} |\n")
            f.write("\n")

            # 详细BUG列表
            f.write("## BUG详情\n\n")

            for bug in self.bugs:
                f.write(f"### {bug['bug_id']}: {bug['title']}\n\n")
                f.write(f"**测试用例**: {bug['test_case_id']}\n")
                f.write(f"**发现时间**: {bug['timestamp']}\n")
                f.write(f"**严重程度**: {bug['severity']}\n")
                f.write(f"**状态**: {bug['status']}\n\n")

                f.write("**复现步骤**:\n```\n")
                f.write(f"步骤 {bug['step']['step_num']}: {bug['step']['step_name']}\n")
                f.write(f"```\n\n")

                f.write("**相关API**:\n```\n")
                f.write(f"{bug['api'].get('method', 'POST')} {bug['api'].get('endpoint', '')}\n")
                f.write(f"```\n\n")

                f.write("**错误信息**:\n```\n")
                f.write(f"{bug['description']}\n")
                f.write(f"```\n\n")

                f.write("**预期行为**: {bug['expected']}\n\n")
                f.write("**实际行为**: {bug['actual']}\n\n")

                if bug.get('test_data'):
                    f.write("**测试数据**:\n```yaml\n")
                    import yaml
                    f.write(yaml.dump(bug['test_data'], allow_unicode=True))
                    f.write("```\n\n")

                f.write("---\n\n")

        logger.info(f"Bug list exported to {output_file}")
