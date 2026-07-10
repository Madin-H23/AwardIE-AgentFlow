# LLM模块设计

## 概述

LLM（大语言模型）模块负责调用大语言模型进行结构化信息抽取，是文档信息抽取流程的核心步骤。本模块采用简洁的设计，只提供两个核心接口：初始化和调用。所有Provider通过配置自动注册和选择，缓存机制自动集成。

## 模块功能

### 1. 简洁的接口设计

**对外接口只有两个：**
- `from_config_loader()`: 初始化引擎
- `chat()`: 调用LLM（自动使用缓存）

### 2. 自动Provider选择

所有Provider都在配置文件中定义，系统根据 `llm.default_provider` 自动选择：
- 支持API类型Provider（如zhipu、kimi、deepseek）
- 支持本地Ollama Provider
- 无需手动注册，配置即注册

### 3. 自动缓存集成

缓存机制完全透明，无需手动管理：
- 自动计算缓存键（基于消息内容）
- 自动查询和保存缓存
- 返回缓存命中状态

## 对外接口

### LLMEngine 类

**初始化（推荐方式）：**

```python
from backend.extract.llm import LLMEngine
from config.loader import get_config

config_loader = get_config()
engine = LLMEngine.from_config_loader(config_loader)
```

**初始化时自动：**
- 从 `config/settings.json` 读取LLM配置
- 根据 `llm.default_provider` 选择Provider
- 自动创建缓存数据库（如果配置启用）

**主要方法：**

#### `chat(messages, temperature=0.7, use_cache=True) -> Tuple[str, bool]`

调用LLM，自动使用缓存。

**参数：**
- `messages` (List[Dict[str, str]]): 消息列表，格式为 `[{"role": "user", "content": "..."}]`
- `temperature` (float): 温度参数，控制输出的随机性（默认0.7）
- `use_cache` (bool): 是否使用缓存（默认True）

**返回：**
- `Tuple[str, bool]`: (LLM响应文本, 是否命中缓存)

**执行流程：**

```
1. 检查是否使用缓存
   ├─> 如果不使用缓存 (use_cache=False) 或缓存未启用
   │   └─> 直接调用LLM，返回 (响应, False)
   │
   └─> 如果使用缓存 (use_cache=True)
       ├─> 计算提示词哈希（基于完整的messages）
       ├─> 查询缓存（使用prompt_hash作为键）
       │
       ├─> 如果缓存命中
       │   └─> 返回 (缓存响应, True)
       │
       └─> 如果缓存未命中
           ├─> 调用LLM
           ├─> 保存到缓存（prompt_hash, llm_prompt, llm_response）
           └─> 返回 (LLM响应, False)
```

**缓存键说明：**
- **prompt_hash**：基于所有user消息的content计算SHA256哈希，作为缓存主键
- 相同提示词文本 → 相同prompt_hash → 命中缓存

**示例：**

```python
# 基本调用（自动使用缓存）
messages = [{"role": "user", "content": "请提取以下文本中的竞赛名称：蓝桥杯全国软件和信息技术专业人才大赛"}]
response, cached = engine.chat(messages, temperature=0.1)
print(f"响应: {response}")
print(f"缓存命中: {cached}")

# 不使用缓存
response, cached = engine.chat(messages, use_cache=False)
```

#### `clear_cache(prompt_hash=None) -> int`

清理缓存。

**参数：**
- `prompt_hash` (Optional[str]): 提示词哈希，如果为None则清理所有缓存

**返回：**
- `int`: 删除的记录数

#### `get_cache_stats() -> Dict[str, Any]`

获取缓存统计信息。

**返回：**
- `Dict[str, Any]`: 包含total、oldest、newest等统计信息

## 数据库表设计

### extract_cache 表

**表结构：**

```sql
CREATE TABLE extract_cache (
    prompt_hash TEXT PRIMARY KEY,         -- 提示词哈希（主键）
    llm_prompt TEXT NOT NULL,             -- LLM提示词（messages的JSON字符串）
    llm_response TEXT NOT NULL,           -- LLM响应文本
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 最后访问时间
);
```

**索引：**

```sql
CREATE INDEX idx_extract_cache_created_at ON extract_cache(created_at);
CREATE INDEX idx_extract_cache_accessed_at ON extract_cache(accessed_at);
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `prompt_hash` | TEXT | 提示词哈希（主键），基于user消息content的SHA256哈希 |
| `llm_prompt` | TEXT | LLM提示词（完整的messages JSON字符串） |
| `llm_response` | TEXT | LLM响应文本 |
| `created_at` | TIMESTAMP | 创建时间 |
| `accessed_at` | TIMESTAMP | 最后访问时间，每次查询时自动更新 |

**数据迁移：**

如果需要迁移现有数据库，执行以下命令：

```bash
# 使用 Python 脚本（推荐）
python database/migrations/simplify_extract_cache.py

