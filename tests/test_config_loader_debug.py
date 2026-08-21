"""ConfigLoader 配置结构冒烟（pytest 函数式，T31-T34 批次3 转换）。"""
from config.loader import ConfigLoader


def test_load_config():
    loader = ConfigLoader()
    config = loader.load_config()

    assert "ocr" in config
    assert "llm" in config
    assert len(config["ocr"]["providers"]) > 0
    assert len(config["llm"]["providers"]) > 0
