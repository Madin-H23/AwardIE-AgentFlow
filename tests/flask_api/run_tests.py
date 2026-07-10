#!/usr/bin/env python
"""
Flask API 测试执行入口

使用方法:
    python tests/flask_api/run_tests.py              # 运行所有测试
    python tests/flask_api/run_tests.py --priority P0  # 只运行P0优先级
    python tests/flask_api/run_tests.py --scenario TC_001  # 运行指定测试用例
"""
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.flask_api.utils.test_runner import TestRunner

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / 'tests/flask_api/reports/test_run.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Flask API 业务流程测试')
    parser.add_argument('--priority', '-p',
                       choices=['P0', 'P1', 'P2'],
                       help='只运行指定优先级的测试用例')
    parser.add_argument('--scenario', '-s',
                       help='运行指定的测试用例（如 TC_001）')
    parser.add_argument('--list', '-l',
                       action='store_true',
                       help='列出所有可用的测试用例')
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='详细输出模式')

    args = parser.parse_args()

    # 初始化测试运行器
    runner = TestRunner()

    # 列出测试用例
    if args.list:
        print("\nAvailable test cases:\n")
        for scenario in runner.test_cases.get('test_scenarios', []):
            priority = scenario.get('priority', 'N/A')
            print(f"[{priority}] {scenario['id']}: {scenario['name']}")
            print(f"   Category: {scenario.get('category', 'N/A')}")
            print(f"   Description: {scenario.get('description', '')}")
            print()
        return

    # 运行单个测试用例
    if args.scenario:
        scenario = next(
            (s for s in runner.test_cases.get('test_scenarios', [])
             if s['id'] == args.scenario),
            None
        )
        if not scenario:
            logger.error(f"测试用例 {args.scenario} 不存在")
            return 1

        logger.info(f"运行单个测试用例: {args.scenario}")
        context = runner.run_test_case(scenario)

        # 输出结果
        summary = context.get_summary()
        print(f"\n测试结果: {summary['passed_assertions']}/{summary['total_assertions']} 断言通过")

        if summary['failed_assertions'] > 0:
            print(f"失败的断言:")
            for assertion in context.get_failed_assertions():
                print(f"  - {assertion.description}: {assertion.error_msg}")

        return 0 if summary['failed_assertions'] == 0 else 1

    # 运行所有测试（可按优先级过滤）
    logger.info("="*60)
    logger.info("开始执行 Flask API 测试")
    logger.info("="*60)

    # 检查服务器是否运行
    logger.info("检查 Flask 服务器...")
    import requests
    try:
        response = requests.get("http://127.0.0.1:5001/login", timeout=5)
        logger.info("✓ Flask 服务器正在运行")
    except requests.exceptions.RequestException:
        logger.error("✗ Flask 服务器未运行，请先启动服务器:")
        logger.error("  python run.py")
        return 1

    # 运行测试
    bug_report = runner.run_all_tests(filter_priority=args.priority)

    # 生成报告
    report = runner.generate_report()

    # 保存报告
    report_file = project_root / "tests/flask_api/reports/test_report.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info(f"\n测试完成！报告已保存到: {report_file}")
    logger.info(f"BUG清单已保存到: {project_root}/tests/flask_api/reports/bug_list.md")

    # 输出摘要
    print("\n" + "="*60)
    print("测试摘要")
    print("="*60)
    print(f"发现 BUG 数量: {len(bug_report.bugs)}")

    if bug_report.bugs:
        print("\n严重程度统计:")
        severity_stats = {}
        for bug in bug_report.bugs:
            severity_stats[bug['severity']] = severity_stats.get(bug['severity'], 0) + 1

        for severity, count in sorted(severity_stats.items()):
            print(f"  {severity}: {count}")

    return 0 if len(bug_report.bugs) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
