"""规则管理面板 —— 展示所有已实现的修改规则，支持复制为自定义规则。"""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFormLayout, QGroupBox, QListView,
    QScrollArea,
)
from PySide6.QtCore import Qt

from rules.custom_rule_manager import load_rules, save_rule, delete_rule

# ── 所有已实现的规则定义 ─────────────────────────────────
ALL_RULES = [
    {
        "name": "DB INI 修改",
        "rule_type": "db_ini",
        "desc": "修改 configs/db.ini 中的键值对",
        "file": "configs/db.ini",
        "trigger": "自动匹配 db.ini 中的 Key",
        "example": "修改 configs/db.ini 中 Key = Value",
        "params": {
            "file": "configs/db.ini",
            "key": "键名",
            "value": "值"
        }
    },
    {
        "name": "属性修改 (prop)",
        "rule_type": "prop",
        "desc": "修改 ctvbuild.prop 中的属性值",
        "file": "ctvbuild.prop",
        "trigger": "自动匹配属性名",
        "example": "默认音量 45\n→ ctvbuild.prop\n→ ro.config.media_vol_default=45",
        "params": {
            "file": "ctvbuild.prop",
            "key": "属性名",
            "value": "值"
        }
    },
    {
        "name": "Build Config 修改",
        "rule_type": "build_config",
        "desc": "修改 build_config.txt 中的键值对",
        "file": "build_config.txt",
        "trigger": "自动匹配配置项",
        "example": "电流 550\n→ build_config.txt\n→ CTV_CFG_PANEL_BACKLIGHT_CURRENT = 600/900\n  只改 / 前面 → 550/900\n\n/ 后面的值由版型决定（900或700等），自动保留",
        "params": {
            "file": "build_config.txt",
            "key": "键名",
            "value": "值"
        }
    },
    {
        "name": "CTV Data 修改",
        "rule_type": "ctv_data",
        "desc": "修改 ctv_data.xml 中的配置节点值",
        "file": "overlay/.../ctv_data.xml",
        "trigger": "自动匹配配置名",
        "example": "打开蓝屏\n→ ctv_data.xml\n→ BlueScreenEnable = true",
        "params": {
            "name": "节点名",
            "value": "值"
        }
    },
    {
        "name": "CTV Data Ensure",
        "rule_type": "ctv_data",
        "desc": "确保节点存在，不存在则添加到 <customized> 第一行",
        "file": "overlay/.../ctv_data.xml",
        "trigger": "自动（如 FakeInfoEnable）",
        "example": "自动检查 FakeInfoEnable\n→ 不存在时添加:\n<!-- 自定义信息FakeInfoEnable -->\n<data name=\"FakeInfoEnable\" value=\"true\"/>",
        "params": {
            "name": "节点名",
            "value": "默认值"
        }
    },
    {
        "name": "功能开关：HBG",
        "rule_type": "build_config",
        "desc": "打开/关闭 HBG",
        "file": "build_config.txt",
        "trigger": "关键词：打开HBG / 关闭HBG",
        "example": "打开HBG → build_config.txt\n→ CTV_CFG_HBG_XYDZ21001 = y",
        "params": {
            "file": "build_config.txt",
            "key": "CTV_CFG_HBG_XYDZ21001",
            "value": "y(开) / (关)"
        }
    },
    {
        "name": "功能开关：TVcasting",
        "rule_type": "build_config",
        "desc": "打开/关闭 TVcasting",
        "file": "build_config.txt",
        "trigger": "关键词：打开TVcasting / 关闭TVcasting",
        "example": "打开TVcasting → build_config.txt\n→ CTV_CFG_TVCASTING = y\n关闭TVcasting → build_config.txt\n→ CTV_CFG_TVCASTING = n",
        "params": {
            "file": "build_config.txt",
            "key": "CTV_CFG_TVCASTING",
            "value": "y(开) / n(关)"
        }
    },
    {
        "name": "功能开关：eshare",
        "rule_type": "build_config",
        "desc": "打开/关闭 eshare",
        "file": "build_config.txt",
        "trigger": "关键词：打开eshare / 关闭eshare",
        "example": "打开eshare → build_config.txt\n→ CTV_CFG_ESHARE = y\n关闭eshare → build_config.txt\n→ CTV_CFG_ESHARE = n",
        "params": {
            "file": "build_config.txt",
            "key": "CTV_CFG_ESHARE",
            "value": "y(开) / n(关)"
        }
    },
    {
        "name": "功能开关：miracast",
        "rule_type": "build_config",
        "desc": "打开/关闭 miracast",
        "file": "build_config.txt",
        "trigger": "关键词：打开miracast / 关闭miracast",
        "example": "打开miracast → build_config.txt\n→ CTV_CFG_MIRACAST = y\n关闭miracast → build_config.txt\n→ CTV_CFG_MIRACAST = n",
        "params": {
            "file": "build_config.txt",
            "key": "CTV_CFG_MIRACAST",
            "value": "y(开) / n(关)"
        }
    },
    {
        "name": "功能开关：杜比",
        "rule_type": "build_config",
        "desc": "打开/关闭 杜比",
        "file": "build_config.txt",
        "trigger": "关键词：打开杜比 / 关闭杜比",
        "example": "打开杜比 → build_config.txt\n→ CTV_CFG_DOLBY = y\n关闭杜比 → build_config.txt\n→ CTV_CFG_DOLBY = n",
        "params": {
            "file": "build_config.txt",
            "key": "CTV_CFG_DOLBY",
            "value": "y(开) / n(关)"
        }
    },
    {
        "name": "功能开关：蓝屏",
        "rule_type": "db_ini",
        "desc": "打开/关闭 蓝屏",
        "file": "configs/db.ini",
        "trigger": "关键词：打开蓝屏 / 关闭蓝屏",
        "example": "打开蓝屏 → configs/db.ini\n→ System_screencolor = 1\n关闭蓝屏 → configs/db.ini\n→ System_screencolor = 0",
        "params": {
            "file": "configs/db.ini",
            "key": "System_screencolor",
            "value": "1(开) / 0(关)"
        }
    },
    {
        "name": "参数修改：电流",
        "rule_type": "build_config",
        "desc": "修改 build_config.txt 中 CTV_CFG_PANEL_BACKLIGHT_CURRENT",
        "file": "build_config.txt",
        "trigger": "关键词：电流 + 数值",
        "example": "电流 550\n→ build_config.txt\n→ CTV_CFG_PANEL_BACKLIGHT_CURRENT = 600/900\n  只改 / 前面 → 550/900\n\n/ 后面的值由版型决定（900或700等），自动保留",
        "params": {
            "file": "build_config.txt",
            "key": "CTV_CFG_PANEL_BACKLIGHT_CURRENT",
            "value": "数值"
        }
    },
    {
        "name": "参数修改：客户",
        "rule_type": "build_config",
        "desc": "修改 build_config.txt 中 CTV_CFG_CUSTOMER",
        "file": "build_config.txt",
        "trigger": "关键词：客户 + 数值",
        "example": "客户 550\n→ build_config.txt\n→ CTV_CFG_CUSTOMER = 550",
        "params": {
            "file": "build_config.txt",
            "key": "CTV_CFG_CUSTOMER",
            "value": "数值"
        }
    },
    {
        "name": "属性：上电模式",
        "rule_type": "prop",
        "desc": "修改 ro.product.powermode",
        "file": "ctvbuild.prop",
        "trigger": "关键词：上电模式",
        "example": "上电模式 待机 → ctvbuild.prop\n→ ro.product.powermode=secondary\n---\n上电模式 开机 → ctvbuild.prop\n→ ro.product.powermode=direct\n---\n上电模式 记忆 → ctvbuild.prop\n→ ro.product.powermode=memory",
        "params": {
            "file": "ctvbuild.prop",
            "key": "ro.product.powermode",
            "value": "待机→secondary / 开机→direct / 记忆→memory"
        }
    },
    {
        "name": "属性：开机模式",
        "rule_type": "prop",
        "desc": "修改 persist.sys.bootanimation.type",
        "file": "ctvbuild.prop",
        "trigger": "关键词：开机模式",
        "example": "开机模式 动画 → ctvbuild.prop\n→ persist.sys.bootanimation.type=0\n---\n开机模式 视频 → ctvbuild.prop\n→ persist.sys.bootanimation.type=1",
        "params": {
            "file": "ctvbuild.prop",
            "key": "persist.sys.bootanimation.type",
            "value": "动画→0 / 视频→1"
        }
    },
    {
        "name": "CTV Data：开机桌面",
        "rule_type": "ctv_data",
        "desc": "修改 BootDesktop",
        "file": "overlay/.../ctv_data.xml",
        "trigger": "关键词：开机桌面",
        "example": "开机桌面 安卓 → ctv_data.xml\n→ BootDesktop = 0\n---\n开机桌面 TV → ctv_data.xml\n→ BootDesktop = 1\n---\n开机桌面 记忆 → ctv_data.xml\n→ BootDesktop = 2",
        "params": {
            "name": "BootDesktop",
            "value": "安卓→0 / TV→1 / 记忆→2"
        }
    },
    {
        "name": "CTV Data：菜单显示时间",
        "rule_type": "ctv_data",
        "desc": "修改 MenuShowTime",
        "file": "overlay/.../ctv_data.xml",
        "trigger": "关键词：菜单显示时间",
        "example": "菜单显示时间 一直显示 → ctv_data.xml\n→ MenuShowTime = 0\n---\n菜单显示时间 5秒 → ctv_data.xml\n→ MenuShowTime = 1\n---\n菜单显示时间 10秒 → ctv_data.xml\n→ MenuShowTime = 2\n---\n菜单显示时间 20秒 → ctv_data.xml\n→ MenuShowTime = 3\n---\n菜单显示时间 30秒 → ctv_data.xml\n→ MenuShowTime = 4\n---\n菜单显示时间 60秒 → ctv_data.xml\n→ MenuShowTime = 5",
        "params": {
            "name": "MenuShowTime",
            "value": "一直显示→0 / 5秒→1 / 10秒→2 / 20秒→3 / 30秒→4 / 60秒→5"
        }
    },
    {
        "name": "CTV Data：语言显示",
        "rule_type": "ctv_data",
        "desc": "修改 LanguageShowCountry",
        "file": "overlay/.../ctv_data.xml",
        "trigger": "关键词：语言显示",
        "example": "语言显示 带国家 → ctv_data.xml\n→ LanguageShowCountry = true\n---\n语言显示 不带国家 → ctv_data.xml\n→ LanguageShowCountry = false",
        "params": {
            "name": "LanguageShowCountry",
            "value": "带国家→true / 不带国家→false"
        }
    },
    {
        "name": "CTV Data：虚假信息显示",
        "rule_type": "ctv_data",
        "desc": "修改 FakeInfoEnable",
        "file": "overlay/.../ctv_data.xml",
        "trigger": "关键词：虚假信息显示",
        "example": "虚假信息显示 打开 → ctv_data.xml\n→ FakeInfoEnable = true\n---\n虚假信息显示 关闭 → ctv_data.xml\n→ FakeInfoEnable = false",
        "params": {
            "name": "FakeInfoEnable",
            "value": "打开→true / 关闭→false"
        }
    },
    {
        "name": "白名单添加",
        "rule_type": "whitelist",
        "desc": "向 etc/whiteList.conf 添加包名",
        "file": "etc/whiteList.conf",
        "trigger": "关键词：白名单",
        "example": "添加 chrome 白名单\n→ etc/whiteList.conf\n→ com.android.chrome",
        "params": {
            "package": "包名",
            "action": "add"
        }
    },
    {
        "name": "白名单移除",
        "rule_type": "whitelist",
        "desc": "从 etc/whiteList.conf 移除包名",
        "file": "etc/whiteList.conf",
        "trigger": "关键词：白名单移除",
        "example": "移除 chrome 白名单\n→ etc/whiteList.conf\n→ 删除 com.android.chrome",
        "params": {
            "package": "包名",
            "action": "remove"
        }
    },
    {
        "name": "预装应用",
        "rule_type": "preinstall",
        "desc": "控制 build_ctv_app.txt 中应用预装状态",
        "file": "build_ctv_app.txt",
        "trigger": "关键词：预装",
        "example": "预装 ESharePlus\n→ build_ctv_app.txt\n→ ESharePlus = Y",
        "params": {
            "app": "应用名",
            "enabled": "true/false"
        }
    },
    {
        "name": "国家列表置顶",
        "rule_type": "country_list_first",
        "desc": "将国家码移到 CountryList 第一位并去重",
        "file": "overlay/.../ctv_data.xml",
        "trigger": "关键词：默认国家",
        "example": "默认国家 AE\n→ CountryList 第一位改为 AE\n→ AE, CN, IN, ...",
        "params": {
            "country_code": "国家码"
        }
    },
    {
        "name": "默认语言 (置顶)",
        "rule_type": "language_first",
        "desc": "将语言移到 CtvLanguage.ini 第一行",
        "file": "configs/CtvLanguage.ini",
        "trigger": "关键词：默认语言",
        "example": "默认语言 en-GB\n→ CtvLanguage.ini 第一行\n→ en-GB, English, United Kingdom",
        "params": {
            "target": "语言码"
        }
    },
    {
        "name": "添加语言",
        "rule_type": "language_add",
        "desc": "向 CtvLanguage.ini 末尾添加新语言",
        "file": "configs/CtvLanguage.ini",
        "trigger": "关键词：添加语言",
        "example": "添加越南语\n→ CtvLanguage.ini 末尾\n→ vi-VN, Vietnamese, Vietnam",
        "params": {
            "target": "语言码"
        }
    },
    {
        "name": "色温调整 (白平衡)",
        "rule_type": "color_temp",
        "desc": "修改 db.ini 中所有 FacColorTemp_*_nature 行",
        "file": "configs/db.ini",
        "trigger": "关键词：W/B、白平衡、R Gain",
        "example": "R Gain 274, G Gain 256, B Gain 292\nR Offset 256, G Offset 256, B Offset 256\n→ FacColorTemp 前6值 = 274,256,292,256,256,256",
        "params": {
            "values": "逗号分隔，3或6个值"
        }
    },
    {
        "name": "NLA 参数 (OSD曲线)",
        "rule_type": "nla",
        "desc": "修改 db.ini 中 NlaInfo_* 中间值",
        "file": "configs/db.ini",
        "trigger": "关键词：曲线、OSD、Brightness、Contrast 等",
        "example": "Brightness 265\n→ NlaInfo_brightness 中间值 = 265\n\nContrast 256\n→ NlaInfo_contrast 中间值 = 256",
        "params": {
            "param": "参数名",
            "value": "值"
        }
    },
    {
        "name": "Color Space 增益",
        "rule_type": "gain",
        "desc": "修改 db.ini 中 PQ_*_SatGain/HueGain/BriGain 前7值",
        "file": "configs/db.ini",
        "trigger": "关键词：Color Space、Saturation、Hue、Brightness",
        "example": "Saturation 3,3,-5,12,5,13,6\n→ PQ_*_SatGain 前7值 = 3,3,-5,12,5,13,6",
        "params": {
            "name": "SatGain/HueGain/BriGain",
            "values": "7个逗号分隔值"
        }
    },
    {
        "name": "菜单开关：内核",
        "rule_type": "ctv_setting",
        "desc": "显示/隐藏 内核 菜单",
        "file": "configs/ctvsetting.xml",
        "trigger": "关键词：显示内核 / 隐藏内核",
        "example": "隐藏内核\n→ ctvsetting.xml\n→ tv kernel enable=hide\n\n显示内核\n→ tv kernel enable=support",
        "params": {
            "name": "tv kernel",
            "enable": "support/hide/disable"
        }
    },
    {
        "name": "菜单开关：sdk",
        "rule_type": "ctv_setting",
        "desc": "显示/隐藏 sdk 菜单",
        "file": "configs/ctvsetting.xml",
        "trigger": "关键词：显示sdk / 隐藏sdk",
        "example": "隐藏sdk\n→ ctvsetting.xml\n→ tv sdk enable=hide\n\n显示sdk\n→ tv sdk enable=support",
        "params": {
            "name": "tv sdk",
            "enable": "support/hide/disable"
        }
    },
    {
        "name": "菜单开关：分辨率",
        "rule_type": "ctv_setting",
        "desc": "显示/隐藏 分辨率 菜单",
        "file": "configs/ctvsetting.xml",
        "trigger": "关键词：显示分辨率 / 隐藏分辨率",
        "example": "隐藏分辨率\n→ ctvsetting.xml\n→ tv resolution enable=hide\n\n显示分辨率\n→ tv resolution enable=support",
        "params": {
            "name": "tv resolution",
            "enable": "support/hide/disable"
        }
    },
    {
        "name": "菜单开关：软件",
        "rule_type": "ctv_setting",
        "desc": "显示/隐藏 软件 菜单",
        "file": "configs/ctvsetting.xml",
        "trigger": "关键词：显示软件 / 隐藏软件",
        "example": "隐藏软件\n→ ctvsetting.xml\n→ tv software enable=hide\n\n显示软件\n→ tv software enable=support",
        "params": {
            "name": "tv software",
            "enable": "support/hide/disable"
        }
    },
    {
        "name": "菜单开关：硬件",
        "rule_type": "ctv_setting",
        "desc": "显示/隐藏 硬件 菜单",
        "file": "configs/ctvsetting.xml",
        "trigger": "关键词：显示硬件 / 隐藏硬件",
        "example": "隐藏硬件\n→ ctvsetting.xml\n→ tv hardware enable=hide\n\n显示硬件\n→ tv hardware enable=support",
        "params": {
            "name": "tv hardware",
            "enable": "support/hide/disable"
        }
    },
    {
        "name": "菜单开关：型号",
        "rule_type": "ctv_setting",
        "desc": "显示/隐藏 型号 菜单",
        "file": "configs/ctvsetting.xml",
        "trigger": "关键词：显示型号 / 隐藏型号",
        "example": "隐藏型号\n→ ctvsetting.xml\n→ tv model enable=hide\n\n显示型号\n→ tv model enable=support",
        "params": {
            "name": "tv model",
            "enable": "support/hide/disable"
        }
    }
]


