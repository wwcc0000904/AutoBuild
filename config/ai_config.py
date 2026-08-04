"""AI 分析器配置 - 密钥走 keyring，其余走 QSettings。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config.logging_setup import get_logger

_KEYRING_SERVICE = "CtvAuto"
_KEYRING_ACCOUNT = "ai_api_key"


@dataclass
class AIConfig:
    enabled: bool = False          # 是否启用真实 AI（False=用 dummy）
    provider: str = "openai"       # 预留：openai / deepseek / qwen ...
    api_key: str = ""
    base_url: str = ""             # 留空=OpenAI 官方；填了走兼容服务
    model: str = "gpt-4o"
    timeout: int = 60


def load_ai_config() -> AIConfig:
    """从 QSettings + keyring 加载 AI 配置。"""
    cfg = AIConfig()
    logger = get_logger()
    try:
        from PySide6.QtCore import QSettings
        s = QSettings("CtvAuto", "SoftwareOutput")
        cfg.enabled = s.value("ai/enabled", False, type=bool)
        cfg.provider = s.value("ai/provider", "openai", type=str)
        cfg.base_url = s.value("ai/base_url", "", type=str)
        cfg.model = s.value("ai/model", "gpt-4o", type=str)
        cfg.timeout = s.value("ai/timeout", 60, type=int)
    except Exception as e:
        logger.warning("读取 AI 配置失败，用默认值: %s", e)

    # 密钥单独走 keyring
    try:
        import keyring
        cfg.api_key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_ACCOUNT) or ""
    except Exception:
        logger.warning("keyring 不可用，AI 密钥留空")
    return cfg


def save_ai_config(cfg: AIConfig) -> None:
    """保存 AI 配置到 QSettings + keyring。"""
    logger = get_logger()
    try:
        from PySide6.QtCore import QSettings
        s = QSettings("CtvAuto", "SoftwareOutput")
        s.setValue("ai/enabled", cfg.enabled)
        s.setValue("ai/provider", cfg.provider)
        s.setValue("ai/base_url", cfg.base_url)
        s.setValue("ai/model", cfg.model)
        s.setValue("ai/timeout", cfg.timeout)
    except Exception as e:
        logger.error("保存 AI 配置失败: %s", e, exc_info=True)

    if cfg.api_key:
        try:
            import keyring
            keyring.set_password(_KEYRING_SERVICE, _KEYRING_ACCOUNT, cfg.api_key)
        except Exception as e:
            logger.warning("keyring 保存密钥失败: %s", e)
