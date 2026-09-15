"""主题配色定义。

每个主题是一个 dict，key 为 CLR_ 前缀的颜色名，value 为十六进制色值。
MainWindow 在 __init__ 时根据当前主题将所有 CLR_* 设为实例属性，
切换主题时调用 _refresh_theme() 重新应用全部样式表。
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

# ── 主题列表 ──────────────────────────────────────────────
THEMES: dict[str, dict] = {
    # ---- 浅色（原有蓝灰毛玻璃风格）----
    "light": {
        "label": "浅色",
        "bg_image": "static/bg_frosted.png",
        "CLR_BG": "#e0e3ed",
        "CLR_SIDEBAR": "#f5f6f9",
        "CLR_CARD": "#ffffff",
        "CLR_CARD_BORDER": "#e5e5e5",
        "CLR_INPUT_BG": "#f8f8f8",
        "CLR_INPUT_BORDER": "#dcdcdc",
        "CLR_TEXT": "#1a1a1a",
        "CLR_TEXT_DIM": "#888888",
        "CLR_ACCENT": "#333333",
        "CLR_ACCENT2": "#555555",
        "CLR_GREEN": "#34c759",
        "CLR_RED": "#ff3b30",
        "CLR_ORANGE": "#ff9500",
        # 派生色（hover / pressed / 边框等）
        "CLR_HOVER": "#f0f0f0",
        "CLR_PRESSED": "#e0e0e0",
        "CLR_NAV_ACTIVE": "#e8e8e8",
        "CLR_TAB_BG": "#eceef2",
        "CLR_TAB_SELECTED": "#ffffff",
        "CLR_BORDER": "#d5d8e0",
        "CLR_SCROLLBAR": "#dcdcdc",
        "CLR_SCROLLBAR_HOVER": "#1a1a1a",
        "CLR_LIST_BG": "#ffffff",
        "CLR_LIST_HOVER": "#f0f0f0",
        "CLR_LIST_SELECTED": "#e0e0e0",
        "CLR_COMBO_HOVER": "#f0f0f0",
        "CLR_COMBO_FOCUS_BG": "#f5f5f5",
        "CLR_ACCENT_HOVER": "#d5d5d5",
        "CLR_ACCENT_PRESSED": "#cccccc",
        "CLR_ACCENT_DISABLED_BG": "#f0f0f0",
        "CLR_ACCENT_DISABLED_FG": "#aaaaaa",
        "CLR_SMALL_HOVER": "#f0f0f0",
        "CLR_SMALL_PRESSED": "#e0e0e0",
        "CLR_COMBO_BORDER_HOVER": "#aaaaaa",
        "CLR_COMBO_BORDER_FOCUS": "#999999",
        "CLR_SPINBOX_BG": "#ffffff",
        "CLR_CHECKBOX_BG": "#ffffff",
        "CLR_CHECKBOX_BORDER": "#dcdcdc",
    },

    # ---- 深色（参考 ref_ui.jpeg 深色风格）----
    "dark": {
        "label": "深色",
        "bg_image": "",  # 深色不用背景图
        "CLR_BG": "#0f1117",
        "CLR_SIDEBAR": "#16181f",
        "CLR_CARD": "#1c1e27",
        "CLR_CARD_BORDER": "#2a2d3a",
        "CLR_INPUT_BG": "#232631",
        "CLR_INPUT_BORDER": "#343846",
        "CLR_TEXT": "#e2e4ea",
        "CLR_TEXT_DIM": "#7a7f94",
        "CLR_ACCENT": "#4a90d9",
        "CLR_ACCENT2": "#6ab0f3",
        "CLR_GREEN": "#34c759",
        "CLR_RED": "#ff453a",
        "CLR_ORANGE": "#ff9f0a",
        "CLR_HOVER": "#282b38",
        "CLR_PRESSED": "#343846",
        "CLR_NAV_ACTIVE": "#282b38",
        "CLR_TAB_BG": "#232631",
        "CLR_TAB_SELECTED": "#1c1e27",
        "CLR_BORDER": "#2a2d3a",
        "CLR_SCROLLBAR": "#3a3d4a",
        "CLR_SCROLLBAR_HOVER": "#5a5d6a",
        "CLR_LIST_BG": "#1c1e27",
        "CLR_LIST_HOVER": "#282b38",
        "CLR_LIST_SELECTED": "#343846",
        "CLR_COMBO_HOVER": "#282b38",
        "CLR_COMBO_FOCUS_BG": "#232631",
        "CLR_ACCENT_HOVER": "#5ba0e9",
        "CLR_ACCENT_PRESSED": "#3a7dc9",
        "CLR_ACCENT_DISABLED_BG": "#2a2d3a",
        "CLR_ACCENT_DISABLED_FG": "#555860",
        "CLR_SMALL_HOVER": "#282b38",
        "CLR_SMALL_PRESSED": "#343846",
        "CLR_COMBO_BORDER_HOVER": "#4a4d5a",
        "CLR_COMBO_BORDER_FOCUS": "#4a90d9",
        "CLR_SPINBOX_BG": "#232631",
        "CLR_CHECKBOX_BG": "#232631",
        "CLR_CHECKBOX_BORDER": "#343846",
    },
}

SETTINGS_KEY = "theme"


def get_theme_names() -> list[str]:
    """返回所有主题的内部名。"""
    return list(THEMES.keys())


def get_theme_label(name: str) -> str:
    return THEMES.get(name, {}).get("label", name)


def get_theme(name: str) -> dict:
    """返回指定主题的配色 dict（不含 label/bg_image 等元字段，纯 CLR_*）。"""
    raw = THEMES.get(name, THEMES["light"])
    return {k: v for k, v in raw.items() if k.startswith("CLR_")}


def get_theme_meta(name: str) -> dict:
    """返回主题元信息（label, bg_image 等）。"""
    raw = THEMES.get(name, THEMES["light"])
    return {k: v for k, v in raw.items() if not k.startswith("CLR_")}


def load_theme_name() -> str:
    """从 QSettings 读取已保存的主题名，默认 light。"""
    s = QSettings("CtvAuto", "SoftwareOutput")
    return s.value(SETTINGS_KEY, "light", type=str)


def save_theme_name(name: str) -> None:
    s = QSettings("CtvAuto", "SoftwareOutput")
    s.setValue(SETTINGS_KEY, name)
