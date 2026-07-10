"""
LLM Adapter —— 把现有 config/settings.json 的多 Provider 配置适配为 LangChain ChatModel

设计动机
========
项目原有的 LLMProvider（backend/extract/llm/provider.py）使用原生 requests.post 直接调用，
虽然能用，但无法获得 LangChain 生态的 Function Calling / bind_tools / 流式输出 / 结构化输出能力。

本模块不重写配置层，而是复用现有的 ConfigLoader + settings.json：
- 读取 llm.providers.{name} 的配置（base_url / api_key_env / model / temperature）
- 把完整 URL（含 /chat/completions）剥离为 OpenAI 兼容的 base_url
- 构造 langchain_openai.ChatOpenAI 实例

这样实现了"改一次配置，抽取与 Agent 共用同一个 Provider"的架构一致性。

覆盖的 Provider
==============
settings.json 中配置的 LLM Provider 均兼容 OpenAI 接口：
- deepseek  : https://api.deepseek.com/v1（OpenAI 兼容）
- zhipu     : https://open.bigmodel.cn/api/paas/v4（OpenAI 兼容，tools 字段支持）
- kimi      : https://api.moonshot.cn/v1（OpenAI 兼容）
- ollama    : http://localhost:11434/v1（Ollama 提供 OpenAI 兼容端点）

为何选择适配到 ChatOpenAI 而非包装原生 LLMProvider？
- 原生 LLMProvider 只返回纯文本，不支持 tool_calls 结构，无法支撑 Function Calling（Stage 2 必需）
- OpenAI 兼容协议已是国内主流 LLM 厂商事实标准，适配后可直接获得 bind_tools / 流式 / 结构化输出
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


# LangChain 为可选依赖：模块可被导入（用于配置校验/类型检查），
# 仅在真正构造 ChatModel 时才要求安装。
try:
    from langchain_openai import ChatOpenAI
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    _LANGCHAIN_AVAILABLE = False


# OpenAI 兼容路径后缀（需从完整 URL 中剥离，得到 ChatOpenAI 期望的 base_url）
_CHAT_COMPLETIONS_SUFFIXES = (
    "/chat/completions",
    "/chat/completions/",
)

# 每个 Provider 的额外默认参数（如智谱对部分参数更敏感，避免触发 400）
_PROVIDER_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "zhipu": {
        # 智谱 v4 接口对额外的 OpenAI 参数较宽容，保持默认即可
    },
    "deepseek": {
        # DeepSeek 不支持 output_parser 的某些字段，bind_tools 时注意
    },
    "kimi": {},
    "ollama": {
        # 本地 Ollama 无需鉴权
        "api_key": "ollama",  # ChatOpenAI 必填字段，Ollama 不校验内容
    },
}


def _strip_chat_completions(url: str) -> str:
    """
    将完整接口 URL 剥离为 OpenAI 兼容的 base_url。

    settings.json 中 base_url 形如：
        https://api.deepseek.com/v1/chat/completions
    ChatOpenAI 期望的 base_url 形如：
        https://api.deepseek.com/v1

    若 URL 不以 /chat/completions 结尾，则原样返回（已假定是合法 base_url）。
    """
    if not url:
        return url
    stripped = url.rstrip("/")
    for suffix in _CHAT_COMPLETIONS_SUFFIXES:
        if stripped.endswith(suffix):
            return stripped[: -len(suffix)].rstrip("/")
    return stripped


def _ensure_v1_path(url: str, provider_name: str) -> str:
    """
    确保 Ollama 等 base_url 包含 /v1（OpenAI 兼容端点）。

    settings.json 中 ollama 的 base_url_env 指向 http://localhost:11434，
    但 ChatOpenAI 需要 http://localhost:11434/v1。
    """
    parsed = urlparse(url)
    path = parsed.path or ""
    if path == "" or path == "/":
        # 根路径，补 /v1
        path = "/v1"
        return urlunparse(parsed._replace(path=path))
    return url


def resolve_provider_config(config_loader, provider_name: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """
    从 ConfigLoader 解析指定 LLM Provider 的配置（已替换环境变量、剥离 URL 后缀）。

    Args:
        config_loader: config.loader.ConfigLoader 实例
        provider_name: Provider 名称；None 则取 llm.default_provider

    Returns:
        (provider_name, resolved_config) 其中 resolved_config 含：
            base_url : str       OpenAI 兼容 base_url
            api_key  : str       从环境变量读取的 key（Ollama 用占位符）
            model    : str
            temperature : float

    Raises:
        ValueError: 配置缺失时（遵守"宁可失败也不要悄悄兜底"规范）
    """
    config = config_loader.load_config()
    if provider_name is None:
        provider_name = config_loader.get_default_provider("llm")

    providers = config.get("llm", {}).get("providers", {})
    raw = providers.get(provider_name)
    if not raw:
        available = list(providers.keys())
        raise ValueError(
            f"配置中未找到 LLM Provider: {provider_name}。"
            f"请在 config/settings.json 的 llm.providers 中配置。可用: {available}"
        )

    # base_url：优先 raw，兼容 base_url_env
    base_url = raw.get("base_url")
    base_url_env = raw.get("base_url_env")
    if not base_url and base_url_env:
        import os
        base_url = os.getenv(base_url_env)
    if not base_url:
        raise ValueError(
            f"LLM Provider '{provider_name}' 缺少 base_url / base_url_env。"
            f"请在 config/settings.json 中补充。"
        )

    # Ollama 需补 /v1；其余剥离 /chat/completions
    if provider_name == "ollama":
        base_url = _ensure_v1_path(base_url, provider_name)
    else:
        base_url = _strip_chat_completions(base_url)

    # api_key：Ollama 用占位符；其余从环境变量读取
    provider_defaults = _PROVIDER_DEFAULTS.get(provider_name, {})
    api_key_env = raw.get("api_key_env")
    api_key = provider_defaults.get("api_key")
    if not api_key:
        if not api_key_env:
            raise ValueError(
                f"LLM Provider '{provider_name}' 缺少 api_key_env。"
                f"请在 config/settings.json 中补充，如 \"api_key_env\": \"DEEPSEEK_API_KEY\"。"
            )
        import os
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(
                f"环境变量 {api_key_env} 未设置。请检查 .env / apikey/apikey.json。"
            )

    model = raw.get("model")
    if not model:
        raise ValueError(f"LLM Provider '{provider_name}' 缺少 model 字段。")

    temperature = raw.get("temperature", 0.1)

    resolved = {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "temperature": temperature,
    }
    logger.info("已解析 LLM Provider 配置: %s -> model=%s, base_url=%s", provider_name, model, base_url)
    return provider_name, resolved


def build_chat_model(
    config_loader,
    provider_name: Optional[str] = None,
    *,
    streaming: bool = False,
    extra_kwargs: Optional[Dict[str, Any]] = None,
):
    """
    从 ConfigLoader 构造一个 LangChain ChatOpenAI 实例（OpenAI 兼容）。

    构造出的实例天然支持：
    - bind_tools(...)  : Function Calling（Stage 2 Agent 必需）
    - stream(...)      : 流式输出（Stage 4 对话界面必需）
    - with_structured_output(...) : 结构化输出（Stage 3 审核 Agent 用）

    Args:
        config_loader: ConfigLoader 实例
        provider_name: 指定 Provider；None 用默认
        streaming: 是否启用流式
        extra_kwargs: 透传给 ChatOpenAI 的额外参数（如 timeout、max_retries）

    Returns:
        langchain_openai.ChatOpenAI 实例

    Raises:
        ImportError: langchain_openai 未安装

    Example:
        >>> from config.loader import get_config
        >>> from backend.agent.llm_adapter import build_chat_model
        >>> llm = build_chat_model(get_config())          # 用默认 provider
        >>> llm = build_chat_model(get_config(), "ollama") # 用本地 Ollama
        >>> llm.invoke([{"role": "user", "content": "你好"}])
    """
    if not _LANGCHAIN_AVAILABLE:
        raise ImportError(
            "langchain-openai 未安装，无法构造 ChatModel。请运行: "
            "pip install langchain langchain-openai langgraph"
        )
    name, cfg = resolve_provider_config(config_loader, provider_name)
    kwargs: Dict[str, Any] = {
        "model": cfg["model"],
        "base_url": cfg["base_url"],
        "api_key": cfg["api_key"],
        "temperature": cfg["temperature"],
        "streaming": streaming,
    }
    if extra_kwargs:
        kwargs.update(extra_kwargs)
    # provider 专属默认（如 ollama 的占位 api_key 已在 resolve 阶段处理）
    return ChatOpenAI(**kwargs)


__all__ = [
    "build_chat_model",
    "resolve_provider_config",
]
