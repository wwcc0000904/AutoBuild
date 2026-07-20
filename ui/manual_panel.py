"""手动模式面板 — 插件卡片 + 当前值展示 + 直接编辑。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QGroupBox, QScrollArea, QStackedWidget, QListView,
    QSizePolicy,
)

import qtawesome as qta
from config.logging_setup import get_logger
from remote_config_reader import RemoteConfigReader


# ── 样式 ──────────────────────────────────────────────────
_C = {
    "bg": "#e0e3ed", "card": "#ffffff", "border": "#e5e5e5",
    "text": "#1a1a1a", "dim": "#999999", "blue": "#4a90d9",
    "green": "#27ae60", "orange": "#e67e22", "input_border": "#dcdcdc",
}


def _card(title: str, subtitle: str = "") -> QGroupBox:
    g = QGroupBox()
    g.setStyleSheet(
        f"QGroupBox {{ background: {_C['card']}; border: 1px solid {_C['border']};"
        f" border-radius: 12px; padding: 20px 16px 12px 16px; margin-top: 18px; }}"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 16px; padding: 0 8px; }}"
    )
    return g


def _card_layout(card: QGroupBox, title: str, subtitle: str = "") -> QVBoxLayout:
    """给卡片设置布局，加标题和副标题，返回内容布局。"""
    lay = QVBoxLayout(card)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {_C['text']}; background: transparent;")
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setStyleSheet(f"font-size: 11px; color: {_C['dim']}; background: transparent;")
        lay.addWidget(s)
    lay.addSpacing(6)
    return lay


def _lbl(text: str, w: int = 0, bold: bool = False, dim: bool = False, size: int = 12) -> QLabel:
    l = QLabel(text)
    c = _C["dim"] if dim else _C["text"]
    wt = "bold" if bold else "normal"
    l.setStyleSheet(f"font-size:{size}px; color:{c}; background:transparent; font-weight:{wt};")
    if w:
        l.setFixedWidth(w)
    return l


def _combo(items: list[str]) -> QComboBox:
    c = QComboBox()
    c.addItems(items)
    c.setStyleSheet(
        f"QComboBox{{background:#fff;color:{_C['text']};border:1px solid {_C['input_border']};"
        f"border-radius:6px;padding:5px 10px;font-size:12px;min-width:120px;}}"
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


def _input(ph: str = "") -> QLineEdit:
    e = QLineEdit()
    e.setPlaceholderText(ph)
    e.setMinimumWidth(120)
    e.setStyleSheet(
        f"QLineEdit{{background:#fff;color:{_C['text']};border:1px solid {_C['input_border']};"
        f"border-radius:6px;padding:5px 10px;font-size:12px;}}"
        f"QLineEdit:focus{{border-color:{_C['blue']};}}"
    )
    return e


def _hline() -> QLabel:
    s = QLabel(); s.setFixedHeight(1)
    s.setStyleSheet(f"background:{_C['border']};margin:4px 0;")
    return s


# ── ToggleRow：名称 + 当前值 + 按钮组 ───────────────────
class ToggleRow(QWidget):
    """一行：名称 | 当前值 | [选项1] [选项2]"""

    value_changed = Signal()

    def __init__(self, name: str, options: list[str], parent=None):
        super().__init__(parent)
        self._options = options
        self._original: Optional[str] = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(8)

        # 名称
        self._name_lbl = _lbl(name, w=110)
        lay.addWidget(self._name_lbl)

        # 当前值
        self._current_lbl = _lbl("—", w=80, dim=True)
        lay.addWidget(self._current_lbl)

        lay.addWidget(_lbl("→", w=16, dim=True))

        # 按钮组
        self._btns: list[QPushButton] = []
        for opt in options:
            btn = QPushButton(opt)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._btn_style(False))
            btn.clicked.connect(lambda _, b=btn, o=opt: self._on_click(b))
            lay.addWidget(btn)
            self._btns.append(btn)

        lay.addStretch()

    def set_current(self, value: str, mapping: dict[str, str] = None):
        """设置当前值显示。mapping: {内部值 → 显示文本}。"""
        self._original = value
        if mapping:
            display = mapping.get(value, value)
        else:
            display = value
        self._current_lbl.setText(display)
        # 自动选中对应的按钮
        for i, btn in enumerate(self._btns):
            btn.setChecked(False)
            btn.setStyleSheet(self._btn_style(False))
        # 如果当前值匹配某个选项，高亮它
        for i, opt in enumerate(self._options):
            if opt == display or (mapping and mapping.get(value) == opt):
                self._btns[i].setChecked(True)
                self._btns[i].setStyleSheet(self._btn_style(True))

    def _on_click(self, clicked_btn: QPushButton):
        for btn in self._btns:
            btn.setChecked(btn is clicked_btn)
            btn.setStyleSheet(self._btn_style(btn is clicked_btn))
        self._current_lbl.setStyleSheet(
            f"font-size:12px;color:{_C['blue']};background:transparent;font-weight:bold;")
        self.value_changed.emit()

    def get_selected(self) -> Optional[str]:
        for i, btn in enumerate(self._btns):
            if btn.isChecked():
                return self._options[i]
        return None

    def is_changed(self) -> bool:
        return self.get_selected() is not None and self.get_selected() != self._original

    def get_new_value(self) -> Optional[str]:
        """返回用户选择的新值（如果不同于原始值）。"""
        sel = self.get_selected()
        if sel is not None and sel != self._original:
            return sel
        return None

    @staticmethod
    def _btn_style(active: bool) -> str:
        if active:
            return ("QPushButton{background:#4a90d9;color:#fff;border:none;"
                    "border-radius:6px;padding:5px 14px;font-size:12px;font-weight:bold;}"
                    "QPushButton:hover{background:#3a7bc8;}")
        return ("QPushButton{background:#f5f5f5;color:#666;border:1px solid #e0e0e0;"
                "border-radius:6px;padding:5px 14px;font-size:12px;}"
                "QPushButton:hover{background:#e8e8e8;color:#333;}")


# ── EditRow：名称 + 当前值 + 输入框 ──────────────────────
class EditRow(QWidget):
    """一行：名称 | 当前值 | [输入框]"""

    value_changed = Signal()

    def __init__(self, name: str, placeholder: str = "", parent=None):
        super().__init__(parent)
        self._original: Optional[str] = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(8)

        self._name_lbl = _lbl(name, w=110)
        lay.addWidget(self._name_lbl)

        self._current_lbl = _lbl("—", w=80, dim=True)
        lay.addWidget(self._current_lbl)

        lay.addWidget(_lbl("→", w=16, dim=True))

        self._input = _input(placeholder)
        self._input.textChanged.connect(self._on_change)
        lay.addWidget(self._input, 1)
        lay.addStretch()

    def set_current(self, value: str):
        self._original = value
        self._current_lbl.setText(value if value else "—")
        self._input.setText("")

    def _on_change(self, text: str):
        if text and text != self._original:
            self._current_lbl.setStyleSheet(
                f"font-size:12px;color:{_C['blue']};background:transparent;font-weight:bold;")
        else:
            self._current_lbl.setStyleSheet(
                f"font-size:12px;color:{_C['dim']};background:transparent;")
        self.value_changed.emit()

    def get_new_value(self) -> Optional[str]:
        text = self._input.text().strip()
        if text and text != self._original:
            return text
        return None

    def is_changed(self) -> bool:
        return self.get_new_value() is not None


# ── LoaderThread：后台加载远程配置 ────────────────────────
class _LoaderThread(QThread):
    loaded = Signal(dict)  # {file_key: {key: value}}

    def __init__(self, ssh_client, source_path: str, parent=None):
        super().__init__(parent)
        self._ssh = ssh_client
        self._path = source_path
        self._logger = get_logger()

    def run(self):
        try:
            r = RemoteConfigReader(self._ssh, self._path)
            self._logger.info("开始加载远程配置: %s", self._path)
            data = {}

            # build_config.txt
            bc_keys = ["CTV_CFG_DOLBY", "CTV_CFG_MIRACAST", "CTV_CFG_HBG_XYDZ21001",
                       "CTV_CFG_TVCASTING", "CTV_CFG_ESHARE", "CTV_CFG_PANEL_BACKLIGHT_CURRENT",
                       "CTV_CFG_CUSTOMER"]
            data["build_config"] = r.read_build_config(bc_keys)
            self._logger.info("build_config: %s", data["build_config"])

            # db.ini
            data["db_ini"] = r.read_db_ini(["System_screencolor"])
            self._logger.info("db_ini: %s", data["db_ini"])

            # 白平衡
            data["color_temp"] = r.read_color_temp()
            self._logger.info("color_temp: %s", data["color_temp"])

            # NLA 参数
            nla_keys = [f"NlaInfo_{p}" for p in ("brightness", "contrast", "saturation", "sharpness", "hue", "backlight")]
            data["nla"] = r.read_db_ini(nla_keys)
            self._logger.info("nla: %s", data["nla"])

            # SatGain / HueGain / BriGain
            data["sat_gain"] = r.read_gain("SatGain")
            data["hue_gain"] = r.read_gain("HueGain")
            data["bri_gain"] = r.read_gain("BriGain")
            self._logger.info("gain: sat=%s hue=%s bri=%s", data["sat_gain"], data["hue_gain"], data["bri_gain"])

            # ctvbuild.prop
            data["prop"] = r.read_prop(["ro.product.powermode", "persist.sys.bootanimation.type"])
            self._logger.info("prop: %s", data["prop"])

            # ctv_data.xml
            data["ctv_data"] = r.read_ctv_data(["BootDesktop", "MenuShowTime", "LanguageShowCountry"])
            self._logger.info("ctv_data: %s", data["ctv_data"])

            # 默认语言
            data["language_first"] = r.read_language_first()
            self._logger.info("language_first: %s", data["language_first"])

            # CountryList
            data["country_list"] = r.read_country_list()
            self._logger.info("country_list: %d 个", len(data["country_list"]))

            # ctvsetting.xml
            en_names = ["tv kernel", "tv sdk", "tv resolution", "tv software", "tv hardware", "tv model", "tv bluetooth"]
            data["ctv_setting"] = r.read_ctv_setting(en_names)
            self._logger.info("ctv_setting: %s", data["ctv_setting"])

            # 预装
            data["preinstall"] = {"ESharePlus": r.read_preinstall("ESharePlus") or "—"}

            # 白名单
            data["whitelist"] = r.read_whitelist_packages()
            self._logger.info("whitelist: %d 个", len(data["whitelist"]))

            self._logger.info("远程配置加载完成")
            self.loaded.emit(data)
        except Exception as e:
            self._logger.error("加载远程配置失败: %s", e, exc_info=True)
            self.loaded.emit({})
            self.loaded.emit({})


# ── ManualPanel ───────────────────────────────────────────

class ManualPanel(QWidget):
    """手动模式面板：插件卡片 + 当前值 + 直接编辑。"""

    execute_requested = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._logger = get_logger()
        self._fm = self._load_mapping()
        self._current_data: dict = {}
        self._ssh = None
        self._source_path = ""
        self._build_ui()

    def _load_mapping(self) -> dict:
        p = Path("config/feature_mapping.json")
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    # ── 加载远程配置 ──

    def load_values(self, ssh_client, source_path: str):
        """异步加载远程配置值。"""
        self._ssh = ssh_client
        self._source_path = source_path
        self._loader = _LoaderThread(ssh_client, source_path, self)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, data: dict):
        self._current_data = data
        # 先过滤国家下拉（只保留 CountryList 中的国家）
        country_list = data.get("country_list", [])
        if country_list:
            self.filter_country_list(country_list)
        # 再填充所有当前值
        self._populate_values(data)

    # ── UI 构建 ──

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # 页码导航
        nav = QWidget(); nav.setStyleSheet("background:transparent;")
        nav_lay = QHBoxLayout(nav); nav_lay.setContentsMargins(0,4,0,4); nav_lay.setSpacing(6)

        self._page_defs = [
            ("build_config.txt", "功能开关 + 参数"),
            ("db.ini", "蓝屏 + 高级参数"),
            ("ctvbuild.prop", "上电/开机模式"),
            ("ctv_data.xml", "桌面/菜单/语言"),
            ("ctvsetting.xml", "菜单项"),
            ("whiteList.conf", "白名单"),
            ("build_ctv_app.txt", "预装应用"),
        ]
        self._nav_btns: list[QPushButton] = []
        for i, (fname, tip) in enumerate(self._page_defs):
            btn = QPushButton(f" {fname}")
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._nav_style(False))
            btn.clicked.connect(lambda _, idx=i: self._switch_page(idx))
            nav_lay.addWidget(btn)
            self._nav_btns.append(btn)
        nav_lay.addStretch()
        root.addWidget(nav)

        # 页面堆叠
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._build_page_build_config()
        self._build_page_db_ini()
        self._build_page_prop()
        self._build_page_ctv_data()
        self._build_page_ctv_setting()
        self._build_page_whitelist()
        self._build_page_preinstall()
        root.addWidget(self._stack, 1)

        # 底部按钮
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
            f"QTextEdit{{background:transparent;color:{_C['text']};border:1px solid {_C['input_border']};"
            f"border-radius:8px;padding:8px;font-family:Menlo,Consolas,monospace;font-size:12px;}}")
        root.addWidget(self._preview_edit)

        self._nav_btns[0].setStyleSheet(self._nav_style(True))

    def _nav_style(self, active: bool) -> str:
        if active:
            return ("QPushButton{background:#e0e0e0;color:#1a1a1a;border:none;border-radius:6px;"
                    "padding:6px 12px;font-size:11px;font-weight:bold;}"
                    "QPushButton:hover{background:#d5d5d5;}")
        return ("QPushButton{background:transparent;color:#888;border:1px solid #ddd;border-radius:6px;"
                "padding:6px 12px;font-size:11px;}"
                "QPushButton:hover{background:#f0f0f0;color:#1a1a1a;}")

    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setStyleSheet(self._nav_style(i == idx))

    # ── 页面构建 ──

    def _make_scroll(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        body = QWidget(); body.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(body); lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)
        scroll.setWidget(body)
        return scroll, lay

    # ── Page 1: build_config.txt ──
    def _build_page_build_config(self):
        scroll, lay = self._make_scroll()
        card = _card("build_config.txt", "路径: build_config.txt")
        gl = _card_layout(card, "build_config.txt", "路径: build_config.txt"); gl.setSpacing(2)

        self._bc_toggles: dict[str, ToggleRow] = {}
        fm_open = self._fm.get("open", {})
        for kw, info in fm_open.items():
            if info.get("file", "") == "build_config.txt":
                row = ToggleRow(kw, ["打开", "关闭"])
                gl.addWidget(row)
                self._bc_toggles[kw] = (row, info["key"])

        gl.addWidget(_hline())

        self._bc_current = EditRow("电流", "mA 数值")
        gl.addWidget(self._bc_current)

        self._bc_customer = EditRow("客户名称", "客户名")
        gl.addWidget(self._bc_customer)

        lay.addWidget(card)
        lay.addStretch()
        self._stack.addWidget(scroll)

    # ── Page 2: db.ini ──
    def _build_page_db_ini(self):
        scroll, lay = self._make_scroll()

        # 蓝屏
        card = _card("db.ini", "路径: configs/db.ini")
        gl = _card_layout(card, "db.ini", "路径: configs/db.ini"); gl.setSpacing(2)
        self._db_blue = ToggleRow("蓝屏", ["打开蓝屏", "关闭蓝屏"])
        gl.addWidget(self._db_blue)
        lay.addWidget(card)

        # 白平衡
        card2 = _card("白平衡", "FacColorTemp_*_nature 行，前6值 = R,G,B,R_O,G_O,B_O")
        gl2 = _card_layout(card2, "白平衡", "FacColorTemp_*_nature 行，前6值"); gl2.setSpacing(6)
        self._wb_rows: list[EditRow] = []
        for tag in ["R Gain", "G Gain", "B Gain", "R Offset", "G Offset", "B Offset"]:
            row = EditRow(tag, "数值")
            gl2.addWidget(row)
            self._wb_rows.append(row)
        lay.addWidget(card2)

        # NLA 非线性参数（6 组）
        card3 = _card("NLA 非线性参数", "NlaInfo_* 行，中间值（第3个）")
        gl3 = _card_layout(card3, "NLA 非线性参数", "NlaInfo_* 行，中间值"); gl3.setSpacing(2)
        self._nla_rows: dict[str, EditRow] = {}
        for param in ("brightness", "contrast", "saturation", "sharpness", "hue", "backlight"):
            row = EditRow(param, "中间值")
            gl3.addWidget(row)
            self._nla_rows[param] = row
        lay.addWidget(card3)

        # SatGain / HueGain / BriGain
        for gain_name in ("SatGain", "HueGain", "BriGain"):
            card_g = _card(gain_name, f"PQ_*_{gain_name} 行，前7值")
            gl_g = _card_layout(card_g, gain_name, f"PQ_*_{gain_name} 行，前7值"); gl_g.setSpacing(2)
            row = EditRow(gain_name, "7个逗号分隔值，如 3,3,-5,12,5,13,6")
            gl_g.addWidget(row)
            setattr(self, f"_gain_{gain_name.lower()}", row)
            lay.addWidget(card_g)

        lay.addStretch()
        self._stack.addWidget(scroll)

    # ── Page 3: ctvbuild.prop ──
    def _build_page_prop(self):
        scroll, lay = self._make_scroll()
        card = _card("ctvbuild.prop", "路径: ctvbuild.prop")
        gl = _card_layout(card, "ctvbuild.prop", "路径: ctvbuild.prop"); gl.setSpacing(2)

        self._prop_power = ToggleRow("上电模式", ["待机", "开机", "记忆"])
        gl.addWidget(self._prop_power)

        self._prop_boot = ToggleRow("开机模式", ["动画", "视频"])
        gl.addWidget(self._prop_boot)

        lay.addWidget(card)
        lay.addStretch()
        self._stack.addWidget(scroll)

    # ── Page 4: ctv_data.xml ──
    def _build_page_ctv_data(self):
        scroll, lay = self._make_scroll()
        card = _card("ctv_data.xml", "路径: overlay/.../ctv_data.xml")
        gl = _card_layout(card, "ctv_data.xml", "路径: overlay/.../ctv_data.xml"); gl.setSpacing(2)

        self._ctv_desktop = ToggleRow("开机桌面", ["安卓", "TV", "记忆"])
        gl.addWidget(self._ctv_desktop)

        self._ctv_menu_time = ToggleRow("菜单显示时间", ["一直显示", "5秒", "10秒", "20秒", "30秒", "60秒"])
        gl.addWidget(self._ctv_menu_time)

        self._ctv_lang = ToggleRow("语言显示国家", ["带国家", "不带国家"])
        gl.addWidget(self._ctv_lang)

        gl.addWidget(_hline())

        # 默认语言
        lang_combo = _combo(["(当前值)"])
        lang_map_path = Path("config/language_map.json")
        if lang_map_path.exists():
            for code, info in json.loads(lang_map_path.read_text(encoding="utf-8")).items():
                lang_combo.addItem(f"{info['name']} ({code})", code)
        self._ctv_lang_combo = lang_combo
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(_lbl("默认语言", w=110))
        row.addWidget(_lbl("当前:", w=36, dim=True))
        self._ctv_lang_current = _lbl("—", w=100, dim=True)
        row.addWidget(self._ctv_lang_current)
        row.addWidget(_lbl("→", w=16, dim=True))
        row.addWidget(lang_combo)
        gl.addLayout(row)

        # 默认国家
        country_combo = _combo(["(当前值)"])
        self._country_map: dict[str, str] = {}
        country_map_path = Path("config/country_map.json")
        if country_map_path.exists():
            self._country_map = json.loads(country_map_path.read_text(encoding="utf-8"))
            for code, name in self._country_map.items():
                country_combo.addItem(f"{name} ({code})", code)
        self._ctv_country_combo = country_combo
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(_lbl("默认国家", w=110))
        row.addWidget(_lbl("当前:", w=36, dim=True))
        self._ctv_country_current = _lbl("—", w=100, dim=True)
        row.addWidget(self._ctv_country_current)
        row.addWidget(_lbl("→", w=16, dim=True))
        row.addWidget(country_combo)
        gl.addLayout(row)

        lay.addWidget(card)
        lay.addStretch()
        self._stack.addWidget(scroll)

    # ── Page 5: ctvsetting.xml ──
    def _build_page_ctv_setting(self):
        scroll, lay = self._make_scroll()
        card = _card("ctvsetting.xml", "路径: configs/ctvsetting.xml")
        gl = _card_layout(card, "ctvsetting.xml", "路径: configs/ctvsetting.xml"); gl.setSpacing(2)

        menu_map = self._fm.get("ctv_setting_menu", {})
        self._ctv_menu_rows: dict[str, tuple[ToggleRow, str]] = {}
        for cn_name, entry in menu_map.items():
            en_name = entry.get("name", cn_name) if isinstance(entry, dict) else entry
            row = ToggleRow(cn_name, ["显示", "隐藏"])
            gl.addWidget(row)
            self._ctv_menu_rows[cn_name] = (row, en_name)

        lay.addWidget(card)
        lay.addStretch()
        self._stack.addWidget(scroll)

    # ── Page 6: whiteList.conf ──
    def _build_page_whitelist(self):
        scroll, lay = self._make_scroll()
        card = _card("whiteList.conf", "路径: etc/whiteList.conf")
        gl = _card_layout(card, "whiteList.conf", "路径: etc/whiteList.conf"); gl.setSpacing(6)

        self._wl_current_lbl = _lbl("当前白名单: 加载中…", dim=True)
        self._wl_current_lbl.setWordWrap(True)
        gl.addWidget(self._wl_current_lbl)

        gl.addWidget(_hline())

        self._wl_pkg = _input("包名，如 com.android.vending")
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(_lbl("包名", w=60))
        row.addWidget(self._wl_pkg, 1)
        gl.addLayout(row)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self._wl_add = QPushButton("  添加")
        self._wl_add.setStyleSheet(
            "QPushButton{background:#27ae60;color:#fff;border:none;border-radius:6px;padding:5px 14px;font-size:12px;}"
            "QPushButton:hover{background:#219a52;}")
        self._wl_remove = QPushButton("  移除")
        self._wl_remove.setStyleSheet(
            "QPushButton{background:#e74c3c;color:#fff;border:none;border-radius:6px;padding:5px 14px;font-size:12px;}"
            "QPushButton:hover{background:#c0392b;}")
        btn_row.addStretch()
        btn_row.addWidget(self._wl_add)
        btn_row.addWidget(self._wl_remove)
        gl.addLayout(btn_row)

        lay.addWidget(card)
        lay.addStretch()
        self._stack.addWidget(scroll)

    # ── Page 7: build_ctv_app.txt ──
    def _build_page_preinstall(self):
        scroll, lay = self._make_scroll()
        card = _card("build_ctv_app.txt", "路径: build_ctv_app.txt")
        gl = _card_layout(card, "build_ctv_app.txt", "路径: build_ctv_app.txt"); gl.setSpacing(2)

        self._pre_eshare = ToggleRow("ESharePlus", ["预装", "取消预装"])
        gl.addWidget(self._pre_eshare)

        lay.addWidget(card)
        lay.addStretch()
        self._stack.addWidget(scroll)

    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setStyleSheet(self._nav_style(i == idx))

    # ── 填充当前值 ──

    def _populate_values(self, data: dict):
        """用远程读取的数据填充所有行的当前值。"""
        # build_config.txt
        bc = data.get("build_config", {})
        for kw, (row, key) in self._bc_toggles.items():
            val = bc.get(key, "")
            display = "打开" if val.lower() == "y" else "关闭" if val.lower() == "n" else val or "—"
            row.set_current(display)

        val = bc.get("CTV_CFG_PANEL_BACKLIGHT_CURRENT", "")
        self._bc_current.set_current(val or "—")

        val = bc.get("CTV_CFG_CUSTOMER", "")
        self._bc_customer.set_current(val or "—")

        # db.ini
        db = data.get("db_ini", {})
        val = db.get("System_screencolor", "")
        bs_display = "打开蓝屏" if val == "1" else "关闭蓝屏" if val == "0" else val or "—"
        self._db_blue.set_current(bs_display)

        # prop
        prop = data.get("prop", {})
        val = prop.get("ro.product.powermode", "")
        pm_map = {"secondary": "待机", "direct": "开机", "memory": "记忆"}
        self._prop_power.set_current(pm_map.get(val, val or "—"))

        val = prop.get("persist.sys.bootanimation.type", "")
        bm_map = {"0": "动画", "1": "视频"}
        self._prop_boot.set_current(bm_map.get(val, val or "—"))

        # ctv_data
        ctd = data.get("ctv_data", {})
        val = ctd.get("BootDesktop", "")
        bd_map = {"0": "安卓", "1": "TV", "2": "记忆"}
        self._ctv_desktop.set_current(bd_map.get(val, val or "—"))

        val = ctd.get("MenuShowTime", "")
        mt_map = {"0": "一直显示", "1": "5秒", "2": "10秒", "3": "20秒", "4": "30秒", "5": "60秒"}
        self._ctv_menu_time.set_current(mt_map.get(val, val or "—"))

        val = ctd.get("LanguageShowCountry", "")
        lc_map = {"true": "带国家", "false": "不带国家"}
        self._ctv_lang.set_current(lc_map.get(val, val or "—"))

        # ctvsetting
        cs = data.get("ctv_setting", {})
        for cn_name, (row, en_name) in self._ctv_menu_rows.items():
            val = cs.get(en_name, "")
            cs_map = {"support": "显示", "hide": "隐藏"}
            row.set_current(cs_map.get(val, val or "—"))

        # 预装
        pi = data.get("preinstall", {})
        val = pi.get("ESharePlus", "—")
        pi_map = {"Y": "预装", "N": "取消预装"}
        self._pre_eshare.set_current(pi_map.get(val, val or "—"))

        # 白名单
        pkgs = data.get("whitelist", [])
        self._wl_current_lbl.setText(f"当前白名单 ({len(pkgs)} 个): {', '.join(pkgs[:10])}{'…' if len(pkgs) > 10 else ''}")

        # 默认语言（从 CtvLanguage.ini 第一行读取）
        lang_first = data.get("language_first", "")
        if lang_first:
            # CSV 格式: code,name,country → 显示 name (code)
            parts = [p.strip() for p in lang_first.split(",")]
            if len(parts) >= 2:
                self._ctv_lang_current.setText(f"{parts[1]} ({parts[0]})")
            else:
                self._ctv_lang_current.setText(lang_first)

        # 默认国家（CountryList 第一项）
        country_list = data.get("country_list", [])
        if country_list:
            first_code = country_list[0]
            name = self._country_map.get(first_code, first_code)
            self._ctv_country_current.setText(f"{name} ({first_code})")

        # NLA 当前值
        nla = data.get("nla", {})
        for param, row in self._nla_rows.items():
            key = f"NlaInfo_{param}"
            val = nla.get(key, "")
            if val:
                vals = [v.strip() for v in val.split(",")]
                mid = vals[2] if len(vals) > 2 else val
                row.set_current(mid)

        # 白平衡当前值
        ct = data.get("color_temp", "")
        if ct:
            vals = [v.strip() for v in ct.split(",")]
            labels = ["R Gain", "G Gain", "B Gain", "R Offset", "G Offset", "B Offset"]
            for i, row in enumerate(self._wb_rows):
                if i < len(vals):
                    row.set_current(vals[i])

        # Gain 当前值
        for gain_name, attr in [("SatGain", "_gain_satgain"), ("HueGain", "_gain_huegain"), ("BriGain", "_gain_brigain")]:
            row_widget = getattr(self, attr, None)
            if row_widget:
                val = data.get(gain_name.lower().replace("gain", "_gain"), "")
                if not val:
                    val = data.get(f"{gain_name.lower()}", "")
                if val:
                    row_widget.set_current(val)

    def filter_country_list(self, allowed_codes: list[str]) -> None:
        combo = self._ctv_country_combo
        combo.blockSignals(True); combo.clear(); combo.addItem("(当前值)")
        allowed = {c.upper() for c in allowed_codes}
        for code, name in self._country_map.items():
            if code.upper() in allowed:
                combo.addItem(f"{name} ({code})", code)
        combo.blockSignals(False)

    # ── 收集修改项 ──

    def collect_modifications(self) -> list[dict]:
        mods: list[dict] = []
        fm = self._fm

        # 功能开关（只收集有变化的）
        for kw, (row, key) in self._bc_toggles.items():
            if not row.is_changed():
                continue
            sel = row.get_selected()
            section = "open" if sel == "打开" else "close"
            info = fm.get(section, {}).get(kw)
            if info:
                t = "db_ini" if info["file"].startswith("configs/") else "build_config"
                e = {"type": t, "file": info["file"], "key": info["key"], "value": info["value"]}
                if t == "build_config": e["mode"] = "value"
                mods.append(e)

        # 电流
        v = self._bc_current.get_new_value()
        if v:
            mods.append({"type": "build_config", "file": "build_config.txt",
                         "key": "CTV_CFG_PANEL_BACKLIGHT_CURRENT", "value": v, "mode": "value_part"})

        # 客户
        v = self._bc_customer.get_new_value()
        if v:
            mods.append({"type": "build_config", "file": "build_config.txt",
                         "key": "CTV_CFG_CUSTOMER", "value": v, "mode": "value"})

        # 蓝屏（只收集有变化的）
        if self._db_blue.is_changed():
            sel = self._db_blue.get_selected()
            mods.append({"type": "db_ini", "file": "configs/db.ini", "key": "System_screencolor",
                         "value": "1" if sel == "打开蓝屏" else "0"})

        # 上电模式
        if self._prop_power.is_changed():
            sel = self._prop_power.get_selected()
            pm = {"待机": "secondary", "开机": "direct", "记忆": "memory"}
            mods.append({"type": "prop", "file": "ctvbuild.prop", "key": "ro.product.powermode", "value": pm.get(sel, sel)})

        # 开机模式
        if self._prop_boot.is_changed():
            sel = self._prop_boot.get_selected()
            bm = {"动画": "0", "视频": "1"}
            mods.append({"type": "prop", "file": "ctvbuild.prop", "key": "persist.sys.bootanimation.type", "value": bm.get(sel, sel)})

        # 开机桌面
        if self._ctv_desktop.is_changed():
            sel = self._ctv_desktop.get_selected()
            dm = {"安卓": "0", "TV": "1", "记忆": "2"}
            mods.append({"type": "ctv_data", "name": "BootDesktop", "value": dm.get(sel, sel)})

        # 菜单显示时间
        if self._ctv_menu_time.is_changed():
            sel = self._ctv_menu_time.get_selected()
            tm = {"一直显示": "0", "5秒": "1", "10秒": "2", "20秒": "3", "30秒": "4", "60秒": "5"}
            mods.append({"type": "ctv_data", "name": "MenuShowTime", "value": tm.get(sel, sel)})

        # 语言显示
        if self._ctv_lang.is_changed():
            sel = self._ctv_lang.get_selected()
            mods.append({"type": "ctv_data", "name": "LanguageShowCountry",
                         "value": "true" if sel == "带国家" else "false"})

        # 默认语言
        if self._ctv_lang_combo.currentIndex() > 0:
            code = self._ctv_lang_combo.currentData()
            if code:
                mods.append({"type": "language_first", "target": code})

        # 默认国家
        if self._ctv_country_combo.currentIndex() > 0:
            code = self._ctv_country_combo.currentData()
            if code:
                mods.append({"type": "country_list_first", "country_code": code})

        # 菜单项（只收集有变化的）
        for cn, (row, en) in self._ctv_menu_rows.items():
            if not row.is_changed():
                continue
            sel = row.get_selected()
            mods.append({"type": "ctv_setting", "name": en,
                         "enable": "support" if sel == "显示" else "hide",
                         "prefix": cn in ("蓝牙",)})

        # 预装（只收集有变化的）
        if self._pre_eshare.is_changed():
            sel = self._pre_eshare.get_selected()
            mods.append({"type": "preinstall", "app": "ESharePlus",
                         "enabled": sel == "预装"})

        # 白名单
        pkg = self._wl_pkg.text().strip()
        if pkg:
            if self._wl_add.isChecked():
                mods.append({"type": "whitelist", "package": pkg, "action": "add"})
            if self._wl_remove.isChecked():
                mods.append({"type": "whitelist", "package": pkg, "action": "remove"})

        # 白平衡
        wb_vals = [row.get_new_value() for row in self._wb_rows]
        wb_filled = [v for v in wb_vals if v]
        if wb_filled:
            if len(wb_filled) == 6:
                mods.append({"type": "color_temp", "values": wb_filled})
            elif len(wb_filled) >= 3 and all(wb_vals[i] for i in range(3)):
                mods.append({"type": "color_temp", "values": [wb_vals[i] for i in range(3)]})

        # NLA
        for param, row in self._nla_rows.items():
            v = row.get_new_value()
            if v:
                mods.append({"type": "nla", "param": param, "value": v, "position": 2})

        # Gain
        for gain_name in ("SatGain", "HueGain", "BriGain"):
            row_widget = getattr(self, f"_gain_{gain_name.lower()}", None)
            if row_widget:
                v = row_widget.get_new_value()
                if v:
                    vals = [x.strip() for x in v.split(",")]
                    if len(vals) >= 7:
                        mods.append({"type": "gain", "name": gain_name, "values": vals[:7]})

        return mods

    def _on_preview(self):
        mods = self.collect_modifications()
        if not mods:
            self._preview_edit.setPlainText("未做任何修改。"); return
        lines = [f"共 {len(mods)} 条修改:"]
        for i, m in enumerate(mods, 1):
            lines.append(f"  {i}. {json.dumps(m, ensure_ascii=False)}")
        self._preview_edit.setPlainText("\n".join(lines))

    def _on_execute(self):
        mods = self.collect_modifications()
        if not mods:
            from PySide6.QtWidgets import QMessageBox
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("提示")
            box.setText("未做任何修改，请先修改至少一项设置。")
            box.setStyleSheet(
                "QMessageBox{background:#ffffff;}"
                "QMessageBox QLabel{color:#1a1a1a;background:transparent;}"
                "QPushButton{background:#e0e0e0;color:#1a1a1a;border:none;border-radius:6px;padding:6px 18px;}")
            box.exec()
            return
        self._logger.info("手动模式执行: %d 条修改", len(mods))
        self._show_progress("正在执行修改…")
        # 用 QTimer 让进度浮层先渲染出来，再执行耗时操作
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.execute_requested.emit(mods))

    def _show_progress(self, text: str):
        """显示半透明进度浮层。"""
        if hasattr(self, '_progress_overlay') and self._progress_overlay:
            self._progress_overlay.close()
            self._progress_overlay.deleteLater()

        overlay = QWidget(self)
        overlay.setObjectName("progressOverlay")
        overlay.setStyleSheet("QWidget#progressOverlay { background: rgba(0,0,0,0.3); }")
        overlay.setGeometry(self.rect())

        # 居中卡片
        card = QWidget(overlay)
        card.setStyleSheet("QWidget { background: #ffffff; border-radius: 12px; }")
        card_w, card_h = 280, 100
        card.setGeometry(
            (self.width() - card_w) // 2, (self.height() - card_h) // 2,
            card_w, card_h
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(10)

        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 13px; color: #1a1a1a; background: transparent;")
        cl.addWidget(lbl)

        from PySide6.QtWidgets import QProgressBar
        bar = QProgressBar()
        bar.setRange(0, 0)  # 不确定进度模式（转圈）
        bar.setStyleSheet(
            "QProgressBar { border: 1px solid #e0e0e0; border-radius: 4px; background: #f0f0f0; height: 8px; }"
            "QProgressBar::chunk { background: #4a90d9; border-radius: 4px; }"
        )
        cl.addWidget(bar)

        overlay.show()
        self._progress_overlay = overlay

    def hide_progress(self):
        """隐藏进度浮层。"""
        if hasattr(self, '_progress_overlay') and self._progress_overlay:
            self._progress_overlay.close()
            self._progress_overlay.deleteLater()
            self._progress_overlay = None
