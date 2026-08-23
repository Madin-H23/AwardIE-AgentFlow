"""
Agent integration 测试 conftest

这些测试需要真实 API 调用（DeepSeek/智谱/硅基流动），通过环境变量控制是否运行：
- 默认跳过（避免 CI 无 key 时失败）
- 设置 RUN_AGENT_INTEGRATION=1 时运行

用法：
    RUN_AGENT_INTEGRATION=1 python -m pytest tests/integration/agent/ -v
"""
import os
import pytest
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# 跳过条件：未显式开启则跳过
SKIP_REASON = (
    "Agent integration 测试需要真实 API。"
    "设置环境变量 RUN_AGENT_INTEGRATION=1 启用。"
)
RUN_INTEGRATION = os.getenv("RUN_AGENT_INTEGRATION") == "1"

skip_if_no_integration = pytest.mark.skipif(
    not RUN_INTEGRATION, reason=SKIP_REASON
)


@pytest.fixture(scope="session")
def config_loader():
    from config.loader import get_config_loader
    return get_config_loader()


@pytest.fixture(scope="session")
def vectorstore(config_loader):
    """加载已入库的向量库（需先运行 tools/init_rag_vectorstore.py）。"""
    from backend.rag.embeddings import build_embeddings
    from backend.rag.vectorstore import build_vectorstore
    emb = build_embeddings(config_loader)
    return build_vectorstore(config_loader, emb)
