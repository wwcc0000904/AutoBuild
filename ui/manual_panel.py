"""手动修改面板 — 专业卡片式布局。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QCheckBox, QGroupBox, QScrollArea,
    QSpinBox, QListView,
)

import qtawesome as qta
from config.logging_setup import get_logger


# ── 样式 ──────────────────────────────────────────────────
_S = {
    "bg": "#e0e3ed",
    "card": "#ffffff",
    "border": "#e5e5e5",
    "text": "#1a1a1a",
    "dim": "#888888",
    "accent": "#333333",
    "input_border": "#dcdcdc",
    "green": "#27ae60",
    "red": "#e74c3c",
    "blue": "#4a90d9",
}


def _css(style_dict: dict) -> str:
    return "; ".join(f"{k}: {v}" for k, v in style_dict.items())


def _card(title: str, icon: str = "") -> QGroupBox:
    g = QGroupBox(f"  {icon} {title}" if icon else f"  {title}")
    g.setStyleSheet(
        f"QGroupBox {{ background: {_S['card']}; border: 1px solid {_S['border']};"
        f" border-radius: 12px; padding: 20px 16px 10px 16px; margin-top: 18px;"
        f" font-size: 13px; font-weight: bold; color: {_S['text']}; }}"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 16px; padding: 0 8px; }}"
    )
    return g


def _label(text: str, width: int = 0, bold: bool = False, dim: bool = False) -> QLabel:
    lbl = QLabel(text)
    color = _S["dim"] if dim else _S["text"]
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(f"font-size: 12px; color: {color}; background: transparent; font-weight: {weight};")
    if width:
        lbl.setFixedWidth(width)
    return lbl


def _combo(items: list[str]) -> QComboBox:
    c = QComboBox()
    c.addItems(items)
    c.setStyleSheet(
        f"QComboBox {{ background: #fff; color: {_S['text']}; border: 1px solid {_S['input_border']};"
        f" border-radius: 6px; padding: 5px 10px; font-size: 12px; }}"
        f"QComboBox:hover {{ border-color: #aaa; }}"
        f"QComboBox::drop-down {{ border: none; width: 20px; }}"
    )
    view = QListView()
    view.setStyleSheet(
        "QListView { background: #fff; border: 1px solid #e5e5e5; outline: none; }"
        "QListView::item { padding: 3px 10px; }"
        "QListView::item:hover { background: #f0f0f0; }"
        "QListView::item:selected { background: #e0e0e0; color: #1a1a1a; }"
    )
    view.setUniformItemSizes(True)
    c.setView(view)
    c.setMaxVisibleItems(15)
    return c


def _checkbox(text: str) -> QCheckBox:
    cb = QCheckBox(text)
    cb.setStyleSheet(f"QCheckBox {{ color: {_S['text']}; background: transparent; spacing: 6px; font-size: 12px; }}")
    return cb


def _spin(min_v: int = 0, max_v: int = 999, placeholder: str = "--") -> QSpinBox:
    sp = QSpinBox()
    sp.setRange(min_v, max_v)
    sp.setSpecialValueText(placeholder)
    sp.setValue(0)
    sp.setStyleSheet(
        f"QSpinBox {{ background: #fff; color: {_S['text']}; border: 1px solid {_S['input_border']};"
        f" border-radius: 6px; padding: 4px 8px; font-size: 12px; }}"
        f"QSpinBox:focus {{ border-color: {_S['accent']}; }}"
    )
    return sp


def _input(placeholder: str = "") -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setStyleSheet(
        f"QLineEdit {{ background: transparent; color: {_S['text']};"
        f" border: 1px solid {_S['input_border']}; border-radius: 6px;"
        f" padding: 6px 10px; font-size: 12px; }}"
        f"QLineEdit:focus {{ border-color: {_S['accent']}; }}"
    )
    return le


def _hline() -> QLabel:
    sep = QLabel()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background: {_S['border']}; margin: 6px 0;")
    return sep


# ── OptionRow：勾选 + 控件，勾选后控件才可用 ──────────────
class OptionRow(QWidget):
    """一行：[✓] 标签  控件。勾选后控件才激活。"""

    def __init__(self, label: str, control: QWidget, parent=None):
        super().__init__(parent)
        self._control = control
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._cb = _checkbox("")
        self._cb.setFixedWidth(20)
        self._cb.toggled.connect(self._on_toggle)
        layout.addWidget(self._cb)

        lbl = _label(label, width=90)
        layout.addWidget(lbl)

        layout.addWidget(control, 1)
        control.setEnabled(False)

    def _on_toggle(self, checked: bool):
        self._control.setEnabled(checked)

    def is_checked(self) -> bool:
        return self._cb.isChecked()

    def value(self):
        if not self._cb.isChecked():
            return None
        if isinstance(self._control, QComboBox):
            return self._control.currentIndex()
        if isinstance(self._control, QSpinBox):
            return self._control.value()
        if isinstance(self._control, QLineEdit):
            return self._control.text().strip()
        if isinstance(self._control, QCheckBox):
            return self._control.isChecked()
        return None


# ── ManualPanel ───────────────────────────────────────────

class ManualPanel(QWidget):
    """手动修改面板。"""

    execute_requested = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._logger = get_logger()
        self._fm = self._load_mapping()
        self._build_ui()

    def _load_mapping(self) -> dict:
        p = Path("config/feature_mapping.json")
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ── 功能开关 ──
        card = _card("功能开关", "⚡")
        gl = QVBoxLayout(card)
        gl.setSpacing(4)

        self._switch_rows: dict[str, tuple[QCheckBox, QComboBox]] = {}
        open_map = self._fm.get("open", {})
        for keyword in open_map:
            row = OptionRow(keyword, _combo(["打开", "关闭"]))
            gl.addWidget(row)
            self._switch_rows[keyword] = (row._cb, row._control)

        _h = _hline()
        gl.addWidget(_h)

        # 蓝屏
        row = OptionRow("蓝屏", _combo(["打开蓝屏", "关闭蓝屏"]))
        gl.addWidget(row)
        self._blue_screen = (row._cb, row._control)

        # 预装
        row = OptionRow("ESharePlus", _combo(["预装", "取消预装"]))
        gl.addWidget(row)
        self._preinstall = (row._cb, row._control)
        lay.addWidget(card)

        # ── 菜单项 ──
        menu_map = self._fm.get("ctv_setting_menu", {})
        if menu_map:
            card = _card("菜单项", "🔧")
            gl = QVBoxLayout(card)
            gl.setSpacing(4)
            self._menu_rows: dict[str, tuple[QCheckBox, QComboBox, str]] = {}
            for cn_name, entry in menu_map.items():
                en_name = entry.get("name", cn_name) if isinstance(entry, dict) else entry
                row = OptionRow(cn_name, _combo(["显示", "隐藏"]))
                gl.addWidget(row)
                self._menu_rows[cn_name] = (row._cb, row._control, en_name)
            lay.addWidget(card)

        # ── 属性 ──
        card = _card("属性修改", "📝")
        gl = QVBoxLayout(card)
        gl.setSpacing(4)

        row = OptionRow("上电模式", _combo(["待机 (secondary)", "开机 (direct)", "记忆 (memory)"]))
        gl.addWidget(row)
        self._power_mode = (row._cb, row._control)

        row = OptionRow("开机模式", _combo(["动画 (0)", "视频 (1)"]))
        gl.addWidget(row)
        self._boot_mode = (row._cb, row._control)
        lay.addWidget(card)

        # ── CTV Data ──
        card = _card("CTV Data", "📋")
        gl = QVBoxLayout(card)
        gl.setSpacing(4)

        row = OptionRow("开机桌面", _combo(["安卓 (0)", "TV (1)", "记忆 (2)"]))
        gl.addWidget(row)
        self._boot_desktop = (row._cb, row._control)

        row = OptionRow("菜单显示时间", _combo(["一直显示 (0)", "5秒 (1)", "10秒 (2)", "20秒 (3)", "30秒 (4)", "60秒 (5)"]))
        gl.addWidget(row)
        self._menu_time = (row._cb, row._control)

        row = OptionRow("语言显示国家", _combo(["带国家 (true)", "不带国家 (false)"]))
        gl.addWidget(row)
        self._lang_country = (row._cb, row._control)
        lay.addWidget(card)

        # ── 语言 & 国家 ──
        card = _card("默认语言 & 国家", "🌐")
        gl = QVBoxLayout(card)
        gl.setSpacing(4)

        lang_combo = _combo(["(请选择)"])
        lang_map_path = Path("config/language_map.json")
        if lang_map_path.exists():
            lang_map = json.loads(lang_map_path.read_text(encoding="utf-8"))
            for code, info in lang_map.items():
                lang_combo.addItem(f"{info['name']} ({code})", code)
        row = OptionRow("默认语言", lang_combo)
        gl.addWidget(row)
        self._default_lang = (row._cb, row._control)

        country_combo = _combo(["(请选择)"])
        country_map_path = Path("config/country_map.json")
        if country_map_path.exists():
            country_map = json.loads(country_map_path.read_text(encoding="utf-8"))
            for code, name in country_map.items():
                country_combo.addItem(f"{name} ({code})", code)
        row = OptionRow("默认国家", country_combo)
        gl.addWidget(row)
        self._default_country = (row._cb, row._control)
        lay.addWidget(card)

        # ── 白名单 ──
        card = _card("白名单", "📃")
        gl = QVBoxLayout(card)
        gl.setSpacing(8)

        pkg_row = QHBoxLayout()
        pkg_row.setSpacing(10)
        pkg_row.addWidget(_label("包名", width=90))
        self._pkg_input = _input("例如: com.android.vending")
        pkg_row.addWidget(self._pkg_input, 1)
        gl.addLayout(pkg_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(16)
        action_row.addSpacing(100)
        self._pkg_add = _checkbox("添加")
        self._pkg_remove = _checkbox("删除")
        action_row.addWidget(self._pkg_add)
        action_row.addWidget(self._pkg_remove)
        action_row.addStretch()
        gl.addLayout(action_row)
        lay.addWidget(card)

        # ── 参数 ──
        card = _card("参数修改", "🔢")
        gl = QVBoxLayout(card)
        gl.setSpacing(4)

        row = OptionRow("电流", _spin(0, 9999, "不修改"))
        gl.addWidget(row)
        self._current = (row._cb, row._control)

        row = OptionRow("客户名称", _input("不修改则留空"))
        gl.addWidget(row)
        self._customer = (row._cb, row._control)
        lay.addWidget(card)

        # ── 高级 ──
        card = _card("高级参数", "🎛")
        gl = QVBoxLayout(card)
        gl.setSpacing(8)

        # 白平衡
        gl.addWidget(_label("白平衡 (R/G/B Gain + Offset)", bold=True))
        wb_row = QHBoxLayout()
        wb_row.setSpacing(6)
        self._wb_inputs: list[QSpinBox] = []
        for tag in ["R", "G", "B", "R_O", "G_O", "B_O"]:
            sp = _spin(0, 999, "--")
            sp.setPrefix(f"{tag}:")
            sp.setMinimumWidth(70)
            wb_row.addWidget(sp)
            self._wb_inputs.append(sp)
        gl.addLayout(wb_row)

        gl.addWidget(_hline())

        # NLA
        gl.addWidget(_label("NLA 非线性参数", bold=True))
        nla_row = QHBoxLayout()
        nla_row.setSpacing(8)
        self._nla_param = _combo(["brightness", "contrast", "saturation", "sharpness", "hue", "backlight"])
        nla_row.addWidget(self._nla_param)
        nla_row.addWidget(_label("中间值:", width=50))
        self._nla_value = _spin(0, 999, "--")
        nla_row.addWidget(self._nla_value)
        gl.addLayout(nla_row)

        gl.addWidget(_hline())

        # Gain
        for gain_name, attr in [("SatGain", "_sat_gain"), ("HueGain", "_hue_gain"), ("BriGain", "_bri_gain")]:
            gl.addWidget(_label(f"{gain_name} (前7值)", bold=True))
            row = QHBoxLayout()
            row.setSpacing(4)
            inputs: list[QSpinBox] = []
            for i in range(7):
                sp = _spin(-99, 99, "--")
                sp.setMinimumWidth(55)
                row.addWidget(sp)
                inputs.append(sp)
            gl.addLayout(row)
            setattr(self, attr, inputs)
        lay.addWidget(card)

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        preview_btn = QPushButton("  预览")
        preview_btn.setIcon(qta.icon("fa5s.eye", color="#888"))
        preview_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #888; border: 1px solid #dcdcdc;"
            " border-radius: 8px; padding: 8px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #f0f0f0; color: #1a1a1a; }"
        )
        preview_btn.clicked.connect(self._on_preview)
        btn_row.addWidget(preview_btn)

        exec_btn = QPushButton("  执行修改")
        exec_btn.setIcon(qta.icon("fa5s.play-circle", color="#1a1a1a"))
        exec_btn.setStyleSheet(
            "QPushButton { background: #e0e0e0; color: #1a1a1a; border: none;"
            " border-radius: 8px; padding: 8px 24px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #d5d5d5; }"
        )
        exec_btn.clicked.connect(self._on_execute)
        btn_row.addWidget(exec_btn)
        lay.addLayout(btn_row)

        # 预览区
        self._preview_edit = QTextEdit()
        self._preview_edit.setReadOnly(True)
        self._preview_edit.setMaximumHeight(100)
        self._preview_edit.setPlaceholderText("点击「预览」查看将要执行的修改…")
        self._preview_edit.setStyleSheet(
            f"QTextEdit {{ background: transparent; color: {_S['text']};"
            f" border: 1px solid {_S['input_border']}; border-radius: 8px;"
            f" padding: 8px; font-family: Menlo,Consolas,monospace; font-size: 12px; }}"
        )
        lay.addWidget(self._preview_edit)

    # ========== 收集 ==========

    def collect_modifications(self) -> list[dict]:
        mods: list[dict] = []
        fm = self._fm

        # 功能开关
        for keyword, (cb, combo) in self._switch_rows.items():
            if not cb.isChecked():
                continue
            section = "open" if combo.currentIndex() == 0 else "close"
            info = fm.get(section, {}).get(keyword)
            if info:
                t = "db_ini" if info["file"].startswith("configs/") else "build_config"
                e = {"type": t, "file": info["file"], "key": info["key"], "value": info["value"]}
                if t == "build_config":
                    e["mode"] = "value"
                mods.append(e)

        # 蓝屏
        cb, combo = self._blue_screen
        if cb.isChecked():
            mods.append({"type": "db_ini", "file": "configs/db.ini", "key": "System_screencolor",
                         "value": "1" if combo.currentIndex() == 0 else "0"})

        # 预装
        cb, combo = self._preinstall
        if cb.isChecked():
            mods.append({"type": "preinstall", "app": "ESharePlus",
                         "enabled": combo.currentIndex() == 0})

        # 菜单项
        for cn_name, (cb, combo, en_name) in self._menu_rows.items():
            if not cb.isChecked():
                continue
            enable = "support" if combo.currentIndex() == 0 else "hide"
            mods.append({"type": "ctv_setting", "name": en_name, "enable": enable, "prefix": cn_name in ("蓝牙",)})

        # 属性
        for (cb, combo), key, val_map in [
            (self._power_mode, "ro.product.powermode", ["secondary", "direct", "memory"]),
            (self._boot_mode, "persist.sys.bootanimation.type", ["0", "1"]),
        ]:
            if cb.isChecked():
                mods.append({"type": "prop", "file": "ctvbuild.prop", "key": key, "value": val_map[combo.currentIndex()]})

        # CTV Data
        for (cb, combo), name, val_map in [
            (self._boot_desktop, "BootDesktop", ["0", "1", "2"]),
            (self._menu_time, "MenuShowTime", ["0", "1", "2", "3", "4", "5"]),
        ]:
            if cb.isChecked():
                mods.append({"type": "ctv_data", "name": name, "value": val_map[combo.currentIndex()]})

        cb, combo = self._lang_country
        if cb.isChecked():
            mods.append({"type": "ctv_data", "name": "LanguageShowCountry",
                         "value": "true" if combo.currentIndex() == 0 else "false"})

        # 语言 & 国家
        cb, combo = self._default_lang
        if cb.isChecked() and combo.currentIndex() > 0:
            code = combo.currentData()
            if code:
                mods.append({"type": "language_first", "target": code})

        cb, combo = self._default_country
        if cb.isChecked() and combo.currentIndex() > 0:
            code = combo.currentData()
            if code:
                mods.append({"type": "country_list_first", "country_code": code})

        # 白名单
        pkg = self._pkg_input.text().strip()
        if pkg:
            if self._pkg_add.isChecked():
                mods.append({"type": "whitelist", "package": pkg, "action": "add"})
            if self._pkg_remove.isChecked():
                mods.append({"type": "whitelist", "package": pkg, "action": "remove"})

        # 电流
        cb, sp = self._current
        if cb.isChecked() and sp.value() > 0:
            mods.append({"type": "build_config", "file": "build_config.txt",
                         "key": "CTV_CFG_PANEL_BACKLIGHT_CURRENT", "value": str(sp.value()), "mode": "value_part"})

        # 客户名称
        cb, le = self._customer
        if cb.isChecked() and le.text().strip():
            mods.append({"type": "build_config", "file": "build_config.txt",
                         "key": "CTV_CFG_CUSTOMER", "value": le.text().strip(), "mode": "value"})

        # 白平衡
        wb_vals = [sp.value() for sp in self._wb_inputs]
        if any(v != 0 for v in wb_vals):
            filled = [str(v) if v != 0 else None for v in wb_vals]
            if all(v is not None for v in filled[:3]) and all(v is None for v in filled[3:]):
                mods.append({"type": "color_temp", "values": filled[:3]})
            elif all(v is not None for v in filled):
                mods.append({"type": "color_temp", "values": filled})

        # NLA
        if self._nla_value.value() > 0:
            mods.append({"type": "nla", "param": self._nla_param.currentText(),
                         "value": str(self._nla_value.value()), "position": 2})

        # Gain
        for name, attr in [("SatGain", "_sat_gain"), ("HueGain", "_hue_gain"), ("BriGain", "_bri_gain")]:
            vals = [str(sp.value()) for sp in getattr(self, attr) if sp.value() != 0]
            if len(vals) == 7:
                mods.append({"type": "gain", "name": name, "values": vals})

        return mods

    def _on_preview(self):
        mods = self.collect_modifications()
        if not mods:
            self._preview_edit.setPlainText("未勾选任何修改项。")
            return
        lines = [f"共 {len(mods)} 条修改项:"]
        for i, m in enumerate(mods, 1):
            lines.append(f"  {i}. {json.dumps(m, ensure_ascii=False)}")
        self._preview_edit.setPlainText("\n".join(lines))

    def _on_execute(self):
        mods = self.collect_modifications()
        if not mods:
            self._preview_edit.setPlainText("未勾选任何修改项，无法执行。")
            return
        self.execute_requested.emit(mods)
