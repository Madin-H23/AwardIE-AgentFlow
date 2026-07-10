"""
验证 Baidu OCR Provider 是否正常工作

模拟 tests/demo/glm_4v_flash_ocr_demo.py 的方式
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def test_baidu_ocr():
    """测试 Baidu OCR"""
    print("="*60)
    print(" Baidu OCR 验证测试")
    print("="*60)

    # 检查环境变量
    print("\n[1] 检查环境变量:")
    api_key = os.getenv("BAIDU_API_KEY")
    secret_key = os.getenv("BAIDU_SECRET_KEY")

    if not api_key or not secret_key:
        print("ERROR: 环境变量未设置")
        print("  请设置 BAIDU_API_KEY 和 BAIDU_SECRET_KEY")
        return False

    print(f"  BAIDU_API_KEY: {api_key[:10]}...{api_key[-4:]}")
    print(f"  BAIDU_SECRET_KEY: {secret_key[:10]}...{secret_key[-4:]}")

    # 获取测试图片
    print("\n[2] 获取测试图片:")
    test_images_dir = project_root / "tests" / "test_images" / "award" / "chinese"
    test_images = list(test_images_dir.glob("*.jpg"))

    if not test_images:
        print("ERROR: 未找到测试图片")
        return False

    test_image = str(test_images[0])
    print(f"  测试图片: {Path(test_image).name}")

    # 创建 Provider
    print("\n[3] 创建 Baidu OCR Provider:")
    from config.loader import get_config
    from backend.ocr.core.provider_factory import ProviderFactory
    from backend.ocr.config import OCRConfig
    from backend.ocr.core.ocr_engine import OCREngine
    import logging

    logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

    config_loader = get_config()
    config = config_loader.load_config()
    baidu_config = config.get('ocr', {}).get('providers', {}).get('baidu', {})

    factory = ProviderFactory(logging.getLogger())
    common_config = {
        'debug': False,
        'max_image_size': 2048,
        'jpeg_quality': 85,
    }

    try:
        provider = factory.create_provider(
            provider_name='baidu',
            provider_config=baidu_config,
            common_config=common_config
        )
        print("  OK: BaiduOCRProvider 创建成功")
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # 执行 OCR
    print("\n[4] 执行 OCR 识别:")
    try:
        ocr_config = OCRConfig(
            provider='baidu',
            db_path=str(project_root / "database" / "ocr_cache.db"),
            temp_dir=str(project_root / "temp" / "ocr_test"),
            debug=False
        )

        engine = OCREngine(ocr_config, provider_config=baidu_config)
        text, from_cache = engine.get_text(test_image, use_cache=False)

        print(f"  识别成功!")
        print(f"  字符数: {len(text)}")
        print(f"  来自缓存: {from_cache}")

        print("\n[5] 识别结果预览:")
        print("-" * 60)
        # 显示前 500 个字符
        preview = text[:500] if len(text) > 500 else text
        print(preview)
        if len(text) > 500:
            print(f"\n... (还有 {len(text) - 500} 个字符)")
        print("-" * 60)

        print("\n" + "="*60)
        print(" 测试通过: Baidu OCR 工作正常")
        print("="*60)
        return True

    except Exception as e:
        print(f"  ERROR: OCR 失败")
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_baidu_ocr()
    sys.exit(0 if success else 1)
