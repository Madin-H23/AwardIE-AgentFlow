> ⚠️ 已归档（2026-08-24）：本文档为历史资料，不反映项目现状。现行权威文档见 docs/README.md 路由。

# OCR识别与缓存设计

## 概述

OCR（光学字符识别）模块负责从图片和PDF文件中提取文本内容，是文档信息抽取流程的第一步。本模块采用配置驱动的插件化架构，支持多种OCR提供商，并通过SQLite缓存机制避免重复识别。

**高精度供应商故障切换与管理员状态管理**：当某高精度供应商调用失败（如 429、超时）时，引擎会将该供应商标记为不可用并自动尝试下一可用高精度；全部不可用时回退到低精度（rapid）。管理员可在系统设置中查看当前使用的高精度供应商、各供应商的可用/禁用状态及故障理由，并可重新启用某供应商或设为当前默认。详见 [OCR供应商故障切换与管理员状态管理.md](OCR供应商故障切换与管理员状态管理.md)。

## 模块功能

### 1. 供应商注册机制

OCR模块使用装饰器模式自动注册Provider，支持动态扩展：

```python
from backend.ocr.core.provider_registry import register_provider

@register_provider("zhipu")
class ZhipuOCRProvider(OCRProvider):
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        # Provider初始化
        pass
    
    def ocr_image(self, image_path: str) -> str:
        # OCR识别实现
        pass
```

**注册特点：**
- 使用 `@register_provider("provider_name")` 装饰器自动注册
- Provider名称在配置文件中指定
- 支持运行时动态发现和加载

### 2. 精度分级

OCR Provider分为两类：

- **高精度Provider** (`is_precise=True`)：使用大型模型，识别精度高，但消耗更多算力和token
  - 默认Provider（如百度、智谱等）
  - 适用于最终识别和重要文档

- **低精度Provider** (`is_precise=False`)：使用轻量级模型，识别速度快，资源消耗低
  - 如 RapidOCR
  - 适用于快速筛选和初步识别

**配置方式：**
在 `config/settings.json` 中为每个Provider配置 `is_precise` 标志：

```json
{
  "ocr": {
    "providers": {
      "zhipu": {
        "is_precise": true,
        ...
      },
      "baidu": {
        "is_precise": true,
        ...
      },
      "rapid": {
        "is_precise": false,
        ...
      }
    }
  }
}
```

### 3. 缓存机制

**缓存策略：**
- **全量缓存**：对所有图片的OCR结果都进行缓存（不再仅限于奖状等特定类型）
- **精度匹配**：缓存记录包含精度标志，支持按精度要求匹配缓存
- **智能回退**：如果低精度缓存存在但需要高精度结果，会自动调用高精度OCR并更新缓存
- **唯一性约束**：每个hash只对应一条记录（基于`image_hash`的唯一索引）

**缓存写入策略：**
- **高精度OCR**：执行后直接覆盖数据库cache（使用`INSERT OR REPLACE`）
  - 如果缓存已存在，无论原缓存是何种精度，都会被高精度结果覆盖
  - 确保高精度结果优先保存
  
- **低精度OCR**：只有在数据库表对应项目为空时才添加（使用`INSERT OR IGNORE`）
  - 如果缓存已存在（无论是高精度还是低精度），都不会插入新记录
  - 避免低精度结果覆盖高精度结果

**缓存匹配逻辑：**
```
查询缓存（根据image_hash）
├─> 缓存未命中
│   └─> 根据is_precise选择Provider，执行OCR，保存结果
│
└─> 缓存命中
    ├─> 缓存是高精度 且 is_precise=True
    │   └─> 直接返回缓存（完全匹配）
    │
    ├─> 缓存是低精度 且 is_precise=False
    │   └─> 直接返回缓存（完全匹配）
    │
    └─> 缓存是低精度 且 is_precise=True
        └─> 使用高精度Provider重新识别，覆盖缓存
```

