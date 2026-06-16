"""手动修改面板 — 直接选择修改项，无需 AI 分析。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QScrollArea,
    QSpinBox,
    QTabWidget,
)

from config.logging_setup import get_logger


class ManualPanel(QWidget):
    """手动修改面板：直接选择修改项并执行。"""

    # Signal: 发射收集到的 modifications 列表
    execute_requested = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._logger = get_logger()
        self._feature_mapping = self._load_mapping()
        self._build_ui()

    def _load_mapping(self) -> dict:
        path = Path("config/feature_mapping.json")
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title = QLabel("🔧 手动修改 — 直接选择修改项")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a1a1a; background: transparent;")
        outer_layout.addWidget(title)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        main_layout = QVBoxLayout(container)

        # Tab 分类
        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # ---- Tab 1: 开关类 ----
        tabs.addTab(self._build_switches_tab(), "开关")

        # ---- Tab 2: 参数类 ----
        tabs.addTab(self._build_params_tab(), "参数")

        # ---- Tab 3: 下拉选择类 ----
        tabs.addTab(self._build_options_tab(), "选项")

        # ---- Tab 4: 高级（白平衡/非线性/Gain）----
        tabs.addTab(self._build_advanced_tab(), "高级")

        # ---- 执行按钮 ----
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._preview_btn = QPushButton("  预览修改项")
        self._preview_btn.setIcon(qta.icon("fa5s.eye", color="#888888"))
        self._preview_btn.clicked.connect(self._on_preview)
        btn_layout.addWidget(self._preview_btn)

        self._execute_btn = QPushButton("  执行修改")
        self._execute_btn.setIcon(qta.icon("fa5s.play-circle", color="#1a1a1a"))
        self._execute_btn.setStyleSheet(
            "QPushButton { background-color: #e0e0e0; color: #1a1a1a; padding: 10px 24px; "
            "font-size: 14px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #d5d5d5; }"
            "QPushButton:pressed { background-color: #cccccc; }"
        )
        self._execute_btn.clicked.connect(self._on_execute)
        btn_layout.addWidget(self._execute_btn)

        main_layout.addLayout(btn_layout)

        # 预览区
        self._preview_edit = QTextEdit()
        self._preview_edit.setReadOnly(True)
        self._preview_edit.setMaximumHeight(120)
        self._preview_edit.setPlaceholderText("点击「预览修改项」查看将要执行的修改…")
        main_layout.addWidget(self._preview_edit)

    # ========== Tab 1: 开关类 ==========

    def _build_switches_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        # build_config 开关
        group1 = QGroupBox("build_config.txt 开关")
        g1_layout = QVBoxLayout(group1)
        self._switches: dict[str, QCheckBox] = {}
        for keyword in ["杜比", "miracast", "HBG", "TVcasting", "ESHARE"]:
            cb = QCheckBox(keyword)
            cb.setToolTip(f"打开/关闭 {keyword}")
            g1_layout.addWidget(cb)
            self._switches[keyword] = cb
        layout.addWidget(group1)

        # 蓝屏开关
        group2 = QGroupBox("蓝屏开关 (db.ini)")
        g2_layout = QVBoxLayout(group2)
        self._blue_screen_combo = QComboBox()
        self._blue_screen_combo.addItems(["不修改", "打开蓝屏 (1)", "关闭蓝屏 (0)"])
        g2_layout.addWidget(self._blue_screen_combo)
        layout.addWidget(group2)

        # 预装应用
        group3 = QGroupBox("预装应用 (build_ctv_app.txt)")
        g3_layout = QVBoxLayout(group3)
        self._preinstall_combo = QComboBox()
        self._preinstall_combo.addItems(["不修改", "预装 ESharePlus (Y)", "取消预装 ESharePlus (n)"])
        g3_layout.addWidget(self._preinstall_combo)
        layout.addWidget(group3)

        # 白名单
        group4 = QGroupBox("白名单 (whiteList.conf)")
        g4_layout = QVBoxLayout(group4)
        pkg_row = QHBoxLayout()
        pkg_row.addWidget(QLabel("包名:"))
        self._pkg_input = QLineEdit()
        self._pkg_input.setPlaceholderText("例如: com.android.vending")
        pkg_row.addWidget(self._pkg_input, 1)
        g4_layout.addLayout(pkg_row)
        action_row = QHBoxLayout()
        self._pkg_add = QCheckBox("添加")
        self._pkg_remove = QCheckBox("删除")
        action_row.addWidget(self._pkg_add)
        action_row.addWidget(self._pkg_remove)
        action_row.addStretch()
        g4_layout.addLayout(action_row)
        layout.addWidget(group4)

        # 菜单项
        group5 = QGroupBox("菜单项隐藏/显示 (ctvsetting.xml)")
        g5_layout = QVBoxLayout(group5)
        self._menu_combos: dict[str, QComboBox] = {}
        menu_map = self._feature_mapping.get("ctv_setting_menu", {})
        for cn_name, en_name in menu_map.items():
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{cn_name} ({en_name}):"))
            combo = QComboBox()
            combo.addItems(["不修改", "显示 (support)", "隐藏 (hide)"])
            row.addWidget(combo, 1)
            g5_layout.addLayout(row)
            self._menu_combos[cn_name] = combo
        layout.addWidget(group5)

        layout.addStretch()
        return page

    # ========== Tab 2: 参数类 ==========

    def _build_params_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        # 电流
        group1 = QGroupBox("电流 (build_config.txt)")
        g1_layout = QVBoxLayout(group1)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("CTV_CFG_PANEL_BACKLIGHT_CURRENT:"))
        self._current_input = QSpinBox()
        self._current_input.setRange(0, 9999)
        self._current_input.setSpecialValueText("不修改")
        self._current_input.setValue(0)
        row1.addWidget(self._current_input)
        g1_layout.addLayout(row1)
        layout.addWidget(group1)

        # 客户名称
        group2 = QGroupBox("客户名称 (build_config.txt)")
        g2_layout = QVBoxLayout(group2)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("CTV_CFG_CUSTOMER:"))
        self._customer_input = QLineEdit()
        self._customer_input.setPlaceholderText("不修改则留空")
        row2.addWidget(self._customer_input, 1)
        g2_layout.addLayout(row2)
        layout.addWidget(group2)

        layout.addStretch()
        return page

    # ========== Tab 3: 下拉选项类 ==========

    def _build_options_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        # 上电模式
        group1 = QGroupBox("上电模式 (ctvbuild.prop)")
        g1_layout = QVBoxLayout(group1)
        self._power_mode_combo = QComboBox()
        self._power_mode_combo.addItems(["不修改", "待机 (secondary)", "开机 (direct)", "记忆 (memory)"])
        g1_layout.addWidget(self._power_mode_combo)
        layout.addWidget(group1)

        # 开机模式
        group2 = QGroupBox("开机模式 (ctvbuild.prop)")
        g2_layout = QVBoxLayout(group2)
        self._boot_mode_combo = QComboBox()
        self._boot_mode_combo.addItems(["不修改", "动画 (0)", "视频 (1)"])
        g2_layout.addWidget(self._boot_mode_combo)
        layout.addWidget(group2)

        # 开机桌面
        group3 = QGroupBox("开机桌面 (ctv_data.xml)")
        g3_layout = QVBoxLayout(group3)
        self._boot_desktop_combo = QComboBox()
        self._boot_desktop_combo.addItems(["不修改", "安卓 (0)", "TV (1)", "记忆 (2)"])
        g3_layout.addWidget(self._boot_desktop_combo)
        layout.addWidget(group3)

        # 菜单显示时间
        group4 = QGroupBox("菜单显示时间 (ctv_data.xml)")
        g4_layout = QVBoxLayout(group4)
        self._menu_time_combo = QComboBox()
        self._menu_time_combo.addItems(["不修改", "一直显示 (0)", "5秒 (1)", "10秒 (2)", "20秒 (3)", "30秒 (4)", "60秒 (5)"])
        g4_layout.addWidget(self._menu_time_combo)
        layout.addWidget(group4)

        # 语言显示
        group5 = QGroupBox("语言显示国家 (ctv_data.xml)")
        g5_layout = QVBoxLayout(group5)
        self._lang_country_combo = QComboBox()
        self._lang_country_combo.addItems(["不修改", "带国家 (true)", "不带国家 (false)"])
        g5_layout.addWidget(self._lang_country_combo)
        layout.addWidget(group5)

        # 默认语言
        group6 = QGroupBox("默认语言 (CtvLanguage.ini)")
        g6_layout = QVBoxLayout(group6)
        self._default_lang_combo = QComboBox()
        self._default_lang_combo.addItem("不修改")
        lang_map_path = Path("config/language_map.json")
        if lang_map_path.exists():
            with open(lang_map_path, encoding="utf-8") as f:
                lang_map = json.load(f)
            for code, info in lang_map.items():
                self._default_lang_combo.addItem(f"{info['name']} ({code})", code)
        g6_layout.addWidget(self._default_lang_combo)
        layout.addWidget(group6)

        # 默认国家
        group7 = QGroupBox("默认国家 (ctv_data.xml CountryList)")
        g7_layout = QVBoxLayout(group7)
        self._default_country_combo = QComboBox()
        self._default_country_combo.addItem("不修改")
        country_map_path = Path("config/country_map.json")
        if country_map_path.exists():
            with open(country_map_path, encoding="utf-8") as f:
                country_map = json.load(f)
            for code, name in country_map.items():
                self._default_country_combo.addItem(f"{name} ({code})", code)
        g7_layout.addWidget(self._default_country_combo)
        layout.addWidget(group7)

        layout.addStretch()
        return page

    # ========== Tab 4: 高级 ==========

    def _build_advanced_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        # 白平衡
        group1 = QGroupBox("白平衡 (db.ini nature 行)")
        g1_layout = QVBoxLayout(group1)
        g1_layout.addWidget(QLabel("R Gain / G Gain / B Gain / R Offset / G Offset / B Offset"))
        wb_row = QHBoxLayout()
        self._wb_inputs: list[QSpinBox] = []
        for label in ["R", "G", "B", "R_O", "G_O", "B_O"]:
            sp = QSpinBox()
            sp.setRange(0, 999)
            sp.setSpecialValueText("--")
            sp.setPrefix(f"{label}:")
            sp.setMinimumWidth(70)
            wb_row.addWidget(sp)
            self._wb_inputs.append(sp)
        g1_layout.addLayout(wb_row)
        layout.addWidget(group1)

        # NLA 非线性参数
        group2 = QGroupBox("NLA 非线性参数 (db.ini)")
        g2_layout = QVBoxLayout(group2)
        nla_row = QHBoxLayout()
        nla_row.addWidget(QLabel("参数:"))
        self._nla_param_combo = QComboBox()
        self._nla_param_combo.addItems(["brightness", "contrast", "saturation", "sharpness", "hue", "backlight"])
        nla_row.addWidget(self._nla_param_combo)
        nla_row.addWidget(QLabel("中间值:"))
        self._nla_value_input = QSpinBox()
        self._nla_value_input.setRange(0, 999)
        self._nla_value_input.setSpecialValueText("--")
        nla_row.addWidget(self._nla_value_input)
        g2_layout.addLayout(nla_row)
        layout.addWidget(group2)

        # SatGain / HueGain / BriGain
        for gain_name in ["SatGain", "HueGain", "BriGain"]:
            group = QGroupBox(f"{gain_name} (db.ini 前7值)")
            g_layout = QVBoxLayout(group)
            row = QHBoxLayout()
            inputs: list[QSpinBox] = []
            for i in range(7):
                sp = QSpinBox()
                sp.setRange(-99, 99)
                sp.setSpecialValueText("--")
                sp.setMinimumWidth(55)
                row.addWidget(sp)
                inputs.append(sp)
            g_layout.addLayout(row)
            layout.addWidget(group)
            if gain_name == "SatGain":
                self._sat_gain_inputs = inputs
            elif gain_name == "HueGain":
                self._hue_gain_inputs = inputs
            else:
                self._bri_gain_inputs = inputs

        layout.addStretch()
        return page

    # ========== 收集修改项 ==========

    def collect_modifications(self) -> list[dict]:
        """收集界面上所有选中的修改项。"""
        mods: list[dict] = []

        # --- 开关类 ---
        mapping = self._feature_mapping
        for keyword, cb in self._switches.items():
            if not cb.isChecked():
                continue
            # 默认打开，后面可以用三态复选框改进
            mod_info = mapping.get("open", {}).get(keyword)
            if mod_info:
                mod_type = "db_ini" if mod_info["file"].startswith("configs/") else "build_config"
                entry = {"type": mod_type, "file": mod_info["file"], "key": mod_info["key"], "value": mod_info["value"]}
                if mod_type == "build_config":
                    entry["mode"] = "value"
                mods.append(entry)

        # --- 蓝屏 ---
        bs_idx = self._blue_screen_combo.currentIndex()
        if bs_idx == 1:
            mods.append({"type": "db_ini", "file": "configs/db.ini", "key": "System_screencolor", "value": "1"})
        elif bs_idx == 2:
            mods.append({"type": "db_ini", "file": "configs/db.ini", "key": "System_screencolor", "value": "0"})

        # --- 预装 ---
        pi_idx = self._preinstall_combo.currentIndex()
        if pi_idx == 1:
            mods.append({"type": "preinstall", "app": "ESharePlus", "enabled": True})
        elif pi_idx == 2:
            mods.append({"type": "preinstall", "app": "ESharePlus", "enabled": False})

        # --- 白名单 ---
        pkg = self._pkg_input.text().strip()
        if pkg:
            if self._pkg_add.isChecked():
                mods.append({"type": "whitelist", "package": pkg, "action": "add"})
            if self._pkg_remove.isChecked():
                mods.append({"type": "whitelist", "package": pkg, "action": "remove"})

        # --- 菜单项 ---
        for cn_name, combo in self._menu_combos.items():
            idx = combo.currentIndex()
            if idx == 0:
                continue
            en_name = mapping.get("ctv_setting_menu", {}).get(cn_name, cn_name)
            enable = "support" if idx == 1 else "hide"
            prefix = cn_name in ("蓝牙",)
            mods.append({"type": "ctv_setting", "name": en_name, "enable": enable, "prefix": prefix})

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

        # --- 语言显示 ---
        lc_idx = self._lang_country_combo.currentIndex()
        if lc_idx == 1:
            mods.append({"type": "ctv_data", "name": "LanguageShowCountry", "value": "true"})
        elif lc_idx == 2:
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
            # 只有前3个有值 → 3值模式，否则6值模式
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

        # --- SatGain ---
        sat_vals = [str(sp.value()) for sp in self._sat_gain_inputs if sp.value() != 0]
        if len(sat_vals) == 7:
            mods.append({"type": "gain", "name": "SatGain", "values": sat_vals})

        # --- HueGain ---
        hue_vals = [str(sp.value()) for sp in self._hue_gain_inputs if sp.value() != 0]
        if len(hue_vals) == 7:
            mods.append({"type": "gain", "name": "HueGain", "values": hue_vals})

        # --- BriGain ---
        bri_vals = [str(sp.value()) for sp in self._bri_gain_inputs if sp.value() != 0]
        if len(bri_vals) == 7:
            mods.append({"type": "gain", "name": "BriGain", "values": bri_vals})

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
