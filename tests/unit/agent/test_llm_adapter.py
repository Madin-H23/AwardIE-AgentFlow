"""
Stage 0 单元测试：LLM Adapter 配置解析

验证 llm_adapter 的配置解析逻辑（不依赖 langchain 真实安装）：
- _strip_chat_completions：剥离 /chat/completions 后缀
- _ensure_v1_path：Ollama 补 /v1
- resolve_provider_config：从 ConfigLoader 解析 provider 配置

这些是纯函数/纯配置逻辑，可在 langchain 未安装时独立验证。
build_chat_model 的端到端调用需要 langchain，放在 integration 测试。
"""
import os
import pytest
from unittest.mock import patch

from backend.agent.llm_adapter import (
    _strip_chat_completions,
    _ensure_v1_path,
    resolve_provider_config,
    resolve_provider_config as _resolve,
)
from config.loader import ConfigLoader


# ==================== _strip_chat_completions ====================

class TestStripChatCompletions:
    """剥离 /chat/completions 后缀"""

    def test_deepseek_url(self):
        url = "https://api.deepseek.com/v1/chat/completions"
        assert _strip_chat_completions(url) == "https://api.deepseek.com/v1"

    def test_zhipu_url(self):
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        assert _strip_chat_completions(url) == "https://open.bigmodel.cn/api/paas/v4"

    def test_kimi_url(self):
        url = "https://api.moonshot.cn/v1/chat/completions"
        assert _strip_chat_completions(url) == "https://api.moonshot.cn/v1"

    def test_already_base_url(self):
        # 已是 base_url（无后缀），原样返回
        url = "https://api.deepseek.com/v1"
        assert _strip_chat_completions(url) == "https://api.deepseek.com/v1"

    def test_trailing_slash(self):
        url = "https://api.deepseek.com/v1/chat/completions/"
        assert _strip_chat_completions(url) == "https://api.deepseek.com/v1"

    def test_empty(self):
        assert _strip_chat_completions("") == ""


# ==================== _ensure_v1_path ====================

class TestEnsureV1Path:
    """Ollama 补 /v1"""

    def test_root_path_gets_v1(self):
        assert _ensure_v1_path("http://localhost:11434", "ollama") == "http://localhost:11434/v1"

    def test_root_with_slash(self):
        assert _ensure_v1_path("http://localhost:11434/", "ollama") == "http://localhost:11434/v1"

    def test_already_has_v1(self):
        # 已含 /v1，不变
        assert _ensure_v1_path("http://localhost:11434/v1", "ollama") == "http://localhost:11434/v1"


# ==================== resolve_provider_config ====================

@pytest.fixture
def config_loader():
    """真实 ConfigLoader（读项目 config/settings.json）。"""
    return ConfigLoader()


class TestResolveProviderConfig:
    """从 ConfigLoader 解析 provider 配置"""

    def test_default_provider_deepseek(self, config_loader):
        """默认 provider 应为 deepseek（settings.json 配置）"""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-fake"}):
            name, cfg = resolve_provider_config(config_loader)
            assert name == "deepseek"
            assert cfg["model"] == "deepseek-v4-flash"
            assert cfg["base_url"] == "https://api.deepseek.com/v1"
            assert cfg["api_key"] == "sk-test-fake"

    def test_zhipu_provider(self, config_loader):
        with patch.dict(os.environ, {"ZHIPUAI_API_KEY": "fake-zhipu"}):
            name, cfg = resolve_provider_config(config_loader, "zhipu")
            assert name == "zhipu"
            assert cfg["base_url"] == "https://open.bigmodel.cn/api/paas/v4"
            assert cfg["model"] == "glm-4.7"

    def test_kimi_provider(self, config_loader):
        with patch.dict(os.environ, {"KIMI_API_KEY": "fake-kimi"}):
            name, cfg = resolve_provider_config(config_loader, "kimi")
            assert name == "kimi"
            assert cfg["base_url"] == "https://api.moonshot.cn/v1"
            assert cfg["model"] == "kimi-latest"

    def test_ollama_gets_v1_suffix(self, config_loader):
        """Ollama base_url 应补 /v1"""
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://localhost:11434"}):
            name, cfg = resolve_provider_config(config_loader, "ollama")
            assert name == "ollama"
            assert cfg["base_url"] == "http://localhost:11434/v1"
            # Ollama 用占位 api_key
            assert cfg["api_key"] == "ollama"

    def test_missing_provider_raises(self, config_loader):
        """不存在的 provider 应抛清晰异常（遵守"宁可失败"规范）"""
        with pytest.raises(ValueError, match="未找到 LLM Provider"):
            resolve_provider_config(config_loader, "nonexistent_provider")

    def test_missing_api_key_raises(self, config_loader):
        """api_key_env 配置但环境变量未设置，应抛异常"""
        with patch.dict(os.environ, {}, clear=True):
            # 清空后 DEEPSEEK_API_KEY 不存在
            os.environ.pop("DEEPSEEK_API_KEY", None)
            with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
                resolve_provider_config(config_loader, "deepseek")


# ==================== RAG / Agent 配置节点存在性 ====================

class TestNewConfigNodes:
    """验证新增的 rag / agent 配置节点可被正确读取"""

    def test_rag_node_exists(self, config_loader):
        config = config_loader.load_config()
        assert "rag" in config
        assert config["rag"]["enabled"] is True
        assert config["rag"]["default_embedding_provider"] == "siliconflow"
        assert config["rag"]["vectorstore"]["persist_path"] == "database/chroma"

    def test_agent_node_exists(self, config_loader):
        config = config_loader.load_config()
        assert "agent" in config
        assert config["agent"]["enabled"] is True
        assert config["agent"]["default_llm_provider"] == "deepseek"
        # 各子 agent 的 provider 配置
        for sub in ["supervisor", "extraction_agent", "review_agent", "qa_agent"]:
            assert sub in config["agent"], f"缺少 agent.{sub} 配置"
