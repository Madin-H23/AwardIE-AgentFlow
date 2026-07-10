"""
OCR Provider 运行时状态：记录被自动标记为不可用的供应商及原因，供引擎跳过、管理端展示与操作。
状态文件路径由配置指定（如 config/ocr_runtime.json），禁止硬编码。
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

_DEFAULT_KEY = "provider_status"


class OCRProviderStatusManager:
    """OCR 供应商运行时状态：读/写禁用列表及原因。"""

    def __init__(self, status_file_path: Path):
        """
        Args:
            status_file_path: 状态文件路径（由配置提供，如 config/ocr_runtime.json）。
        """
        if not status_file_path:
            raise ValueError("ocr 运行时状态文件路径不能为空，请在 config/settings.json 的 ocr.runtime_status_path 中配置")
        self._path = Path(status_file_path)

    def _load(self) -> Dict[str, Any]:
        """加载状态文件。不存在或空则返回 { provider_status: {} }。"""
        if not self._path.exists():
            return {_DEFAULT_KEY: {}}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("读取 OCR 运行时状态文件失败，将使用空状态: %s", e)
            return {_DEFAULT_KEY: {}}
        if _DEFAULT_KEY not in data or not isinstance(data[_DEFAULT_KEY], dict):
            return {_DEFAULT_KEY: {}}
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        """写回状态文件。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_disabled_providers(self) -> Dict[str, Dict[str, str]]:
        """
        返回当前被标记为禁用的供应商及其原因、时间。

        Returns:
            { "zhipu": { "reason": "...", "disabled_at": "..." }, ... }
            仅包含 disabled 为 true 的项。
        """
        data = self._load()
        status = data.get(_DEFAULT_KEY, {})
        result = {}
        for name, info in status.items():
            if isinstance(info, dict) and info.get("disabled") is True:
                result[name] = {
                    "reason": info.get("disabled_reason", ""),
                    "disabled_at": info.get("disabled_at", ""),
                }
        return result

    def is_disabled(self, provider_name: str) -> bool:
        """判断某供应商是否被标记为禁用。"""
        data = self._load()
        info = data.get(_DEFAULT_KEY, {}).get(provider_name)
        return isinstance(info, dict) and info.get("disabled") is True

    def mark_disabled(self, provider_name: str, reason: str) -> None:
        """将某供应商标记为不可用并记录原因。"""
        data = self._load()
        if _DEFAULT_KEY not in data:
            data[_DEFAULT_KEY] = {}
        data[_DEFAULT_KEY][provider_name] = {
            "disabled": True,
            "disabled_reason": reason,
            "disabled_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._save(data)
        logger.info("OCR 供应商已标记为不可用: %s, 原因: %s", provider_name, reason)

    def clear_disabled(self, provider_name: str) -> None:
        """清除某供应商的禁用状态（重新启用）。"""
        data = self._load()
        if _DEFAULT_KEY not in data:
            return
        if provider_name in data[_DEFAULT_KEY]:
            del data[_DEFAULT_KEY][provider_name]
            self._save(data)
            logger.info("OCR 供应商已重新启用: %s", provider_name)
