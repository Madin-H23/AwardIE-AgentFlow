"""OCR 禁用自动恢复（T19）：环境性禁用随凭据恢复自动解除（防 P0-1 复发）。

背景：P0-1 曾因配置键名不匹配导致 baidu secret 静默失败、provider 被标记禁用；
补配 .env 后禁用记录不会自动恢复，引擎长期跳过该 provider。本模块在启动时
对"环境性禁用"（disabled_reason 不含"管理员手动禁用"标记）做自检：
provider 配置声明的凭据环境变量已齐全 → 调用 `provider_status.clear_disabled`
重新启用。管理员显式下线的 provider（人为离线/不合规）不自动恢复。

实现位置刻意放在非冻结层（backend/utils）：只调用冻结模块（backend/ocr）
的公开接口 clear_disabled，不改动 backend/ocr 任何业务逻辑。
调用方：run.py 启动时（OCR 引擎构造前）执行一次。
"""
import logging
import os

logger = logging.getLogger(__name__)

# 管理员显式下线标记（出现在 disabled_reason 中时不自动恢复）
_MANUAL_DISABLE_MARKER = "管理员手动禁用"


def auto_recover_disabled_providers(config_loader) -> int:
    """检查并自动恢复"凭据已齐全但被环境性禁用"的 OCR provider。

    Args:
        config_loader: 统一配置加载器（config.loader.get_config()）

    Returns:
        恢复数量（失败降级返回 0，绝不阻塞启动）。
    """
    try:
        from backend.ocr.core.provider_status import OCRProviderStatusManager
    except Exception as e:  # noqa: BLE001 —— 冻结模块缺失时跳过
        logger.warning("[ocr-recover] OCR 状态管理不可用，跳过自动恢复: %s", e)
        return 0

    try:
        cfg = config_loader.load_config()
        ocr_cfg = cfg.get("ocr", {}) or {}
        status_mgr = OCRProviderStatusManager(
            config_loader.get_path("ocr", "runtime_status_path"))
        disabled = status_mgr.get_disabled_providers()
        providers_cfg = ocr_cfg.get("providers", {}) or {}
    except Exception as e:  # noqa: BLE001
        logger.warning("[ocr-recover] 读取 OCR 配置/状态失败，跳过自动恢复: %s", e)
        return 0

    restored = 0
    for name, info in disabled.items():
        reason = info.get("reason", "")
        if _MANUAL_DISABLE_MARKER in reason:
            continue
        provider_conf = providers_cfg.get(name) or {}
        if _credentials_ready(provider_conf):
            try:
                status_mgr.clear_disabled(name)
                restored += 1
                logger.info("[ocr-recover] %s 凭据已齐全，自动解除禁用（原原因: %s）", name, reason)
            except Exception as e:  # noqa: BLE001
                logger.warning("[ocr-recover] 解除 %s 禁用失败: %s", name, e)
    return restored


def _credentials_ready(provider_conf: dict) -> bool:
    """凭据就绪判定：provider 配置声明的 api_key_env/secret_key_env 等环境变量已非空。

    apikey.json 经 ConfigLoader.load_api_keys_into_env 注入同名环境变量；
    全部声明项非空才视为恢复（如 baidu 需 key+secret 双凭据，只补一个不误启）。
    """
    declared = [v for k, v in provider_conf.items()
               if k.endswith("_env") and isinstance(v, str) and v]
    if not declared:
        # 无凭据类 env 声明的 provider（如本地 paddle）不做自动恢复判断
        return False
    return all(bool(os.getenv(env_var)) for env_var in declared)