## LLM 引擎与缓存

### 运行机制

本模块解决两个问题：屏蔽不同 LLM 供应商（OpenAI 兼容云端 API、本地 Ollama）的调用细节；为高频的抽取请求提供基于数据库的响应缓存，避免重复付费和等待。

整体调用链如下：

1. 抽取器（如奖状抽取器）构造 `messages` 列表和 `temperature`，调用 `LLMEngine.chat()`。
2. `chat()` 首先判断是否启用缓存（`use_cache` 且 `cache_db` 存在）。若启用，则基于所有 `role == "user"` 的 `content` 拼接后计算 SHA256 哈希，作为缓存键。
3. 用哈希查询 `ExtractCacheDB`。命中则直接返回响应文本和 `True`（缓存命中），不触发任何 Provider 调用。
4. 未命中则调用 `LLMProvider.chat()`（或 `OllamaLLMProvider.chat()`），后者负责实际 HTTP 请求、鉴权、超时、重试和熔断。
5. 拿到响应后，若缓存可用，将 `(哈希, 原始messages JSON, 响应文本)` 存入 SQLite 缓存表。
6. 返回响应文本和 `False`（未命中缓存）。

`LLMEngine` 不关心底层 Provider 是 API 还是 Ollama——所有 Provider 实现相同的 `chat(messages, temperature) -> str` 接口。Provider 的选择和构建由 `LLMEngine.from_config_loader()` 工厂完成，它读取 `settings.json` 中的 `llm.providers` 配置，根据 `provider_type` 和名称判断返回哪个 Provider 子类。

```mermaid
flowchart TD
    A[上层抽取器] -->|messages, temperature| B[LLMEngine.chat]
    B --> C{use_cache && cache_db?}
    C -->|否| D[Provider.chat]
    C -->|是| E[计算 prompt_hash]
    E --> F[ExtractCacheDB.get]
    F -->|命中| G[返回响应, True]
    F -->|未命中| D
    D --> H{是否启用缓存?}
    H -->|是| I[ExtractCacheDB.save]
    I --> J[返回响应, False]
    H -->|否| J
    D -.-> K[CircuitBreaker.guard]
    D -.

Sources: [backend/extract/llm/llm_engine.py](backend/extract/llm/llm_engine.py#L1) [backend/extract/llm/provider.py](backend/extract/llm/provider.py#L1) [backend/extract/llm/cache_db.py](backend/extract/llm/cache_db.py#L1) [backend/agent/llm_adapter.py](backend/agent/llm_adapter.py#L1) [backend/extract/prompts/default_prompt.json](backend/extract/prompts/default_prompt.json#L1)