"""手动修改面板 — 按文件分页卡片布局。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QCheckBox, QGroupBox, QScrollArea,
    QSpinBox, QStackedWidget, QListView,
)

import qtawesome as qta
from config.logging_setup import get_logger


# ── 样式 ──────────────────────────────────────────────────
_CLR = {
    "bg": "#e0e3ed", "card": "#ffffff", "border": "#e5e5e5",
    "text": "#1a1a1a", "dim": "#888888", "accent": "#333333",
    "input_border": "#dcdcdc",
}


def _card(title: str) -> QGroupBox:
    g = QGroupBox(f"  {title}")
    g.setStyleSheet(
        f"QGroupBox {{ background: {_CLR['card']}; border: 1px solid {_CLR['border']};"
        f" border-radius: 12px; padding: 20px 16px 10px 16px; margin-top: 18px;"
        f" font-size: 13px; font-weight: bold; color: {_CLR['text']}; }}"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 16px; padding: 0 8px; }}"
    )
    return g


def _lbl(text: str, w: int = 0, bold: bool = False, dim: bool = False) -> QLabel:
    l = QLabel(text)
    c = _CLR["dim"] if dim else _CLR["text"]
    wt = "bold" if bold else "normal"
    l.setStyleSheet(f"font-size:12px; color:{c}; background:transparent; font-weight:{wt};")
    if w:
        l.setFixedWidth(w)
    return l


def _combo(items: list[str]) -> QComboBox:
    c = QComboBox()
    c.addItems(items)
    c.setStyleSheet(
        f"QComboBox{{background:#fff;color:{_CLR['text']};border:1px solid {_CLR['input_border']};"
        f"border-radius:6px;padding:5px 10px;font-size:12px;}}"
        f"QComboBox:hover{{border-color:#aaa;}}QComboBox::drop-down{{border:none;width:20px;}}"
    )
    v = QListView()
    v.setStyleSheet("QListView{background:#fff;border:1px solid #e5e5e5;outline:none;}"
                    "QListView::item{padding:3px 10px;}"
                    "QListView::item:hover{background:#f0f0f0;}"
                    "QListView::item:selected{background:#e0e0e0;color:#1a1a1a;}")
    v.setUniformItemSizes(True)
    c.setView(v)
    c.setMaxVisibleItems(15)
    return c


def _cb(text: str) -> QCheckBox:
    c = QCheckBox(text)
    c.setStyleSheet(f"QCheckBox{{color:{_CLR['text']};background:transparent;spacing:6px;font-size:12px;}}")
    return c


def _spin(lo=0, hi=999, ph="--") -> QSpinBox:
    s = QSpinBox(); s.setRange(lo, hi); s.setSpecialValueText(ph); s.setValue(0)
    s.setStyleSheet(f"QSpinBox{{background:#fff;color:{_CLR['text']};border:1px solid {_CLR['input_border']};"
                    f"border-radius:6px;padding:4px 8px;font-size:12px;}}QSpinBox:focus{{border-color:{_CLR['accent']};}}")
    return s


def _input(ph="") -> QLineEdit:
    e = QLineEdit(); e.setPlaceholderText(ph)
    e.setStyleSheet(f"QLineEdit{{background:transparent;color:{_CLR['text']};border:1px solid {_CLR['input_border']};"
                    f"border-radius:6px;padding:6px 10px;font-size:12px;}}QLineEdit:focus{{border-color:{_CLR['accent']};}}")
    return e


def _hline() -> QLabel:
    s = QLabel(); s.setFixedHeight(1); s.setStyleSheet(f"background:{_CLR['border']};margin:6px 0;")
    return s


# ── OptionRow ─────────────────────────────────────────────
class OptionRow(QWidget):
    """[✓] 标签  控件 — 勾选后控件才激活。"""
    def __init__(self, label: str, control: QWidget, parent=None):
        super().__init__(parent)
        self._control = control
        lay = QHBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(10)
        self._cb = _cb(""); self._cb.setFixedWidth(20); self._cb.toggled.connect(lambda c: control.setEnabled(c))
        lay.addWidget(self._cb)
        lay.addWidget(_lbl(label, w=90))
        lay.addWidget(control, 1)
        control.setEnabled(False)

    def is_checked(self) -> bool: return self._cb.isChecked()
    def value(self):
        if not self._cb.isChecked(): return None
        if isinstance(self._control, QComboBox): return self._control.currentIndex()
        if isinstance(self._control, QSpinBox): return self._control.value()
        if isinstance(self._control, QLineEdit): return self._control.text().strip()
        if isinstance(self._control, QCheckBox): return self._control.isChecked()
        return None


# ── ManualPanel ───────────────────────────────────────────

class ManualPanel(QWidget):
    """手动修改面板：按修改文件分页，每页一张卡片。"""

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
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(6)

        # ── 页码导航 ──
        nav = QWidget()
        nav.setStyleSheet("background: transparent;")
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(0, 4, 0, 4)
        nav_lay.setSpacing(6)

        self._pages_info: list[tuple[str, str]] = [
            ("📄 build_config.txt",     "功能开关 + 参数"),
            ("📊 db.ini",              "蓝屏 + 高级参数"),
            ("📝 ctvbuild.prop",       "上电/开机模式"),
            ("📋 ctv_data.xml",        "桌面/菜单/语言/国家"),
            ("⚙️ ctvsetting.xml",      "菜单项显示/隐藏"),
            ("📃 whiteList.conf",      "白名单"),
            ("📦 build_ctv_app.txt",   "预装应用"),
        ]
        self._nav_btns: list[QPushButton] = []
        for i, (icon_name, tip) in enumerate(self._pages_info):
            btn = QPushButton(f" {i+1}")
            btn.setFixedSize(32, 28)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._nav_style(False))
            btn.clicked.connect(lambda _, idx=i: self._switch_page(idx))
            nav_lay.addWidget(btn)
            self._nav_btns.append(btn)

        # 文件名标签
        self._page_label = QLabel(self._pages_info[0][0])
        self._page_label.setStyleSheet(f"font-size: 12px; color: {_CLR['dim']}; background: transparent; padding-left: 8px;")
        nav_lay.addWidget(self._page_label)
        nav_lay.addStretch()
        root.addWidget(nav)

        # ── 页面堆叠 ──
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        self._stack.addWidget(self._page_build_config())
        self._stack.addWidget(self._page_db_ini())
        self._stack.addWidget(self._page_prop())
        self._stack.addWidget(self._page_ctv_data())
        self._stack.addWidget(self._page_ctv_setting())
        self._stack.addWidget(self._page_whitelist())
        self._stack.addWidget(self._page_preinstall())

        root.addWidget(self._stack, 1)

        # ── 底部按钮 ──
        btn_row = QHBoxLayout(); btn_row.setSpacing(10); btn_row.addStretch()

        preview_btn = QPushButton("  预览")
        preview_btn.setIcon(qta.icon("fa5s.eye", color="#888"))
        preview_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#888;border:1px solid #dcdcdc;border-radius:8px;padding:8px 16px;font-size:12px;}"
            "QPushButton:hover{background:#f0f0f0;color:#1a1a1a;}")
        preview_btn.clicked.connect(self._on_preview)
        btn_row.addWidget(preview_btn)

        exec_btn = QPushButton("  执行修改")
        exec_btn.setIcon(qta.icon("fa5s.play-circle", color="#1a1a1a"))
        exec_btn.setStyleSheet(
            "QPushButton{background:#e0e0e0;color:#1a1a1a;border:none;border-radius:8px;padding:8px 24px;font-size:13px;font-weight:bold;}"
            "QPushButton:hover{background:#d5d5d5;}")
        exec_btn.clicked.connect(self._on_execute)
        btn_row.addWidget(exec_btn)
        root.addLayout(btn_row)

        # 预览区
        self._preview_edit = QTextEdit()
        self._preview_edit.setReadOnly(True); self._preview_edit.setMaximumHeight(90)
        self._preview_edit.setPlaceholderText("点击「预览」查看将要执行的修改…")
        self._preview_edit.setStyleSheet(
            f"QTextEdit{{background:transparent;color:{_CLR['text']};border:1px solid {_CLR['input_border']};"
            f"border-radius:8px;padding:8px;font-family:Menlo,Consolas,monospace;font-size:12px;}}")
        root.addWidget(self._preview_edit)

        self._nav_btns[0].setStyleSheet(self._nav_style(True))

    def _nav_style(self, active: bool) -> str:
        if active:
            return ("QPushButton{background:#e0e0e0;color:#1a1a1a;border:none;border-radius:6px;"
                    "padding:4px 8px;font-size:12px;font-weight:bold;}"
                    "QPushButton:hover{background:#d5d5d5;}")
        return ("QPushButton{background:transparent;color:#888;border:1px solid #ddd;border-radius:6px;"
                "padding:4px 8px;font-size:12px;}"
                "QPushButton:hover{background:#f0f0f0;color:#1a1a1a;}")

    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setStyleSheet(self._nav_style(i == idx))
        self._page_label.setText(self._pages_info[idx][0])

    # ================================================================
    #  Page 1: build_config.txt — 功能开关 + 电流 + 客户
    # ================================================================
    def _page_build_config(self) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        body = QWidget(); body.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(body); lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)

        # 功能开关
        card = _card("功能开关 (build_config.txt)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        self._switch_rows: dict[str, tuple[QCheckBox, QComboBox]] = {}
        for kw in self._fm.get("open", {}):
            row = OptionRow(kw, _combo(["打开", "关闭"]))
            gl.addWidget(row)
            self._switch_rows[kw] = (row._cb, row._control)
        lay.addWidget(card)

        # 电流
        card = _card("电流 (CTV_CFG_PANEL_BACKLIGHT_CURRENT)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        row = OptionRow("电流值", _spin(0, 9999, "不修改"))
        gl.addWidget(row)
        self._current = (row._cb, row._control)
        lay.addWidget(card)

        # 客户名称
        card = _card("客户名称 (CTV_CFG_CUSTOMER)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        row = OptionRow("客户名称", _input("不修改则留空"))
        gl.addWidget(row)
        self._customer = (row._cb, row._control)
        lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(body)
        return scroll

    # ================================================================
    #  Page 2: db.ini — 蓝屏 + 白平衡 + NLA + Gain
    # ================================================================
    def _page_db_ini(self) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        body = QWidget(); body.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(body); lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)

        # 蓝屏
        card = _card("蓝屏开关 (System_screencolor)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        row = OptionRow("蓝屏", _combo(["打开蓝屏 (1)", "关闭蓝屏 (0)"]))
        gl.addWidget(row)
        self._blue_screen = (row._cb, row._control)
        lay.addWidget(card)

        # 白平衡
        card = _card("白平衡 (FacColorTemp nature)")
        gl = QVBoxLayout(card); gl.setSpacing(8)
        gl.addWidget(_lbl("R Gain / G Gain / B Gain / R Offset / G Offset / B Offset", bold=True))
        wb_row = QHBoxLayout(); wb_row.setSpacing(6)
        self._wb_inputs: list[QSpinBox] = []
        for tag in ["R", "G", "B", "R_O", "G_O", "B_O"]:
            sp = _spin(0, 999, "--"); sp.setPrefix(f"{tag}:"); sp.setMinimumWidth(70)
            wb_row.addWidget(sp); self._wb_inputs.append(sp)
        gl.addLayout(wb_row)
        lay.addWidget(card)

        # NLA
        card = _card("NLA 非线性参数")
        gl = QVBoxLayout(card); gl.setSpacing(8)
        nla_row = QHBoxLayout(); nla_row.setSpacing(8)
        self._nla_param = _combo(["brightness", "contrast", "saturation", "sharpness", "hue", "backlight"])
        nla_row.addWidget(self._nla_param)
        nla_row.addWidget(_lbl("中间值:", w=50))
        self._nla_value = _spin(0, 999, "--"); nla_row.addWidget(self._nla_value)
        gl.addLayout(nla_row)
        lay.addWidget(card)

        # Gain
        for name, attr in [("SatGain", "_sat_gain"), ("HueGain", "_hue_gain"), ("BriGain", "_bri_gain")]:
            card = _card(f"{name} (前7值)")
            gl = QVBoxLayout(card); gl.setSpacing(4)
            row_lay = QHBoxLayout(); row_lay.setSpacing(4)
            inputs: list[QSpinBox] = []
            for i in range(7):
                sp = _spin(-99, 99, "--"); sp.setMinimumWidth(55)
                row_lay.addWidget(sp); inputs.append(sp)
            gl.addLayout(row_lay)
            setattr(self, attr, inputs)
            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(body)
        return scroll

    # ================================================================
    #  Page 3: ctvbuild.prop — 上电模式 + 开机模式
    # ================================================================
    def _page_prop(self) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        body = QWidget(); body.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(body); lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)

        card = _card("上电模式 (ro.product.powermode)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        row = OptionRow("上电模式", _combo(["待机 (secondary)", "开机 (direct)", "记忆 (memory)"]))
        gl.addWidget(row)
        self._power_mode = (row._cb, row._control)
        lay.addWidget(card)

        card = _card("开机模式 (persist.sys.bootanimation.type)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        row = OptionRow("开机模式", _combo(["动画 (0)", "视频 (1)"]))
        gl.addWidget(row)
        self._boot_mode = (row._cb, row._control)
        lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(body)
        return scroll

    # ================================================================
    #  Page 4: ctv_data.xml — 开机桌面/菜单时间/语言显示/国家/语言
    # ================================================================
    def _page_ctv_data(self) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        body = QWidget(); body.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(body); lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)

        card = _card("开机桌面 (BootDesktop)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        row = OptionRow("开机桌面", _combo(["安卓 (0)", "TV (1)", "记忆 (2)"]))
        gl.addWidget(row)
        self._boot_desktop = (row._cb, row._control)
        lay.addWidget(card)

        card = _card("菜单显示时间 (MenuShowTime)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        row = OptionRow("显示时间", _combo(["一直显示 (0)", "5秒 (1)", "10秒 (2)", "20秒 (3)", "30秒 (4)", "60秒 (5)"]))
        gl.addWidget(row)
        self._menu_time = (row._cb, row._control)
        lay.addWidget(card)

        card = _card("语言显示国家 (LanguageShowCountry)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        row = OptionRow("语言显示", _combo(["带国家 (true)", "不带国家 (false)"]))
        gl.addWidget(row)
        self._lang_country = (row._cb, row._control)
        lay.addWidget(card)

        # 默认语言
        card = _card("默认语言 (CtvLanguage.ini)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        lang_combo = _combo(["(请选择)"])
        lang_map_path = Path("config/language_map.json")
        if lang_map_path.exists():
            for code, info in json.loads(lang_map_path.read_text(encoding="utf-8")).items():
                lang_combo.addItem(f"{info['name']} ({code})", code)
        row = OptionRow("默认语言", lang_combo)
        gl.addWidget(row)
        self._default_lang = (row._cb, row._control)
        lay.addWidget(card)

        # 默认国家
        card = _card("默认国家 (CountryList)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        country_combo = _combo(["(请选择)"])
        self._country_map: dict[str, str] = {}
        country_map_path = Path("config/country_map.json")
        if country_map_path.exists():
            self._country_map = json.loads(country_map_path.read_text(encoding="utf-8"))
            for code, name in self._country_map.items():
                country_combo.addItem(f"{name} ({code})", code)
        row = OptionRow("默认国家", country_combo)
        gl.addWidget(row)
        self._default_country = (row._cb, row._control)
        self._country_combo = country_combo
        lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(body)
        return scroll

    # ================================================================
    #  Page 5: ctvsetting.xml — 菜单项
    # ================================================================
    def _page_ctv_setting(self) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        body = QWidget(); body.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(body); lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)

        menu_map = self._fm.get("ctv_setting_menu", {})
        card = _card("菜单项显示/隐藏 (ctvsetting.xml)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        self._menu_rows: dict[str, tuple[QCheckBox, QComboBox, str]] = {}
        for cn_name, entry in menu_map.items():
            en_name = entry.get("name", cn_name) if isinstance(entry, dict) else entry
            row = OptionRow(cn_name, _combo(["显示", "隐藏"]))
            gl.addWidget(row)
            self._menu_rows[cn_name] = (row._cb, row._control, en_name)
        lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(body)
        return scroll

    # ================================================================
    #  Page 6: whiteList.conf — 白名单
    # ================================================================
    def _page_whitelist(self) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        body = QWidget(); body.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(body); lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)

        card = _card("白名单 (whiteList.conf)")
        gl = QVBoxLayout(card); gl.setSpacing(8)

        pkg_row = QHBoxLayout(); pkg_row.setSpacing(10)
        pkg_row.addWidget(_lbl("包名", w=60))
        self._pkg_input = _input("例如: com.android.vending")
        pkg_row.addWidget(self._pkg_input, 1)
        gl.addLayout(pkg_row)

        action_row = QHBoxLayout(); action_row.setSpacing(16); action_row.addSpacing(70)
        self._pkg_add = _cb("添加到白名单")
        self._pkg_remove = _cb("从白名单移除")
        action_row.addWidget(self._pkg_add)
        action_row.addWidget(self._pkg_remove)
        action_row.addStretch()
        gl.addLayout(action_row)
        lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(body)
        return scroll

    # ================================================================
    #  Page 7: build_ctv_app.txt — 预装
    # ================================================================
    def _page_preinstall(self) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        body = QWidget(); body.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(body); lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)

        card = _card("预装应用 (build_ctv_app.txt)")
        gl = QVBoxLayout(card); gl.setSpacing(4)
        row = OptionRow("ESharePlus", _combo(["预装 (Y)", "取消预装 (n)"]))
        gl.addWidget(row)
        self._preinstall = (row._cb, row._control)
        lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(body)
        return scroll

    # ================================================================
    #  CountryList 过滤
    # ================================================================
    def filter_country_list(self, allowed_codes: list[str]) -> None:
        combo = self._country_combo
        combo.blockSignals(True); combo.clear(); combo.addItem("(请选择)")
        allowed = {c.upper() for c in allowed_codes}
        for code, name in self._country_map.items():
            if code.upper() in allowed:
                combo.addItem(f"{name} ({code})", code)
        combo.blockSignals(False)

    # ================================================================
    #  收集修改项
    # ================================================================
    def collect_modifications(self) -> list[dict]:
        mods: list[dict] = []
        fm = self._fm

        # 功能开关
        for kw, (cb, combo) in self._switch_rows.items():
            if not cb.isChecked(): continue
            section = "open" if combo.currentIndex() == 0 else "close"
            info = fm.get(section, {}).get(kw)
            if info:
                t = "db_ini" if info["file"].startswith("configs/") else "build_config"
                e = {"type": t, "file": info["file"], "key": info["key"], "value": info["value"]}
                if t == "build_config": e["mode"] = "value"
                mods.append(e)

        # 蓝屏
        cb, combo = self._blue_screen
        if cb.isChecked():
            mods.append({"type": "db_ini", "file": "configs/db.ini", "key": "System_screencolor",
                         "value": "1" if combo.currentIndex() == 0 else "0"})

        # 预装
        cb, combo = self._preinstall
        if cb.isChecked():
            mods.append({"type": "preinstall", "app": "ESharePlus", "enabled": combo.currentIndex() == 0})

        # 菜单项
        for cn, (cb, combo, en) in self._menu_rows.items():
            if not cb.isChecked(): continue
            mods.append({"type": "ctv_setting", "name": en,
                         "enable": "support" if combo.currentIndex() == 0 else "hide",
                         "prefix": cn in ("蓝牙",)})

        # 属性
        for (cb, combo), key, vm in [
            (self._power_mode, "ro.product.powermode", ["secondary", "direct", "memory"]),
            (self._boot_mode, "persist.sys.bootanimation.type", ["0", "1"]),
        ]:
            if cb.isChecked():
                mods.append({"type": "prop", "file": "ctvbuild.prop", "key": key, "value": vm[combo.currentIndex()]})

        # CTV Data
        for (cb, combo), name, vm in [
            (self._boot_desktop, "BootDesktop", ["0", "1", "2"]),
            (self._menu_time, "MenuShowTime", ["0", "1", "2", "3", "4", "5"]),
        ]:
            if cb.isChecked():
                mods.append({"type": "ctv_data", "name": name, "value": vm[combo.currentIndex()]})

        cb, combo = self._lang_country
        if cb.isChecked():
            mods.append({"type": "ctv_data", "name": "LanguageShowCountry",
                         "value": "true" if combo.currentIndex() == 0 else "false"})

        # 语言 & 国家
        cb, combo = self._default_lang
        if cb.isChecked() and combo.currentIndex() > 0:
            code = combo.currentData()
            if code: mods.append({"type": "language_first", "target": code})

        cb, combo = self._default_country
        if cb.isChecked() and combo.currentIndex() > 0:
            code = combo.currentData()
            if code: mods.append({"type": "country_list_first", "country_code": code})

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

        # 客户
        cb, le = self._customer
        if cb.isChecked() and le.text().strip():
            mods.append({"type": "build_config", "file": "build_config.txt",
                         "key": "CTV_CFG_CUSTOMER", "value": le.text().strip(), "mode": "value"})

        # 白平衡
        wb = [sp.value() for sp in self._wb_inputs]
        if any(v != 0 for v in wb):
            f = [str(v) if v != 0 else None for v in wb]
            if all(v is not None for v in f[:3]) and all(v is None for v in f[3:]):
                mods.append({"type": "color_temp", "values": f[:3]})
            elif all(v is not None for v in f):
                mods.append({"type": "color_temp", "values": f})

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
            self._preview_edit.setPlainText("未勾选任何修改项。"); return
        lines = [f"共 {len(mods)} 条修改项:"]
        for i, m in enumerate(mods, 1):
            lines.append(f"  {i}. {json.dumps(m, ensure_ascii=False)}")
        self._preview_edit.setPlainText("\n".join(lines))

    def _on_execute(self):
        mods = self.collect_modifications()
        if not mods:
            self._preview_edit.setPlainText("未勾选任何修改项，无法执行。"); return
        self.execute_requested.emit(mods)
