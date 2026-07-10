#!/usr/bin/env python3
"""
验证 PaddleOCR（CPU）是否安装正确、能正常识别图片文字。
用法：在项目根目录执行（或把 图片路径 换成你的图片）：
  python tools/verify_paddle_ocr.py
  python tools/verify_paddle_ocr.py /path/to/your/image.jpg
"""
import os
import sys
from pathlib import Path

# 必须在 import paddle 相关模块之前设置
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"  # 跳过模型源连通性检查
os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")       # 使用国内源（百度 BOS）下载模型
os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLP_LOG_LEVEL", "ERROR")
os.environ.setdefault("PADDLEOCR_LOG_LEVEL", "ERROR")
# 禁用 OneDNN/MKLDNN，避免 CPU 推理时报 ConvertPirAttribute2RuntimeAttribute not support
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_use_dnnl"] = "0"

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    if len(sys.argv) >= 2:
        image_path = Path(sys.argv[1])
    else:
        # 默认用测试图片（若存在）
        default = ROOT / "tests" / "test_images" / "award"
        candidates = list(default.glob("*.jpg")) + list(default.glob("*.png")) if default.exists() else []
        if not candidates:
            print("用法: python tools/verify_paddle_ocr.py <图片路径>")
            print("示例: python tools/verify_paddle_ocr.py /home/ubuntu/csddata/test.jpg")
            sys.exit(1)
        image_path = candidates[0]
        print(f"未传入图片路径，使用: {image_path}")

    if not image_path.exists():
        print(f"错误: 文件不存在: {image_path}")
        sys.exit(1)

    image_path = str(image_path.resolve())
    print("PaddleOCR 初始化中（CPU, 中文）...")

    try:
        from paddleocr import PaddleOCR
    except Exception as e:
        err = str(e)
        if "libGL.so.1" in err or "libGL" in err:
            print("错误: 缺少 OpenGL 库（无头服务器常见）。请先安装系统依赖：")
            print("  sudo apt update && sudo apt install -y libgl1 libglib2.0-0")
            print("（Ubuntu 24+ 用 libgl1；若为 22.04 可试 libgl1-mesa-glx）")
            print("然后重新运行本脚本。")
        else:
            print(f"错误: PaddleOCR 加载失败。若未安装请执行: pip install paddlepaddle paddleocr\n{e}")
        sys.exit(1)

    # 新版 PaddleOCR：device="cpu"，use_textline_orientation 替代 use_angle_cls；部分版本不支持 show_log
    # 初始化时临时屏蔽 PaddleOCR 的 "Connectivity check ... skipped" 等提示
    with open(os.devnull, "w") as devnull:
        _stdout, _stderr = sys.stdout, sys.stderr
        try:
            sys.stdout = sys.stderr = devnull
            ocr = PaddleOCR(device="cpu", lang="ch", use_textline_orientation=False)
        finally:
            sys.stdout, sys.stderr = _stdout, _stderr
    # 新版 API 使用 predict；返回格式与 ocr() 兼容（list of [box, (text, conf)]）
    try:
        result = ocr.predict(image_path)
    except NotImplementedError as e:
        if "ConvertPirAttribute2RuntimeAttribute" in str(e) or "onednn" in str(e).lower():
            print("错误: 当前 PaddlePaddle 版本在 CPU 上存在已知问题。请降级到 3.2.0：")
            print("  pip uninstall paddlepaddle -y")
            print("  pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/")
            print("详见 docs/PaddleOCR模型路径与国内源.md 第三节。")
        else:
            raise
        sys.exit(1)
    if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
        result = list(result)
    # 单张图时可能为 [page_result] 或直接一页结果
    if not result:
        print("识别结果为空（可能图片无文字或格式不支持）。")
        sys.exit(0)
    page = result[0] if isinstance(result[0], (list, tuple)) else result
    if not page:
        print("识别结果为空。")
        sys.exit(0)

    lines = []
    for line in page:
        if not line:
            continue
        text = None
        if isinstance(line, dict):
            text = line.get("transcription") or line.get("text") or line.get("rec_text")
        elif isinstance(line, (list, tuple)) and len(line) >= 2:
            part = line[1]
            text = part[0] if isinstance(part, (list, tuple)) else part
        if text is not None:
            lines.append(str(text))
    text = "\n".join(lines)
    print("识别到的文字：")
    print("-" * 40)
    print(text)
    print("-" * 40)
    print(f"共 {len(lines)} 行，{len(text)} 字。PaddleOCR 工作正常。")


if __name__ == "__main__":
    main()
