"""手动修改面板 — 卡片式布局，与规则管理风格统一。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal, Qt
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QCheckBox, QGroupBox, QScrollArea,
    QSpinBox, QListView,
)

from config.logging_setup import get_logger


# ── 样式常量 ──────────────────────────────────────────────
_CLR_BG = "#e0e3ed"
_CLR_CARD = "#ffffff"
_CLR_CARD_BORDER = "#e5e5e5"
_CLR_TEXT = "#1a1a1a"
_CLR_TEXT_DIM = "#888888"
_CLR_ACCENT = "#333333"
_CLR_INPUT_BORDER = "#dcdcdc"


def _card_style() -> str:
    return (
        f"QGroupBox {{ background: {_CLR_CARD}; border: 1px solid {_CLR_CARD_BORDER};"
        f" border-radius: 12px; padding: 16px 12px 8px 12px; margin-top: 16px;"
        f" font-size: 13px; font-weight: bold; color: {_CLR_TEXT}; }}"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 16px; padding: 0 8px; }}"
    )


def _input_style() -> str:
    return (
        f"QLineEdit {{ background: transparent; color: {_CLR_TEXT};"
        f" border: 1px solid {_CLR_INPUT_BORDER}; border-radius: 6px;"
        f" padding: 6px 10px; font-size: 12px; }}"
        f"QLineEdit:focus {{ border-color: {_CLR_ACCENT}; }}"
    )


def _combo_style() -> str:
    return (
        f"QComboBox {{ background: transparent; color: {_CLR_TEXT};"
        f" border: 1px solid #dcdcdc; border-radius: 6px;"
        f" padding: 6px 10px; font-size: 12px; }}"
        f"QComboBox:hover {{ background: #f0f0f0; border-color: #aaaaaa; }}"
        f"QComboBox:focus {{ border-color: #999999; background: #f5f5f5; }}"
        f"QComboBox::drop-down {{ border: none; width: 20px; }}"
    )


def _spin_style() -> str:
    return (
        f"QSpinBox {{ background: #ffffff; color: {_CLR_TEXT};"
        f" border: 1px solid #d5d8e0; border-radius: 6px; padding: 4px 8px; }}"
        f"QSpinBox:focus {{ border-color: {_CLR_ACCENT}; }}"
    )


def _btn_primary() -> str:
    return (
        "QPushButton { background: #e0e0e0; color: #1a1a1a; border: none;"
        " border-radius: 8px; padding: 8px 18px; font-size: 12px; font-weight: bold; }"
        "QPushButton:hover { background: #d5d5d5; }"
        "QPushButton:pressed { background: #cccccc; }"
    )


def _btn_secondary() -> str:
    return (
        "QPushButton { background: transparent; color: #888888;"
        " border: 1px solid #dcdcdc; border-radius: 8px; padding: 8px 14px; font-size: 12px; }"
        "QPushButton:hover { background: #f0f0f0; border-color: #d0d0d0; color: #1a1a1a; }"
    )


def _fix_combo(combo: QComboBox):
    view = QListView()
    view.setStyleSheet(
        "QListView { background: #ffffff; border: 1px solid #e5e5e5; outline: none; }"
        "QListView::item { padding: 2px 8px; }"
        "QListView::item:hover { background: #f0f0f0; }"
        "QListView::item:selected { background: #e0e0e0; color: #1a1a1a; }"
    )
    view.setUniformItemSizes(True)
    combo.setView(view)
    combo.setMaxVisibleItems(15)


# ── ManualPanel ───────────────────────────────────────────

class ManualPanel(QWidget):
    """手动修改面板：卡片式布局，直接选择修改项。"""

    execute_requested = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._logger = get_logger()
        self._feature_mapping = self._load_mapping()
        self._build_ui()

    def _load_mapping(self) -> dict:
        path = Path("config/feature_mapping.json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # 滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        main = QVBoxLayout(container)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(12)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # ── 卡片：功能开关 ──
        card = QGroupBox("  ⚡ 功能开关")
        card.setStyleSheet(_card_style())
        gl = QVBoxLayout(card)
        gl.setSpacing(6)

        # 功能开关 → 复选框（三态：未选中=不修改，半选=关闭，全选=打开）
        self._switches: dict[str, QCheckBox] = {}
        open_map = self._feature_mapping.get("open", {})
        for keyword in open_map:
            cb = QCheckBox(keyword)
            cb.setTristate(True)
            cb.setCheckState(Qt.CheckState.PartiallyChecked)  # 默认"不修改"
            cb.setToolTip(f"✓ 打开 / ✗ 关闭 / — 不修改（点击切换）")
            cb.setStyleSheet(f"color: {_CLR_TEXT}; background: transparent; spacing: 6px;")
            gl.addWidget(cb)
            self._switches[keyword] = cb

        # 蓝屏
        cb = QCheckBox("蓝屏")
        cb.setTristate(True)
        cb.setCheckState(Qt.CheckState.PartiallyChecked)
        cb.setToolTip("✓ 打开蓝屏 / ✗ 关闭蓝屏 / — 不修改")
        cb.setStyleSheet(f"color: {_CLR_TEXT}; background: transparent; spacing: 6px;")
        gl.addWidget(cb)
        self._blue_screen_cb = cb
        main.addWidget(card)

        # ── 卡片：预装应用 ──
        card = QGroupBox("  📦 预装应用")
        card.setStyleSheet(_card_style())
        gl = QVBoxLayout(card)
        cb = QCheckBox("ESharePlus")
        cb.setTristate(True)
        cb.setCheckState(Qt.CheckState.PartiallyChecked)
        cb.setToolTip("✓ 预装 / ✗ 取消预装 / — 不修改")
        cb.setStyleSheet(f"color: {_CLR_TEXT}; background: transparent; spacing: 6px;")
        gl.addWidget(cb)
        self._preinstall_cb = cb
        main.addWidget(card)

        # ── 卡片：白名单 ──
        card = QGroupBox("  📃 白名单 (whiteList.conf)")
        card.setStyleSheet(_card_style())
        gl = QVBoxLayout(card)
        gl.setSpacing(8)
        pkg_row = QHBoxLayout()
        pkg_row.setSpacing(8)
        lbl = QLabel("包名")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"font-size: 12px; color: {_CLR_TEXT}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pkg_row.addWidget(lbl)
        self._pkg_input = QLineEdit()
        self._pkg_input.setPlaceholderText("例如: com.android.vending")
        self._pkg_input.setStyleSheet(_input_style())
        pkg_row.addWidget(self._pkg_input, 1)
        gl.addLayout(pkg_row)
        action_row = QHBoxLayout()
        action_row.addSpacing(88)
        self._pkg_add = QCheckBox("添加")
        self._pkg_remove = QCheckBox("删除")
        self._pkg_add.setStyleSheet(f"color: {_CLR_TEXT}; background: transparent;")
        self._pkg_remove.setStyleSheet(f"color: {_CLR_TEXT}; background: transparent;")
        action_row.addWidget(self._pkg_add)
        action_row.addWidget(self._pkg_remove)
        action_row.addStretch()
        gl.addLayout(action_row)
        main.addWidget(card)

        # ── 卡片：菜单项 ──
        menu_map = self._feature_mapping.get("ctv_setting_menu", {})
        if menu_map:
            card = QGroupBox("  🔧 菜单项 (ctvsetting.xml)")
            card.setStyleSheet(_card_style())
            gl = QVBoxLayout(card)
            gl.setSpacing(4)
            self._menu_cbs: dict[str, tuple[QCheckBox, str]] = {}
            for cn_name, entry in menu_map.items():
                en_name = entry.get("name", cn_name) if isinstance(entry, dict) else entry
                cb = QCheckBox(cn_name)
                cb.setTristate(True)
                cb.setCheckState(Qt.CheckState.PartiallyChecked)
                cb.setToolTip(f"✓ 显示 / ✗ 隐藏 / — 不修改")
                cb.setStyleSheet(f"color: {_CLR_TEXT}; background: transparent; spacing: 6px;")
                gl.addWidget(cb)
                self._menu_cbs[cn_name] = (cb, en_name)
            main.addWidget(card)

        # ── 卡片：属性修改 ──
        card = QGroupBox("  📝 属性修改 (ctvbuild.prop)")
        card.setStyleSheet(_card_style())
        gl = QVBoxLayout(card)
        gl.setSpacing(8)

        # 上电模式
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("上电模式")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"font-size: 12px; color: {_CLR_TEXT}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)
        self._power_mode_combo = QComboBox()
        self._power_mode_combo.addItems(["不修改", "待机 (secondary)", "开机 (direct)", "记忆 (memory)"])
        self._power_mode_combo.setStyleSheet(_combo_style())
        _fix_combo(self._power_mode_combo)
        row.addWidget(self._power_mode_combo, 1)
        gl.addLayout(row)

        # 开机模式
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("开机模式")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"font-size: 12px; color: {_CLR_TEXT}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)
        self._boot_mode_combo = QComboBox()
        self._boot_mode_combo.addItems(["不修改", "动画 (0)", "视频 (1)"])
        self._boot_mode_combo.setStyleSheet(_combo_style())
        _fix_combo(self._boot_mode_combo)
        row.addWidget(self._boot_mode_combo, 1)
        gl.addLayout(row)
        main.addWidget(card)

        # ── 卡片：CTV Data ──
        card = QGroupBox("  📋 CTV Data (ctv_data.xml)")
        card.setStyleSheet(_card_style())
        gl = QVBoxLayout(card)
        gl.setSpacing(8)

        _ctv_options = [
            ("开机桌面", "_boot_desktop_combo", ["不修改", "安卓 (0)", "TV (1)", "记忆 (2)"]),
            ("菜单显示时间", "_menu_time_combo", ["不修改", "一直显示 (0)", "5秒 (1)", "10秒 (2)", "20秒 (3)", "30秒 (4)", "60秒 (5)"]),
        ]
        for label, attr, items in _ctv_options:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setFixedWidth(80)
            lbl.setStyleSheet(f"font-size: 12px; color: {_CLR_TEXT}; background: transparent;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl)
            combo = QComboBox()
            combo.addItems(items)
            combo.setStyleSheet(_combo_style())
            _fix_combo(combo)
            row.addWidget(combo, 1)
            gl.addLayout(row)
            setattr(self, attr, combo)

        # 语言显示 → 复选框
        cb = QCheckBox("语言显示国家")
        cb.setTristate(True)
        cb.setCheckState(Qt.CheckState.PartiallyChecked)
        cb.setToolTip("✓ 带国家 / ✗ 不带国家 / — 不修改")
        cb.setStyleSheet(f"color: {_CLR_TEXT}; background: transparent; spacing: 6px;")
        gl.addWidget(cb)
        self._lang_country_cb = cb
        main.addWidget(card)

        # ── 卡片：默认语言/国家 ──
        card = QGroupBox("  🌐 默认语言 & 国家")
        card.setStyleSheet(_card_style())
        gl = QVBoxLayout(card)
        gl.setSpacing(8)

        # 默认语言
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("默认语言")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"font-size: 12px; color: {_CLR_TEXT}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)
        self._default_lang_combo = QComboBox()
        self._default_lang_combo.setStyleSheet(_combo_style())
        _fix_combo(self._default_lang_combo)
        self._default_lang_combo.addItem("不修改")
        lang_map_path = Path("config/language_map.json")
        if lang_map_path.exists():
            lang_map = json.loads(lang_map_path.read_text(encoding="utf-8"))
            for code, info in lang_map.items():
                self._default_lang_combo.addItem(f"{info['name']} ({code})", code)
        row.addWidget(self._default_lang_combo, 1)
        gl.addLayout(row)

        # 默认国家
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("默认国家")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"font-size: 12px; color: {_CLR_TEXT}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)
        self._default_country_combo = QComboBox()
        self._default_country_combo.setStyleSheet(_combo_style())
        _fix_combo(self._default_country_combo)
        self._default_country_combo.addItem("不修改")
        country_map_path = Path("config/country_map.json")
        if country_map_path.exists():
            country_map = json.loads(country_map_path.read_text(encoding="utf-8"))
            for code, name in country_map.items():
                self._default_country_combo.addItem(f"{name} ({code})", code)
        row.addWidget(self._default_country_combo, 1)
        gl.addLayout(row)
        main.addWidget(card)

        # ── 卡片：参数 ──
        card = QGroupBox("  🔢 参数修改 (build_config.txt)")
        card.setStyleSheet(_card_style())
        gl = QVBoxLayout(card)
        gl.setSpacing(8)

        # 电流
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("电流")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"font-size: 12px; color: {_CLR_TEXT}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)
        self._current_input = QSpinBox()
        self._current_input.setRange(0, 9999)
        self._current_input.setSpecialValueText("不修改")
        self._current_input.setValue(0)
        self._current_input.setStyleSheet(_spin_style())
        row.addWidget(self._current_input, 1)
        gl.addLayout(row)

        # 客户名称
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("客户名称")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"font-size: 12px; color: {_CLR_TEXT}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)
        self._customer_input = QLineEdit()
        self._customer_input.setPlaceholderText("不修改则留空")
        self._customer_input.setStyleSheet(_input_style())
        row.addWidget(self._customer_input, 1)
        gl.addLayout(row)
        main.addWidget(card)

        # ── 卡片：高级 ──
        card = QGroupBox("  🎛 高级参数 (db.ini)")
        card.setStyleSheet(_card_style())
        gl = QVBoxLayout(card)
        gl.setSpacing(10)

        # 白平衡
        wb_lbl = QLabel("白平衡 (R/G/B Gain + R/G/B Offset)")
        wb_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: #555; background: transparent;")
        gl.addWidget(wb_lbl)
        wb_row = QHBoxLayout()
        wb_row.setSpacing(6)
        self._wb_inputs: list[QSpinBox] = []
        for label in ["R", "G", "B", "R_O", "G_O", "B_O"]:
            sp = QSpinBox()
            sp.setRange(0, 999)
            sp.setSpecialValueText("--")
            sp.setPrefix(f"{label}:")
            sp.setMinimumWidth(70)
            sp.setStyleSheet(_spin_style())
            wb_row.addWidget(sp)
            self._wb_inputs.append(sp)
        gl.addLayout(wb_row)

        # NLA
        nla_lbl = QLabel("NLA 非线性参数")
        nla_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: #555; background: transparent; margin-top: 6px;")
        gl.addWidget(nla_lbl)
        nla_row = QHBoxLayout()
        nla_row.setSpacing(8)
        nla_row.addWidget(QLabel("参数:"))
        self._nla_param_combo = QComboBox()
        self._nla_param_combo.addItems(["brightness", "contrast", "saturation", "sharpness", "hue", "backlight"])
        self._nla_param_combo.setStyleSheet(_combo_style())
        _fix_combo(self._nla_param_combo)
        nla_row.addWidget(self._nla_param_combo)
        nla_row.addWidget(QLabel("中间值:"))
        self._nla_value_input = QSpinBox()
        self._nla_value_input.setRange(0, 999)
        self._nla_value_input.setSpecialValueText("--")
        self._nla_value_input.setStyleSheet(_spin_style())
        nla_row.addWidget(self._nla_value_input)
        gl.addLayout(nla_row)

        # SatGain / HueGain / BriGain
        for gain_name in ["SatGain", "HueGain", "BriGain"]:
            gain_lbl = QLabel(f"{gain_name} (前7值)")
            gain_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: #555; background: transparent; margin-top: 4px;")
            gl.addWidget(gain_lbl)
            row = QHBoxLayout()
            row.setSpacing(4)
            inputs: list[QSpinBox] = []
            for i in range(7):
                sp = QSpinBox()
                sp.setRange(-99, 99)
                sp.setSpecialValueText("--")
                sp.setMinimumWidth(55)
                sp.setStyleSheet(_spin_style())
                row.addWidget(sp)
                inputs.append(sp)
            gl.addLayout(row)
            if gain_name == "SatGain":
                self._sat_gain_inputs = inputs
            elif gain_name == "HueGain":
                self._hue_gain_inputs = inputs
            else:
                self._bri_gain_inputs = inputs
        main.addWidget(card)

        # ── 底部按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self._preview_btn = QPushButton("  预览")
        self._preview_btn.setIcon(qta.icon("fa5s.eye", color="#888"))
        self._preview_btn.setStyleSheet(_btn_secondary())
        self._preview_btn.clicked.connect(self._on_preview)
        btn_layout.addWidget(self._preview_btn)

        self._execute_btn = QPushButton("  执行修改")
        self._execute_btn.setIcon(qta.icon("fa5s.play-circle", color="#1a1a1a"))
        self._execute_btn.setStyleSheet(_btn_primary())
        self._execute_btn.clicked.connect(self._on_execute)
        btn_layout.addWidget(self._execute_btn)

        main.addLayout(btn_layout)

        # 预览区
        self._preview_edit = QTextEdit()
        self._preview_edit.setReadOnly(True)
        self._preview_edit.setMaximumHeight(120)
        self._preview_edit.setPlaceholderText("点击「预览」查看将要执行的修改…")
        self._preview_edit.setStyleSheet(
            f"QTextEdit {{ background: transparent; color: {_CLR_TEXT};"
            f" border: 1px solid {_CLR_INPUT_BORDER}; border-radius: 8px;"
            f" padding: 8px; font-family: Menlo,Consolas,monospace; font-size: 12px; }}"
        )
        main.addWidget(self._preview_edit)

    # ========== 收集修改项 ==========

    def collect_modifications(self) -> list[dict]:
        mods: list[dict] = []
        mapping = self._feature_mapping

        # --- 功能开关（三态复选框：未选=关闭，半选=不修改，全选=打开）---
        for keyword, cb in self._switches.items():
            state = cb.checkState()
            if state == Qt.CheckState.PartiallyChecked:
                continue  # 不修改
            section = "open" if state == Qt.CheckState.Checked else "close"
            mod_info = mapping.get(section, {}).get(keyword)
            if mod_info:
                mod_type = "db_ini" if mod_info["file"].startswith("configs/") else "build_config"
                entry = {"type": mod_type, "file": mod_info["file"], "key": mod_info["key"], "value": mod_info["value"]}
                if mod_type == "build_config":
                    entry["mode"] = "value"
                mods.append(entry)

        # --- 蓝屏 ---
        bs_state = self._blue_screen_cb.checkState()
        if bs_state == Qt.CheckState.Checked:
            mods.append({"type": "db_ini", "file": "configs/db.ini", "key": "System_screencolor", "value": "1"})
        elif bs_state == Qt.CheckState.Unchecked:
            mods.append({"type": "db_ini", "file": "configs/db.ini", "key": "System_screencolor", "value": "0"})

        # --- 预装 ---
        pi_state = self._preinstall_cb.checkState()
        if pi_state == Qt.CheckState.Checked:
            mods.append({"type": "preinstall", "app": "ESharePlus", "enabled": True})
        elif pi_state == Qt.CheckState.Unchecked:
            mods.append({"type": "preinstall", "app": "ESharePlus", "enabled": False})

        # --- 白名单 ---
        pkg = self._pkg_input.text().strip()
        if pkg:
            if self._pkg_add.isChecked():
                mods.append({"type": "whitelist", "package": pkg, "action": "add"})
            if self._pkg_remove.isChecked():
                mods.append({"type": "whitelist", "package": pkg, "action": "remove"})

        # --- 菜单项（三态复选框）---
        for cn_name, (cb, en_name) in self._menu_cbs.items():
            state = cb.checkState()
            if state == Qt.CheckState.PartiallyChecked:
                continue
            enable = "support" if state == Qt.CheckState.Checked else "hide"
            prefix = cn_name in ("蓝牙",)
            mods.append({"type": "ctv_setting", "name": en_name, "enable": enable, "prefix": prefix})

        # --- 上电模式 ---
        power_map = {1: "secondary", 2: "direct", 3: "memory"}
        pm_idx = self._power_mode_combo.currentIndex()
        if pm_idx in power_map:
            mods.append({"type": "prop", "file": "ctvbuild.prop", "key": "ro.product.powermode", "value": power_map[pm_idx]})

        # --- 开机模式 ---
        boot_map = {1: "0", 2: "1"}
        bm_idx = self._boot_mode_combo.currentIndex()
        if bm_idx in boot_map:
            mods.append({"type": "prop", "file": "ctvbuild.prop", "key": "persist.sys.bootanimation.type", "value": boot_map[bm_idx]})

        # --- 开机桌面 ---
        desktop_map = {1: "0", 2: "1", 3: "2"}
        bd_idx = self._boot_desktop_combo.currentIndex()
        if bd_idx in desktop_map:
            mods.append({"type": "ctv_data", "name": "BootDesktop", "value": desktop_map[bd_idx]})

        # --- 菜单显示时间 ---
        time_map = {1: "0", 2: "1", 3: "2", 4: "3", 5: "4", 6: "5"}
        mt_idx = self._menu_time_combo.currentIndex()
        if mt_idx in time_map:
            mods.append({"type": "ctv_data", "name": "MenuShowTime", "value": time_map[mt_idx]})

        # --- 语言显示（三态复选框）---
        lc_state = self._lang_country_cb.checkState()
        if lc_state == Qt.CheckState.Checked:
            mods.append({"type": "ctv_data", "name": "LanguageShowCountry", "value": "true"})
        elif lc_state == Qt.CheckState.Unchecked:
            mods.append({"type": "ctv_data", "name": "LanguageShowCountry", "value": "false"})

        # --- 默认语言 ---
        lang_idx = self._default_lang_combo.currentIndex()
        if lang_idx > 0:
            lang_code = self._default_lang_combo.currentData()
            if lang_code:
                mods.append({"type": "language_first", "target": lang_code})

        # --- 默认国家 ---
        country_idx = self._default_country_combo.currentIndex()
        if country_idx > 0:
            country_code = self._default_country_combo.currentData()
            if country_code:
                mods.append({"type": "country_list_first", "country_code": country_code})

        # --- 电流 ---
        current_val = self._current_input.value()
        if current_val > 0:
            mods.append({
                "type": "build_config", "file": "build_config.txt",
                "key": "CTV_CFG_PANEL_BACKLIGHT_CURRENT", "value": str(current_val), "mode": "value_part",
            })

        # --- 客户名称 ---
        customer_name = self._customer_input.text().strip()
        if customer_name:
            mods.append({
                "type": "build_config", "file": "build_config.txt",
                "key": "CTV_CFG_CUSTOMER", "value": customer_name, "mode": "value",
            })

        # --- 白平衡 ---
        wb_values = []
        has_wb = False
        for sp in self._wb_inputs:
            v = sp.value()
            if v == 0:
                wb_values.append(None)
            else:
                wb_values.append(str(v))
                has_wb = True
        if has_wb:
            non_none = [v for v in wb_values if v is not None]
            if all(v is not None for v in wb_values[:3]) and all(v is None for v in wb_values[3:]):
                mods.append({"type": "color_temp", "values": wb_values[:3]})
            elif all(v is not None for v in wb_values):
                mods.append({"type": "color_temp", "values": wb_values})

        # --- NLA ---
        nla_val = self._nla_value_input.value()
        if nla_val > 0:
            param = self._nla_param_combo.currentText()
            mods.append({"type": "nla", "param": param, "value": str(nla_val), "position": 2})

        # --- SatGain / HueGain / BriGain ---
        for gain_name, inputs_attr in [("SatGain", "_sat_gain_inputs"), ("HueGain", "_hue_gain_inputs"), ("BriGain", "_bri_gain_inputs")]:
            vals = [str(sp.value()) for sp in getattr(self, inputs_attr) if sp.value() != 0]
            if len(vals) == 7:
                mods.append({"type": "gain", "name": gain_name, "values": vals})

        return mods

    def _on_preview(self) -> None:
        mods = self.collect_modifications()
        if not mods:
            self._preview_edit.setPlainText("未选择任何修改项。")
            return
        lines = [f"共 {len(mods)} 条修改项:"]
        for i, mod in enumerate(mods, 1):
            lines.append(f"  {i}. {json.dumps(mod, ensure_ascii=False)}")
        self._preview_edit.setPlainText("\n".join(lines))

    def _on_execute(self) -> None:
        mods = self.collect_modifications()
        if not mods:
            self._preview_edit.setPlainText("未选择任何修改项，无法执行。")
            return
        self.execute_requested.emit(mods)
