"""
临时脚本：测试 PIL / OpenCV 读取 NO.ISCC 图片
- 页面能显示说明浏览器能解码，PIL/OpenCV 失败可能是路径编码或 PNG 变体问题
- 使用字节流 + cv2.imdecode 可绕过 Windows 路径编码问题
"""
import sys
from pathlib import Path

# 项目根
ROOT = Path(__file__).resolve().parent.parent
# 图片路径（与 file_import 中一致：files/temp_upload/session_id/hash.png）
IMAGE_REL = "files/temp_upload/1c314c7e-d25f-4597-a536-ea25bca702de/4297ec598c78e5e86af98d2eae76c907.png"
IMAGE_PATH = ROOT / IMAGE_REL


def main():
    if not IMAGE_PATH.exists():
        print(f"文件不存在: {IMAGE_PATH}")
        return 1

    path_str = str(IMAGE_PATH)
    print(f"路径(字符串): {path_str}")
    print(f"路径(repr):   {repr(path_str)}")
    print()

    # 1. PIL
    print("1. PIL Image.open(路径字符串)")
    try:
        from PIL import Image
        with Image.open(path_str) as img:
            img.load()
        print(f"   成功: size={img.size}, mode={img.mode}")
    except Exception as e:
        print(f"   失败: {type(e).__name__}: {e}")

    # 2. OpenCV 路径字符串（Windows 中文路径可能失败）
    print("\n2. cv2.imread(路径字符串)")
    try:
        import cv2
        img = cv2.imread(path_str, cv2.IMREAD_UNCHANGED)
        if img is not None:
            print(f"   成功: shape={img.shape}")
        else:
            print("   失败: cv2.imread 返回 None（常见于中文路径/编码）")
    except Exception as e:
        print(f"   失败: {type(e).__name__}: {e}")

    # 3. OpenCV 字节流（绕过路径，与浏览器读文件类似）
    print("\n3. 读文件字节 + cv2.imdecode(字节)")
    try:
        import cv2
        import numpy as np
        with open(IMAGE_PATH, "rb") as f:
            buf = f.read()
        arr = np.frombuffer(buf, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img is not None:
            print(f"   成功: shape={img.shape}, 字节长度={len(buf)}")
        else:
            print("   失败: cv2.imdecode 返回 None（PNG 内容可能不兼容）")
    except Exception as e:
        print(f"   失败: {type(e).__name__}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
