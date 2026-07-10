"""
Flask API 测试执行器
数据驱动的测试执行引擎
"""
import yaml
import logging
import importlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from .api_client import FlaskAPIClient
from .assertions import AssertionContext, BugReport

logger = logging.getLogger(__name__)


class TestRunner:
    """测试执行器"""

    def __init__(self, config_dir: str = None):
        """
        初始化测试执行器

        Args:
            config_dir: 配置文件目录
        """
        self.project_root = Path(__file__).parent.parent.parent.parent
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = self.project_root / "tests/flask_api/fixtures"

        # 加载配置
        self.test_data = self._load_yaml("test_data.yaml")
        self.test_cases = self._load_yaml("test_cases.yaml")

        # 初始化客户端
        self.client = FlaskAPIClient()

        # 测试结果
        self.results = []
        self.bug_report = BugReport()

        # 测试用户映射
        self.test_users = self.test_data.get('test_users', {})

        logger.info("TestRunner initialized")

    def _load_yaml(self, filename: str) -> Dict:
        """加载YAML配置"""
        file_path = self.config_dir / filename
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            return {}

    def _get_sample_by_id(self, sample_id: str) -> Optional[Dict]:
        """根据ID获取测试样本"""
        for sample in self.test_data.get('test_samples', []):
            if sample['id'] == sample_id:
                return sample
        return None

    def _get_user_info(self, user_key: str) -> Optional[Dict]:
        """获取测试用户信息"""
        return self.test_users.get(user_key)

    def run_test_case(self, test_case: Dict) -> AssertionContext:
        """
        执行单个测试用例

        Args:
            test_case: 测试用例配置

        Returns:
            AssertionContext
        """
        test_id = test_case['id']
        test_name = test_case['name']
        logger.info(f"\n{'='*60}")
        logger.info(f"Running test case: {test_id} - {test_name}")
        logger.info(f"{'='*60}")

        context = AssertionContext(test_id)

        try:
            # 执行每个步骤
            for step in test_case.get('steps', []):
                self._execute_step(step, context)

                # 如果步骤失败且设置了快速失败，则中断
                if context.get_failed_assertions() and test_case.get('fail_fast', False):
                    logger.error(f"Test case {test_id} failed at step {context.current_step}")
                    break

            # 执行清理
            self._execute_cleanup(test_case, context)

        except Exception as e:
            logger.error(f"Test case {test_id} crashed: {e}")
            context.add_step("Test crashed")
            context.assert_true(
                "Test execution completed without crash",
                False,
                str(e)
            )

        return context

    def _execute_step(self, step: Dict, context: AssertionContext):
        """执行单个步骤"""
        action = step.get('action')
        api = step.get('api', '')
        user = step.get('user')
        params = step.get('params', {})
        assertions = step.get('assertions', [])
        capture = step.get('capture', {})

        context.add_step(f"{action}: {api}")

        # 执行动作
        if action == 'login':
            self._action_login(user, context)
        elif action == 'logout':
            self.client.logout()
        elif action == 'get_page':
            self._action_get(api, params, context)
        elif action == 'upload_files':
            self._action_upload_files(step, context)
        elif action == 'batch_submit':
            self._action_batch_submit(step, context)
        elif action == 'check_visibility':
            self._action_check_visibility(step, context)
        elif action == 'approve':
            self._action_approve(step, context)
        # TODO: 添加更多动作类型

        # 执行断言
        for assertion_str in assertions:
            self._evaluate_assertion(assertion_str, context, step)

        # 捕获变量
        for var_name, value_expr in capture.items():
            resolved_value = self.client.resolve_value(value_expr)
            context.variables[var_name] = resolved_value

    def _action_login(self, user_key: str, context: AssertionContext):
        """执行登录动作"""
        user_info = self._get_user_info(user_key)
        if not user_info:
            context.assert_true(f"User {user_key} exists", False, "User not found in config")
            return

        username = user_info.get('user_id')
        password = user_info.get('password')

        success, error = self.client.login(username, password)
        context.assert_true(
            f"Login as {user_info['name']} ({user_info['role']})",
            success,
            error
        )

    def _action_get(self, endpoint: str, params: Dict, context: AssertionContext):
        """执行GET请求"""
        success, result = self.client.get(endpoint, params=params, expect_json=True)
        context.assert_true(f"GET {endpoint} success", success)

        if success and isinstance(result, dict):
            # 存储响应供后续断言使用
            context.last_response = result

    def _action_upload_files(self, step: Dict, context: AssertionContext):
        """执行文件上传"""
        files = step.get('files', [])
        endpoint = step.get('api')

        uploaded_ids = []

        for sample_id in files:
            sample = self._get_sample_by_id(sample_id)
            if not sample:
                context.assert_true(f"Sample {sample_id} exists", False)
                continue

            file_path = sample.get('file_path')
            full_path = self.project_root / file_path

            success, result = self.client.upload_file(endpoint, str(full_path),
                                                     step.get('params'))

            context.assert_true(f"Upload {sample_id} success", success)

            if success and isinstance(result, dict):
                # 捕获pending_id
                if 'pending_id' in result:
                    uploaded_ids.append(result['pending_id'])
                elif 'pending_ids' in result:
                    uploaded_ids.extend(result['pending_ids'])

        context.client.capture_var('pending_ids', uploaded_ids)

    def _action_batch_submit(self, step: Dict, context: AssertionContext):
        """执行批量提交"""
        endpoint = step.get('api')
        params = step.get('params', {})

        # 解析变量
        resolved_params = {}
        for key, value in params.items():
            resolved_params[key] = self.client.resolve_value(value)

        success, result = self.client.post(endpoint, data=resolved_params)
        context.assert_true(f"Batch submit success", success)

        if success and isinstance(result, dict):
            if 'award_ids' in result:
                context.client.capture_var('award_ids', result['award_ids'])

    def _action_approve(self, step: Dict, context: AssertionContext):
        """执行审核通过"""
        endpoint = step.get('api')
        pending_id = self.client.resolve_value(step.get('pending_id', ''))
        endpoint = endpoint.replace('${pending_id}', str(pending_id))

        success, result = self.client.post(endpoint)
        context.assert_true(f"Approve pending {pending_id} success", success)

        if success and isinstance(result, dict):
            if 'award_id' in result:
                context.client.capture_var('award_id', result['award_id'])

    def _action_check_visibility(self, step: Dict, context: AssertionContext):
        """检查可见性"""
        endpoint = step.get('api')
        success, result = self.client.get(endpoint, expect_json=True)

        context.assert_true(f"GET {endpoint} success", success)

        # 这里需要更复杂的逻辑来验证可见性
        # 简化版：假设result中有visible_ids字段
        pass

    def _evaluate_assertion(self, assertion_str: str, context: AssertionContext,
                           step: Dict):
        """评估断言"""
        # 简化的断言解析器
        # 实际实现需要解析更复杂的表达式

        if 'status_code ==' in assertion_str:
            # 解析状态码断言
            expected_status = int(assertion_str.split('==')[1].strip())
            if hasattr(context, 'last_response'):
                actual_status = context.last_response.get('status_code', 0)
                context.assert_status_code(actual_status, expected_status, step.get('api'))

        elif 'response[' in assertion_str:
            # 解析响应字段断言
            # 例如: response['success'] == True
            pass

        elif 'session[' in assertion_str:
            # 解析session断言
            pass

    def _execute_cleanup(self, test_case: Dict, context: AssertionContext):
        """执行清理操作"""
        cleanup = test_case.get('post_cleanup', [])
        if not cleanup:
            return

        logger.info("Executing cleanup...")

        for cleanup_action in cleanup:
            # 清理操作实现
            pass

    def run_all_tests(self, filter_priority: Optional[str] = None) -> BugReport:
        """
        运行所有测试用例

        Args:
            filter_priority: 过滤优先级 (P0, P1, P2)

        Returns:
            BugReport
        """
        all_scenarios = self.test_cases.get('test_scenarios', [])

        # 过滤测试用例
        if filter_priority:
            filtered_scenarios = [s for s in all_scenarios if s.get('priority') == filter_priority]
        else:
            filtered_scenarios = all_scenarios

        logger.info(f"Running {len(filtered_scenarios)} test scenarios...")

        for scenario in filtered_scenarios:
            context = self.run_test_case(scenario)
            self.results.append({
                'test_case': scenario,
                'context': context
            })

            # 收集失败的断言为BUG
            for assertion in context.get_failed_assertions():
                self.bug_report.add_bug(
                    test_case_id=scenario['id'],
                    assertion=assertion,
                    step_info=context.steps[context.current_step - 1]
                    if context.current_step > 0 else {},
                    api_info={'method': 'POST', 'endpoint': scenario.get('category', '')},
                    test_data={}
                )

        # 导出BUG报告
        report_file = self.project_root / "tests/flask_api/reports/bug_list.md"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        self.bug_report.export_to_markdown(str(report_file))

        return self.bug_report

    def generate_report(self) -> str:
        """生成测试报告"""
        total_cases = len(self.results)
        total_assertions = sum(len(r['context'].assertions) for r in self.results)
        total_passed = sum(len([a for a in r['context'].assertions if a.passed])
                           for r in self.results)
        total_failed = total_assertions - total_passed

        report = f"""
# Flask API 测试报告

**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 测试摘要

| 项目 | 数量 |
|------|------|
| 测试用例数 | {total_cases} |
| 总断言数 | {total_assertions} |
| 通过断言 | {total_passed} |
| 失败断言 | {total_failed} |
| 通过率 | {(total_passed/total_assertions*100):.1f}% |

## 测试用例详情

"""

        for result in self.results:
            test_case = result['test_case']
            context = result['context']
            summary = context.get_summary()

            report += f"### {test_case['id']}: {test_case['name']}\n\n"
            report += f"- **优先级**: {test_case.get('priority', 'N/A')}\n"
            report += f"- **分类**: {test_case.get('category', 'N/A')}\n"
            report += f"- **状态**: {'✅ 通过' if summary['failed_assertions'] == 0 else '❌ 失败'}\n"
            report += f"- **断言**: {summary['passed_assertions']}/{summary['total_assertions']} 通过\n\n"

        # BUG清单引用
        report += f"\n## BUG清单\n\n"
        report += f"详细BUG信息请查看: `tests/flask_api/reports/bug_list.md`\n"
        report += f"共发现 {len(self.bug_report.bugs)} 个BUG\n"

        return report
