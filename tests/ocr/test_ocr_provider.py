"""
OCR 厂商对比测试程序

统一的 OCR 测试工具，支持交互式菜单选择。

使用方法:
    python tests/ocr/test_ocr_provider.py
"""
import os
import sys
import json
import time
import base64
import hashlib
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Any
from difflib import SequenceMatcher

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def calculate_similarity(text1: str, text2: str) -> float:
    """计算两个文本的相似度 (0-1)"""
    return SequenceMatcher(None, text1, text2).ratio()


def calculate_all_similarities(results: Dict[str, str]) -> Dict[str, Dict[str, float]]:
    """计算所有厂商之间的相似度矩阵"""
    similarities = {}
    providers = list(results.keys())

    for i, provider1 in enumerate(providers):
        similarities[provider1] = {}
        for j, provider2 in enumerate(providers):
            if i == j:
                similarities[provider1][provider2] = 1.0
            elif results.get(provider1) and results.get(provider2):
                similarities[provider1][provider2] = calculate_similarity(
                    results[provider1], results[provider2]
                )
            else:
                similarities[provider1][provider2] = 0.0

    return similarities


def image_to_base64(image_path: str) -> str:
    """将图片转换为 base64 编码"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


def get_file_hash(file_path: str) -> str:
    """计算文件的 SHA256 哈希值"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_image_size(file_path: str) -> Tuple[int, int]:
    """获取图片尺寸"""
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            return img.size
    except:
        return (0, 0)


def _run_single_provider(provider_name: str, provider_config: dict, image_path: str, temp_dir: str, cache_db_path: str) -> Tuple[str, float, bool, str]:
    """测试单个 OCR 厂商"""
    start_time = time.time()
    error_msg = ""

    try:
        # 动态获取 OCR 类（避免循环导入）
        from backend.ocr.config import OCRConfig
        from backend.ocr.core.ocr_engine import OCREngine

        # 创建配置
        config = OCRConfig(
            provider=provider_name,
            db_path=cache_db_path,
            temp_dir=temp_dir,
            debug=False
        )

        # 创建引擎
        engine = OCREngine(config, provider_config=provider_config)

        # 执行识别（不使用缓存）
        text, from_cache = engine.get_text(image_path, use_cache=False)

        elapsed = time.time() - start_time
        return (text, elapsed, True, error_msg)

    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = str(e)
        return ("", elapsed, False, error_msg)


def run_test(image_files: List[str], providers_to_test: List[str] = None) -> Dict[str, Any]:
    """运行 OCR 对比测试"""

    # 加载配置
    from config.loader import get_config
    config_loader = get_config()
    config = config_loader.load_config()

    # 获取所有 OCR 厂商配置
    ocr_providers = config.get('ocr', {}).get('providers', {})

    # 过滤要测试的厂商
    if providers_to_test:
        ocr_providers = {k: v for k, v in ocr_providers.items() if k in providers_to_test}

    if not ocr_providers:
        print("错误: 没有可用的 OCR 厂商配置")
        return {}

    # 设置路径
    temp_dir = str(project_root / "temp" / "ocr_test")
    cache_db_path = str(project_root / "database" / "ocr_cache.db")
    Path(temp_dir).mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"OCR 厂商对比测试")
    print(f"{'='*60}")
    print(f"测试厂商: {', '.join(ocr_providers.keys())}")
    print(f"测试图片数量: {len(image_files)}")
    print(f"{'='*60}\n")

    # 存储所有测试结果
    all_results = {}

    for idx, image_path in enumerate(image_files, 1):
        print(f"[{idx}/{len(image_files)}] 测试图片: {Path(image_path).name}")

        image_results = {
            'path': image_path,
            'name': Path(image_path).name,
            'size': get_image_size(image_path),
            'hash': get_file_hash(image_path),
            'providers': {},
            'similarities': {}
        }

        # 测试每个厂商
        for provider_name, provider_config in ocr_providers.items():
            print(f"  - 测试厂商: {provider_name}...", end=" ", flush=True)

            text, elapsed, success, error_msg = _run_single_provider(
                provider_name, provider_config, image_path, temp_dir, cache_db_path
            )

            if success:
                print(f"✓ ({elapsed:.2f}s, {len(text)} 字符)")
                image_results['providers'][provider_name] = {
                    'text': text,
                    'elapsed': elapsed,
                    'success': True,
                    'char_count': len(text)
                }
            else:
                print(f"✗ ({elapsed:.2f}s)")
                image_results['providers'][provider_name] = {
                    'text': "",
                    'elapsed': elapsed,
                    'success': False,
                    'error': error_msg
                }

        # 计算相似度矩阵
        successful_results = {
            k: v['text'] for k, v in image_results['providers'].items()
            if v['success'] and v['text']
        }

        if successful_results:
            image_results['similarities'] = calculate_all_similarities(successful_results)

        all_results[image_path] = image_results
        print()

    return all_results


