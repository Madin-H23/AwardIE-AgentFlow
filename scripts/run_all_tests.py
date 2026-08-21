"""
统一测试运行器

运行所有测试套件，生成综合报告。
"""
import sys
from pathlib import Path

# 设置项目根目录
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os
import subprocess
import time
from datetime import datetime
from typing import Tuple


def run_test_suite(name: str, script_path: str) -> Tuple[bool, str]:
    """运行单个测试套件"""
    print(f"\n{'=' * 60}")
    print(f"运行测试套件: {name}")
    print(f"{'=' * 60}")
    
    start_time = time.time()
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"[PASS] {name} - 耗时 {elapsed:.2f}秒")
            return True, result.stdout or ""
        else:
            print(f"[FAIL] {name} - 耗时 {elapsed:.2f}秒")
            # 只输出关键错误信息，避免编码问题
            if result.stdout:
                try:
                    print(result.stdout[-500:])  # 只输出最后500字符
                except:
                    pass
            if result.stderr:
                try:
                    print(result.stderr[-500:])  # 只输出最后500字符
                except:
                    pass
            return False, (result.stdout or "") + (result.stderr or "")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[ERROR] {name} - 执行失败: {e} - 耗时 {elapsed:.2f}秒")
        return False, str(e)


def main():
    """主函数"""
    print("=" * 60)
    print("统一测试运行器")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 定义测试套件
    test_suites = [
        ("文件流转测试", "tests/test_files.py"),
        ("页面渲染测试", "tests/test_page_rendering.py"),
        ("路由完整性测试", "tests/test_routes_integrity.py"),
        ("首页渲染测试", "tests/test_index_page.py"),
    ]
    
    results = []
    total_start = time.time()
    
    # 运行所有测试套件
    for name, script in test_suites:
        script_path = project_root / script
        if not script_path.exists():
            print(f"[SKIP] {name} - 测试文件不存在: {script}")
            results.append((name, False, f"测试文件不存在: {script}"))
            continue
        
        success, output = run_test_suite(name, str(script_path))
        results.append((name, success, output))
    
    total_elapsed = time.time() - total_start
    
    # 生成总结报告
    print("\n" + "=" * 60)
    print("测试总结报告")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"\n总计: {total} 个测试套件")
    print(f"通过: {passed}")
    print(f"失败: {total - passed}")
    print(f"总耗时: {total_elapsed:.2f}秒")
    
    print("\n详细结果:")
    for name, success, _ in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {name}")
    
    # 返回退出码
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
