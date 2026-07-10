# LLM模块测试用例

## 概述

本文档描述了LLM模块的测试用例，包括Provider初始化、API调用、缓存机制等功能的测试。

## 测试程序

**位置：** `tests/extract/unit/llm_unit_test.py`

**使用方法：**
```bash
python tests/extract/unit/llm_unit_test.py
```

## 测试内容

测试程序提供以下功能：

1. **Engine初始化测试**
   - 测试从配置创建LLMEngine
   - 验证Engine和Provider初始化

2. **API Key验证测试**
   - 测试API Key未设置时的错误处理
   - 验证异常类型和错误信息

3. **LLM调用测试（带缓存）**
   - 测试基本的LLM API调用
   - 验证响应格式和内容
   - 验证缓存命中状态

4. **缓存机制测试**
   - 缓存保存和获取
   - 缓存覆盖
   - 缓存未命中
   - 通过提示词哈希查询
   - 缓存统计信息
   - 缓存删除

5. **缓存集成测试**
   - 测试LLMEngine的缓存集成
   - 验证缓存自动使用

## 测试用例列表

### 测试用例1：Engine初始化测试

**测试目标：** 验证LLMEngine可以从配置正确初始化

**测试步骤：**
1. 使用ConfigLoader创建LLMEngine实例
2. 验证Engine初始化成功
3. 验证Provider已正确创建

**预期结果：**
- Engine初始化成功
- Provider已正确创建

**测试代码：**
```python
from backend.extract.llm import LLMEngine
from config.loader import get_config

config_loader = get_config()
engine = LLMEngine.from_config_loader(config_loader)
assert engine is not None
assert engine.provider is not None
```

---

### 测试用例2：API Key验证测试

**测试目标：** 验证API Key未设置时正确抛出异常

**测试步骤：**
1. 使用不存在的环境变量创建Provider
2. 尝试调用LLM API
3. 验证抛出ValueError或LLMError异常

**预期结果：**
- 抛出ValueError或LLMError异常
- 异常信息包含"未设置"或环境变量名

**测试代码：**
```python
test_config = {
    "url": "https://test.example.com/api",
    "api_key_env": "NONEXISTENT_API_KEY",
    "model": "test-model"
}
provider = LLMProvider.from_config(test_config)
try:
    provider.chat([{"role": "user", "content": "test"}])
    assert False, "应该抛出异常"
except (ValueError, LLMError) as e:
    assert "未设置" in str(e) or "NONEXISTENT_API_KEY" in str(e)
```

---

### 测试用例3：LLM调用测试（带缓存）

**测试目标：** 验证LLM API调用功能和缓存机制

**前置条件：**
- 已配置有效的LLM Provider（API Key已设置）
- 网络连接正常

**测试步骤：**
1. 准备测试消息
2. 调用Engine.chat()方法（不使用缓存）
3. 验证返回响应非空
4. 验证缓存命中状态

**预期结果：**
- LLM调用成功
- 返回非空响应文本
- 缓存命中状态正确（第一次为False）

**测试代码：**
```python
messages = [{"role": "user", "content": "请用一句话回答：1+1等于几？"}]
response, cached = engine.chat(messages, temperature=0.1, use_cache=False)
assert response and len(response) > 0
assert cached == False  # 不使用缓存时应该为False
```

**注意事项：**
- 此测试需要真实的API配置，如果未配置将跳过
- 测试可能消耗API配额

---

### 测试用例4：缓存保存和获取测试

**测试目标：** 验证缓存的基本保存和获取功能

**测试步骤：**
1. 准备测试数据（提示词哈希、提示词、响应）
2. 调用cache.save()保存缓存
3. 调用cache.get()获取缓存
4. 验证获取的响应与保存的响应一致

**预期结果：**
- 缓存保存成功
- 缓存获取成功
- 获取的响应与保存的响应完全一致

**测试代码：**
```python
prompt_hash = hashlib.sha256("test prompt".encode()).hexdigest()
llm_prompt = "测试提示词"
llm_response = "测试响应"

# 保存
cache.save(prompt_hash, llm_prompt, llm_response)

# 获取
cached_response = cache.get(prompt_hash)
assert cached_response == llm_response
```

---

### 测试用例5：缓存覆盖测试

**测试目标：** 验证相同提示词哈希的覆盖行为

**测试步骤：**
1. 使用相同的提示词哈希保存第一条数据
2. 使用相同的提示词哈希保存第二条数据（应该覆盖第一条）
3. 获取缓存
4. 验证获取的是第二条数据

**预期结果：**
- 第二次保存覆盖第一次保存的数据
- 获取到的响应是第二次保存的响应

**测试代码：**
```python
prompt_hash = hashlib.sha256("test prompt".encode()).hexdigest()

# 第一次保存
cache.save(prompt_hash, "提示词1", "响应1")

# 第二次保存（应该覆盖）
cache.save(prompt_hash, "提示词2", "响应2")

# 获取缓存
cached_response = cache.get(prompt_hash)
assert cached_response == "响应2"
```

---

### 测试用例6：缓存未命中测试

**测试目标：** 验证缓存未命中时的行为

**测试步骤：**
1. 查询不存在的提示词哈希
2. 验证返回None

**预期结果：**
- 缓存未命中时返回None

**测试代码：**
```python
nonexistent_hash = hashlib.sha256("nonexistent prompt".encode()).hexdigest()
cached_response = cache.get(nonexistent_hash)
assert cached_response is None
```