# 或使用 SQL 文件
sqlite3 database/extract_cache.db < database/migrations/simplify_extract_cache.sql
```

**注意：** 迁移会删除所有现有缓存数据，请根据需要先备份。

## 使用示例

### 示例1：基本使用（推荐方式）

```python
from backend.extract.llm import LLMEngine
from config.loader import get_config

# 初始化引擎（自动从配置读取）
config_loader = get_config()
engine = LLMEngine.from_config_loader(config_loader)

# 调用LLM（自动使用缓存）
messages = [{"role": "user", "content": "请提取以下文本中的竞赛名称：蓝桥杯全国软件和信息技术专业人才大赛"}]
response, cached = engine.chat(messages, temperature=0.1)

print(f"响应: {response}")
print(f"缓存命中: {cached}")
```

**说明：**
- 使用 `from_config_loader()` 是最简单的方式
- 无需手动读取配置文件或构建配置字典
- 自动使用 `config/settings.json` 中的 `llm.default_provider`
- 缓存自动启用（如果配置中启用）

### 示例2：缓存管理

```python
# 查看缓存统计
stats = engine.get_cache_stats()
print(f"缓存总数: {stats['total']}")
print(f"最早缓存: {stats['oldest']}")
print(f"最新缓存: {stats['newest']}")

# 清理指定缓存（需要prompt_hash）
prompt_hash = "abc123..."
deleted = engine.clear_cache(prompt_hash)
print(f"删除了 {deleted} 条缓存")

# 清空所有缓存
deleted = engine.clear_cache()
print(f"清空了 {deleted} 条缓存")
```

### 示例3：不使用缓存

```python
# 强制不使用缓存（每次都是真实调用）
response, cached = engine.chat(messages, use_cache=False)
# cached 始终为 False
```

### 示例4：Ollama本地模型

如果配置文件中 `llm.default_provider` 设置为 `ollama`，系统会自动使用Ollama Provider：

```python
# 配置文件中设置：
# {
#   "llm": {
#     "default_provider": "ollama",
#     "providers": {
#       "ollama": {
#         "type": "local",
#         "model": "cnshenyang/qwen3-nothink:30b",
#         "base_url": "http://127.0.0.1:11434",
#         "temperature": 0,
#         "format": "json"
#       }
#     }
#   }
# }

# 使用方式完全相同
engine = LLMEngine.from_config_loader(config_loader)
response, cached = engine.chat(messages)
```

## 配置说明

### LLM配置

在 `config/settings.json` 中配置：

```json
{
  "llm": {
    "default_provider": "zhipu",
    "providers": {
      "zhipu": {
        "type": "api",
        "api_key_env": "ZHIPUAI_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-4-flash",
        "temperature": 0.1
      },
      "kimi": {
        "type": "api",
        "api_key_env": "KIMI_API_KEY",
        "base_url": "https://api.moonshot.cn/v1/chat/completions",
        "model": "kimi-latest",
        "temperature": 0.3
      },
      "ollama": {
        "type": "local",
        "model": "cnshenyang/qwen3-nothink:30b",
        "base_url": "http://127.0.0.1:11434",
        "temperature": 0,
        "format": "json"
      }
    },
    "cache": {
      "enabled": true,
      "db_path": "database/extract_cache.db"
    }
  }
}
```

**配置字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `default_provider` | string | 默认使用的Provider名称 |
| `providers` | object | Provider配置字典 |
| `providers.{name}.type` | string | Provider类型："api" 或 "local" |
| `providers.{name}.api_key_env` | string | API Key环境变量名（API类型必需） |
| `providers.{name}.base_url` | string | API地址（API类型必需） |
| `providers.{name}.model` | string | 模型名称（必需） |
| `providers.{name}.temperature` | number | 温度参数（可选） |
| `cache.enabled` | boolean | 是否启用缓存（默认true） |
| `cache.db_path` | string | 缓存数据库路径 |

## 注意事项

1. **API Key管理**：所有API Key必须通过环境变量配置，不要硬编码在代码中
2. **缓存键计算**：缓存键基于消息内容的哈希，相同消息会产生相同缓存键
3. **错误处理**：LLM调用可能因网络、API限制等原因失败，会抛出 `LLMError` 异常
4. **Ollama依赖**：使用Ollama Provider需要安装 `ollama` 库：`pip install ollama`
5. **缓存清理**：定期清理旧缓存和未访问缓存，避免数据库过大

## 模块结构

```
backend/extract/llm/
├── __init__.py          # 模块入口，导出LLMEngine
├── llm_engine.py        # LLM引擎（主接口）
├── provider.py          # LLM Provider实现
└── cache_db.py          # 缓存数据库
```

## 设计原则

1. **简洁性**：只提供必要的接口，隐藏实现细节
2. **自动化**：配置驱动，自动选择Provider和启用缓存
3. **透明性**：缓存机制对用户完全透明
4. **一致性**：与OCR模块的设计保持一致
