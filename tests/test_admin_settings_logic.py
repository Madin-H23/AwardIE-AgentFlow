"""admin settings 逻辑冒烟（pytest 函数式，T31-T34 批次3 转换）。"""
import json

from config.loader import get_config


def test_settings_logic():
    """模拟 admin.py settings() 的 OCR provider 装配逻辑"""
    config_loader = get_config()
    app_config = config_loader.load_config()

    available_ocr_providers = []
    providers_config = {"ocr": {}, "llm": {}}
    user_keys = {}

    if "ocr" in app_config and "providers" in app_config["ocr"]:
        for name, conf in app_config["ocr"]["providers"].items():
            available_ocr_providers.append(name)
            api_key_env = conf.get("api_key_env")
            current_key = user_keys.get("ocr", {}).get(name, "")
            providers_config["ocr"][name] = {
                "needs_key": bool(api_key_env),
                "api_key": current_key,
                "type": conf.get("type"),
            }

    assert len(available_ocr_providers) > 0
    assert "zhipu" in providers_config["ocr"]
    assert providers_config["ocr"]["zhipu"]["needs_key"]