**缓存键设计：**
- 基于文件内容SHA256哈希（不包含Provider信息）
- PDF文件和转换后的图片hash不同（因为文件内容不同）
- 每个hash只对应一条记录，通过`is_precise`字段区分精度级别

### 4. 图片预处理

所有OCR调用前都会进行图片预处理，包括：

1. **EXIF方向校正**：自动校正图片方向
2. **自动旋转**：检测并修正竖版图片
3. **格式转换**：RGBA/P → RGB
4. **尺寸调整**：超过最大尺寸时按比例缩小
5. **质量压缩**：JPEG压缩优化

**预处理参数：**
- `max_image_size`: 最大图片尺寸（默认2048像素）
- `jpeg_quality`: JPEG压缩质量（默认85）

## 对外接口

### OCREngine 类

**初始化：**

```python
from backend.ocr import OCREngine
from config.loader import get_config

config_loader = get_config()
engine = OCREngine.from_config_loader(config_loader)
```

**初始化时自动设置（from_config_loader）：**
- **高精度链**：`_precise_order`（高精度供应商有序列表，仅 `is_precise=True` 的；default 优先）、`_precise_configs`、`_status_manager`（运行时状态管理器）、`_precise_instances`（按需懒创建）。高精度调用时按序尝试未禁用的供应商，失败则写状态并试下一个，全部失败再回退低精度。详见 [OCR供应商故障切换与管理员状态管理.md](OCR供应商故障切换与管理员状态管理.md)。
- **低精度**：`_fast_provider`、`_fast_provider_name`（is_precise=False 的第一个 Provider）。
- **配置**：需在 `config/settings.json` 的 `ocr` 下配置 `runtime_status_path`（如 `config/ocr_runtime.json`），缺失时抛错。

**主要方法：**

#### `get_text(file_path, use_cache=True, is_precise=False) -> Tuple[str, bool]`

从文件提取文本内容（支持图片和PDF第一页）。

**参数：**
- `file_path` (str): 文件路径（图片或PDF）
- `use_cache` (bool): 是否使用缓存（默认True）
- `is_precise` (bool): 是否要求高精度识别（默认False）

**返回：**
- `Tuple[str, bool]`: (文本内容, 是否命中缓存)

**执行流程：**

```
1. 文件存在性检查
   └─> 如果不存在，抛出 OCRFileNotFoundError

2. PDF处理（如果是PDF）
   └─> 转换为第一页图片
       ├─> 转换后的图片保存在PDF文件同目录下
       ├─> 文件名与PDF相同，扩展名为`.png`
       ├─> 示例：`/path/to/document.pdf` → `/path/to/document.png`
       └─> 使用转换后的图片路径继续处理

3. 缓存处理逻辑
   ├─> 如果不使用缓存 (use_cache=False)
   │   └─> 根据 is_precise 选择Provider
   │
   └─> 如果使用缓存 (use_cache=True)
       ├─> 计算文件哈希
       ├─> 查询缓存数据库
       │
       ├─> 如果缓存未命中
       │   └─> 根据 is_precise 选择Provider
       │
       └─> 如果缓存命中
           ├─> 如果缓存是高精度 且 is_precise=True
           │   └─> 直接返回缓存结果
           │
           ├─> 如果缓存是低精度 且 is_precise=False
           │   └─> 直接返回缓存结果
           │
           └─> 如果缓存是低精度 且 is_precise=True
               └─> 使用高精度Provider重新识别

4. 图片预处理
   └─> 调用 _compress_image() 进行预处理

5. OCR识别
   ├─> 若 is_precise=True：按高精度有序列表（跳过已禁用的）依次尝试 Provider.ocr_image()；某次失败则写运行时状态（mark_disabled）并试下一个；全部失败则回退到低精度 Provider。详见 [OCR供应商故障切换与管理员状态管理.md](OCR供应商故障切换与管理员状态管理.md)。
   └─> 若 is_precise=False：调用选定的低精度 Provider.ocr_image()

6. 保存缓存
   └─> 将结果保存到数据库（包含is_precise标志）

7. 返回结果
   └─> (识别文本, 缓存命中标志)
```

