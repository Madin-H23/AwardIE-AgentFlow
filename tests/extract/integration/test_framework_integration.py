"""
抽取框架集成测试

使用真实文件测试OCR、LLM和框架的完整集成流程。

测试文件来源：tests/test_images/other/
- PDF文件：23吴思颖-HCIE证书.pdf
- 普通图片：照片2.jpg
- 奖状图片：大数据挑战赛赛项 华东赛区省赛本研组 二等奖.png
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List

# 项目根
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.extract import ExtractFramework, Extractor, ExtractorValidator
from backend.extract.types import ExtractResult, ExtractStatus, TemplateType
from backend.extract.extractors.base import Extractor, ExtractContext


@dataclass
class IntegrationTestResult:
    """集成测试结果"""
    name: str
    passed: bool
    message: str
    duration: float = 0.0
    result: ExtractResult = None


class MockAwardExtractor(Extractor):
    """Mock奖状抽取器（用于测试）"""

    def __init__(self):
        super().__init__(
            name="award",
            description="奖状抽取器，用于识别各类竞赛奖状证书",
            keywords=["奖", "竞赛", "挑战赛", "杯", "大赛", "证书", "获奖"],
            judgment_text="识别各类竞赛奖状证书，包括蓝桥杯、挑战赛等",
            extensions=[".jpg", ".jpeg", ".png", ".gif", ".bmp", ".pdf"],
            validator=None,
        )

    def extract(self, ctx: ExtractContext) -> ExtractResult:
        # 如果是测试环境（没有配置API Key），返回模拟结果
        if ctx.ocr_text:
            # 检查关键词
            text = ctx.ocr_text.lower()
            if any(k in text for k in ["奖", "竞赛", "挑战赛", "杯", "大赛", "证书"]):
                return ExtractResult(
                    status=ExtractStatus.SUCCESS,
                    data={"note": "模拟抽取成功：识别到奖状内容", "ocr_text_length": len(ctx.ocr_text)},
                    template_type=TemplateType.AWARD,
                )
        return ExtractResult(
            status=ExtractStatus.NO_TEMPLATE,
            data={"note": "不匹配奖状特征"},
            template_type=TemplateType.OTHER,
        )


def run_integration_tests() -> List[IntegrationTestResult]:
    """运行所有集成测试"""
    results = []

    # 测试文件路径
    test_images_dir = project_root / "tests" / "test_images" / "other"

    # 检查是否有API Key配置
    config_path = project_root / "apikey" / "apikey.json"
    has_api_key = False
    if config_path.exists():
        import json
        with open(config_path, 'r', encoding='utf-8') as f:
            apikey_config = json.load(f)
            llm_config = apikey_config.get('llm', {})
            # 检查是否有配置了API Key的provider
            for provider_name, provider_config in llm_config.get('providers', {}).items():
                api_key_env = provider_config.get('api_key_env')
                if api_key_env and os.getenv(api_key_env):
                    has_api_key = True
                    break

    # 测试1：PDF文件处理
    results.append(_test_pdf_processing(test_images_dir, has_api_key))

    # 测试2：普通图片（应该返回other）
    results.append(_test_normal_image(test_images_dir, has_api_key))

    # 测试3：奖状图片（应该返回award）
    results.append(_test_award_image(test_images_dir, has_api_key))

    # 测试4：不支持的扩展名
    results.append(_test_unsupported_extension())

    return results


def _test_pdf_processing(test_dir: Path, has_api_key: bool) -> IntegrationTestResult:
    """测试PDF文件处理"""
    name = "PDF文件处理"
    start_time = time.time()

    pdf_file = test_dir / "23吴思颖-HCIE证书.pdf"
    if not pdf_file.exists():
        return IntegrationTestResult(
            name=name,
            passed=False,
            message=f"测试文件不存在: {pdf_file}",
            duration=time.time() - start_time,
        )

    try:
        from config.loader import get_config

        config_loader = get_config()
        framework = ExtractFramework.from_config_loader(config_loader)
        framework.register(MockAwardExtractor())

        result = framework.extract(str(pdf_file), use_ocr_cache=True, use_llm_cache=True)

        # 验证结果
        ok = (
            result.status in [ExtractStatus.SUCCESS, ExtractStatus.NO_TEMPLATE]
            and result.ocr_text is not None
            and len(result.ocr_text) > 0
            and result.ocr_cache_hit is not None  # 确保设置了缓存状态
        )

        message = f"OCR识别文本长度: {len(result.ocr_text) if result.ocr_text else 0}, "
        message += f"状态: {result.status.value}, 模板类型: {result.template_type}, "
        message += f"缓存命中: {result.ocr_cache_hit}"

        return IntegrationTestResult(
            name=name,
            passed=ok,
            message=message,
            duration=time.time() - start_time,
            result=result,
        )

    except Exception as e:
        return IntegrationTestResult(
            name=name,
            passed=False,
            message=f"测试失败: {e}",
            duration=time.time() - start_time,
        )


def _test_normal_image(test_dir: Path, has_api_key: bool) -> IntegrationTestResult:
    """测试普通图片（应该返回other）"""
    name = "普通图片处理"
    start_time = time.time()

    image_file = test_dir / "照片2.jpg"
    if not image_file.exists():
        return IntegrationTestResult(
            name=name,
            passed=False,
            message=f"测试文件不存在: {image_file}",
            duration=time.time() - start_time,
        )

    try:
        from config.loader import get_config

        config_loader = get_config()
        framework = ExtractFramework.from_config_loader(config_loader)
        framework.register(MockAwardExtractor())

        result = framework.extract(str(image_file), use_ocr_cache=True, use_llm_cache=True)

        # 验证结果
        ok = (
            result.template_type == TemplateType.OTHER
            and result.ocr_text is not None
            and result.extractor_name == "other"
        )

        message = f"OCR识别文本长度: {len(result.ocr_text) if result.ocr_text else 0}, "
        message += f"模板类型: {result.template_type}, 提示: {result.data.get('note', '')}"

        return IntegrationTestResult(
            name=name,
            passed=ok,
            message=message,
            duration=time.time() - start_time,
            result=result,
        )

    except Exception as e:
        return IntegrationTestResult(
            name=name,
            passed=False,
            message=f"测试失败: {e}",
            duration=time.time() - start_time,
        )


def _test_award_image(test_dir: Path, has_api_key: bool) -> IntegrationTestResult:
    """测试奖状图片（应该返回award）"""
    name = "奖状图片处理"
    start_time = time.time()

    # 使用一个包含"奖"字的图片
    image_file = test_dir / "大数据挑战赛赛项 华东赛区省赛本研组 二等奖.png"
    if not image_file.exists():
        return IntegrationTestResult(
            name=name,
            passed=False,
            message=f"测试文件不存在: {image_file}",
            duration=time.time() - start_time,
        )

    try:
        from config.loader import get_config

        config_loader = get_config()
        framework = ExtractFramework.from_config_loader(config_loader)
        framework.register(MockAwardExtractor())

        result = framework.extract(str(image_file), use_ocr_cache=True, use_llm_cache=True)

        # 验证结果
        ok = (
            result.template_type == TemplateType.AWARD
            and result.ocr_text is not None
            and result.extractor_name == "award"
        )

        message = f"OCR识别文本长度: {len(result.ocr_text) if result.ocr_text else 0}, "
        message += f"模板类型: {result.template_type}, 抽取器: {result.extractor_name}"

        return IntegrationTestResult(
            name=name,
            passed=ok,
            message=message,
            duration=time.time() - start_time,
            result=result,
        )

    except Exception as e:
        return IntegrationTestResult(
            name=name,
            passed=False,
            message=f"测试失败: {e}",
            duration=time.time() - start_time,
        )


def _test_unsupported_extension() -> IntegrationTestResult:
    """测试不支持的扩展名"""
    name = "不支持的扩展名"
    start_time = time.time()

    try:
        from config.loader import get_config
        import tempfile

        config_loader = get_config()
        framework = ExtractFramework.from_config_loader(config_loader)
        framework.register(MockAwardExtractor())

        # 创建一个临时的不支持扩展名文件
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            temp_path = f.name

        try:
            result = framework.extract(temp_path, use_ocr_cache=True, use_llm_cache=True)

            # 验证结果
            ok = (
                result.template_type == TemplateType.OTHER
                and result.data.get("note") == "不支持的文件扩展名"
            )

            message = f"模板类型: {result.template_type}, 提示: {result.data.get('note', '')}"

            return IntegrationTestResult(
                name=name,
                passed=ok,
                message=message,
                duration=time.time() - start_time,
                result=result,
            )

        finally:
            # 删除临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        return IntegrationTestResult(
            name=name,
            passed=False,
            message=f"测试失败: {e}",
            duration=time.time() - start_time,
        )


def write_report(results: List[IntegrationTestResult], report_dir: Path) -> None:
    """生成测试报告"""
    report_dir.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    lines = [
        "# 抽取框架集成测试报告",
        "",
        f"运行时间: {datetime.now().isoformat()}",
        f"通过: {passed} / {total}",
        "",
        "| 用例 | 结果 | 说明 | 耗时",
        "|------|------|------|--------|",
    ]
    for r in results:
        status = "通过" if r.passed else "失败"
        lines.append(f"| {r.name} | {status} | {r.message[:80]} | {r.duration:.2f}s |")
    path = report_dir / "集成测试报告.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已保存到: {path}")


if __name__ == "__main__":
    print("=" * 60)
    print("抽取框架集成测试")
    print("=" * 60)
    print()

    results = run_integration_tests()

    # 打印结果
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"{status}: {r.name} - {r.message}")

    # 统计
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    failed = total - passed

    print()
    print("=" * 60)
    print(f"总计: {total}, 通过: {passed}, 失败: {failed}")
    print("=" * 60)

    # 生成报告
    report_dir = project_root / "tests" / "reports" / "extract" / "集成测试"
    write_report(results, report_dir)

    if failed > 0:
        raise SystemExit(1)
