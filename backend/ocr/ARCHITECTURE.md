# OCR 模块架构设计文档

## 概述

OCR 模块已重构为**配置驱动的插件化架构**，所有配置来自 `config/settings.json`，支持 Provider 自动注册和动态加载。

## 核心设计原则

1. **配置驱动**：所有配置（包括厂商特定配置）都从 `config/settings.json` 读取
2. **插件化架构**：Provider 使用装饰器自动注册，无需修改核心代码即可添加新厂商
3. **统一接口**：所有 Provider 实现相同的接口，但配置参数可以不同
4. **零硬编码**：移除所有厂商特定的硬编码字段

## 架构组件

### 1. Provider 注册机制 (`provider_registry.py`)

使用装饰器模式自动注册 Provider：

```python
from .provider_registry import register_provider

@register_provider("zhipu")
class ZhipuOCRProvider(OCRProvider):
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        # 从 config 字典中读取参数
        self.api_key = config.get('api_key', '')
        self.api_url = config.get('api_url', '...')
```

### 2. Provider 工厂 (`provider_factory.py`)

根据配置自动创建 Provider 实例：

```python
factory = ProviderFactory(logger)
provider = factory.create_provider(
    provider_name="baidu",
    provider_config={"api_key": "...", "secret_key": "..."},
    common_config={"debug": False, "max_image_size": 2048}
)
```

### 3. 简化的 OCRConfig (`config.py`)

只保留通用配置，移除所有厂商特定字段：

```python
@dataclass
class OCRConfig:
    db_path: str = ""           # 缓存数据库路径
    temp_dir: str = ""          # 临时文件目录
    provider: str = ""          # Provider 名称
    max_image_size: int = 2048  # 通用图片处理参数
    jpeg_quality: int = 85
    debug: bool = False
    use_cache: bool = True
    # 不再有 baidu_api_key, api_url 等硬编码字段
```

### 4. OCREngine (`ocr_engine.py`)

使用工厂模式初始化 Provider：

```python
# 推荐方式：从配置加载器创建
engine = OCREngine.from_config_loader(config_loader)

# 或直接传入配置
engine = OCREngine(ocr_config, provider_config=provider_config_dict)
```

## 配置文件结构

`config/settings.json` 中的 OCR 配置：

```json
{
  "ocr": {
    "default_provider": "baidu",
    "providers": {
      "zhipu": {
        "type": "api",
        "api_key_env": "ZHIPUAI_API_KEY",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/files/ocr",
        "model": "glm-4",
        "max_image_size": 2048,
        "jpeg_quality": 85
      },
      "baidu": {
        "type": "api",
        "api_key_env": "BAIDU_API_KEY",
        "secret_key_env": "BAIDU_SECRET_KEY",
        "api_url": "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
      },
      "paddle": {
        "type": "local",
        "device": "gpu",
        "lang": "ch",
        "ocr_version": "PP-OCRv5",
        "use_doc_orientation_classify": false
      }
    },
    "cache": {
      "enabled": true,
      "db_path": "database/ocr_cache.db"
    }
  }
}
```

## 添加新 Provider

### 步骤 1：实现 Provider 类

```python
from .provider_registry import register_provider
from .providers import OCRProvider

@register_provider("my_provider")
class MyOCRProvider(OCRProvider):
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        super().__init__(config, logger)
        # 从配置中读取参数
        self.api_key = config.get('api_key', '')
        self.api_url = config.get('api_url', '')
        # 验证必需参数
        if not self.api_key:
            raise OCRAPIServiceError("API key 未配置")
    
    def ocr_image(self, image_path: str) -> Tuple[str, Dict[str, Any]]:
        # 实现 OCR 逻辑
        text = "..."
        raw_data = {...}
        return text, raw_data
```

### 步骤 2：在配置文件中添加配置

```json
{
  "ocr": {
    "providers": {
      "my_provider": {
        "type": "api",
        "api_key_env": "MY_API_KEY",
        "api_url": "https://api.example.com/ocr"
      }
    }
  }
}
```

### 步骤 3：使用新 Provider

```python
# 在 settings.json 中设置 default_provider 为 "my_provider"
# 或在使用时指定
engine = OCREngine.from_config_loader(config_loader)
```

**无需修改任何核心代码！**

## 使用示例

### 方式 1：使用配置加载器（推荐）

```python
from config.loader import get_config
from backend.ocr import OCREngine, OCRConfig
from backend.services.context import ServiceContext

config_loader = get_config()
context = ServiceContext()

# 创建通用配置
ocr_config = OCRConfig(
    db_path=str(context.ocr_cache_path),
    temp_dir=str(context.temp_dir),
    provider=config_loader.get_default_provider('ocr'),
    debug=False
)

# 获取 Provider 配置
provider_config = config_loader.get_provider_config('ocr', ocr_config.provider)

# 创建引擎
engine = OCREngine(ocr_config, provider_config=provider_config)
```

### 方式 2：直接使用工厂

```python
from backend.ocr.core.provider_factory import ProviderFactory
from backend.ocr import OCRConfig

factory = ProviderFactory()
provider = factory.create_provider(
    provider_name="baidu",
    provider_config={
        "api_key": "...",
        "secret_key": "...",
        "api_url": "..."
    },
    common_config={
        "debug": False,
        "max_image_size": 2048
    }
)
```

## 优势

1. **零硬编码**：所有配置来自外部文件，易于维护
2. **易于扩展**：添加新 Provider 只需实现类和添加配置，无需修改核心代码
3. **配置统一**：所有配置集中在 `settings.json`，避免配置分散
4. **类型安全**：Provider 接口统一，但配置灵活
5. **向后兼容**：保留必要的向后兼容支持

## 迁移指南

### 旧代码

```python
config = OCRConfig(
    api_key="...",
    baidu_api_key="...",
    baidu_secret_key="...",
    device="gpu",
    # ... 很多硬编码字段
)
engine = OCREngine(config)
```

### 新代码

```python
# 配置在 settings.json 中
config_loader = get_config()
provider_config = config_loader.get_provider_config('ocr', 'baidu')

ocr_config = OCRConfig(
    db_path="...",
    temp_dir="...",
    provider="baidu"
)
engine = OCREngine(ocr_config, provider_config=provider_config)
```

## 注意事项

1. **环境变量**：配置中使用 `api_key_env` 格式，会自动从环境变量读取
2. **Provider 注册**：确保导入 `providers` 模块以触发自动注册
3. **配置验证**：Provider 应在 `__init__` 中验证必需参数
4. **向后兼容**：`create_ocr_engine` 函数已更新，但旧用法可能不再支持
