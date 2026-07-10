"""
服务上下文管理

整合 OCR、文档抽取等服务，提供统一的上下文管理
"""
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 延迟导入，避免循环依赖
def _get_config_loader():
    """获取配置加载器（延迟导入）"""
    from config.loader import get_config
    return get_config()

# 确保项目根目录在 Python 路径中
# 项目根目录从配置加载器获取，而不是硬编码
try:
    config_loader = _get_config_loader()
    project_root = config_loader.project_root
except Exception:
    # 降级方案：如果配置加载失败，使用相对路径
    project_root = Path(__file__).parent.parent.parent
    logger.warning(f"无法从配置加载器获取项目根目录，使用降级方案: {project_root}")

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

class ServiceContext:
    """
    服务上下文类

    负责初始化和管理所有核心组件的单例实例
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceContext, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.project_root = project_root
        self._ocr_engine = None
        self._template_manager = None
        self._llm_provider = None
        self._extract_cache_db = None
        self._extract_framework = None

        # 从配置文件加载路径（不允许硬编码）
        try:
            config_loader = _get_config_loader()
            
            # 数据库路径（database 现在是顶层配置）
            self.ocr_cache_path = config_loader.get_path("database", "ocr_cache_db")
            self.extract_cache_path = config_loader.get_path("database", "extract_cache_db")
            self.validation_db_path = config_loader.get_path("database", "validation_db")

            # 验证配置现在从 settings.json 的 validation 配置节读取，不再需要单独的配置文件

            # 临时文件目录 - 使用统一文件管理器获取 temp_upload 目录
            from backend.services.unified_file_manager import get_unified_file_manager, SessionStatus
            file_manager = get_unified_file_manager()
            self.temp_dir = file_manager.files_root / SessionStatus.TEMP_UPLOAD.directory
        except Exception as e:
            raise ValueError(
                f"无法从配置文件加载路径配置。请确保 config/settings.json 中包含相关配置。"
                f"错误详情: {e}"
            ) from e

        self._initialized = True

    def initialize(self):
        """初始化所有组件"""
        try:
            logger.info("正在初始化服务上下文...")

            # 延迟导入，避免循环依赖
            from backend.ocr import OCRConfig, OCREngine
            from backend.extract.template.manager import TemplateManager
            from backend.extract import ExtractFramework
            from backend.extract.llm import LLMProvider, OllamaLLMProvider, ExtractCacheDB
            from config.loader import get_config

            config_loader = get_config()

            # 1. 初始化 OCR 引擎（使用配置驱动的工厂模式）
            logger.info("初始化 OCR 引擎...")
            default_ocr = config_loader.get_default_provider('ocr')
            ocr_provider_config = config_loader.get_provider_config('ocr', default_ocr)

            # 构建通用 OCR 配置
            ocr_config = OCRConfig(
                db_path=str(self.ocr_cache_path),
                temp_dir=str(self.temp_dir),
                provider=default_ocr,
                debug=False
            )
            
            # 使用配置驱动的工厂模式创建引擎
            self._ocr_engine = OCREngine(ocr_config, provider_config=ocr_provider_config)
            logger.info(f"OCR 引擎初始化完成 (provider: {default_ocr})")

            # 2. 初始化 LLM 提供者
            logger.info("初始化 LLM 提供者...")
            default_llm = config_loader.get_default_provider('llm')

            # 特殊处理 ollama：使用 OllamaLLMProvider
            if default_llm == "ollama" or "ollama" in default_llm.lower():
                # OllamaLLMProvider 已从 backend.extract.llm 导入

                # 获取 ollama 配置
                config = config_loader.load_config()
                ollama_config = config['llm']['providers'][default_llm]

                self._llm_provider = OllamaLLMProvider.from_config(ollama_config)
                logger.info(f"LLM 提供者初始化完成 (provider: {default_llm}, model: {ollama_config.get('model')})")
            else:
                # 其他 LLM 使用通用 LLMProvider
                # 获取原始配置（未替换环境变量）以获取 api_key_env
                config = config_loader.load_config()
                raw_provider_config = config['llm']['providers'][default_llm]

                # 获取替换后的配置（用于获取其他字段）
                llm_provider_config = config_loader.get_provider_config('llm', default_llm)

                # 检查 provider 类型
                provider_type = raw_provider_config.get("type", "api")  # 默认为 API 类型

                # 构建 LLMProvider 期望的配置格式
                api_config = {
                    "url": raw_provider_config.get("base_url") or raw_provider_config.get("url") or llm_provider_config.get("base_url") or llm_provider_config.get("url"),
                    "api_key_env": raw_provider_config.get("api_key_env"),  # 使用原始配置中的 api_key_env
                    "model": llm_provider_config.get("model", raw_provider_config.get("model", "glm-4-flash")),
                    "temperature": llm_provider_config.get("temperature", raw_provider_config.get("temperature", 0.7))
                }

                # 验证必需字段（根据 provider 类型）
                if provider_type == "api":
                    # API 类型需要 api_key_env
                    if not api_config.get("api_key_env"):
                        raise ValueError(
                            f"LLM配置中缺少 'api_key_env' 字段。"
                            f"请在配置文件的 llm.providers.{default_llm} 中添加 'api_key_env' 字段，"
                            f"例如: \"api_key_env\": \"ZHIPUAI_API_KEY\""
                        )

                    if not api_config.get("url"):
                        raise ValueError(
                            f"LLM配置中缺少 'url' 或 'base_url' 字段。"
                            f"请在配置文件的 llm.providers.{default_llm} 中添加 'url' 或 'base_url' 字段。"
                        )
                elif provider_type == "local":
                    # 本地类型（如 ollama）只需要 url
                    if not api_config.get("url"):
                        raise ValueError(
                            f"本地 LLM 配置中缺少 'url' 或 'base_url' 字段。"
                            f"请在配置文件的 llm.providers.{default_llm} 中添加本地服务地址，"
                            f"例如: \"base_url\": \"http://localhost:11434\""
                        )
                    # 本地模型不需要 api_key_env，设置为 None
                    api_config["api_key_env"] = None

                self._llm_provider = LLMProvider(
                    api_config=api_config
                )
                logger.info(f"LLM 提供者初始化完成 (provider: {default_llm}, model: {api_config['model']})")

            # 3. 初始化抽取缓存数据库
            self._extract_cache_db = ExtractCacheDB(str(self.extract_cache_path))
            logger.info("抽取缓存数据库初始化完成")

            # 4. 初始化模板管理器
            logger.info("初始化模板管理器...")
            # 设置配置目录路径（从配置文件读取）
            config_loader = _get_config_loader()
            config_dir = config_loader.get_path("document_extract", "config_dir")
            
            # 如果配置路径不存在，尝试使用默认路径 backend/extract/config
            if not config_dir or not config_dir.exists():
                default_config_dir = Path(__file__).parent.parent / "extract" / "config"
                if default_config_dir.exists():
                    logger.info(f"配置路径不存在，使用默认路径: {default_config_dir}")
                    config_dir = default_config_dir
                else:
                    logger.warning(f"配置路径不存在，且默认路径也不存在: {default_config_dir}")
                    config_dir = None
            
            # 加载字段定义文件
            import json
            # prompts 目录已移至 backend/extract/prompts
            prompts_dir = Path(__file__).parent.parent / "extract" / "prompts"
            base_fields_map = {}
            
            type_files = {
                "award": "award_fields.json",
                "patent": "patent_fields.json",
                "software": "software_fields.json"
            }
            
            for type_name, filename in type_files.items():
                file_path = prompts_dir / filename
                if file_path.exists():
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            base_fields_map[type_name] = json.load(f)
                        logger.info(f"加载字段定义: {filename} ({len(base_fields_map[type_name])} 个字段)")
                    except Exception as e:
                        logger.warning(f"加载字段定义失败 {filename}: {e}")
                else:
                    logger.warning(f"字段定义文件不存在: {file_path}")
            
            self._template_manager = TemplateManager(
                db_path=str(self.validation_db_path),
                base_fields_map=base_fields_map,
                config_dir=str(config_dir) if config_dir else None
            )
            logger.info("模板管理器初始化完成")

            # 5. 初始化抽取框架 (替代旧的 UniversalExtractor)
            logger.info("初始化抽取框架...")
            # 使用配置驱动的工厂模式创建抽取框架
            framework = ExtractFramework.from_config_loader(config_loader)
            
            # 6. 注册抽取器
            from backend.extract import (
                InnovationExtractor, 
                PatentExtractor, 
                SoftwareExtractor, 
                AwardExtractor
            )
            
            # 注册 InnovationExtractor
            try:
                framework.register(InnovationExtractor.from_config_loader(config_loader))
            except Exception as e:
                logger.warning(f"注册 InnovationExtractor 失败: {e}")
                
            # 注册 PatentExtractor 和 SoftwareExtractor
            try:
                framework.register(PatentExtractor.from_config_loader(config_loader))
                framework.register(SoftwareExtractor.from_config_loader(config_loader))
            except Exception as e:
                logger.warning(f"注册证书抽取器失败: {e}")
                
            # 注册 AwardExtractor（需要 template_manager）
            try:
                award_config = config_loader.load_config().get("extract", {}).get("award", {})
                framework.register(AwardExtractor(award_config, template_manager=self._template_manager))
            except Exception as e:
                logger.warning(f"注册 AwardExtractor 失败: {e}")
            
            self._extract_framework = framework
            logger.info("抽取框架初始化及抽取器注册完成")

            logger.info("服务上下文初始化完成")
            return True

        except Exception as e:
            logger.error(f"服务上下文初始化失败: {e}")
            raise

    @property
    def ocr_engine(self):
        """获取 OCR 引擎"""
        if self._ocr_engine is None:
            self.initialize()
        return self._ocr_engine

    @property
    def template_manager(self):
        """获取模板管理器"""
        if self._template_manager is None:
            self.initialize()
        return self._template_manager

    @property
    def llm_provider(self):
        """获取 LLM 提供者"""
        if self._llm_provider is None:
            self.initialize()
        return self._llm_provider

    @property
    def extract_cache_db(self):
        """获取抽取缓存数据库"""
        if self._extract_cache_db is None:
            self.initialize()
        return self._extract_cache_db

    @property
    def extract_framework(self):
        """获取抽取框架"""
        if self._extract_framework is None:
            self.initialize()
        return self._extract_framework
    
    @property
    def universal_extractor(self):
        """获取通用抽取器（已弃用，请使用 extract_framework）"""
        import warnings
        warnings.warn(
            "universal_extractor 已弃用，请使用 extract_framework 替代",
            DeprecationWarning,
            stacklevel=2
        )
        if self._extract_framework is None:
            self.initialize()
        return self._extract_framework


# 全局单例
_context = None

def get_context() -> ServiceContext:
    """获取全局服务上下文实例"""
    global _context
    if _context is None:
        _context = ServiceContext()
    return _context
