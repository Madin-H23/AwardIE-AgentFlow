"""
文档抽取测试

交互式测试图片、PDF和Excel文件解析功能，生成详细HTML报告。
使用 backend/extract 模块的 ExtractFramework 进行抽取。

支持文件类型：
- 图片：.jpg, .jpeg, .png, .jfif
- PDF：.pdf
- Excel：.xlsx, .xls（大创项目）

使用方法:
    python tests/extract_test.py

作者: Claude
日期: 2026-01-17
更新: 2026-01-29 - 添加Excel文件支持
"""
import os
import sys
import base64
import json
import webbrowser
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.resolve()  # 使用 resolve() 获取绝对路径
# 统一使用 Windows 路径格式（反斜杠）
project_root_str = str(project_root).replace('/', '\\')

# 确保项目根目录在 sys.path 的最前面
# 先移除可能存在的旧路径（包括混合格式的）
paths_to_remove = []
for i, path in enumerate(sys.path):
    path_normalized = path.replace('/', '\\')
    if path_normalized == project_root_str or path == project_root_str:
        paths_to_remove.append(i)
# 从后往前删除，避免索引变化
for i in reversed(paths_to_remove):
    sys.path.pop(i)

# 插入到最前面
sys.path.insert(0, project_root_str)


def print_separator(title: str = "") -> str:
    """生成分隔线"""
    if title:
        return f"\n{'=' * 20} {title} {'=' * 20}"
    else:
        return "=" * 60


