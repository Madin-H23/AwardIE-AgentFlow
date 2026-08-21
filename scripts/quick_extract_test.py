"""
快速测试 single_extract.py

处理单张图片以验证功能。

支持命令行非交互运行：
  python tests/quick_extract_test.py --file "images_files/测试图片/奖状/教师证书.jpg" --report "批量文档抽取测试.html"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.extract_test import ExtractTester


def _project_root() -> Path:
    """项目根目录（基于脚本位置解析，避免受 cwd 影响）"""
    return Path(__file__).resolve().parent.parent


def _parse_args():
    project_root = _project_root()
    parser = argparse.ArgumentParser(description="快速单图片抽取测试")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="测试文件路径（相对项目根或绝对路径），指定后非交互运行",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="批量文档抽取测试.html",
        help="HTML 报告文件名，输出到 tests/reports/ 下（默认: 批量文档抽取测试.html）",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="生成报告后不自动打开浏览器",
    )
    args = parser.parse_args()
    if args.file is not None:
        p = Path(args.file)
        if not p.is_absolute():
            p = (project_root / p).resolve()
        else:
            p = p.resolve()
        args.file = p
    return args


def run_interactive():
    """交互式运行：菜单选缓存、选图片、生成报告"""
    print("=" * 60)
    print(" 快速测试 - 单图片抽取")
    print("=" * 60)

    tester = ExtractTester()
    tester.show_cache_menu()

    ocr_provider, llm_provider = tester.get_providers()
    tester.ocr_provider = ocr_provider
    tester.llm_provider = llm_provider

    print(f"\nOCR厂商: {ocr_provider.upper()}")
    print(f"LLM厂商: {llm_provider.upper()}")
    print(f"\n缓存设置:")
    print(f"  OCR缓存: {'启用' if tester.use_ocr_cache else '禁用'}")
    print(f"  LLM缓存: {'启用' if tester.use_llm_cache else '禁用'}")

    project_root = _project_root()
    test_dir = project_root / "images_files" / "测试图片" / "奖状"
    test_images = list(test_dir.glob("*.jpg")) if test_dir.exists() else []

    if not test_images:
        print(f"\n错误: 未找到测试图片在 {test_dir}")
        return

    print(f"\n找到 {len(test_images)} 张测试图片:")
    for idx, img in enumerate(test_images, 1):
        print(f"  {idx}. {img.name}")

    print(f"\n默认使用: {test_images[0].name}")
    choice = input("请输入序号选择其他图片 (直接回车使用默认): ").strip()

    if choice.isdigit():
        idx = int(choice) - 1
        test_image = test_images[idx] if 0 <= idx < len(test_images) else test_images[0]
    else:
        test_image = test_images[0]

    print(f"\n测试图片: {test_image.name}")
    print("\n处理中...")
    result = tester.process_file(test_image)
    tester.results.append(result)

    if result.get("error_message") or (result.get("data") and result.get("data", {}).get("note")):
        print("\n  [异常/other] 便于测试查看:")
        if result.get("error_message"):
            print(f"    error_message: {result['error_message']}")
        note = result.get("data", {}).get("note") if result.get("data") else None
        if note:
            print(f"    data.note: {note}")
        if result.get("status") in ("ocr_error", "llm_error", "no_template"):
            print(f"    status: {result.get('status')}")

    print("\n生成报告...")
    report_path = tester.generate_html_report("单图片抽取测试.html")
    print(f"\n完成! 报告路径: {report_path}")


def run_with_file(test_file: Path, report_name: str, open_browser: bool):
    """非交互运行：指定文件、报告名，默认启用双缓存"""
    print("=" * 60)
    print(" 快速测试 - 单图片抽取（非交互）")
    print("=" * 60)

    if not test_file.exists():
        raise FileNotFoundError(
            f"测试文件不存在: {test_file}\n（项目根: {_project_root()}）"
        )

    tester = ExtractTester()
    tester.use_ocr_cache = True
    tester.use_llm_cache = True

    ocr_provider, llm_provider = tester.get_providers()
    tester.ocr_provider = ocr_provider
    tester.llm_provider = llm_provider

    print(f"\nOCR厂商: {ocr_provider.upper()}")
    print(f"LLM厂商: {llm_provider.upper()}")
    print(f"缓存: OCR=启用, LLM=启用")
    print(f"测试文件: {test_file.name}")

    print("\n处理中...")
    result = tester.process_file(test_file)
    tester.results.append(result)

    if result.get("error_message") or (result.get("data") and result.get("data", {}).get("note")):
        print("\n  [异常/other] 便于测试查看:")
        if result.get("error_message"):
            print(f"    error_message: {result['error_message']}")
        note = result.get("data", {}).get("note") if result.get("data") else None
        if note:
            print(f"    data.note: {note}")
    if result.get("template_id") is not None or result.get("template_name"):
        print(f"  匹配模板: ID={result.get('template_id')}, 名称={result.get('template_name')}")
    else:
        print("  无奖状模板匹配")

    print("\n生成报告...")
    report_path = tester.generate_html_report(report_name, open_browser=open_browser)
    print(f"\n完成! 报告路径: {report_path}")
    return report_path


def main():
    args = _parse_args()

    if args.file is not None:
        run_with_file(args.file, args.report, open_browser=not args.no_browser)
    else:
        run_interactive()


if __name__ == "__main__":
    main()
