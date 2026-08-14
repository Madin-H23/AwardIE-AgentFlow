"""
Chroma 向量库管理

基于 langchain_chroma 提供向量库的构建、加载、检索能力。

持久化路径由配置驱动：config/settings.json -> rag.vectorstore.persist_path
默认持久化到 database/chroma/，与项目其他 SQLite 库同级。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 惰性导入
try:
    import langchain_chroma  # noqa: F401
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False


def resolve_vectorstore_config(config_loader) -> Dict[str, Any]:
    """
    解析向量库配置，返回绝对持久化路径与集合列表。

    Returns:
        {
            "persist_path": <绝对路径 str>,
            "default_collection": str,
            "collections": List[str],
        }
    """
    config = config_loader.load_config()
    vs_cfg = config.get("rag", {}).get("vectorstore", {})
    persist_path = vs_cfg.get("persist_path", "database/chroma")
    # 转绝对路径（相对项目根）
    p = Path(persist_path)
    if not p.is_absolute():
        p = (config_loader.project_root / p).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return {
        "persist_path": str(p),
        "default_collection": vs_cfg.get("default_collection", "competition_rules"),
        "collections": vs_cfg.get("collections", ["competition_rules"]),
    }


def build_vectorstore(
    config_loader,
    embeddings,
    collection_name: Optional[str] = None,
):
    """
    构造（或加载已有的）Chroma 向量库。

    若指定 collection 已存在，则加载已有数据；否则首次写入时创建。

    Args:
        config_loader: ConfigLoader 实例
        embeddings: LangChain Embeddings 实例（由 build_embeddings 构造）
        collection_name: 集合名；None 用默认（competition_rules）

    Returns:
        langchain_chroma.Chroma 实例

    Raises:
        ImportError: langchain-chroma 未安装

    Example:
        >>> from config.loader import get_config
        >>> from backend.rag.embeddings import build_embeddings
        >>> from backend.rag.vectorstore import build_vectorstore
        >>> emb = build_embeddings(get_config())
        >>> vs = build_vectorstore(get_config(), emb)
    """
    if not _CHROMA_AVAILABLE:
        raise ImportError(
            "langchain-chroma 未安装。请运行: pip install langchain-chroma chromadb"
        )
    from langchain_chroma import Chroma

    vs_cfg = resolve_vectorstore_config(config_loader)
    if collection_name is None:
        collection_name = vs_cfg["default_collection"]

    logger.info("加载 Chroma 向量库: collection=%s, path=%s", collection_name, vs_cfg["persist_path"])
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=vs_cfg["persist_path"],
    )


def list_collections(config_loader) -> List[str]:
    """返回配置中声明的所有集合名。"""
    return resolve_vectorstore_config(config_loader)["collections"]


def build_default_vectorstore(config_loader):
    """
    按默认配置惰性构建向量库（embedding + Chroma）。

    供 Agent 节点（QA/审核）在未显式传入 vectorstore 时兜底使用。
    任何失败返回 None，由调用方降级处理，绝不抛异常。
    """
    try:
        from backend.rag.embeddings import build_embeddings
        emb = build_embeddings(config_loader)
        return build_vectorstore(config_loader, emb)
    except Exception as e:
        logger.warning("构建默认向量库失败，跳过 RAG: %s", e)
        return None


__all__ = [
    "build_vectorstore",
    "resolve_vectorstore_config",
    "list_collections",
    "build_default_vectorstore",
]
