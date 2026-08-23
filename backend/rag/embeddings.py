"""
Embedding Provider 封装

把 config/settings.json 的 rag.embedding 配置适配为 LangChain Embeddings。

设计动机
========
LangChain 的向量库（Chroma）需要一个 Embeddings 对象。
项目用智谱 embedding-3（OpenAI 兼容接口），因此用 langchain_openai.OpenAIEmbeddings 适配。

为什么不用原生 requests 自建？
- 与 LLM Adapter 同理：复用 LangChain 生态，Chroma 自动调用，无需手写向量化循环
- OpenAI 兼容协议，参数标准

复用现有配置：
- 读取 rag.embedding.{provider} 的 base_url / api_key_env / model / dimensions
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 惰性导入：模块可在 langchain 未装时被导入
try:
    from langchain_openai import OpenAIEmbeddings
    _EMBEDDINGS_AVAILABLE = True
except ImportError:
    OpenAIEmbeddings = None  # type: ignore[assignment,misc]
    _EMBEDDINGS_AVAILABLE = False


def _strip_embeddings_suffix(url: str) -> str:
    """
    剥离 /embeddings 后缀，得到 OpenAI 兼容 base_url。

    settings.json 中 embedding 的 base_url 形如：
        https://open.bigmodel.cn/api/paas/v4/embeddings
    OpenAIEmbeddings 期望：
        https://open.bigmodel.cn/api/paas/v4
    """
    if not url:
        return url
    stripped = url.rstrip("/")
    if stripped.endswith("/embeddings"):
        return stripped[: -len("/embeddings")].rstrip("/")
    return stripped


def resolve_embedding_config(config_loader, provider_name: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """
    从 ConfigLoader 解析 embedding provider 配置。

    Args:
        config_loader: ConfigLoader 实例
        provider_name: embedding provider 名；None 取 rag.default_embedding_provider

    Returns:
        (provider_name, config) 含 base_url / api_key / model / dimensions

    Raises:
        ValueError: 配置缺失时
    """
    config = config_loader.load_config()
    rag_cfg = config.get("rag", {})
    if not rag_cfg:
        raise ValueError("config 中缺少 rag 节点，请在 config/settings.json 中配置 rag")

    if provider_name is None:
        provider_name = rag_cfg.get("default_embedding_provider")
        if not provider_name:
            raise ValueError("rag.default_embedding_provider 未配置")

    embedding_cfg = rag_cfg.get("embedding", {})
    raw = embedding_cfg.get(provider_name)
    if not raw:
        available = list(embedding_cfg.keys())
        raise ValueError(
            f"未找到 embedding provider: {provider_name}。"
            f"请在 config/settings.json 的 rag.embedding 中配置。可用: {available}"
        )

    base_url = _strip_embeddings_suffix(raw.get("base_url", ""))
    if not base_url:
        raise ValueError(f"embedding provider '{provider_name}' 缺少 base_url")

    api_key_env = raw.get("api_key_env")
    if not api_key_env:
        raise ValueError(f"embedding provider '{provider_name}' 缺少 api_key_env")
    import os
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise ValueError(f"环境变量 {api_key_env} 未设置")

    model = raw.get("model")
    if not model:
        raise ValueError(f"embedding provider '{provider_name}' 缺少 model")

    dimensions = raw.get("dimensions", 1024)

    resolved = {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "dimensions": dimensions,
    }
    logger.info("已解析 embedding 配置: %s -> model=%s", provider_name, model)
    return provider_name, resolved


def build_embeddings(config_loader, provider_name: Optional[str] = None):
    """
    构造 LangChain Embeddings 实例。

    Args:
        config_loader: ConfigLoader 实例
        provider_name: embedding provider 名；None 用默认

    Returns:
        SimpleOpenAIEmbeddings 实例（实现 LangChain Embeddings 接口）

    注意：
        不使用 langchain_openai.OpenAIEmbeddings，因为它会对 query/document
        添加不对称的前缀（BGE 系列的 "Represent this sentence..." 指令），
        导致 bge-m3 这类无需前缀的模型检索质量严重下降（正确结果反而得分最低）。
        自建 SimpleOpenAIEmbeddings 直接调用 API，query 与 document 编码完全对称。

    Example:
        >>> from config.loader import get_config_loader
        >>> from backend.rag.embeddings import build_embeddings
        >>> emb = build_embeddings(get_config_loader())
        >>> vec = emb.embed_query("挑战杯竞赛")
    """
    # 只依赖 openai SDK（项目已安装），不强制 langchain_openai
    try:
        from openai import OpenAI  # noqa: F401
    except ImportError:
        raise ImportError(
            "openai 未安装，无法构造 Embeddings。请运行: pip install openai"
        )
    name, cfg = resolve_embedding_config(config_loader, provider_name)
    return SimpleOpenAIEmbeddings(
        api_key=cfg["api_key"],
        base_url=_strip_embeddings_suffix(cfg["base_url"]),
        model=cfg["model"],
        dimensions=cfg.get("dimensions"),
    )


class SimpleOpenAIEmbeddings:
    """
    轻量 Embeddings 实现（兼容 LangChain Embeddings 接口）。

    直接调用 OpenAI 兼容的 /embeddings 接口，不添加任何前缀，
    保证 query 与 document 编码对称，适用于 bge-m3 等模型。

    实现 LangChain Embeddings 协议的两个方法：
    - embed_query(text) -> List[float]      单条查询向量化
    - embed_documents(texts) -> List[List[float]]  批量文档向量化
    """

    def __init__(self, api_key: str, base_url: str, model: str, dimensions=None):
        self._api_key = api_key
        self._base_url = base_url
        self.model = model
        self.dimensions = dimensions
        self._client = None  # 惰性初始化

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            # P2-21：补 timeout（原无超时，embedding 慢响应会长时间阻塞 QA/审核节点）
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url, timeout=30)
        return self._client

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """批量向量化（内部统一入口，query/document 完全对称）。

        P2-21：指数退避重试 3 次（仅网络/5xx 类失败重试；4xx 参数错直接抛）。
        """
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
        import requests

        def _retryable(exc):
            return isinstance(exc, (requests.Timeout, requests.ConnectionError, requests.HTTPError))

        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4),
               retry=retry_if_exception(_retryable), reraise=True)
        def _call():
            client = self._get_client()
            kwargs = {"model": self.model, "input": texts}
            if self.dimensions:
                kwargs["dimensions"] = self.dimensions
            return client.embeddings.create(**kwargs)

        resp = _call()
        # 按 index 排序保证顺序正确
        sorted_data = sorted(resp.data, key=lambda x: x.index)
        return [d.embedding for d in sorted_data]

    def embed_query(self, text: str) -> List[float]:
        """单条查询向量化（LangChain Embeddings 协议）。"""
        return self._embed([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量文档向量化（LangChain Embeddings 协议）。"""
        # 硅基流动单次上限较高，但仍分批保证稳定（每批 64）
        results = []
        for i in range(0, len(texts), 64):
            results.extend(self._embed(texts[i:i + 64]))
        return results


__all__ = [
    "build_embeddings",
    "resolve_embedding_config",
]