---

### 测试用例7：缓存统计信息测试

**测试目标：** 验证缓存统计信息功能

**测试步骤：**
1. 保存多个测试缓存
2. 调用cache.get_stats()获取统计信息
3. 验证统计信息正确

**预期结果：**
- 统计信息包含总记录数
- 总记录数等于保存的缓存数量

**测试代码：**
```python
# 保存一些测试数据
for i in range(5):
    prompt_hash = hashlib.sha256(f"test prompt {i}".encode()).hexdigest()
    cache.save(prompt_hash, f"提示词{i}", f"响应{i}")

# 获取统计信息
stats = cache.get_stats()
assert stats["total"] >= 5
```

---

### 测试用例8：缓存删除测试

**测试目标：** 验证缓存删除功能

**测试步骤：**
1. 保存一个测试缓存
2. 调用cache.delete()删除缓存
3. 验证删除成功（返回删除数量）
4. 验证缓存已被删除（查询返回None）

**预期结果：**
- 删除操作返回删除数量（1）
- 删除后查询返回None

**测试代码：**
```python
prompt_hash = hashlib.sha256("test delete prompt".encode()).hexdigest()

# 保存缓存
cache.save(prompt_hash, "测试提示词", "测试响应")

# 删除缓存
deleted_count = cache.delete(prompt_hash)
assert deleted_count == 1

# 验证删除
cached_response = cache.get(prompt_hash)
assert cached_response is None
```

---

### 测试用例10：缓存集成测试

**测试目标：** 验证LLMEngine的缓存集成功能

**前置条件：**
- 已配置有效的LLM Provider（API Key已设置）
- 网络连接正常
- 缓存已启用

**测试步骤：**
1. 第一次调用（不使用缓存，确保是真实调用）
2. 第二次调用（使用缓存）
3. 验证两次响应一致
4. 验证第二次缓存命中

**预期结果：**
- 两次调用响应一致
- 第二次调用缓存命中（cached=True）

**测试代码：**
```python
messages = [{"role": "user", "content": "测试缓存：请回答1+1等于几？"}]

# 第一次调用（不使用缓存）
response1, cached1 = engine.chat(messages, temperature=0.1, use_cache=False)
assert cached1 == False

# 第二次调用（使用缓存）
response2, cached2 = engine.chat(messages, temperature=0.1, use_cache=True)
assert response1 == response2
assert cached2 == True  # 应该命中缓存
```

**注意事项：**
- 此测试需要真实的API配置，如果未配置将跳过
- 测试可能消耗API配额（仅第一次调用）
- 如果缓存未启用，第二次调用也会是真实调用

---

## 测试环境要求

### 必需配置

1. **LLM Provider配置**
   - 在 `config/settings.json` 中配置至少一个LLM Provider
   - 设置相应的API Key环境变量

2. **Python依赖**
   - `requests`：用于HTTP请求
   - `sqlite3`：用于缓存数据库（Python标准库）

3. **可选依赖**
   - `ollama`：如果测试Ollama Provider需要安装

### 环境变量

根据配置的Provider设置相应的环境变量：

- `ZHIPUAI_API_KEY`：智谱AI API Key
- `KIMI_API_KEY`：Kimi API Key
- `DEEPSEEK_API_KEY`：DeepSeek API Key
- `OLLAMA_BASE_URL`：Ollama服务地址（可选）

## 测试输出

### 控制台输出

测试程序会在控制台输出：
- 每个测试的执行状态（✓ 通过、✗ 失败、! 错误）
- 测试执行时间
- 测试摘要（总数、通过数、失败数、错误数）

### 测试结果

测试结果包含以下信息：
- 测试用例编号和名称
- 测试状态（passed/failed/error）
- 预期结果和实际结果
- 执行时间
- 错误信息（如果有）

## 注意事项

1. **API配额消耗**
   - 测试用例3和10会进行真实的API调用，会消耗API配额
   - 建议在测试环境中使用测试API Key

2. **网络依赖**
   - 部分测试需要网络连接
   - 如果网络不稳定，可能导致测试失败

3. **测试数据隔离**
   - 测试使用临时数据库文件，不会影响生产数据
   - 测试结束后会自动清理临时文件

4. **跳过测试**
   - 如果未配置有效的LLM Provider，相关测试会被跳过
   - 跳过的测试状态为"error"，但不影响其他测试

5. **Ollama测试**
   - 如果需要测试Ollama Provider，需要：
     - 安装 `ollama` 库：`pip install ollama`
     - 启动Ollama服务
     - 配置相应的模型

## 扩展测试

### 添加新的测试用例

1. 在 `LLMTester` 类中添加新的测试方法
2. 方法名以 `test_` 开头
3. 返回 `TestResult` 对象
4. 在 `run_all_tests()` 方法中注册新测试

示例：
```python
def test_custom_feature(self) -> TestResult:
    """测试用例N：自定义功能测试"""
    test_name = "自定义功能测试"
    start_time = time.time()
    
    try:
        # 测试逻辑
        # ...
        
        status = "passed"
        message = "测试通过"
    except Exception as e:
        status = "error"
        message = f"测试失败: {e}"
    
    duration = time.time() - start_time
    return TestResult(
        test_case="test_N",
        test_name=test_name,
        status=status,
        expected="预期结果",
        actual=message,
        message=message,
        duration=duration
    )
```