class ExtractTester:
    """文档抽取测试器 - 支持图片、PDF、Excel文件"""

    def __init__(self):
        self.use_ocr_cache = True
        self.use_llm_cache = True
        self.test_images_dir = Path(r"D:\code\教学工具\信息管理rebuild\images_files\测试图片")
        self.selected_path: Optional[Path] = None
        self.results: List[Dict[str, Any]] = []

        # 存储OCR和LLM厂商信息
        self.ocr_provider = "unknown"
        self.llm_provider = "unknown"
        
        # 抽取框架（延迟初始化）
        self._framework: Optional[Any] = None

    def load_config(self):
        """加载配置"""
        from config.loader import get_config
        config_loader = get_config()
        return config_loader.load_config()

    def get_providers(self) -> Tuple[str, str]:
        """获取当前使用的OCR和LLM厂商"""
        config = self.load_config()

        # 获取OCR厂商
        ocr_provider = config.get('ocr', {}).get('default_provider', 'unknown')

        # 获取LLM厂商
        llm_provider = config.get('llm', {}).get('default_provider', 'unknown')

        return ocr_provider, llm_provider

    def show_cache_menu(self) -> bool:
        """显示缓存选择菜单"""
        print("\n" + print_separator("缓存设置"))
        print("\n请选择缓存选项:")
        print("  1. 启用 OCR 和 LLM 缓存")
        print("  2. 仅启用 OCR 缓存")
        print("  3. 仅启用 LLM 缓存")
        print("  4. 禁用所有缓存")
        print()

        while True:
            choice = input("请输入选项 (1-4): ").strip()
            if choice == '1':
                self.use_ocr_cache = True
                self.use_llm_cache = True
                return True
            elif choice == '2':
                self.use_ocr_cache = True
                self.use_llm_cache = False
                return True
            elif choice == '3':
                self.use_ocr_cache = False
                self.use_llm_cache = True
                return True
            elif choice == '4':
                self.use_ocr_cache = False
                self.use_llm_cache = False
                return True
            else:
                print("无效选项，请重新输入")

    def show_provider_info(self):
        """显示厂商信息"""
        ocr_provider, llm_provider = self.get_providers()
        self.ocr_provider = ocr_provider
        self.llm_provider = llm_provider

        print("\n" + print_separator("厂商信息"))
        print(f"\nOCR 厂商: {ocr_provider.upper()}")
        print(f"LLM 厂商: {llm_provider.upper()}")

    def get_test_path(self) -> Path:
        """获取测试文件路径"""
        print("\n" + print_separator("选择测试路径"))
        print(f"\n默认路径: {self.test_images_dir}")
        print()

        path_str = input(f"请输入测试文件路径 (直接回车使用默认): ").strip()
        if path_str:
            path = Path(path_str)
            if not path.exists():
                print(f"路径不存在，使用默认路径")
                return self.test_images_dir
            return path
        return self.test_images_dir

    def navigate_directory(self, current_dir: Path) -> Optional[Tuple[Path, str]]:
        """
        目录导航，返回选择的图片或目录
        
        Returns:
            Tuple[Path, str]: (路径, 操作类型)
            - ('file', Path): 选择单个文件
            - ('navigate', Path): 进入目录
            - ('select_dir', Path): 选择当前目录的所有文件
            - None: 取消或退出
        """
        while True:
            print("\n" + print_separator(f"当前目录: {current_dir.name}"))
            print()

            # 列出子目录和图片
            items = self.list_directory_items(current_dir)

            if not items:
                print("目录为空")
                return None

            # 显示菜单
            print(f"{'序号':<6} {'类型':<10} {'名称'}")
            print("-" * 80)
            for idx, item in enumerate(items):
                item_type = "[目录]" if item['is_dir'] else "[文件]"
                print(f"{idx + 1:<6} {item_type:<10} {item['name']}")

            print()
            print("  0. 返回上级目录 (如果已在根目录则退出)")
            print("  d. 选择当前目录 (遍历目录中的所有文件)")
            print("  q. 退出")
            print()

            choice = input("请选择序号或操作: ").strip()

            if choice.lower() == 'q':
                return None
            elif choice == '0':
                # 返回上级目录
                if current_dir == self.test_images_dir or current_dir.parent == self.test_images_dir:
                    print("已在根目录")
                    continue
                else:
                    return (current_dir.parent, 'navigate')
            elif choice.lower() == 'd':
                # 选择当前目录
                return (current_dir, 'select_dir')
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(items):
                    item = items[idx]
                    item_path = current_dir / item['name']

                    if item['is_dir']:
                        # 进入子目录
                        return (item_path, 'navigate')
                    else:
                        # 选择图片
                        return (item_path, 'file')
                else:
                    print("无效序号")
            else:
                print("无效输入")

    def list_directory_items(self, directory: Path) -> List[Dict[str, Any]]:
        """列出目录项"""
        items = []

        # 先列目录
        for item in sorted(directory.iterdir()):
            if item.is_dir():
                items.append({
                    'name': item.name,
                    'is_dir': True,
                    'path': item
                })

        # 再列支持的文件（图片、PDF、Excel）
        supported_extensions = {'.jpg', '.jpeg', '.png', '.jfif', '.pdf', '.xlsx', '.xls'}
        for item in sorted(directory.iterdir()):
            if item.is_file() and item.suffix.lower() in supported_extensions:
                items.append({
                    'name': item.name,
                    'is_dir': False,
                    'path': item
                })

        return items

    def collect_files_from_directory(self, directory: Path) -> List[Path]:
        """
        递归收集目录中的所有支持的文件
        
        Args:
            directory: 要遍历的目录
            
        Returns:
            文件路径列表
        """
        files = []
        supported_extensions = {'.jpg', '.jpeg', '.png', '.jfif', '.pdf', '.xlsx', '.xls'}
        
        try:
            for item in directory.rglob('*'):
                if item.is_file() and item.suffix.lower() in supported_extensions:
                    files.append(item)
        except Exception as e:
            print(f"遍历目录时出错: {e}")
            
        return sorted(files)

    def select_files(self, root_path: Path) -> List[Path]:
        """选择要处理的文件"""
        files = []

        current_path = root_path
        while True:
            result = self.navigate_directory(current_path)
            if result is None:
                # 用户取消或退出
                break

            selected_path, action_type = result

            if action_type == 'navigate':
                # 进入目录
                current_path = selected_path
            elif action_type == 'select_dir':
                # 选择当前目录的所有文件
                dir_files = self.collect_files_from_directory(selected_path)
                if dir_files:
                    files.extend(dir_files)
                    print(f"\n已选择目录: {selected_path.name}")
                    print(f"找到 {len(dir_files)} 个文件:")
                    for f in dir_files[:10]:  # 只显示前10个
                        print(f"  - {f.name}")
                    if len(dir_files) > 10:
                        print(f"  ... 还有 {len(dir_files) - 10} 个文件")
                    
                    # 询问是否继续选择
                    continue_choice = input("\n是否继续选择其他文件或目录? (y/n): ").strip().lower()
                    if continue_choice != 'y':
                        break
                else:
                    print(f"\n目录中没有找到支持的文件")
            elif action_type == 'file':
                # 选择了一个文件
                files.append(selected_path)
                print(f"\n已选择: {selected_path.name}")

                # 询问是否继续选择
                continue_choice = input("\n是否继续选择其他文件? (y/n): ").strip().lower()
                if continue_choice != 'y':
                    break

        return files

    def _get_framework(self):
        """获取或创建抽取框架（单例模式）"""
        if self._framework is None:
            from backend.extract import ExtractFramework, InnovationExtractor, PatentExtractor, SoftwareExtractor, AwardExtractor
            from backend.extract.template import TemplateManager
            from config.loader import get_config
            import json
            from pathlib import Path

            # 创建配置加载器
            config_loader = get_config()
            config = config_loader.load_config()

            # 创建抽取框架
            framework = ExtractFramework.from_config_loader(config_loader)

            # 创建模板管理器（用于AwardExtractor）
            db_path = str(config_loader.get_path("database", "competitions_db"))
            base_fields_map = {}
            
            # 加载各类型的字段定义
            for doc_type in ["award", "patent", "software"]:
                fields_file = project_root / "backend" / "extract" / "prompts" / f"{doc_type}_fields.json"
                if fields_file.exists():
                    with open(fields_file, "r", encoding="utf-8") as f:
                        base_fields_map[doc_type] = json.load(f)
            
            config_dir = project_root / "backend" / "extract" / "config"
            template_manager = TemplateManager(
                db_path=db_path,
                base_fields_map=base_fields_map,
                config_dir=str(config_dir) if config_dir.exists() else None
            )

            # 注册所有可用的抽取器
            framework.register(InnovationExtractor.from_config_loader(config_loader))
            framework.register(PatentExtractor.from_config_loader(config_loader))
            framework.register(SoftwareExtractor.from_config_loader(config_loader))
            
            # 注册AwardExtractor（需要template_manager）
            award_config = config.get("extract", {}).get("award", {})
            framework.register(AwardExtractor(award_config, template_manager=template_manager))
            
            self._framework = framework
        
        return self._framework

    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """处理单个文件"""
        print(f"\n处理中: {file_path.name}...")

        try:
            # 导入类型定义
            from backend.extract.types import ExtractStatus, TemplateType

            # 获取抽取框架
            framework = self._get_framework()

            # 执行抽取
            result = framework.extract(
                str(file_path),
                use_ocr_cache=self.use_ocr_cache,
                use_llm_cache=self.use_llm_cache
            )

            # 计算相对路径（相对于项目根目录）
            try:
                relative_path = file_path.relative_to(project_root)
            except ValueError:
                # 如果文件不在项目根目录下，使用绝对路径
                relative_path = Path(file_path)
            
            # 构建结果数据 - 收集所有可用信息
            # ExtractResult 字段映射：status, data, error_message, template_type, extractor_name,
            # ocr_text, ocr_cache_hit, llm_prompt, llm_response, llm_cache_hit, validation_result, metadata
            is_success = result.status == ExtractStatus.SUCCESS and result.template_type != TemplateType.OTHER
            
            # 从 result 或 metadata 中获取 llm_prompt 和 llm_response
            llm_prompt = result.llm_prompt or (result.metadata.get('llm_prompt') if result.metadata else None)
            llm_response = result.llm_response or (result.metadata.get('llm_response') if result.metadata else None)
            
            # 提取模板信息（从metadata中提取，适用于所有类型）
            template_id = None
            template_name = None
            if result.metadata:
                template_id = result.metadata.get('template_id')
                template_name = result.metadata.get('template_name')
            
            result_data = {
                'file_path': str(file_path),
                'file_path_relative': str(relative_path),
                'file_name': file_path.name,
                'success': is_success,
                'status': result.status.value,
                'extractor_name': result.extractor_name or 'Unknown',
                'ocr_cache_hit': result.ocr_cache_hit,
                'llm_cache_hit': result.llm_cache_hit,
                'ocr_provider': self.ocr_provider,
                'llm_provider': self.llm_provider,
                'ocr_text': result.ocr_text,
                'llm_prompt': llm_prompt,
                'template_type': result.template_type,
                'llm_response': llm_response,
                'data': result.data,
                'error_message': result.error_message,
                'validation_result': result.validation_result.to_dict() if result.validation_result else None,
                'metadata': result.metadata,
                'template_id': template_id,
                'template_name': template_name
            }

            print(f"完成: {result.status.value}")
            if is_success:
                print(f"  类型: {result.template_type}")
                if result.extractor_name:
                    print(f"  抽取器: {result.extractor_name}")

            # 异常/other 时打印便于测试：OCR/LLM 失败等会带 error_message 和 data.note
            if result.error_message or (result.data and result.data.get("note")):
                print("  [异常/other] 便于测试查看:")
                if result.error_message:
                    print(f"    error_message: {result.error_message}")
                if result.data and result.data.get("note"):
                    print(f"    data.note: {result.data.get('note')}")
                if result.status in (ExtractStatus.OCR_ERROR, ExtractStatus.LLM_ERROR):
                    print(f"    status: {result.status.value}")
            
            # 打印模板匹配信息（对所有类型都显示）
            if result.template_type == TemplateType.AWARD:
                if template_id or template_name:
                    print(f"  ✓ 匹配奖状模板: ID={template_id}, 名称={template_name}")
                else:
                    print(f"  ✗ 无奖状模板匹配")
            elif result.template_type in [TemplateType.PATENT, TemplateType.SOFTWARE]:
                # 专利和软著也可能有模板，但通常不需要显示
                if template_id or template_name:
                    print(f"  ✓ 匹配模板: ID={template_id}, 名称={template_name}")

            return result_data

        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()

            # 计算相对路径（相对于项目根目录）
            try:
                relative_path = file_path.relative_to(project_root)
            except ValueError:
                # 如果文件不在项目根目录下，使用绝对路径
                relative_path = Path(file_path)
            
            return {
                'file_path': str(file_path),
                'file_path_relative': str(relative_path),
                'file_name': file_path.name,
                'success': False,
                'status': 'error',
                'error_message': str(e)
            }

    def generate_html_report(self, pic_name: str, open_browser: bool = True):
        """生成HTML报告"""
        print("\n生成HTML报告...")

        report_dir = project_root / "tests" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / pic_name

        html = self._build_html()

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"报告已生成: {report_path}")
        
        # 自动打开浏览器
        if open_browser:
            try:
                # 将路径转换为 file:// URL
                report_url = report_path.as_uri()
                webbrowser.open(report_url)
                print(f"已在浏览器中打开报告: {report_url}")
            except Exception as e:
                print(f"无法自动打开浏览器: {e}")
                print(f"请手动打开: {report_path}")
        
        return report_path

    def _build_html(self) -> str:
        """构建HTML内容"""
        from backend.extract.types import TemplateType
        from datetime import datetime

        # 生成时间字符串
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ocr_provider = self.ocr_provider.upper()
        llm_provider = self.llm_provider.upper()

        # 生成左侧导航栏的测试项列表
        nav_items = ""
        for idx, result in enumerate(self.results, 1):
            status_class = "success" if result['success'] else "error"
            if result.get('status') == 'other':
                status_class = "other"
            
            # 检查验证结果
            validation_marker = ""
            validation_class = ""
            validation_result = result.get('validation_result')
            if validation_result:
                is_valid = validation_result.get('is_valid')
                if is_valid is True:
                    validation_marker = '<span class="nav-validation nav-validation-valid" title="验证通过">✓</span>'
                    validation_class = "nav-has-validation nav-validation-valid"
                elif is_valid is False:
                    validation_marker = '<span class="nav-validation nav-validation-invalid" title="验证失败">✗</span>'
                    validation_class = "nav-has-validation nav-validation-invalid"
            
            nav_items += f'''
                <a href="#test-item-{idx}" class="nav-item {validation_class}" data-target="test-item-{idx}">
                    <span class="nav-number">[{idx}]</span>
                    <span class="nav-name">{self._escape_html(result['file_name'][:30])}</span>
                    <span class="nav-status nav-status-{status_class}"></span>
                    {validation_marker}
                </a>'''

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文档抽取测试报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 0;
            line-height: 1.6;
        }}
        .main-wrapper {{
            display: flex;
            min-height: 100vh;
        }}
        /* 左侧导航栏 */
        .sidebar {{
            width: 320px;
            background: white;
            height: 100vh;
            position: sticky;
            top: 0;
            overflow-y: auto;
            border-right: 1px solid #e9ecef;
            flex-shrink: 0;
        }}
        .sidebar::-webkit-scrollbar {{
            width: 6px;
        }}
        .sidebar::-webkit-scrollbar-thumb {{
            background: #667eea;
            border-radius: 3px;
        }}
        .sidebar-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        .sidebar-header h2 {{
            font-size: 1.3em;
            margin-bottom: 8px;
        }}
        .sidebar-header .meta {{
            font-size: 0.8em;
            opacity: 0.9;
        }}
        .sidebar-summary {{
            padding: 15px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .sidebar-summary-item {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.9em;
        }}
        .sidebar-summary-item:last-child {{ margin-bottom: 0; }}
        .sidebar-summary-label {{ color: #6c757d; }}
        .sidebar-summary-value {{ font-weight: 600; color: #667eea; }}
        .nav-list {{
            list-style: none;
            padding: 10px 0;
        }}
        .nav-item {{
            display: flex;
            align-items: center;
            padding: 12px 20px;
            color: #333;
            text-decoration: none;
            border-left: 3px solid transparent;
            transition: all 0.2s ease;
            cursor: pointer;
        }}
        .nav-item:hover {{
            background: #f8f9fa;
            border-left-color: #667eea;
        }}
        .nav-item.active {{
            background: #e7f1ff;
            border-left-color: #667eea;
        }}
        .nav-number {{
            color: #667eea;
            font-weight: 600;
            margin-right: 10px;
            font-size: 0.9em;
            flex-shrink: 0;
        }}
        .nav-name {{
            flex: 1;
            font-size: 0.9em;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .nav-status {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        .nav-status-success {{ background: #28a745; }}
        .nav-status-error {{ background: #dc3545; }}
        .nav-status-other {{ background: #ffc107; }}
        .nav-validation {{
            margin-left: 8px;
            font-weight: bold;
            flex-shrink: 0;
            width: 18px;
            height: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            font-size: 12px;
        }}
        .nav-validation-valid {{
            background: #28a745;
            color: white;
        }}
        .nav-validation-invalid {{
            background: #dc3545;
            color: white;
        }}
        .nav-has-validation {{
            padding-right: 12px;
        }}
        /* 右侧主内容区 */
        .main-content {{
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.9; font-size: 0.95em; }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .summary-card .number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}
        .summary-card .label {{
            color: #6c757d;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .test-item {{
            border-bottom: 1px solid #e9ecef;
            padding: 30px;
            scroll-margin-top: 20px;
        }}
        .test-item:last-child {{ border-bottom: none; }}
        .test-header {{
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }}
        .status-badge {{
            padding: 6px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
            margin-left: 15px;
            max-width: 500px;
            word-break: break-word;
            white-space: normal;
            display: inline-block;
            line-height: 1.4;
        }}
        .status-success {{ background: #d4edda; color: #155724; }}
        .status-error {{ background: #f8d7da; color: #721c24; }}
        .status-other {{ background: #fff3cd; color: #856404; }}
        .image-container {{
            text-align: center;
            margin-bottom: 30px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
        }}
        .image-container img {{
            max-width: 100%;
            max-height: 500px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            cursor: pointer;
            transition: transform 0.3s ease;
        }}
        .image-container img:hover {{
            transform: scale(1.02);
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .info-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .info-label {{
            color: #6c757d;
            font-size: 0.85em;
            margin-bottom: 5px;
        }}
        .info-value {{
            font-weight: 600;
            word-break: break-all;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 1.3em;
            color: #333;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        .code-block {{
            background: #282c34;
            color: #abb2bf;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
            line-height: 1.5;
            white-space: pre-wrap;
        }}
        .json-block {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
            line-height: 1.5;
        }}
        .cache-badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
            margin-left: 8px;
        }}
        .cache-hit {{ background: #d4edda; color: #155724; }}
        .cache-miss {{ background: #f8d7da; color: #721c24; }}
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            cursor: pointer;
        }}
        .modal img {{
            max-width: 90%;
            max-height: 90%;
            margin: auto;
            display: block;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }}
        /* 移动端响应式 */
        @media (max-width: 768px) {{
            .main-wrapper {{ flex-direction: column; }}
            .sidebar {{ width: 100%; height: auto; max-height: 200px; }}
        }}
    </style>
</head>
<body>
    <div class="main-wrapper">
        <!-- 左侧导航栏 -->
        <div class="sidebar">
            <div class="sidebar-header">
                <h2>测试导航</h2>
                <div class="meta">{current_time}</div>
            </div>
            <div class="sidebar-summary">
                <div class="sidebar-summary-item">
                    <span class="sidebar-summary-label">OCR</span>
                    <span class="sidebar-summary-value">{ocr_provider}</span>
                </div>
                <div class="sidebar-summary-item">
                    <span class="sidebar-summary-label">LLM</span>
                    <span class="sidebar-summary-value">{llm_provider}</span>
                </div>
            </div>
            <div class="nav-list">
                {nav_items}
            </div>
        </div>

        <!-- 右侧主内容区 -->
        <div class="main-content">
            <div class="container">
                <div class="header">
                    <h1>文档抽取测试报告</h1>
                    <div class="meta">
                        生成时间: {current_time} |
                        OCR: {ocr_provider} |
                        LLM: {llm_provider}
                    </div>
                </div>

                <div class="summary">
"""

        # 计算统计数据
        total = len(self.results)
        success = sum(1 for r in self.results if r['success'])
        failed = total - success

        html += f"""
            <div class="summary-card">
                <div class="number">{total}</div>
                <div class="label">处理文件数</div>
            </div>
            <div class="summary-card">
                <div class="number">{success}</div>
                <div class="label">成功</div>
            </div>
            <div class="summary-card">
                <div class="number">{failed}</div>
                <div class="label">失败</div>
            </div>
        </div>
"""

        # 生成每个测试项
        for idx, result in enumerate(self.results, 1):
            html += self._build_test_item(idx, result)

        html += """
            </div>
        </div>
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

        function toggleSection(previewId, fullId, buttonElement) {
            const preview = document.getElementById(previewId);
            const full = document.getElementById(fullId);
            const button = buttonElement || event.target;

            if (full.style.display === 'none') {
                preview.style.display = 'none';
                full.style.display = 'block';
                button.textContent = '折叠内容';
            } else {
                preview.style.display = 'block';
                full.style.display = 'none';
                button.textContent = '展开完整内容';
            }
        }

        function toggleCollapsibleSection(contentId, buttonId) {
            const content = document.getElementById(contentId);
            const button = document.getElementById(buttonId);
            
            if (content.style.display === 'none') {
                content.style.display = 'block';
                button.textContent = '▲ 收起';
            } else {
                content.style.display = 'none';
                button.textContent = '▼ 展开';
            }
        }

        // 导航高亮功能
        document.addEventListener('DOMContentLoaded', function() {{
            const navItems = document.querySelectorAll('.nav-item');
            const testItems = document.querySelectorAll('.test-item');

            // 点击导航项时高亮
            navItems.forEach(item => {{
                item.addEventListener('click', function(e) {{
                    // 移除所有active类
                    navItems.forEach(nav => nav.classList.remove('active'));
                    // 添加active类到当前项
                    this.classList.add('active');
                }});
            }});

            // 滚动时高亮对应的导航项
            function highlightNavOnScroll() {{
                let current = '';

                testItems.forEach(item => {{
                    const rect = item.getBoundingClientRect();
                    if (rect.top <= 150 && rect.bottom >= 150) {{
                        current = item.id;
                    }}
                }});

                navItems.forEach(item => {{
                    item.classList.remove('active');
                    if (item.getAttribute('href') === '#' + current) {{
                        item.classList.add('active');
                    }}
                }});
            }}

            // 监听滚动事件
            const mainContent = document.querySelector('.main-content');
            mainContent.addEventListener('scroll', highlightNavOnScroll);
            window.addEventListener('scroll', highlightNavOnScroll);
        }});
    </script>
</body>
</html>
"""
        return html

    def _build_test_item(self, idx: int, result: Dict[str, Any]) -> str:
        """构建单个测试项的HTML"""
        status_class = "status-success" if result['success'] else "status-error"
        if result.get('status') == 'other':
            status_class = "status-other"

        # 读取并编码图片/文件
        try:
            img_path = Path(result['file_path'])
            if img_path.exists():
                suffix = img_path.suffix.lower()
                # 如果是PDF或Excel，无法显示
                if suffix in ['.pdf', '.xlsx', '.xls']:
                    file_type = 'PDF' if suffix == '.pdf' else 'Excel'
                    img_html = f'<div style="padding:40px;text-align:center;color:#6c757d;">{file_type}文件（无法预览）</div>'
                else:
                    with open(img_path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode('utf-8')
                    img_html = f'<img src="data:image/jpeg;base64,{img_b64}" alt="{result["file_name"]}" onclick="openModal(this)">'
            else:
                img_html = '<div style="padding:40px;text-align:center;color:#6c757d;">文件不存在</div>'
        except:
            img_html = '<div style="padding:40px;text-align:center;color:#dc3545;">无法读取文件</div>'

        # 构建状态显示文本
        status_text = result.get('status', 'unknown').upper()
        
        # 如果是奖状类型，显示模板信息
        if result.get('template_type') == 'award':
            template_info_parts = []
            if result.get('template_id'):
                template_info_parts.append(f"ID:{result['template_id']}")
            if result.get('template_name'):
                template_info_parts.append(result['template_name'])
            
            if template_info_parts:
                template_display = " | ".join(template_info_parts)
                status_text = f"{status_text} | {template_display}"
            else:
                # 明确标记"无奖状模板"
                status_text = f"{status_text} | 无奖状模板"
        
        html = f"""
        <div class="test-item" id="test-item-{idx}">
            <div class="test-header">
                <h3>[{idx}] {result['file_name']}</h3>
                <span class="status-badge {status_class}" title="{self._escape_html(status_text)}">{self._escape_html(status_text)}</span>
            </div>

            <div class="image-container">
                {img_html}
            </div>

            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">OCR 厂商</div>
                    <div class="info-value">{result.get('ocr_provider', 'unknown').upper()}
                        <span class="cache-badge {'cache-hit' if result.get('ocr_cache_hit') else 'cache-miss'}">
                            {'缓存命中' if result.get('ocr_cache_hit') else '未使用缓存'}
                        </span>
                    </div>
                </div>
                <div class="info-item">
                    <div class="info-label">LLM 厂商</div>
                    <div class="info-value">{result.get('llm_provider', 'unknown').upper()}
                        <span class="cache-badge {'cache-hit' if result.get('llm_cache_hit') else 'cache-miss'}">
                            {'缓存命中' if result.get('llm_cache_hit') else '未使用缓存'}
                        </span>
                    </div>
                </div>
"""

        # 添加额外信息
        if result.get('extractor_name'):
            html += f"""
                <div class="info-item">
                    <div class="info-label">抽取器</div>
                    <div class="info-value">{result.get('extractor_name')}</div>
                </div>
"""

        if result.get('template_type'):
            display_name = self._get_type_display_name(result['template_type'])
            html += f"""
                <div class="info-item">
                    <div class="info-label">识别类型</div>
                    <div class="info-value">{display_name}</div>
                </div>
"""

        # 如果是奖状类型，显示模板信息（无论是否匹配都要显示）
        if result.get('template_type') == 'award':
            template_info = []
            if result.get('template_id'):
                template_info.append(f"ID: {result['template_id']}")
            if result.get('template_name'):
                template_info.append(result['template_name'])
            
            if template_info:
                template_display = " | ".join(template_info)
            else:
                template_display = "无奖状模板"
            
            html += f"""
                <div class="info-item">
                    <div class="info-label">匹配模板</div>
                    <div class="info-value">{self._escape_html(template_display)}</div>
                </div>
"""


        # 添加文件路径信息（显示相对路径）
        if result.get('file_path_relative'):
            html += f"""
                <div class="info-item">
                    <div class="info-label">文件路径</div>
                    <div class="info-value" style="word-break: break-all; font-family: monospace; font-size: 0.9em;">{self._escape_html(result.get('file_path_relative'))}</div>
                </div>
"""

        html += """
            </div>
"""

        # 如果有错误信息
        if result.get('error_message'):
            html += f"""
            <div class="section">
                <div class="section-title">错误信息</div>
                <div class="code-block">{self._escape_html(result['error_message'])}</div>
            </div>
"""

        # 抽取器信息
        extractor_info = {}
        if result.get('extractor_name'):
            extractor_info['抽取器名称'] = result['extractor_name']
        if result.get('template_type'):
            display_name = self._get_type_display_name(result['template_type'])
            extractor_info['识别类型'] = f"{result['template_type']} ({display_name})"
        
        if extractor_info:
            html += self._build_data_section("抽取器信息", extractor_info)

        # 以下信息对所有类型（包括other类型）都显示，只要字段有值
        # LLM 提示词 - 默认收起（如果有）
        if result.get('llm_prompt'):
            html += self._build_collapsible_section("LLM 提示词（发送给LLM的信息）", result['llm_prompt'], section_id=f"llm_prompt_{idx}")

        # LLM 响应 - 默认收起（如果有）
        if result.get('llm_response'):
            html += self._build_collapsible_section("LLM 响应（LLM返回的信息）", result['llm_response'], section_id=f"llm_response_{idx}")

        # 最终抽取结果 - 始终展示（如果有data，包括other类型）
        if result.get('data'):
            html += self._build_data_section("最终抽取结果", result['data'])

        # 验证结果 - 默认收起（如果有）
        if result.get('validation_result'):
            html += self._build_collapsible_data_section("验证结果", result['validation_result'], section_id=f"validation_{idx}")

        # OCR 文本 - 默认收起（如果有）
        if result.get('ocr_text'):
            html += self._build_collapsible_section("OCR 识别结果", result['ocr_text'], section_id=f"ocr_{idx}")

        # 元数据 - 默认收起（如果有）
        if result.get('metadata'):
            html += self._build_collapsible_data_section("元数据", result['metadata'], section_id=f"metadata_{idx}")

        html += """
        </div>
"""
        return html

    def _build_section(self, title: str, content: str, max_preview: int = 500, section_id: str = None) -> str:
        """构建内容区块，支持展开/折叠"""
        if not content:
            return ""
        
        section_id = section_id or f"section_{id(content)}"
        full_id = f"full_{section_id}"
        preview_id = f"preview_{section_id}"
        
        preview = content
        show_more = False
        if len(content) > max_preview:
            preview = content[:max_preview] + "\n... (内容已截断，点击展开查看完整内容)"
            show_more = True

        html = f"""
            <div class="section">
                <div class="section-title">{title}</div>
                <div class="code-block" id="{preview_id}">{self._escape_html(preview)}</div>
"""
        
        if show_more:
            html += f"""
                <div class="code-block" id="{full_id}" style="display:none;">{self._escape_html(content)}</div>
                <button onclick="toggleSection('{preview_id}', '{full_id}', this)" style="margin-top:10px;padding:8px 16px;background:#667eea;color:white;border:none;border-radius:4px;cursor:pointer;">
                    展开完整内容
                </button>
"""
        
        html += """
            </div>
"""
        return html

    def _build_collapsible_section(self, title: str, content: str, section_id: str = None) -> str:
        """构建可折叠的内容区块（默认收起）"""
        if not content:
            return ""
        
        section_id = section_id or f"section_{id(content)}"
        content_id = f"content_{section_id}"
        button_id = f"button_{section_id}"
        
        # 预览文本（前100个字符）
        preview_text = content[:100] + "..." if len(content) > 100 else content
        
        html = f"""
            <div class="section">
                <div class="section-title" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;" onclick="toggleCollapsibleSection('{content_id}', '{button_id}')">
                    <span>{title}</span>
                    <span id="{button_id}" style="font-size:0.8em;color:#667eea;">▼ 展开</span>
                </div>
                <div class="code-block" id="{content_id}" style="display:none;">{self._escape_html(content)}</div>
            </div>
"""
        return html

    def _build_collapsible_data_section(self, title: str, data: Dict[str, Any], section_id: str = None) -> str:
        """构建可折叠的数据展示区块（默认收起）"""
        if not data:
            return ""
        
        section_id = section_id or f"data_section_{id(data)}"
        content_id = f"content_{section_id}"
        button_id = f"button_{section_id}"
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        
        html = f"""
            <div class="section">
                <div class="section-title" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;" onclick="toggleCollapsibleSection('{content_id}', '{button_id}')">
                    <span>{title}</span>
                    <span id="{button_id}" style="font-size:0.8em;color:#667eea;">▼ 展开</span>
                </div>
                <div class="json-block" id="{content_id}" style="display:none;">{self._escape_html(json_str)}</div>
            </div>
"""
        return html

    def _build_data_section(self, title: str, data: Dict[str, Any]) -> str:
        """构建数据展示区块"""
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        return f"""
            <div class="section">
                <div class="section-title">{title}</div>
                <div class="json-block">{self._escape_html(json_str)}</div>
            </div>
"""

    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#039;'))

    def _get_type_display_name(self, type_value: str) -> str:
        """获取类型显示名称"""
        from backend.extract.types import TemplateType
        return TemplateType.get_display_name(type_value)

    def run(self):
        """运行测试"""
        print("=" * 60)
        print(" 文档抽取测试")
        print("=" * 60)

        # 1. 缓存设置
        self.show_cache_menu()

        # 2. 显示厂商信息
        self.show_provider_info()

        # 3. 获取测试路径
        test_path = self.get_test_path()

        if not test_path.exists():
            print(f"\n错误: 测试路径不存在: {test_path}")
            return

        # 4. 选择文件
        self.selected_path = test_path
        files = self.select_files(test_path)

        if not files:
            print("\n未选择任何文件，测试结束")
            return

        print(f"\n已选择 {len(files)} 个文件")

        # 5. 处理文件
        print("\n" + "=" * 60)
        print(" 开始处理")
        print("=" * 60)

        for file_path in files:
            result = self.process_file(file_path)
            self.results.append(result)

        # 6. 生成报告
        self.generate_html_report("批量文档抽取测试.html")

        print("\n" + "=" * 60)
        print(" 测试完成")
        print("=" * 60)


def main():
    """主函数"""
    tester = ExtractTester()
    try:
        tester.run()
    except KeyboardInterrupt:
        print("\n\n测试已取消")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
