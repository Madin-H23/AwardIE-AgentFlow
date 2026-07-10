"""
RAG 知识库初始化脚本

把竞赛等级分类表入库到 Chroma 向量库，供 RAG 问答使用。

用法：
    python tools/init_rag_vectorstore.py

前置条件：
    1. 智谱 embedding API 可用（ZHIPUAI_API_KEY 已配置且有余额）
    2. 已安装依赖：pip install langchain-chroma chromadb

充值智谱后，直接运行此脚本即可完成入库。
"""
import sys
import logging
from pathlib import Path

# 添加项目根到路径
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    from config.loader import get_config
    from backend.rag.embeddings import build_embeddings
    from backend.rag.vectorstore import build_vectorstore
    from backend.rag.indexer import index_competition_levels, get_collection_stats

    config_loader = get_config()

    logger.info("=== RAG 知识库初始化 ===")
    logger.info("1. 构造 embedding 服务...")
    emb = build_embeddings(config_loader)

    logger.info("2. 构造/加载向量库...")
    vs = build_vectorstore(config_loader, emb)

    logger.info("3. 解析并入库竞赛等级分类表（分批，每批 32 条）...")
    try:
        count = index_competition_levels(config_loader, vs)
        logger.info("✓ 入库成功：%d 条竞赛条目", count)
    except Exception as e:
        logger.error("✗ 入库失败：%s", e)
        logger.error("如果是余额不足(429)，请充值智谱后重试。")
        sys.exit(1)

    logger.info("4. 验证入库结果...")
    stats = get_collection_stats(vs)
    logger.info("✓ 向量库统计：%s", stats)

    # 简单检索验证
    logger.info("5. 检索验证...")
    try:
        results = vs.similarity_search("挑战杯", k=2)
        for i, doc in enumerate(results, 1):
            logger.info("  [%d] %s", i, doc.page_content[:80])
        logger.info("✓ RAG 知识库就绪，可进行问答")
    except Exception as e:
        logger.error("检索验证失败：%s", e)


if __name__ == "__main__":
    main()