class RulePanel(QWidget):
    """规则管理页面：展示所有规则 + 自定义规则管理。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_rule: dict | None = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # 帮助说明
        help_lbl = QLabel(
            "💡 以下是系统已实现的所有修改规则。点击「复制」可创建自定义规则副本并修改参数。"
        )
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet(
            "background: #f8f9fb; border: 1px solid #e8eaf0; border-radius: 8px; "
            "padding: 10px 14px; font-size: 12px; color: #666666;"
        )
        root.addWidget(help_lbl)

        # ── 规则列表（内置 + 自定义）──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # ── 编辑表单（默认隐藏）──
        self._form_group = QGroupBox("添加自定义规则")
        self._form_group.setVisible(False)
        self._form_group.setStyleSheet(
            "QGroupBox { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px; "
            "padding: 16px; margin-top: 10px; font-weight: bold; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 6px; }"
        )
        form_layout = QVBoxLayout(self._form_group)

        # 基本字段
        basic = QFormLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("规则名称")
        self._name_input.setMinimumWidth(400)
        self._keywords_input = QLineEdit()
        self._keywords_input.setPlaceholderText("触发关键词，逗号分隔")
        self._keywords_input.setMinimumWidth(400)
        self._type_combo = QComboBox()
        self._type_combo.setView(QListView())
        self._type_combo.setMinimumWidth(400)
        self._type_combo.setStyleSheet(
            "QComboBox { background: #ffffff; color: #1a1a1a; border: 1px solid #dcdcdc; "
            "border-radius: 6px; padding: 6px 10px; font-size: 12px; }"
            "QComboBox::drop-down { border: none; width: 24px; }"
            "QComboBox QAbstractItemView { background: #ffffff; color: #1a1a1a; "
            "border: 1px solid #dcdcdc; selection-background-color: #e8e8e8; "
            "selection-color: #1a1a1a; }"
            "QComboBox QAbstractItemView::item { padding: 4px 8px; min-height: 24px; }"
        )
        from rules.custom_rule_manager import RULE_TYPES
        for key, info in RULE_TYPES.items():
            self._type_combo.addItem(info["label"], key)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        basic.addRow("名称:", self._name_input)
        basic.addRow("关键词:", self._keywords_input)
        basic.addRow("类型:", self._type_combo)
        form_layout.addLayout(basic)

        # 参数输入
        self._params_layout = QFormLayout()
        self._params_inputs: dict[str, QLineEdit] = {}
        form_layout.addLayout(self._params_layout)

        # 按钮
        btn_row = QHBoxLayout()
        save_btn = QPushButton("  保存")
        save_btn.setIcon(qta.icon("fa5s.save", color="#1a1a1a"))
        save_btn.setStyleSheet(self._btn_style())
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("  取消")
        cancel_btn.setStyleSheet(self._btn_style_secondary())
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        form_layout.addLayout(btn_row)

        root.addWidget(self._form_group)

        # 刷新列表
        self._refresh_list()

    # ── 刷新规则列表 ──────────────────────────────────
    def _refresh_list(self):
        # 清空
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # 内置规则标题
        builtin_title = QLabel("📋 内置规则（已实现，共 {} 条）".format(len(ALL_RULES)))
        builtin_title.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #1a1a1a; "
            "padding: 6px 0; background: transparent;"
        )
        self._list_layout.addWidget(builtin_title)

        # 内置规则卡片
        for rule in ALL_RULES:
            self._list_layout.addWidget(self._make_rule_card(rule, is_builtin=True))

        # 自定义规则
        custom_rules = load_rules()
        spacer = QLabel("")
        spacer.setFixedHeight(6)
        spacer.setStyleSheet("background: transparent;")
        self._list_layout.addWidget(spacer)

        custom_title = QLabel(f"✏️ 自定义规则（共 {len(custom_rules)} 条）")
        custom_title.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #1a1a1a; "
            "padding: 6px 0; background: transparent;"
        )
        self._list_layout.addWidget(custom_title)

        # 添加自定义规则按钮
        add_btn = QPushButton("  添加自定义规则")
        add_btn.setIcon(qta.icon("fa5s.plus-circle", color="#1a1a1a"))
        add_btn.setStyleSheet(self._btn_style())
        add_btn.clicked.connect(self._on_add)
        self._list_layout.addWidget(add_btn)

        if custom_rules:
            for rule in custom_rules:
                self._list_layout.addWidget(self._make_rule_card(rule, is_builtin=False))
        else:
            no_custom = QLabel("暂无自定义规则。点击「复制」内置规则可快速创建。")
            no_custom.setStyleSheet(
                "color: #999; font-size: 12px; padding: 10px; background: transparent;"
            )
            self._list_layout.addWidget(no_custom)

        self._list_layout.addStretch()

    def _make_rule_card(self, rule: dict, is_builtin: bool) -> QWidget:
        """创建一条规则的卡片。"""
        card = QWidget()
        card.setStyleSheet(
            "QWidget { background: #ffffff; border: 1px solid #e8e8e8; border-radius: 8px; }"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # 左侧：名称 + 描述
        info = QVBoxLayout()
        info.setSpacing(3)
        name_lbl = QLabel(rule.get("name", ""))
        name_lbl.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #1a1a1a; background: transparent;"
        )
        info.addWidget(name_lbl)

        desc = rule.get("desc", "")
        file = rule.get("file", "")
        if file:
            desc += f"  →  {file}"
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("font-size: 11px; color: #888; background: transparent;")
        desc_lbl.setWordWrap(True)
        info.addWidget(desc_lbl)

        trigger = rule.get("trigger", "")
        if trigger:
            trig_lbl = QLabel(f"触发: {trigger}")
            trig_lbl.setStyleSheet("font-size: 11px; color: #aaa; background: transparent;")
            info.addWidget(trig_lbl)

        layout.addLayout(info, 1)

        # 右侧：操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        if is_builtin:
            example_btn = QPushButton("  示例")
            example_btn.setIcon(qta.icon("fa5s.info-circle", color="#888"))
            example_btn.setStyleSheet(self._btn_style_secondary())
            example_btn.clicked.connect(lambda _, r=rule: self._show_example(r))
            btn_row.addWidget(example_btn)

            copy_btn = QPushButton("  复制")
            copy_btn.setIcon(qta.icon("fa5s.copy", color="#1a1a1a"))
            copy_btn.setStyleSheet(self._btn_style())
            copy_btn.clicked.connect(lambda _, r=rule: self._on_copy_builtin(r))
            btn_row.addWidget(copy_btn)
        else:
            edit_btn = QPushButton("  编辑")
            edit_btn.setIcon(qta.icon("fa5s.edit", color="#1a1a1a"))
            edit_btn.setStyleSheet(self._btn_style())
            edit_btn.clicked.connect(lambda _, r=rule: self._on_edit(r))
            btn_row.addWidget(edit_btn)

            del_btn = QPushButton("  删除")
            del_btn.setIcon(qta.icon("fa5s.trash-alt", color="#e17055"))
            del_btn.setStyleSheet(self._btn_style_secondary())
            del_btn.clicked.connect(lambda _, r=rule: self._on_delete(r))
            btn_row.addWidget(del_btn)

        layout.addLayout(btn_row)
        return card

    # ── 操作 ──────────────────────────────────────────
    def _on_type_changed(self, idx: int):
        rule_type = self._type_combo.currentData()
        from rules.custom_rule_manager import RULE_TYPES
        params = RULE_TYPES.get(rule_type, {}).get("params", [])
        # 清空旧输入（用 removeRow 避免破坏布局）
        while self._params_layout.rowCount() > 0:
            self._params_layout.removeRow(0)
        self._params_inputs.clear()
        hints = {
            "file": "文件路径 如 configs/db.ini", "key": "键名",
            "value": "值", "name": "节点名/菜单名",
            "package": "包名 如 com.example.app", "action": "add 或 remove",
            "app": "应用名 如 ESharePlus", "enabled": "true 或 false",
            "country_code": "国家码 如 CN", "target": "语言码 如 zh-Hans-CN",
            "values": "逗号分隔数值 如 274,256,292", "param": "参数名",
            "enable": "support / hide / disable",
        }
        for p in params:
            inp = QLineEdit()
            inp.setPlaceholderText(hints.get(p, p))
            inp.setMinimumWidth(400)
            self._params_inputs[p] = inp
            self._params_layout.addRow(f"{p}:", inp)

    def _on_add(self):
        self._editing_rule = None
        self._form_group.setTitle("添加自定义规则")
        self._name_input.clear()
        self._keywords_input.clear()
        self._type_combo.setCurrentIndex(0)
        self._on_type_changed(0)
        self._form_group.setVisible(True)

    def _on_edit(self, rule: dict):
        self._editing_rule = rule
        self._form_group.setTitle("编辑自定义规则")
        self._name_input.setText(rule.get("name", ""))
        self._keywords_input.setText(rule.get("keywords", ""))
        rtype = rule.get("rule_type", "")
        self._type_combo.blockSignals(True)
        idx = self._type_combo.findData(rtype)
        self._type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._type_combo.blockSignals(False)
        self._on_type_changed(idx if idx >= 0 else 0)
        params = rule.get("params", {})
        for key, inp in self._params_inputs.items():
            inp.setText(str(params.get(key, "")))
        self._form_group.setVisible(True)

    def _styled_msg(self, icon, title, text, buttons=None):
        """白底弹窗。"""
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        if buttons:
            box.setStandardButtons(buttons)
        box.setStyleSheet(
            "QMessageBox { background: #ffffff; }"
            "QMessageBox QLabel { color: #1a1a1a; background: transparent; font-size: 13px; }"
            "QMessageBox QPushButton { background: #e0e0e0; color: #1a1a1a; border: none; "
            "border-radius: 6px; padding: 6px 18px; font-size: 13px; min-width: 60px; }"
            "QMessageBox QPushButton:hover { background: #d5d5d5; }"
        )
        return box

    def _on_delete(self, rule: dict):
        rule_id = rule.get("id")
        if not rule_id:
            self._styled_msg(
                QMessageBox.Icon.Warning, "无法删除",
                "该规则没有 id（可能是旧数据），请手动编辑 config/custom_rules.json。",
            ).exec()
            return
        ret = self._styled_msg(
            QMessageBox.Icon.Question, "确认删除",
            f"确定要删除规则「{rule.get('name', '')}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ).exec()
        if ret == QMessageBox.StandardButton.Yes:
            delete_rule(rule_id)
            self._refresh_list()

    def _on_save(self):
        name = self._name_input.text().strip()
        keywords = self._keywords_input.text().strip()
        rule_type = self._type_combo.currentData()
        if not name:
            self._styled_msg(QMessageBox.Icon.Warning, "提示", "请填写规则名称").exec()
            return
        if not keywords:
            self._styled_msg(QMessageBox.Icon.Warning, "提示", "请填写触发关键词").exec()
            return
        # 必填参数校验
        from rules.custom_rule_manager import RULE_TYPES
        required = RULE_TYPES.get(rule_type, {}).get("required", [])
        params = {}
        for key, inp in self._params_inputs.items():
            val = inp.text().strip()
            if val:
                params[key] = val
        for rkey in required:
            if not params.get(rkey):
                self._styled_msg(
                    QMessageBox.Icon.Warning, "参数缺失",
                    f"请填写必填参数: {rkey}",
                ).exec()
                return
        # preinstall 的 enabled 规范化为 bool
        if rule_type == "preinstall" and "enabled" in params:
            params["enabled"] = str(params["enabled"]).lower() in ("true", "y", "1", "yes")
        rule = {"name": name, "keywords": keywords, "rule_type": rule_type, "params": params}
        if self._editing_rule and self._editing_rule.get("id"):
            rule["id"] = self._editing_rule["id"]
        save_rule(rule)
        self._form_group.setVisible(False)
        self._refresh_list()

    def _on_copy_builtin(self, rule: dict):
        """复制内置规则到自定义规则。"""
        self._editing_rule = None
        self._form_group.setTitle("复制规则（可修改参数后保存）")
        self._name_input.setText(rule.get("name", ""))
        self._keywords_input.setText(rule.get("trigger", ""))
        rtype = rule.get("rule_type", "")
        self._type_combo.blockSignals(True)
        idx = self._type_combo.findData(rtype)
        self._type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._type_combo.blockSignals(False)
        self._on_type_changed(idx if idx >= 0 else 0)
        params = rule.get("params", {})
        for key, inp in self._params_inputs.items():
            inp.setText(str(params.get(key, "")))
        self._form_group.setVisible(True)

    def _on_cancel(self):
        self._form_group.setVisible(False)

    def _show_example(self, rule: dict):
        example = rule.get("example", "暂无示例")
        msg = QMessageBox(self)
        msg.setWindowTitle(f"示例 — {rule.get('name', '')}")
        msg.setText(example.replace(chr(10), "<br>"))
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStyleSheet(
            "QMessageBox { background: #ffffff; }"
            "QLabel { color: #1a1a1a; font-size: 13px; background: transparent; min-width: 400px; }"
            "QPushButton { background: #e0e0e0; color: #1a1a1a; border: none; "
            "border-radius: 6px; padding: 6px 18px; font-size: 12px; }"
            "QPushButton:hover { background: #d5d5d5; }"
        )
        msg.exec()

    # ── 样式 ──────────────────────────────────────────
    @staticmethod
    def _btn_style():
        return (
            "QPushButton { background: #e0e0e0; color: #1a1a1a; border: none; "
            "border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
            "QPushButton:hover { background: #d5d5d5; }"
            "QPushButton:pressed { background: #cccccc; }"
        )

    @staticmethod
    def _btn_style_secondary():
        return (
            "QPushButton { background: transparent; color: #888888; border: 1px solid #dcdcdc; "
            "border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
            "QPushButton:hover { background: #f0f0f0; }"
        )