def generate_html_report(all_results: Dict[str, Any], provider_names: List[str], output_path: str):
    """生成 HTML 对比报告"""

    def get_similarity_color(value: float) -> str:
        """根据相似度值返回颜色"""
        if value >= 0.9:
            return "#28a745"  # 绿色
        elif value >= 0.7:
            return "#ffc107"  # 黄色
        else:
            return "#dc3545"  # 红色

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCR 厂商对比测试报告</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header .meta { opacity: 0.9; font-size: 0.95em; }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .summary-card .number {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }
        .summary-card .label {
            color: #6c757d;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .test-item {
            border-bottom: 1px solid #e9ecef;
            padding: 30px;
        }
        .test-item:last-child { border-bottom: none; }
        .test-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }
        .test-number {
            background: #667eea;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            margin-right: 15px;
        }
        .test-title { font-size: 1.3em; color: #333; }
        .test-info {
            color: #6c757d;
            font-size: 0.9em;
            margin-left: auto;
        }
        .image-container {
            text-align: center;
            margin-bottom: 30px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
        }
        .image-container img {
            max-width: 100%;
            max-height: 500px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        .image-container img:hover {
            transform: scale(1.02);
        }
        .providers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .provider-card {
            border: 1px solid #dee2e6;
            border-radius: 8px;
            overflow: hidden;
        }
        .provider-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .provider-header .status {
            font-size: 0.85em;
            padding: 4px 12px;
            border-radius: 20px;
        }
        .status.success { background: rgba(40, 167, 69, 0.3); }
        .status.error { background: rgba(220, 53, 69, 0.3); }
        .provider-meta {
            padding: 10px 20px;
            background: #f8f9fa;
            font-size: 0.85em;
            color: #6c757d;
            border-bottom: 1px solid #e9ecef;
        }
        .provider-content {
            padding: 20px;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
            line-height: 1.5;
            background: #fff;
        }
        .provider-content.error {
            color: #dc3545;
            font-style: italic;
        }
        .similarity-section {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
        }
        .similarity-section h3 {
            margin-bottom: 15px;
            color: #333;
            font-size: 1.2em;
        }
        .similarity-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }
        .similarity-table th, .similarity-table td {
            padding: 12px 15px;
            text-align: center;
            border: 1px solid #dee2e6;
        }
        .similarity-table th {
            background: #667eea;
            color: white;
            font-weight: 600;
        }
        .similarity-table td:first-child {
            background: #f8f9fa;
            font-weight: 600;
        }
        .similarity-value {
            font-weight: bold;
            font-size: 1.1em;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            cursor: pointer;
        }
        .modal img {
            max-width: 90%;
            max-height: 90%;
            margin: auto;
            display: block;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OCR 厂商对比测试报告</h1>
            <div class="meta">
                生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
                测试厂商: {', '.join(provider_names)} |
                测试图片数: {len(all_results)}
            </div>
        </div>

        <div class="summary">
"""

    # 计算统计数据
    total_images = len(all_results)
    total_tests = sum(len(r['providers']) for r in all_results.values())
    successful_tests = sum(
        sum(1 for p in r['providers'].values() if p['success'])
        for r in all_results.values()
    )

    html += f"""
            <div class="summary-card">
                <div class="number">{total_images}</div>
                <div class="label">测试图片数</div>
            </div>
            <div class="summary-card">
                <div class="number">{len(provider_names)}</div>
                <div class="label">OCR 厂商</div>
            </div>
            <div class="summary-card">
                <div class="number">{successful_tests}</div>
                <div class="label">成功识别</div>
            </div>
            <div class="summary-card">
                <div class="number">{successful_tests/total_tests*100:.1f}%</div>
                <div class="label">成功率</div>
            </div>
        </div>
"""

    # 生成每个测试项
    for idx, (image_path, result) in enumerate(all_results.items(), 1):
        img_b64 = image_to_base64(image_path)
        size_info = f"{result['size'][0]}×{result['size'][1]}" if result['size'] != (0, 0) else "未知"

        html += f"""
        <div class="test-item">
            <div class="test-header">
                <div class="test-number">{idx}</div>
                <div class="test-title">{result['name']}</div>
                <div class="test-info">
                    尺寸: {size_info} |
                    哈希: {result['hash'][:16]}...
                </div>
            </div>

            <div class="image-container">
                <img src="data:image/jpeg;base64,{img_b64}" alt="{result['name']}" onclick="openModal(this)">
            </div>

            <h3 style="margin-bottom: 20px; color: #333;">识别结果</h3>
            <div class="providers-grid">
"""

        # 厂商结果卡片
        for provider_name, provider_result in result['providers'].items():
            if provider_result['success']:
                status_class = "success"
                status_text = f"✓ {provider_result['elapsed']:.2f}s"
                content = provider_result['text']
                meta = f"字符数: {provider_result['char_count']}"
            else:
                status_class = "error"
                status_text = f"✗ {provider_result['elapsed']:.2f}s"
                content = f"识别失败"
                meta = "错误"

            html += f"""
                <div class="provider-card">
                    <div class="provider-header">
                        <span>{provider_name.upper()}</span>
                        <span class="status {status_class}">{status_text}</span>
                    </div>
                    <div class="provider-meta">{meta}</div>
                    <div class="provider-content {'error' if not provider_result['success'] else ''}">{content}</div>
                </div>
"""

        html += """
            </div>
"""

        # 相似度矩阵
        if result['similarities']:
            providers = list(result['similarities'].keys())

            html += """
            <div class="similarity-section">
                <h3>相似度矩阵</h3>
                <table class="similarity-table">
                    <thead>
                        <tr>
                            <th>厂商</th>
"""

            for provider in providers:
                html += f'<th>{provider.upper()}</th>'

            html += """
                        </tr>
                    </thead>
                    <tbody>
"""

            for provider1 in providers:
                html += f'<tr><td>{provider1.upper()}</td>'
                for provider2 in providers:
                    value = result['similarities'][provider1][provider2]
                    color = get_similarity_color(value)
                    html += f'<td><span class="similarity-value" style="color: {color}">{value:.4f}</span></td>'
                html += '</tr>'

            html += """
                    </tbody>
                </table>
            </div>
"""

        html += """
        </div>
"""

    html += """
    </div>

    <div id="imageModal" class="modal" onclick="closeModal()">
        <img id="modalImage">
    </div>

    <script>
        function openModal(img) {
            document.getElementById('imageModal').style.display = 'block';
            document.getElementById('modalImage').src = img.src;
        }

        function closeModal() {
            document.getElementById('imageModal').style.display = 'none';
        }
    </script>
</body>
</html>
"""

    # 写入文件
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def select_providers(providers_dict: Dict[str, dict]) -> List[str]:
    """显示厂商选择菜单，返回选中的厂商列表"""
    providers = list(providers_dict.keys())

    print("\n" + "="*60)
    print(" 选择 OCR 厂商")
    print("="*60)
    print()
    print("可用的 OCR 厂商:")
    print()

    for idx, provider in enumerate(providers, 1):
        provider_type = providers_dict[provider].get('type', 'unknown')
        type_label = "API" if provider_type == "api" else "本地"
        print(f"  {idx}. {provider.upper()} ({type_label})")

    print()
    print("选择方式:")
    print("  - 输入数字编号，用空格或逗号分隔多个选项")
    print("  - 输入 'all' 或 '*' 选择全部厂商")
    print("  - 输入 '0' 取消")
    print()
    print("="*60)

    while True:
        try:
            choice = input("请选择要测试的厂商: ").strip()

            if choice.lower() in ['0', 'cancel', 'exit']:
                return None

            # 选择全部
            if choice.lower() in ['all', '*']:
                print(f"\n已选择全部厂商: {', '.join(providers)}")
                if input("确认? (y/n): ").strip().lower() == 'y':
                    return providers
                continue

            # 解析选择的编号
            # 支持空格、逗号、中文逗号分隔
            import re
            indices = re.split(r'[,，\s]+', choice)
            indices = [i for i in indices if i]

            selected = []
            valid = True
            for idx_str in indices:
                try:
                    idx = int(idx_str)
                    if 1 <= idx <= len(providers):
                        selected.append(providers[idx - 1])
                    else:
                        print(f"无效的编号: {idx}")
                        valid = False
                        break
                except ValueError:
                    print(f"无效的输入: {idx_str}")
                    valid = False
                    break

            if not valid:
                continue

            if not selected:
                print("请至少选择一个厂商")
                continue

            # 去重
            selected = list(dict.fromkeys(selected))

            print(f"\n已选择: {', '.join(selected)}")
            if input("确认? (y/n): ").strip().lower() == 'y':
                return selected

        except (EOFError, ValueError):
            # 输入结束或值错误时退出
            print("\n\n已取消")
            return None
        except KeyboardInterrupt:
            print("\n\n已取消")
            return None
        except Exception as e:
            print(f"输入无效，请重新输入 ({e})")


def show_menu():
    """显示交互式菜单"""
    print("\n" + "="*60)
    print(" OCR 厂商对比测试")
    print("="*60)
    print()
    print("请选择测试模式:")
    print()
    print("  1. 使用默认测试路径中的所有图片")
    print("     路径: tests/test_images/award/chinese")
    print()
    print("  2. 指定图片目录路径")
    print()
    print("  3. 单张图片测试（从默认路径随机选择）")
    print()
    print("  4. 指定单张图片路径")
    print()
    print("  0. 退出")
    print()
    print("="*60)


def get_user_choice():
    """获取用户选择"""
    while True:
        try:
            choice = input("请输入选项 (0-4): ").strip()
            if choice in ['0', '1', '2', '3', '4']:
                return int(choice)
            print("无效选项，请重新输入")
        except KeyboardInterrupt:
            print("\n\n已取消")
            return 0
        except:
            print("输入无效，请输入数字 0-4")


def main():
    """主程序"""

    # 报告输出路径
    report_path = project_root / "tests" / "reports" / "ocr对比报告.html"

    # 加载配置获取可用厂商（在菜单外加载一次）
    from config.loader import get_config
    config_loader = get_config()
    config = config_loader.load_config()
    ocr_providers = config.get('ocr', {}).get('providers', {})

    if not ocr_providers:
        print("\n错误: 配置文件中没有找到 OCR 厂商")
        print("请检查 config/settings.json 文件")
        input("\n按回车键退出...")
        return

    # 厂商选择菜单
    selected_providers = select_providers(ocr_providers)
    if selected_providers is None:
        print("\n已取消")
        return

    # 过滤出选中的厂商配置
    ocr_providers = {k: v for k, v in ocr_providers.items() if k in selected_providers}

    while True:
        show_menu()
        choice = get_user_choice()

        if choice == 0:
            print("\n再见!")
            break

        print(f"\n当前选择的 OCR 厂商: {', '.join(ocr_providers.keys())}\n")

        image_files = []

        if choice == 1:
            # 使用默认测试路径
            default_dir = project_root / "tests" / "test_images" / "award" / "chinese"
            image_dir = Path(default_dir)

            if not image_dir.exists():
                print(f"错误: 默认测试目录不存在: {default_dir}")
                input("\n按回车键继续...")
                continue

            extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf'}
            image_files = [
                str(f) for f in image_dir.iterdir()
                if f.suffix.lower() in extensions
            ]

            if not image_files:
                print("错误: 目录中没有找到图片文件")
                input("\n按回车键继续...")
                continue

            print(f"找到 {len(image_files)} 个测试图片")

        elif choice == 2:
            # 指定图片目录
            dir_path = input("\n请输入图片目录路径: ").strip()
            dir_path = dir_path.strip('"').strip("'")

            image_dir = Path(dir_path)
            if not image_dir.exists():
                print(f"错误: 目录不存在: {dir_path}")
                input("\n按回车键继续...")
                continue

            extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf'}
            image_files = [
                str(f) for f in image_dir.iterdir()
                if f.suffix.lower() in extensions
            ]

            if not image_files:
                print("错误: 目录中没有找到支持的图片文件")
                input("\n按回车键继续...")
                continue

            print(f"找到 {len(image_files)} 个测试图片")

        elif choice == 3:
            # 从默认路径随机选择
            default_dir = project_root / "tests" / "test_images" / "award" / "chinese"
            image_dir = Path(default_dir)

            if not image_dir.exists():
                print(f"错误: 默认测试目录不存在: {default_dir}")
                input("\n按回车键继续...")
                continue

            extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf'}
            all_files = [
                str(f) for f in image_dir.iterdir()
                if f.suffix.lower() in extensions
            ]

            if not all_files:
                print("错误: 目录中没有找到图片文件")
                input("\n按回车键继续...")
                continue

            selected = random.choice(all_files)
            print(f"\n随机选择: {Path(selected).name}")
            image_files = [selected]

        elif choice == 4:
            # 指定单张图片
            file_path = input("\n请输入图片路径: ").strip()
            file_path = file_path.strip('"').strip("'")

            image_path = Path(file_path)
            if not image_path.exists():
                print(f"错误: 文件不存在: {file_path}")
                input("\n按回车键继续...")
                continue

            extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf'}
            if image_path.suffix.lower() not in extensions:
                print(f"警告: 文件格式可能不支持 ({image_path.suffix})")

            print(f"\n测试图片: {image_path.name}")
            image_files = [str(image_path)]

        # 确认测试
        print(f"\n将测试 {len(image_files)} 个图片")
        confirm = input("是否开始测试? (y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消测试")
            input("\n按回车键继续...")
            continue

        # 运行测试
        try:
            selected_provider_names = list(ocr_providers.keys())
            results = run_test(image_files, selected_provider_names)

            if results:
                # 生成报告
                provider_names = list(ocr_providers.keys())
                generate_html_report(results, provider_names, report_path)

                print("\n" + "="*60)
                print("测试完成!")
                print("="*60)
                print(f"\n报告已保存到:")
                print(f"  {report_path}")
                print(f"\n可以在浏览器中打开查看详细对比结果")

            else:
                print("\n测试失败，没有生成报告")

        except Exception as e:
            print(f"\n测试过程中出错: {e}")
            import traceback
            traceback.print_exc()

        input("\n按回车键继续...")


if __name__ == '__main__':
    main()
