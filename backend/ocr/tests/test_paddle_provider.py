"""
PaddleOCR Provider 单元测试

遵循 TDD 方法：
1. 先写测试
2. 运行测试验证失败
3. 实现功能
4. 运行测试验证通过
"""
import pytest
from pathlib import Path
from pathlib import Path
import sys
import logging

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from ocr_core.core.providers import PaddleOCRProvider
from ocr_core.config import OCRConfig
from ocr_core.exceptions import OCRAPIServiceError


def test_paddle_provider_init():
    """测试 PaddleOCR Provider 初始化"""
    logger = logging.getLogger(__name__)

    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    config = OCRConfig(
        db_path=str(temp_dir / "test_ocr_cache.db"),
        temp_dir=str(temp_dir / "ocr_temp"),
        provider="paddle",
        device="cpu",
        lang="ch",
        ocr_version="PP-OCRv5"
    )

    provider = PaddleOCRProvider(config, logger)
    assert provider.device == "cpu"
    assert provider.lang == "ch"
    assert provider.ocr_version == "PP-OCRv5"


def test_paddle_provider_ocr_image():
    """测试 PaddleOCR 识别（需要安装 PaddleOCR）"""
    pytest.skip("跳过：需要安装 PaddleOCR 和模型文件")
    # 实际测试在集成测试中进行


def test_paddle_provider_init_with_custom_params():
    """测试使用自定义参数初始化 PaddleOCR Provider"""
    logger = logging.getLogger(__name__)

    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    config = OCRConfig(
        db_path=str(temp_dir / "test_ocr_cache.db"),
        temp_dir=str(temp_dir / "ocr_temp"),
        provider="paddle",
        device="gpu",
        lang="en",
        ocr_version="PP-OCRv4",
        use_doc_orientation_classify=True,
        use_doc_unwarping=True,
        use_textline_orientation=True
    )

    provider = PaddleOCRProvider(config, logger)
    assert provider.device == "gpu"
    assert provider.lang == "en"
    assert provider.ocr_version == "PP-OCRv4"
    assert provider.use_doc_orientation_classify is True
    assert provider.use_doc_unwarping is True
    assert provider.use_textline_orientation is True


def test_paddle_provider_lazy_init():
    """测试 PaddleOCR 延迟初始化"""
    logger = logging.getLogger(__name__)

    config = OCRConfig(
        provider="paddle",
        device="cpu",
        lang="ch"
    )

    provider = PaddleOCRProvider(config, logger)
    # 初始化时不应立即加载 PaddleOCR
    assert provider._ocr is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
