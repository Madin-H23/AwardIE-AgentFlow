"""T19 测试：OCR 禁用自动恢复（环境性禁用随凭据齐全自动解除）。

规则：disabled_reason 不含"管理员手动禁用"且 provider 配置声明的凭据 env 全非空
→ clear_disabled；管理员手动下线不自动恢复；凭据不全不恢复；无禁用不动作。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.utils.ocr_provider_auto_recover import (  # noqa: E402
    auto_recover_disabled_providers,
)


@pytest.fixture()
def status_file(tmp_path):
    p = tmp_path / "ocr_runtime.json"
    p.write_text(json.dumps({
        "provider_status": {
            "zhipu": {"disabled": True, "disabled_reason": "http 401: invalid api key",
                      "disabled_at": "2026-07-01T00:00:00"},
            "paddle": {"disabled": True, "disabled_reason": "管理员手动禁用",
                       "disabled_at": "2026-02-01T00:00:00"},
        }
    }, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture()
def config_loader(tmp_path, status_file):
    class FakeLoader:
        def __init__(self):
            self._status_path = status_file

        def load_config(self):
            return {
                "ocr": {
                    "runtime_status_path": str(self._status_path),
                    "providers": {
                        "zhipu": {"api_key_env": "ZHIPUAI_API_KEY"},
                        "baidu": {"api_key_env": "BAIDU_API_KEY",
                                  "secret_key_env": "BAIDU_SECRET_KEY"},
                        "paddle": {"type": "local"},
                    },
                }
            }

        def get_path(self, *keys):
            return self._status_path

    return FakeLoader()


def _disabled_names(status_file):
    data = json.loads(status_file.read_text(encoding="utf-8"))
    return {k for k, v in data.get("provider_status", {}).items()
            if isinstance(v, dict) and v.get("disabled") is True}


class TestAutoRecover:
    def test_recover_environmental_disable_only(self, config_loader, status_file, monkeypatch):
        # zhipu 凭据就绪（环境性禁用）→ 恢复；paddle 管理员手动禁用 → 保留
        monkeypatch.setenv("ZHIPUAI_API_KEY", "sk-test")
        assert auto_recover_disabled_providers(config_loader) == 1
        assert _disabled_names(status_file) == {"paddle"}

    def test_credentials_incomplete_keeps_disabled(self, config_loader, status_file, monkeypatch):
        # zhipu 凭据未就绪 → 不恢复；paddle 仍保留
        monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
        assert auto_recover_disabled_providers(config_loader) == 0
        assert _disabled_names(status_file) == {"zhipu", "paddle"}

    def test_partial_baidu_credentials_not_recovered(self, config_loader, status_file, monkeypatch):
        # 新增 baidu 环境性禁用（如 token 过期）：只补 api key 不补 secret → 不恢复
        data = json.loads(status_file.read_text(encoding="utf-8"))
        data["provider_status"]["baidu"] = {"disabled": True,
                                            "disabled_reason": "access_token 获取失败",
                                            "disabled_at": "2026-08-01T00:00:00"}
        status_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setenv("BAIDU_API_KEY", "ak")
        monkeypatch.delenv("BAIDU_SECRET_KEY", raising=False)
        monkeypatch.setenv("ZHIPUAI_API_KEY", "sk-test")
        assert auto_recover_disabled_providers(config_loader) == 1  # 仅 zhipu
        assert _disabled_names(status_file) == {"paddle", "baidu"}

    def test_no_disabled_no_op(self, config_loader, status_file, monkeypatch):
        status_file.write_text(json.dumps({"provider_status": {}}, ensure_ascii=False),
                               encoding="utf-8")
        monkeypatch.setenv("ZHIPUAI_API_KEY", "sk-test")
        assert auto_recover_disabled_providers(config_loader) == 0

    def test_missing_status_file_no_crash(self, tmp_path, monkeypatch):
        class EmptyLoader:
            def load_config(self):
                return {"ocr": {"runtime_status_path": str(tmp_path / "nope.json"),
                                "providers": {"zhipu": {"api_key_env": "ZHIPUAI_API_KEY"}}}}

            def get_path(self, *keys):
                return tmp_path / "nope.json"

        monkeypatch.setenv("ZHIPUAI_API_KEY", "sk-test")
        assert auto_recover_disabled_providers(EmptyLoader()) == 0  # 不崩溃、不创建文件
        assert not (tmp_path / "nope.json").exists()