"""P0-8 回归测试：竖图不得被宽高比启发式旋转（手机竖拍证书=主流输入）。"""
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

SRC = PROJECT_ROOT / 'backend' / 'ocr' / 'core' / 'providers.py'


def _compress_methods() -> dict:
    """AST 提取所有 _compress_image 方法体源码（基类+子类覆盖均检查）。"""
    tree = ast.parse(SRC.read_text(encoding='utf-8'))
    out = {}
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        for fn in [n for n in cls.body if isinstance(n, (ast.FunctionDef,)) and n.name == '_compress_image']:
            out[f"{cls.name}._compress_image"] = ast.get_source_segment(SRC.read_text(encoding='utf-8'), fn)
    return out


def test_rotate_heuristic_removed():
    """任何 _compress_image 实现中不得再出现 rotate( 调用（方向只由 EXIF 决定）。"""
    methods = _compress_methods()
    assert methods, '未找到 _compress_image'
    for name, src in methods.items():
        assert '.rotate(' not in src, f'{name} 仍含旋转启发式'


def test_exif_transpose_kept():
    """EXIF 方向校正必须保留（删启发式不能误删正道）。"""
    full = SRC.read_text(encoding='utf-8')
    assert 'exif_transpose' in full


def test_vertical_image_dimensions_preserved(tmp_path):
    """行为级验证：构造 1080x1920 竖图（无 EXIF），压缩后宽高比仍为竖（不被横置）。"""
    from PIL import Image
    from backend.ocr.core.providers import RapidOCRProvider  # 任意继承 _compress_image 的轻量 provider
    import logging

    img_path = tmp_path / "vertical.png"
    Image.new("RGB", (1080, 1920), "white").save(img_path)

    class _P(RapidOCRProvider):
        def __init__(self):
            self.logger = logging.getLogger('t')
            self.max_image_size = 4000
            self.jpeg_quality = 85

    # RapidOCRProvider 若 __init__ 依赖重资源，绕过：直接调未绑定方法
    p = object.__new__(_P)
    p.logger = logging.getLogger('t')
    p.max_image_size = 4000
    p.jpeg_quality = 85
    data = p._compress_image(str(img_path))
    from PIL import Image as I
    import io
    with I.open(io.BytesIO(data)) as out:
        w, h = out.size
    assert h > w, f"竖图被横置了: {w}x{h}"
