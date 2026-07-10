"""
OCR引擎

提供图片和PDF第一页的文本识别功能
使用配置驱动的 Provider 工厂模式
支持精度分级、全量缓存、图片预处理
"""
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from .cache_db import CacheDB
from .provider_status import OCRProviderStatusManager
from ..config import OCRConfig
from ..utils.logger import setup_logger
from ..exceptions import OCRFileNotFoundError, OCRError, OCRImageProcessingError
from .provider_factory import ProviderFactory
from .providers import OCRProvider


class OCREngine:
    """OCR识别引擎"""

    def __init__(self, config: OCRConfig, provider_config: Optional[Dict[str, Any]] = None):
        """
        初始化 OCR 引擎（不推荐直接使用，建议使用from_config_loader）

        Args:
            config: OCR通用配置对象
            provider_config: Provider 特定配置字典（可选）
        """
        self.config = config
        self.cache_db = CacheDB(config.db_path)
        self.logger = setup_logger("OCREngine", config.log_level, config.log_file)

        # 验证配置
        config.validate()
        
        # 保存Provider工厂实例
        self._provider_factory = ProviderFactory(self.logger)
        
        # 注意：不再在初始化时创建单一provider实例
        # Provider将在from_config_loader中根据精度要求动态创建
        
        self.last_ocr_warning = None  # 高精度失败回退到低精度时由 get_text/_ocr_image 设置，供上层读取
        self.last_ocr_failure_reason = None  # 图片读取失败（PIL+OpenCV 均失败）时设置，供上层转为 OCR_ERROR 结果而不抛异常
        self._log("OCR Engine initialized")

    @classmethod
    def from_config_loader(cls, config_loader, common_config: Optional[OCRConfig] = None):
        """
        从配置加载器创建 OCREngine（推荐方式）
        
        初始化时会自动识别并创建高精度和低精度Provider
        
        Args:
            config_loader: ConfigLoader 实例
            common_config: 通用配置（可选，如果不提供则使用默认值）
            
        Returns:
            OCREngine 实例
        """
        # 获取所有Provider配置
        config = config_loader.load_config()
        ocr_config = config.get('ocr', {})
        all_providers = ocr_config.get('providers', {})

        # 获取PDF转图片的DPI配置
        pdf_dpi = ocr_config.get('pdf_dpi', 200.0)
        # 运行时状态文件路径（禁止硬编码，缺失时抛错）
        runtime_status_path = ocr_config.get('runtime_status_path')
        if not runtime_status_path:
            raise ValueError(
                "ocr.runtime_status_path 未配置，请在 config/settings.json 的 ocr 节点下配置 runtime_status_path（如 config/ocr_runtime.json）"
            )
        status_path = config_loader.project_root / runtime_status_path

        # 识别默认高精度Provider与高精度有序列表（仅 is_precise 为 True 的；default 优先，其余按配置键顺序）
        default_provider = config_loader.get_default_provider('ocr')
        precise_names = [
            n for n, c in all_providers.items()
            if c.get('is_precise', True) is True
        ]
        if default_provider in precise_names:
            precise_order = [default_provider] + [n for n in precise_names if n != default_provider]
        else:
            precise_order = list(precise_names)

        # 识别低精度Provider（is_precise=false的第一个）
        fast_provider_name = None
        fast_provider_config = None
        for name, provider_config in all_providers.items():
            if provider_config.get('is_precise', True) is False:
                fast_provider_name = name
                fast_provider_config = provider_config
                break

        # 创建通用配置
        if common_config is None:
            from backend.services.context import ServiceContext
            context = ServiceContext()
            common_config = OCRConfig(
                db_path=str(context.ocr_cache_path),
                temp_dir=str(context.temp_dir),
                provider=default_provider,  # 用于兼容，实际不使用
                debug=False
            )

        # 创建引擎实例
        engine = cls(common_config, provider_config=None)
        engine._pdf_dpi = pdf_dpi
        engine._precise_order = precise_order
        engine._default_provider_name = default_provider
        engine._status_manager = OCRProviderStatusManager(status_path)
        engine._precise_instances = {}
        engine._common_provider_config = {
            'debug': common_config.debug,
            'max_image_size': common_config.max_image_size,
            'jpeg_quality': common_config.jpeg_quality,
        }
        engine._precise_configs = {}
        for name in precise_order:
            try:
                engine._precise_configs[name] = config_loader.get_provider_config('ocr', name)
            except Exception:
                continue
        engine._provider_factory = ProviderFactory(engine.logger)
        engine.logger.info("高精度Provider链已设置: %s（按序尝试，失败自动切换）", precise_order)

        # 低精度Provider（单一实例）
        if fast_provider_name:
            engine._fast_provider = engine._provider_factory.create_provider(
                provider_name=fast_provider_name,
                provider_config=config_loader.get_provider_config('ocr', fast_provider_name),
                common_config=engine._common_provider_config
            )
            engine._fast_provider_name = fast_provider_name
        else:
            engine._fast_provider = None
            engine._fast_provider_name = None
            engine.logger.warning("未找到低精度Provider（is_precise=false），低精度OCR将不可用")

        return engine

    def _log(self, message: str):
        """记录调试日志"""
        if self.config.debug:
            self.logger.debug(message)

    def _get_effective_precise_order(self) -> List[str]:
        """返回当前未禁用的高精度供应商名称有序列表。"""
        return [n for n in self._precise_order if not self._status_manager.is_disabled(n)]

    def _get_or_create_precise_provider(self, name: str) -> OCRProvider:
        """按需创建并返回高精度 Provider 实例。"""
        if name not in self._precise_instances:
            if name not in self._precise_configs:
                raise RuntimeError(f"高精度供应商配置不存在: {name}")
            self._precise_instances[name] = self._provider_factory.create_provider(
                provider_name=name,
                provider_config=self._precise_configs[name],
                common_config=self._common_provider_config
            )
        return self._precise_instances[name]

    def _get_compression_provider(self) -> Optional[OCRProvider]:
        """返回用于图片预处理的 Provider（优先第一个可用高精度，否则低精度）。"""
        for name in self._get_effective_precise_order():
            try:
                return self._get_or_create_precise_provider(name)
            except Exception:
                continue
        return self._fast_provider

    def get_current_effective_precise_provider_name(self) -> Optional[str]:
        """返回当前实际使用的第一个可用高精度供应商名称（供管理端展示）；无可用时返回 None。"""
        order = self._get_effective_precise_order()
        return order[0] if order else None

    def get_precise_order(self) -> List[str]:
        """返回高精度供应商有序列表（含已禁用的）。"""
        return list(self._precise_order)

    def get_status_manager(self) -> OCRProviderStatusManager:
        """返回运行时状态管理器（供管理端读/写禁用状态）。"""
        return self._status_manager

    def _calculate_hash(self, file_path: str) -> str:
        """
        计算文件的 SHA256 哈希（基于文件内容，不包含Provider信息）

        Args:
            file_path: 文件路径

        Returns:
            SHA256哈希值
        """
        sha256 = hashlib.sha256()
        
        # 只基于文件内容计算hash，不包含Provider信息
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _load_cache(self, file_hash: str) -> Optional[tuple[str, str, bool]]:
        """
        尝试加载缓存

        Args:
            file_hash: 文件哈希值

        Returns:
            (OCR文本, Provider名称, is_precise) 元组，如果不存在返回None
        """
        result = self.cache_db.get_ocr_cache(file_hash)
        if result:
            ocr_text, provider, is_precise = result
            self._log(f"缓存命中，哈希：{file_hash}，提供者：{provider}，精度：{'高' if is_precise else '低'}")
            return (ocr_text, provider, is_precise)
        else:
            self._log(f"缓存未命中，哈希：{file_hash}")
        return None

    def _save_cache(self, file_hash: str, ocr_text: str, provider: str, is_precise: bool) -> None:
        """
        保存缓存

        Args:
            file_hash: 文件哈希值
            ocr_text: OCR识别的纯文本
            provider: Provider名称
            is_precise: 是否为高精度识别
        """
        if self.cache_db.save_ocr_cache(file_hash, ocr_text, provider, is_precise):
            self._log(f"缓存已保存，哈希：{file_hash}，提供者：{provider}，精度：{'高' if is_precise else '低'}")
        else:
            self.logger.error(f"保存缓存失败，哈希：{file_hash}")

    def _compress_image(self, image_path: str) -> str:
        """
        对图片进行预处理（压缩、格式转换等）
        
        Args:
            image_path: 原始图片路径
            
        Returns:
            预处理后的图片路径（临时文件）
        """
        try:
            provider = self._get_compression_provider()
            if not provider:
                # 如果没有Provider，直接返回原路径
                return image_path
            
            # 调用Provider的_compress_image方法
            compressed_bytes = provider._compress_image(image_path)
            
            # 保存到临时文件
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.jpg',
                dir=str(self.config.temp_dir)
            )
            temp_file.write(compressed_bytes)
            temp_file.close()
            
            self._log(f"图片预处理完成，临时文件：{temp_file.name}")
            return temp_file.name
        except Exception as e:
            self.logger.warning(f"图片预处理失败，使用原始图片: {e}")
            return image_path

    def _ocr_image(self, image_path: str, is_precise: bool, use_cache: bool = True) -> Tuple[str, bool]:
        """
        OCR识别图片

        Args:
            image_path: 图片路径
            is_precise: 是否使用高精度OCR
            use_cache: 是否使用缓存（读取缓存）

        Returns:
            (文本内容, 是否命中缓存)
        """
        if not os.path.exists(image_path):
            raise OCRFileNotFoundError(f"未找到图片：{image_path}")

        self.last_ocr_failure_reason = None  # 读取失败时写入原因，供上层转为 OCR_ERROR 结果而不抛异常
        # 计算文件hash（基于文件内容）
        file_hash = self._calculate_hash(image_path)

        # 1. 尝试读取缓存（只有当use_cache=True且config.use_cache=True时）
        if use_cache and self.config.use_cache:
            cache_result = self._load_cache(file_hash)
            if cache_result:
                cached_text, cached_provider, cached_is_precise = cache_result
                
                # 缓存匹配逻辑
                if cached_is_precise and is_precise:
                    # 缓存是高精度，要求高精度 -> 直接返回
                    return cached_text, True
                elif not cached_is_precise and not is_precise:
                    # 缓存是低精度，要求低精度 -> 直接返回
                    return cached_text, True
                elif not cached_is_precise and is_precise:
                    # 缓存是低精度，要求高精度 -> 需要重新识别（不返回，继续执行）
                    self._log("缓存是低精度，要求高精度，将使用高精度OCR重新识别")
                # else: 缓存是高精度，要求低精度 -> 直接返回（虽然精度更高但可用）
                elif cached_is_precise and not is_precise:
                    return cached_text, True

        # 2. 选择Provider（低精度时单一实例；高精度时在步骤4中按序尝试）
        if not is_precise:
            if self._fast_provider:
                provider = self._fast_provider
                provider_name = self._fast_provider_name
            else:
                order = self._get_effective_precise_order()
                if not order:
                    self.logger.warning("低精度Provider不可用且无可用高精度，将尝试高精度链")
                provider = None
                provider_name = None
                if order:
                    provider_name = order[0]
                    provider = self._get_or_create_precise_provider(provider_name)
                    is_precise = True

        # 3. 图片预处理
        processed_image_path = self._compress_image(image_path)
        try:
            # 3.1 校验图片可被正常解码（损坏的 PNG 等会导致 RapidOCR/PIL 报错，提前给出明确提示）
            # 优先使用 PIL，如果失败则尝试用 OpenCV 读取并转换（某些 PNG 变体 PIL 不支持但 OpenCV 可以）
            try:
                from PIL import Image
                with Image.open(processed_image_path) as img:
                    img.load()
            except (SyntaxError, OSError) as e:
                self.logger.warning("PIL 无法打开图片，尝试用 OpenCV 读取: %s", e)
                # 尝试用 OpenCV 读取并转换为标准格式
                try:
                    import cv2
                    import numpy as np
                    # 仅用字节流 + imdecode，不调用 imread(路径)，避免 Windows 下中文路径乱码传入 OpenCV C++ 层导致无法打开
                    with open(image_path, "rb") as f:
                        buf = f.read()
                    cv_img = cv2.imdecode(np.frombuffer(buf, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                    if cv_img is None:
                        self.last_ocr_failure_reason = "图片在压缩或OCR阶段无法解析（格式与当前解析库不兼容），页面预览可能正常，可尝试重新导出或更换图片。"
                        return ("", False)
                    
                    # 转换 BGR 到 RGB（OpenCV 使用 BGR，PIL 使用 RGB）
                    if len(cv_img.shape) == 3 and cv_img.shape[2] == 3:
                        cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                    elif len(cv_img.shape) == 3 and cv_img.shape[2] == 4:
                        cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGRA2RGBA)
                    
                    # 保存为临时 JPEG 文件（标准格式，PIL 和 RapidOCR 都能处理）
                    temp_converted = tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix='.jpg',
                        dir=str(self.config.temp_dir)
                    )
                    temp_converted_path = temp_converted.name
                    temp_converted.close()
                    
                    # 使用 PIL 保存（确保格式标准）
                    pil_img = Image.fromarray(cv_img)
                    if pil_img.mode in ('RGBA', 'P'):
                        pil_img = pil_img.convert('RGB')
                    pil_img.save(temp_converted_path, format='JPEG', quality=95)
                    
                    # 替换 processed_image_path 为转换后的文件
                    if processed_image_path != image_path and os.path.exists(processed_image_path):
                        try:
                            os.unlink(processed_image_path)
                        except:
                            pass
                    processed_image_path = temp_converted_path
                    self.logger.info("已通过 OpenCV 成功读取并转换图片: %s", processed_image_path)
                except ImportError:
                    self.logger.error("OpenCV 未安装，无法尝试备用读取方案")
                    self.last_ocr_failure_reason = "图片文件格式异常（PIL 无法解析），且 OpenCV 不可用。请重新导出图片或安装 OpenCV。"
                    return ("", False)
                except Exception as e2:
                    self.logger.error("OpenCV 也无法读取图片: %s", e2)
                    self.last_ocr_failure_reason = "图片在压缩或OCR阶段无法解析（格式与当前解析库不兼容），页面预览可能正常，可尝试重新导出或更换图片。"
                    return ("", False)
            # 4. 调用 Provider：高精度按序尝试（失败则标记禁用并试下一个），全部失败再回退低精度
            if is_precise:
                effective_order = self._get_effective_precise_order()
                for name in effective_order:
                    try:
                        p = self._get_or_create_precise_provider(name)
                        text = p.ocr_image(processed_image_path)
                        if self.config.use_cache and (text or "").strip():
                            self._save_cache(file_hash, text, name, True)
                        return (text or "", False)
                    except OCRError as e:
                        self.logger.warning("高精度OCR失败 [%s]: %s", name, e)
                        self._status_manager.mark_disabled(name, str(e))
                        continue
                self.last_ocr_warning = "高精度OCR不可用（如限频），已使用低精度OCR"
                if self._fast_provider:
                    try:
                        text = self._fast_provider.ocr_image(processed_image_path)
                        if self.config.use_cache and (text or "").strip():
                            self._save_cache(file_hash, text, self._fast_provider_name, False)
                        return (text or "", False)
                    except Exception as e2:
                        self.logger.warning("低精度OCR也失败: %s", e2)
                        self.last_ocr_warning = f"高精度OCR失败；低精度OCR也失败: {e2}"
                        return ("", False)
                self.last_ocr_warning = "无可用高精度且无低精度Provider"
                return ("", False)
            # 低精度或“无低精度时用高精度”的单次调用
            if provider is None:
                self.last_ocr_warning = "无可用OCR Provider（高精度已禁用且未配置低精度）"
                return ("", False)
            text = provider.ocr_image(processed_image_path)
            # 5. 保存缓存
            if self.config.use_cache and (text or "").strip():
                self._save_cache(file_hash, text, provider_name, is_precise)
            elif self.config.use_cache and not (text or "").strip():
                self._log("OCR 结果为空，跳过写入缓存，避免覆盖已有有效缓存")
            return text, False
        finally:
            # 清理临时文件（如果不是原始文件）
            if processed_image_path != image_path and os.path.exists(processed_image_path):
                try:
                    os.unlink(processed_image_path)
                except:
                    pass

    def get_text(self, file_path: str, use_cache: bool = True, is_precise: bool = False) -> Tuple[str, bool]:
        """
        主入口：获取文件文字（支持图片和PDF第一页）

        Args:
            file_path: 文件路径（图片或PDF）
            use_cache: 是否使用缓存
            is_precise: 是否要求高精度识别（默认False）

        Returns:
            (文本内容, 是否命中缓存)

        Raises:
            OCRFileNotFoundError: 文件不存在
        """
        self.last_ocr_warning = None
        if not os.path.exists(file_path):
            raise OCRFileNotFoundError(f"未找到文件：{file_path}")

        # 判断文件类型
        file_path_lower = file_path.lower()

        if file_path_lower.endswith('.pdf'):
            # PDF处理：将第一页转为图片，然后OCR
            try:
                from backend.utils.pdf_to_image import pdf_to_image

                pdf_path_obj = Path(file_path)
                pdf_dir = pdf_path_obj.parent
                pdf_name = pdf_path_obj.stem
                
                # 转换PDF第一页为图片，保存到PDF同目录
                pdf_result = pdf_to_image(
                    pdf_path=file_path,
                    output_dir=str(pdf_dir),  # 输出到PDF同目录
                    dpi=getattr(self, '_pdf_dpi', 200.0),  # 使用配置的DPI，默认200.0
                    first_page_only=True
                )

                # 检查转换结果
                if not pdf_result.get("success"):
                    error_msg = pdf_result.get("error", "PDF转图片失败")
                    self.logger.error(f"PDF转图片失败: {error_msg}")
                    raise OCRFileNotFoundError(f"PDF转图片失败: {error_msg}")

                # 获取第一页图片路径
                image_path = pdf_result.get("first_page_path")
                if not image_path:
                    # 如果没有 first_page_path，尝试从 images 列表获取
                    images = pdf_result.get("images", [])
                    if images:
                        image_path = images[0]
                    else:
                        raise OCRFileNotFoundError("PDF转图片成功但未找到图片路径")
                
                # 确保图片保存在PDF同目录，文件名为{pdf_name}.png
                image_path_obj = Path(image_path)
                expected_path = pdf_dir / f"{pdf_name}.png"
                
                # 如果路径不正确，移动或重命名文件
                if image_path_obj != expected_path:
                    if image_path_obj.exists():
                        # 如果目标文件已存在，先删除
                        if expected_path.exists():
                            expected_path.unlink()
                        # 移动文件到正确位置
                        image_path_obj.rename(expected_path)
                        image_path = str(expected_path)
                        self._log(f"PDF转换图片已移动到: {expected_path.name}")
                    else:
                        raise OCRFileNotFoundError(f"PDF转换图片不存在: {image_path}")

                # OCR识别
                return self._ocr_image(image_path, is_precise, use_cache)
            except ImportError as e:
                self.logger.error(f"PDF处理模块导入失败: {e}")
                raise
            except Exception as e:
                self.logger.error(f"PDF处理失败: {e}")
                raise
        else:
            # 直接OCR图片
            return self._ocr_image(file_path, is_precise, use_cache)

    def clear_cache(self, file_path: Optional[str] = None) -> None:
        """
        清理缓存

        Args:
            file_path: 如果提供，只清理该文件的缓存；否则清理所有缓存
        """
        if file_path:
            if os.path.exists(file_path):
                file_hash = self._calculate_hash(file_path)
                count = self.cache_db.delete_ocr_cache(file_hash)
                if count > 0:
                    self._log(f"已清理缓存：{file_path}")
                else:
                    self._log(f"未找到缓存：{file_path}")
            else:
                self.logger.warning(f"待清理缓存的文件不存在：{file_path}")
        else:
            count = self.cache_db.delete_ocr_cache()
            self._log(f"已清理全部缓存（共 {count} 条记录）")

    def get_cache_stats(self):
        """获取缓存统计信息"""
        return self.cache_db.get_cache_stats()
