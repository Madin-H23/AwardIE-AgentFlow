"""ConfigLoader API key 注入回归（pytest 函数式，T31-T34 批次3 转换）。"""
import json
import os
from pathlib import Path

import pytest

from config.loader import ConfigLoader


@pytest.fixture()
def loader_with_keys(tmp_path, monkeypatch):
    test_dir = tmp_path
    config_dir = test_dir / "config"
    apikey_dir = test_dir / "apikey"
    config_dir.mkdir()
    apikey_dir.mkdir()

    (config_dir / "settings.json").write_text(json.dumps({
        "ocr": {"providers": {"zhipu": {"api_key_env": "ZHIPUAI_API_KEY"}}},
        "llm": {"providers": {"deepseek": {"api_key_env": "DEEPSEEK_API_KEY"}}},
    }), encoding="utf-8")
    (apikey_dir / "apikey.json").write_text(json.dumps({
        "ocr": {"zhipu": "test_zhipu_key"},
        "llm": {"deepseek": "test_deepseek_key"},
    }), encoding="utf-8")

    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    return ConfigLoader(project_root=test_dir)


def test_load_api_keys(loader_with_keys, monkeypatch):
    """加载配置后 API key 应注入环境变量"""
    loader_with_keys.load_config()
    assert os.environ.get("ZHIPUAI_API_KEY") == "test_zhipu_key"
    assert os.environ.get("DEEPSEEK_API_KEY") == "test_deepseek_key"
