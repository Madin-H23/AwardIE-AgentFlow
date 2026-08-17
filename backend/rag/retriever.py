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
        Document 列表（**低于 score_threshold 的结果已过滤——P2-23 根治**）
    """
    hits = retrieve_with_scores(config_loader, vectorstore, query,
                                filter=filter, top_k=top_k)
    return [d for d, _s in hits]


def retrieve_with_scores(
    config_loader,
    vectorstore,
    query: str,
    *,
    filter: Optional[Dict[str, Any]] = None,
    top_k: Optional[int] = None,
) -> List[tuple]:
    """
    带分数检索（P2-6/P2-23：review_agent 交叉校验统一入口）。

    与 retrieve() 走同一 MMR 配置与 score_threshold 过滤；
    返回 [(Document, score)]，score 越高越相关（Chroma 语义）。
    低于 threshold 的结果直接丢弃——**无关查询返回空**，不再强行关联（P2-23）。
    """
    cfg = resolve_retrieval_config(config_loader)
    search_kwargs: Dict[str, Any] = {"k": top_k or cfg["top_k"]}
    if cfg["search_type"] == "mmr":
        search_kwargs["fetch_k"] = max(search_kwargs["k"] * 2, 8)
        search_kwargs["lambda_mult"] = cfg["mmr_lambda"]
    if filter:
        search_kwargs["filter"] = filter
    retriever = vectorstore.as_retriever(
        search_type=cfg["search_type"], search_kwargs=search_kwargs)
    docs = retriever.invoke(query)
    # LangChain retriever 不回传 score；对命中集补一次底层相似度取分（成本可控）
    scored = []
    if docs:
        raw = vectorstore.similarity_search_with_score(query, k=len(docs) * 2)
        score_map = {d.page_content: s for d, s in raw}
        for d in docs:
            s = float(score_map.get(d.page_content, 0.0))
            if s >= cfg["score_threshold"]:
                scored.append((d, s))
    scored.sort(key=lambda x: -x[1])
    logger.debug("检索(带分) query=%r 命中 %d/%d 条（threshold=%.2f）",
                 query, len(scored), len(docs), cfg["score_threshold"])
    return scored


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
