"""P1-5 回归测试：工作流单例（get_default 双检锁/同实例/热更新失效）。"""
import sys
import threading
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.graph.workflow import MultiAgentWorkflow


class FakeWorkflow(MultiAgentWorkflow):
    """轻量替身：不触发 LangGraph 真实编译，验证单例机制本身。"""
    built = 0
    _default = None                       # 独立槽（避免继承基类槽的赋值陷阱）
    _default_lock = threading.Lock()

    def __init__(self):
        FakeWorkflow.built += 1

    @classmethod
    def from_config(cls, config_loader, **kwargs):
        return cls()


@pytest.fixture(autouse=True)
def reset_singleton():
    FakeWorkflow._default = None
    FakeWorkflow.built = 0
    yield
    FakeWorkflow._default = None


def test_get_default_returns_same_instance():
    FakeWorkflow.built = 0
    a = FakeWorkflow.get_default(None)
    b = FakeWorkflow.get_default(None)
    assert a is b
    assert FakeWorkflow.built == 1                     # 只编译一次


def test_concurrent_get_default_builds_once():
    import threading
    FakeWorkflow.built = 0
    results = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        results.append(FakeWorkflow.get_default(None))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(set(id(r) for r in results)) == 1       # 全同一实例
    assert FakeWorkflow.built == 1                     # 双检锁只编译一次


def test_reset_invalidates():
    a = FakeWorkflow.get_default(None)
    FakeWorkflow.reset_default()
    b = FakeWorkflow.get_default(None)
    assert a is not b                                  # 热更新后重建


def test_chat_uses_singleton():
    """源码防回退：chat.py 不得再直接 from_config（每请求重建痛点）。"""
    src = (PROJECT_ROOT / "app" / "routes" / "chat.py").read_text(encoding='utf-8')
    assert "MultiAgentWorkflow.from_config" not in src
    assert "MultiAgentWorkflow.get_default" in src