**示例：**

```python
# 低精度快速识别（使用缓存）
text, cached = engine.get_text("image.jpg", use_cache=True, is_precise=False)

# 高精度识别（使用缓存，如果缓存是低精度会自动升级）
text, cached = engine.get_text("image.jpg", use_cache=True, is_precise=True)

# 强制重新识别（不使用缓存）
text, cached = engine.get_text("image.jpg", use_cache=False, is_precise=True)
```

#### `get_current_effective_precise_provider_name() -> Optional[str]`

返回当前实际使用的第一个可用高精度供应商名称（供管理端展示）；无可用时返回 None。高精度链与禁用状态见 [OCR供应商故障切换与管理员状态管理.md](OCR供应商故障切换与管理员状态管理.md)。

#### `get_precise_order() -> List[str]`

返回高精度供应商有序列表（含已禁用的）。

#### `get_status_manager() -> OCRProviderStatusManager`

返回运行时状态管理器（供管理端读/写禁用状态）。

#### `clear_cache(file_path=None) -> None`

清理缓存。

**参数：**
- `file_path` (Optional[str]): 如果提供，只清理该文件的缓存；否则清理所有缓存

#### `get_cache_stats() -> CacheStats`

获取缓存统计信息。

**返回：**
- `CacheStats`: 包含count、oldest、newest等统计信息

### OCRProvider 接口

所有Provider必须实现以下接口：

```python
class OCRProvider(ABC):
    @abstractmethod
    def ocr_image(self, image_path: str) -> str:
        """
        执行OCR识别
        
        Args:
            image_path: 图片路径
            
        Returns:
            识别的文本内容（纯文本）
        """
        pass
```

## 数据库表设计

### ocr_cache 表

**表结构：**

```sql
CREATE TABLE ocr_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_hash TEXT NOT NULL UNIQUE,    -- 文件哈希（包含Provider信息）
    ocr_text TEXT NOT NULL,             -- OCR识别的纯文本
    provider TEXT NOT NULL,             -- Provider名称
    is_precise BOOLEAN NOT NULL,        -- 是否为高精度识别（新增）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**索引：**

```sql
CREATE INDEX idx_ocr_cache_hash ON ocr_cache(image_hash);
CREATE INDEX idx_ocr_cache_created_at ON ocr_cache(created_at);
CREATE INDEX idx_ocr_cache_provider ON ocr_cache(provider);
CREATE INDEX idx_ocr_cache_is_precise ON ocr_cache(is_precise);
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键，自增 |
| `image_hash` | TEXT | 文件哈希值（基于文件内容，不包含Provider信息），唯一索引 |
| `ocr_text` | TEXT | OCR识别的文本内容 |
| `provider` | TEXT | OCR Provider名称（如 "zhipu", "baidu", "rapid"） |
| `is_precise` | BOOLEAN | 是否为高精度识别（true=高精度，false=低精度） |
| `created_at` | TIMESTAMP | 创建时间 |
| `updated_at` | TIMESTAMP | 更新时间 |

### 数据库操作

#### CacheDB 类

**位置：** `backend/ocr/core/cache_db.py`

**主要方法：**

```python
class CacheDB:
    def get_ocr_cache(self, image_hash: str) -> Optional[tuple[str, str, bool]]:
        """
        获取 OCR 缓存
        
        Args:
            image_hash: 图片哈希值
            
        Returns:
            (OCR文本, Provider名称, is_precise) 元组，如果不存在返回 None
        """
        pass
    
    def save_ocr_cache(
        self, 
        image_hash: str, 
        ocr_text: str, 
        provider: str, 
        is_precise: bool
    ) -> bool:
        """
        保存 OCR 缓存
        
        Args:
            image_hash: 图片哈希值
            ocr_text: OCR识别的纯文本
            provider: OCR提供者名称
            is_precise: 是否为高精度识别
            
        Returns:
            是否保存成功
        """
        pass
    
    def delete_ocr_cache(self, image_hash: Optional[str] = None) -> int:
        """
        删除 OCR 缓存
        
        Args:
            image_hash: 如果提供，删除指定哈希的缓存；否则删除所有
            
        Returns:
            删除的记录数
        """
        pass
    
    def get_cache_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        pass
```

