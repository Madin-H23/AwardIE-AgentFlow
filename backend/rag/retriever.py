"""
检索器（Retriever）

封装向量库的检索逻辑，支持相似度检索与 MMR（Maximal Marginal Relevance）。

MMR 的作用
==========
竞赛名称相似时（如"挑战杯"多个相关赛事），纯相似度检索会返回高度重复的结果。
MMR 在"与查询相关"和"结果之间多样"之间取平衡（lambda 参数控制），
有效降低重复召回，这是 RAG 工程的常见优化点。

检索参数全部来自配置（rag.retrieval），不硬编码。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def resolve_retrieval_config(config_loader) -> Dict[str, Any]:
    """解析检索参数配置。"""
    config = config_loader.load_config()
    ret = config.get("rag", {}).get("retrieval", {})
    return {
        "top_k": ret.get("top_k", 4),
        "score_threshold": ret.get("score_threshold", 0.5),
        "search_type": ret.get("search_type", "mmr"),  # similarity | mmr
        "mmr_lambda": ret.get("mmr_lambda", 0.5),
    }


def build_retriever(config_loader, vectorstore, search_kwargs: Optional[Dict[str, Any]] = None):
    """
    把向量库转为 LangChain Retriever。

    Args:
        config_loader: ConfigLoader 实例
        vectorstore: Chroma 向量库
        search_kwargs: 覆盖默认检索参数（如按 metadata 过滤）

    Returns:
        VectorStoreRetriever 实例

    Example:
        >>> retriever = build_retriever(get_config(), vs)
        >>> docs = retriever.invoke("挑战杯是什么级别")
    """
    cfg = resolve_retrieval_config(config_loader)
    base_kwargs: Dict[str, Any] = {"k": cfg["top_k"]}
    if cfg["search_type"] == "mmr":
        base_kwargs["fetch_k"] = max(cfg["top_k"] * 2, 8)
        base_kwargs["lambda_mult"] = cfg["mmr_lambda"]
    if search_kwargs:
        base_kwargs.update(search_kwargs)

    return vectorstore.as_retriever(
        search_type=cfg["search_type"],
        search_kwargs=base_kwargs,
    )


def retrieve(
    config_loader,
    vectorstore,
    query: str,
    *,
    filter: Optional[Dict[str, Any]] = None,
    top_k: Optional[int] = None,
) -> List[Any]:
    """
    便捷检索：直接返回 Document 列表（含 page_content + metadata）。

    Args:
        config_loader: ConfigLoader 实例
        vectorstore: Chroma 向量库
        query: 查询文本
        filter: 元数据过滤（如 {"category": "A"} 只在 A 类检索）
        top_k: 覆盖默认 top_k

    Returns:
        Document 列表
    """
    search_kwargs: Dict[str, Any] = {}
    if filter:
        search_kwargs["filter"] = filter
    if top_k is not None:
        search_kwargs["k"] = top_k
    retriever = build_retriever(config_loader, vectorstore, search_kwargs=search_kwargs)
    docs = retriever.invoke(query)
    logger.debug("检索 query=%r 命中 %d 条", query, len(docs))
    return docs


def format_context(docs: List[Any]) -> str:
    """
    把检索结果格式化为 LLM 上下文字符串（带来源编号）。

    用于 RAG Prompt 拼接。
    """
    if not docs:
        return "（未检索到相关知识）"
    parts = []
    for i, d in enumerate(docs, 1):
        meta = d.metadata or {}
        name = meta.get("name", "")
        parts.append(f"[{i}] {d.page_content}")
    return "\n\n".join(parts)


__all__ = [
    "build_retriever",
    "retrieve",
    "format_context",
    "resolve_retrieval_config",
]