**SQL操作示例：**

```sql
-- 查询缓存
SELECT ocr_text, provider, is_precise 
FROM ocr_cache 
WHERE image_hash = ?;

-- 保存缓存（使用INSERT OR REPLACE处理重复键）
INSERT OR REPLACE INTO ocr_cache 
    (image_hash, ocr_text, provider, is_precise, updated_at)
VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP);

-- 按精度统计
SELECT is_precise, COUNT(*) as count 
FROM ocr_cache 
GROUP BY is_precise;
```

## 使用示例

### 示例1：基本使用

```python
from backend.ocr import OCREngine
from config.loader import get_config

# 初始化引擎
config_loader = get_config()
engine = OCREngine.from_config_loader(config_loader)

# 低精度快速识别（适合快速筛选）
text, cached = engine.get_text(
    "path/to/image.jpg",
    use_cache=True,
    is_precise=False
)
print(f"识别结果: {text[:100]}...")
print(f"缓存命中: {cached}")

# 高精度识别（适合最终处理）
text, cached = engine.get_text(
    "path/to/image.jpg",
    use_cache=True,
    is_precise=True
)
```

### 示例2：PDF处理

```python
# PDF文件会自动转换为第一页图片进行OCR
text, cached = engine.get_text(
    "path/to/document.pdf",
    use_cache=True,
    is_precise=True
)
```

### 示例3：缓存管理

```python
# 清理指定文件缓存
engine.clear_cache("path/to/image.jpg")

# 清理所有缓存
engine.clear_cache()

# 查看缓存统计
stats = engine.get_cache_stats()
print(f"缓存总数: {stats.count}")
print(f"最早缓存: {stats.oldest}")
print(f"最新缓存: {stats.newest}")
```

### 示例4：在文档抽取中使用

```python
from backend.services.context import ServiceContext

context = ServiceContext()
engine = context.ocr_engine

# 快速筛选阶段：使用低精度OCR
fast_text, _ = engine.get_text(
    file_path,
    use_cache=True,
    is_precise=False
)

# 最终识别阶段：使用高精度OCR
precise_text, cached = engine.get_text(
    file_path,
    use_cache=True,
    is_precise=True
)
```

### 示例5：配置Provider精度

在 `config/settings.json` 中配置：

```json
{
  "ocr": {
    "default_provider": "baidu",
    "providers": {
      "zhipu": {
        "type": "api",
        "is_precise": true,
        "api_key_env": "ZHIPUAI_API_KEY",
        ...
      },
      "baidu": {
        "type": "api",
        "is_precise": true,
        "api_key_env": "BAIDU_API_KEY",
        ...
      },
      "rapid": {
        "type": "local",
        "is_precise": false,
        "device": "cpu"
      }
    }
  }
}
```

### 示例6：缓存精度匹配逻辑

```python
# 场景1：低精度缓存存在，需要低精度结果
# → 直接返回缓存（命中）

# 场景2：高精度缓存存在，需要高精度结果
# → 直接返回缓存（命中）

# 场景3：低精度缓存存在，需要高精度结果
# → 调用高精度OCR，更新缓存（未命中，但复用低精度结果）

# 场景4：高精度缓存存在，需要低精度结果
# → 直接返回缓存（命中，虽然精度更高但可用）

# 场景5：无缓存，需要低精度结果
# → 调用低精度OCR，保存缓存

# 场景6：无缓存，需要高精度结果
# → 调用高精度OCR，保存缓存
```

## 数据迁移

### 添加 is_precise 列

对于现有数据库，需要执行以下SQL添加新列：

```sql
ALTER TABLE ocr_cache ADD COLUMN is_precise BOOLEAN NOT NULL DEFAULT 1;
```

**注意：** 此操作需要单独执行，不在项目代码中处理。建议使用独立的迁移脚本。

### 更新现有缓存记录

将现有所有缓存记录的 `is_precise` 设置为 `true`（因为历史缓存都是高精度识别）：

```sql
UPDATE ocr_cache SET is_precise = 1 WHERE is_precise IS NULL OR is_precise = 0;
```

**注意：** 此操作也需要单独执行，不在项目代码中处理兼容逻辑。

## OCR测试

### 测试程序

**位置：** `tests/ocr/test_ocr.py`

**使用方法：**
```bash
python tests/ocr/test_ocr.py
```

### 测试内容

测试程序提供以下功能：

1. **多Provider对比测试**
   - 支持同时测试多个OCR Provider
   - 对比不同Provider的识别结果
   - 计算Provider之间的相似度矩阵

2. **识别精度对比**
   - 测试高精度和低精度OCR的识别效果
   - 对比不同精度级别的识别结果

3. **相似度分析**
   - 计算所有Provider识别结果之间的相似度
   - 生成相似度矩阵，便于分析识别一致性

4. **性能测试**
   - 统计每个Provider的识别耗时
   - 对比不同Provider的处理速度

### 输入文件设置

**默认路径：**
- `tests/test_images/award/chinese`

**支持的文件格式：**
- 图片格式：`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`
- 文档格式：`.pdf`

**输入方式：**
1. **默认目录模式**：使用默认测试路径中的所有图片
2. **指定目录模式**：手动指定包含测试图片的目录路径
3. **单张图片模式**：从默认路径随机选择一张图片，或指定单张图片路径

### 输出位置

**HTML报告：**
- 路径：`tests/reports/ocr对比报告.html`
- 内容：
  - 测试图片预览
  - 各Provider的识别结果
  - 相似度矩阵表格
  - 性能统计信息

**控制台输出：**
- 实时显示测试进度
- 每个Provider的识别结果摘要
- 测试统计信息

### 使用步骤

1. **运行程序**
   ```bash
   python tests/ocr/test_ocr.py
   ```

2. **选择要测试的Provider**
   - 程序会显示所有可用的OCR Provider
   - 支持多选（输入编号，用空格或逗号分隔）
   - 输入 `all` 或 `*` 选择全部Provider

3. **选择测试模式**
   - 选项1：使用默认测试路径中的所有图片
   - 选项2：指定图片目录路径
   - 选项3：单张图片测试（从默认路径随机选择）
   - 选项4：指定单张图片路径

4. **查看测试结果**
   - 控制台实时显示测试进度和结果
   - 测试完成后自动生成HTML报告
   - 在浏览器中打开HTML报告查看详细对比结果

### 新接口使用

测试程序使用新的OCR接口：

```python
# 创建OCR引擎
engine = OCREngine.from_config_loader(config_loader)

# 测试高精度OCR
text, cached = engine.get_text(
    image_path,
    use_cache=False,  # 测试时不使用缓存，确保真实测试
    is_precise=True   # 使用高精度OCR
)

# 测试低精度OCR
text, cached = engine.get_text(
    image_path,
    use_cache=False,
    is_precise=False  # 使用低精度OCR
)
```

**精度选择：**
- 测试程序会根据Provider配置中的`is_precise`标志自动选择精度
- 也可以手动指定`is_precise`参数进行测试

### 测试报告示例

HTML报告包含以下内容：

1. **测试概览**
   - 测试图片数量
   - 测试的Provider列表
   - 成功识别数量
   - 总体成功率

2. **每张图片的详细结果**
   - 图片预览
   - 各Provider的识别文本
   - 识别耗时
   - 字符数统计

3. **相似度矩阵**
   - Provider之间的相似度对比
   - 颜色编码（绿色=高相似度，红色=低相似度）

### 注意事项

1. **缓存设置**：测试时通常设置`use_cache=False`，确保每次都是真实识别
2. **环境变量**：确保相关API密钥已正确配置在环境变量中
3. **文件路径**：支持相对路径和绝对路径
4. **PDF处理**：PDF文件会自动转换为第一页图片进行测试
