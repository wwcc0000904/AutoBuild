"""规则管理面板 —— 方块卡片网格布局，点击展开详情。"""
from __future__ import annotations

import json
from pathlib import Path

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFormLayout, QGroupBox, QListView,
    QScrollArea, QDialog, QSizePolicy, QLayout, QLayoutItem, QTextEdit,
)
from PySide6.QtCore import Qt, QSize, QRect, QPoint, QPropertyAnimation, QEasingCurve

from rules.custom_rule_manager import load_rules, save_rule, delete_rule


# ── FlowLayout：流式布局（Qt 官方示例移植）──────────────────
class FlowLayout(QLayout):
    """按行排列子 widget，超出宽度自动换行。"""

    def __init__(self, parent=None, margin=0, h_spacing=10, v_spacing=10):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._h_space = h_spacing
        self._v_space = v_spacing
        self._items: list[QLayoutItem] = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        line_h = 0

        for item in self._items:
            wid = item.widget()
            if wid and not wid.isVisible():
                continue
            space_x = self._h_space
            space_y = self._v_space
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective.right() + 1 and line_h > 0:
                x = effective.x()
                y = y + line_h + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_h = max(line_h, item.sizeHint().height())

        return y + line_h - rect.y() + m.bottom()


class _FlowLayoutContainer(QWidget):
    """支持 heightForWidth 的容器，让 FlowLayout 在 QVBoxLayout 中正确工作。"""

    def __init__(self, flow_layout: FlowLayout, parent=None):
        super().__init__(parent)
        self._flow = flow_layout
        self.setLayout(flow_layout)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._flow.heightForWidth(width)


# ── 规则类型图标映射 ──────────────────────────────────────
_RULE_TYPE_ICONS = {
    "build_config": ("fa5s.cogs", "#4a90d9"),
    "prop": ("fa5s.file-code", "#8e44ad"),
    "ctv_data": ("fa5s.database", "#e67e22"),
    "db_ini": ("fa5s.sliders-h", "#27ae60"),
    "whitelist": ("fa5s.list-ul", "#e74c3c"),
    "preinstall": ("fa5s.box", "#f39c12"),
    "country_list_first": ("fa5s.globe-americas", "#1abc9c"),
    "language_first": ("fa5s.language", "#3498db"),
    "language_add": ("fa5s.plus-circle", "#3498db"),
    "color_temp": ("fa5s.palette", "#9b59b6"),
    "nla": ("fa5s.chart-line", "#2ecc71"),
    "gain": ("fa5s.signal", "#e67e22"),
    "ctv_setting": ("fa5s.toggle-on", "#34495e"),
    "action_prefix": ("fa5s.text-width", "#795548"),
}

# ── 规则类型中文标签 ──────────────────────────────────────
_TYPE_LABELS = {
    "build_config": "Build Config",
    "prop": "属性",
    "ctv_data": "CTV Data",
    "db_ini": "DB INI",
    "whitelist": "白名单",
    "preinstall": "预装",
    "country_list_first": "国家",
    "language_first": "语言置顶",
    "language_add": "添加语言",
    "color_temp": "色温",
    "nla": "NLA",
    "gain": "增益",
    "ctv_setting": "菜单开关",
    "action_prefix": "全局前缀",
}


def _get_rule_icon(rule_type: str) -> tuple[str, str]:
    return _RULE_TYPE_ICONS.get(rule_type, ("fa5s.cog", "#888888"))


def _get_type_label(rule_type: str) -> str:
    return _TYPE_LABELS.get(rule_type, rule_type)

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
    },
    # ── 全局配置 ──
    {
        "name": "全局：打开动词",
        "rule_type": "action_prefix",
        "desc": "功能开关的打开动词前缀（全局生效）",
        "file": "feature_mapping.json",
        "trigger": "所有 open 类规则共用",
        "example": "打开杜比 → 匹配「打开」\n开启HBG → 匹配「开启」\n可在下方添加更多动词，如「启用」「激活」",
        "params": {}
    },
    {
        "name": "全局：关闭动词",
        "rule_type": "action_prefix",
        "desc": "功能开关的关闭动词前缀（全局生效）",
        "file": "feature_mapping.json",
        "trigger": "所有 close 类规则共用",
        "example": "关闭杜比 → 匹配「关闭」\n可在下方添加更多动词，如「禁用」「取消」",
        "params": {}
    },
    {
        "name": "全局：隐藏动词",
        "rule_type": "action_prefix",
        "desc": "隐藏类操作的动词前缀（全局生效）",
        "file": "feature_mapping.json",
        "trigger": "所有 hide 类规则共用",
        "example": "隐藏内核 → 匹配「隐藏」",
        "params": {}
    },
    {
        "name": "全局：显示动词",
        "rule_type": "action_prefix",
        "desc": "显示类操作的动词前缀（全局生效）",
        "file": "feature_mapping.json",
        "trigger": "所有 show 类规则共用",
        "example": "显示内核 → 匹配「显示」",
        "params": {}
    },
    {
        "name": "全局：值连接词",
        "rule_type": "action_prefix",
        "desc": "属性/CTVData 值匹配的连接词（全局生效）",
        "file": "feature_mapping.json",
        "trigger": "上电模式为待机 / 上电模式设为待机 等",
        "example": "上电模式待机 → 匹配「」（无连接词）\n上电模式为待机 → 匹配「为」\n上电模式设为待机 → 匹配「设为」\n可在下方添加更多连接词",
        "params": {}
    }
]


# ── 规则名 → feature_mapping.json 关键词路径 ──────────────
_RULE_KW_PATH: dict[str, str] = {
    # 国家/语言
    "国家列表置顶":        "country",
    "默认语言 (置顶)":    "language",
    "添加语言":           "language",
    # 开关
    "功能开关：HBG":       "open.HBG",
    "功能开关：TVcasting": "open.TVcasting",
    "功能开关：eshare":    "open.eshare",
    "功能开关：miracast":  "open.miracast",
    "功能开关：杜比":      "open.杜比",
    "功能开关：蓝屏":      "open.蓝屏",
    # 参数
    "参数修改：电流":      "param.电流",
    "参数修改：客户":      "param.客户",
    # 属性
    "属性：上电模式":      "prop.上电模式",
    "属性：开机模式":      "prop.开机模式",
    # CTV Data
    "CTV Data：开机桌面":       "ctv_data.开机桌面",
    "CTV Data：菜单显示时间":    "ctv_data.菜单显示时间",
    "CTV Data：语言显示":        "ctv_data.语言显示",
    "CTV Data：虚假信息显示":    "ctv_data.虚假信息显示",
    # 菜单开关
    "菜单开关：内核":      "ctv_setting_menu.内核",
    "菜单开关：sdk":       "ctv_setting_menu.sdk",
    "菜单开关：分辨率":    "ctv_setting_menu.分辨率",
    "菜单开关：软件":      "ctv_setting_menu.软件",
    "菜单开关：硬件":      "ctv_setting_menu.硬件",
    "菜单开关：型号":      "ctv_setting_menu.型号",
    # 通用规则（存到 keywords.xxx）
    "DB INI 修改":        "keywords.db_ini",
    "属性修改 (prop)":    "keywords.prop",
    "Build Config 修改":  "keywords.build_config",
    "CTV Data 修改":      "keywords.ctv_data",
    "CTV Data Ensure":    "keywords.ctv_data_ensure",
    "白名单添加":         "keywords.whitelist_add",
    "白名单移除":         "keywords.whitelist_remove",
    "预装应用":           "keywords.preinstall",
    "色温调整 (白平衡)":  "keywords.color_temp",
    "NLA 参数 (OSD曲线)": "keywords.nla",
    "Color Space 增益":   "keywords.gain",
    # 全局前缀配置
    "全局：打开动词":     "action_prefixes.open",
    "全局：关闭动词":     "action_prefixes.close",
    "全局：隐藏动词":     "action_prefixes.hide",
    "全局：显示动词":     "action_prefixes.show",
    "全局：值连接词":     "value_prefixes.default",
}


def _get_kw_path_for_rule(rule_name: str) -> str | None:
    return _RULE_KW_PATH.get(rule_name)


def _load_feature_mapping() -> dict:
    p = Path("config/feature_mapping.json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _save_feature_mapping(data: dict) -> None:
    p = Path("config/feature_mapping.json")
    p.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def _resolve_keywords_from_path(mapping: dict, kw_path: str) -> list[str]:
    """从 feature_mapping.json 中按路径读取关键词列表。"""
    parts = kw_path.split(".")
    node = mapping
    for part in parts:
        if isinstance(node, dict):
            node = node.get(part, {})
        else:
            return []
    # 有 keywords 数组 → 直接返回
    if isinstance(node, dict) and "keywords" in node:
        return list(node["keywords"])
    # 节点是 dict 但没有 keywords → 尝试从 value_map key 或中文 key 推断
    if isinstance(node, dict):
        if "value_map" in node:
            return list(node["value_map"].keys())
        _skip = {"file", "key", "value", "mode", "pattern", "name", "value_map", "keywords"}
        keys = [k for k in node.keys() if k not in _skip]
        if keys:
            return keys
    # 节点是字符串（如 ctv_setting_menu.xxx → "tv kernel"）
    if isinstance(node, str):
        return [parts[-1]]
    # 节点是列表
    if isinstance(node, list):
        return list(node)
    # 节点不存在 → 返回空，用户可自行添加
    return []


def _save_keywords_to_path(mapping: dict, kw_path: str, keywords: list[str]) -> None:
    """将关键词保存到 feature_mapping.json 对应路径。自动创建 keywords 数组。"""
    parts = kw_path.split(".")
    node = mapping
    for part in parts[:-1]:
        if part not in node:
            node[part] = {}
        node = node[part]
    leaf = parts[-1]
    target = node.get(leaf)
    if isinstance(target, dict):
        target["keywords"] = keywords
        node[leaf] = target
    elif isinstance(target, str):
        node[leaf] = {"value": target, "keywords": keywords}
    else:
        node[leaf] = {"keywords": keywords}


def _resolve_patterns_from_path(mapping: dict, kw_path: str) -> dict[str, list[str]]:
    """读取匹配模式，如 {"hide": ["隐藏","不显示"], "support": ["显示"]}。"""
    parts = kw_path.split(".")
    node = mapping
    for part in parts:
        if isinstance(node, dict):
            node = node.get(part, {})
        else:
            return {}
    if isinstance(node, dict) and "patterns" in node:
        return {k: list(v) for k, v in node["patterns"].items()}
    return {}


def _save_patterns_to_path(mapping: dict, kw_path: str, patterns: dict[str, list[str]]) -> None:
    """保存匹配模式到 feature_mapping.json。"""
    parts = kw_path.split(".")
    node = mapping
    for part in parts[:-1]:
        if part not in node:
            node[part] = {}
        node = node[part]
    leaf = parts[-1]
    target = node.get(leaf)
    if isinstance(target, dict):
        target["patterns"] = patterns
    else:
        node[leaf] = {"name": leaf, "patterns": patterns}




# ── RuleCardWidget：小卡片 + 点击弹出浮层详情 ─────────────
class RuleCardWidget(QWidget):
    """小卡片 → 点击弹出浮层详情，不影响网格布局。"""

    from PySide6.QtCore import Signal
    copy_requested = Signal(dict)
    edit_requested = Signal(dict)
    delete_requested = Signal(dict)

    COMPACT_W = 170
    COMPACT_H = 90

    def __init__(self, rule: dict, is_builtin: bool, parent=None):
        super().__init__(parent)
        self._rule = rule
        self._is_builtin = is_builtin
        self._overlay = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_compact()
        self.setFixedSize(self.COMPACT_W, self.COMPACT_H)

    # ── 紧凑卡片（始终不变）──
    def _build_compact(self):
        card = QWidget(self)
        card.setStyleSheet(
            "QWidget { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px; }"
            "QWidget:hover { border-color: #a0a0a0; background: #fafafa; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        rule_type = self._rule.get("rule_type", "")
        icon_name, icon_color = _get_rule_icon(rule_type)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(16, 16))
        icon_lbl.setStyleSheet("background: transparent;")
        top_row.addWidget(icon_lbl)
        type_lbl = QLabel(_get_type_label(rule_type))
        type_lbl.setStyleSheet(f"font-size: 10px; color: {icon_color}; background: transparent; font-weight: bold;")
        top_row.addWidget(type_lbl)
        top_row.addStretch()
        layout.addLayout(top_row)

        name_lbl = QLabel(self._rule.get("name", ""))
        name_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #1a1a1a; background: transparent;")
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl)

        file_path = self._rule.get("file", "")
        if file_path:
            file_lbl = QLabel(file_path)
            file_lbl.setStyleSheet("font-size: 10px; color: #aaa; background: transparent;")
            file_lbl.setMaximumWidth(self.COMPACT_W - 24)
            layout.addWidget(file_lbl)

        card.setGeometry(0, 0, self.COMPACT_W, self.COMPACT_H)

    # ── 点击弹出浮层 ──
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._show_overlay()
        super().mousePressEvent(event)

    def _show_overlay(self):
        """在顶层窗口上弹出浮层详情。"""
        # 找到顶层窗口
        win = self.window()
        if not win:
            return
        # 关闭已有浮层
        if RuleCardWidget._active_overlay:
            RuleCardWidget._active_overlay.close()
            RuleCardWidget._active_overlay.deleteLater()
            RuleCardWidget._active_overlay = None

        overlay = _RuleDetailOverlay(self._rule, self._is_builtin, win)
        # 信号穿透
        overlay.copy_requested.connect(self.copy_requested)
        overlay.edit_requested.connect(self.edit_requested)
        overlay.delete_requested.connect(self.delete_requested)
        overlay.show()
        RuleCardWidget._active_overlay = overlay

    # 类变量：当前活跃的浮层
    _active_overlay: "_RuleDetailOverlay | None" = None


class _RuleDetailOverlay(QWidget):
    """半透明遮罩 + 居中详情卡片浮层。"""

    from PySide6.QtCore import Signal
    copy_requested = Signal(dict)
    edit_requested = Signal(dict)
    delete_requested = Signal(dict)

    def __init__(self, rule: dict, is_builtin: bool, parent: QWidget):
        super().__init__(parent)
        self._rule = rule
        self._is_builtin = is_builtin
        self.setObjectName("ruleOverlay")
        # 覆盖整个父窗口
        self.setGeometry(parent.rect())
        self.setStyleSheet("QWidget#ruleOverlay { background: rgba(0, 0, 0, 0.35); }")

        # ── 居中详情卡片 ──
        card_w, card_h = 560, 480
        card = QWidget(self)
        card.setObjectName("detailCard")
        card.setStyleSheet(
            "QWidget#detailCard { background: #ffffff; border: 14px; border-radius: 14px; }"
        )
        card_w = min(card_w, parent.width() - 80)
        card_h = min(card_h, parent.height() - 60)
        cx = (parent.width() - card_w) // 2
        cy = (parent.height() - card_h) // 2
        card.setGeometry(cx, cy, card_w, card_h)

        root = QVBoxLayout(card)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(8)

        rule_type = rule.get("rule_type", "")
        icon_name, icon_color = _get_rule_icon(rule_type)

        # 标题行
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(20, 20))
        icon_lbl.setStyleSheet("background: transparent;")
        title_row.addWidget(icon_lbl)
        name_lbl = QLabel(rule.get("name", ""))
        name_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: #1a1a1a; background: transparent;")
        title_row.addWidget(name_lbl, 1)
        close_btn = QPushButton()
        close_btn.setIcon(qta.icon("fa5s.times", color="#999"))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #f0f0f0; }"
        )
        close_btn.clicked.connect(self.close_and_cleanup)
        title_row.addWidget(close_btn)
        root.addLayout(title_row)

        # 分隔线
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #e8e8e8;")
        root.addWidget(sep)

        # 滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 4, 0)
        body_lay.setSpacing(8)

        # 描述
        desc = rule.get("desc", "")
        if desc:
            lbl = QLabel(f"描述: {desc}")
            lbl.setStyleSheet("font-size: 12px; color: #555; background: transparent;")
            lbl.setWordWrap(True)
            body_lay.addWidget(lbl)

        # 触发条件
        trigger = rule.get("trigger", "")
        if trigger:
            lbl = QLabel(f"触发: {trigger}")
            lbl.setStyleSheet("font-size: 12px; color: #666; background: transparent;")
            lbl.setWordWrap(True)
            body_lay.addWidget(lbl)

        # 参数
        params = rule.get("params", {})
        if params:
            params_text = "  |  ".join(f"{k}={v}" for k, v in params.items() if v)
            lbl = QLabel(f"参数: {params_text}")
            lbl.setStyleSheet(
                "font-size: 11px; color: #888; background: #f8f9fb; border: 1px solid #eee;"
                " border-radius: 6px; padding: 4px 8px;"
            )
            lbl.setWordWrap(True)
            body_lay.addWidget(lbl)

        # 示例
        example = rule.get("example", "")
        if example:
            t = QLabel("示例:")
            t.setStyleSheet("font-size: 12px; font-weight: bold; color: #444; background: transparent;")
            body_lay.addWidget(t)
            lbl = QLabel(example)
            lbl.setStyleSheet(
                "font-size: 11px; color: #555; background: #fafafa; border: 1px solid #eee;"
                " border-radius: 6px; padding: 6px 10px; font-family: Menlo, monospace;"
            )
            lbl.setWordWrap(True)
            body_lay.addWidget(lbl)

        # 触发关键词
        if is_builtin:
            rule_name = rule.get("name", "")
            kw_path = _get_kw_path_for_rule(rule_name)
            if kw_path:
                fm = _load_feature_mapping()
                current_kws = _resolve_keywords_from_path(fm, kw_path)

                kw_header = QHBoxLayout()
                kw_title = QLabel("触发关键词:")
                kw_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #444; background: transparent;")
                kw_header.addWidget(kw_title)
                kw_header.addStretch()
                body_lay.addLayout(kw_header)

                self._kw_widget = KeywordListWidget()
                self._kw_widget.set_keywords(current_kws)
                body_lay.addWidget(self._kw_widget)
                self._kw_path = kw_path

                # 匹配模式（如 hide→["隐藏","不显示"], support→["显示"]）
                patterns = _resolve_patterns_from_path(fm, kw_path)
                if patterns:
                    sep2 = QLabel()
                    sep2.setFixedHeight(1)
                    sep2.setStyleSheet("background: #e8e8e8;")
                    body_lay.addWidget(sep2)

                    pat_title = QLabel("匹配模式:")
                    pat_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #444; background: transparent;")
                    body_lay.addWidget(pat_title)

                    self._pattern_widgets: dict[str, KeywordListWidget] = {}
                    _pat_labels = {
                        "hide": "→ 隐藏 (hide)",
                        "support": "→ 显示 (support)",
                        "value": "→ 值映射",
                    }
                    for val_name, kw_list in patterns.items():
                        lbl = QLabel(_pat_labels.get(val_name, f"→ {val_name}"))
                        lbl.setStyleSheet("font-size: 11px; color: #666; background: transparent; padding-left: 8px;")
                        body_lay.addWidget(lbl)
                        w = KeywordListWidget()
                        w.set_keywords(kw_list)
                        body_lay.addWidget(w)
                        self._pattern_widgets[val_name] = w

                    self._pat_kw_path = kw_path

        body_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        if is_builtin:
            rule_name = rule.get("name", "")
            _kw_path = _get_kw_path_for_rule(rule_name)
            if _kw_path:
                save_kw_btn = QPushButton("  保存关键词")
                save_kw_btn.setIcon(qta.icon("fa5s.save", color="#fff"))
                save_kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                save_kw_btn.setStyleSheet(
                    "QPushButton { background: #4a90d9; color: #ffffff; border: none;"
                    " border-radius: 6px; padding: 6px 16px; font-size: 12px; font-weight: bold; }"
                    "QPushButton:hover { background: #3a7bc8; }"
                )
                save_kw_btn.clicked.connect(self._save_keywords)
                btn_row.addWidget(save_kw_btn)

                # 保存匹配模式按钮（仅当有 patterns 时显示）
                _fm_check = _load_feature_mapping()
                if _resolve_patterns_from_path(_fm_check, _kw_path):
                    save_pat_btn = QPushButton("  保存匹配模式")
                    save_pat_btn.setIcon(qta.icon("fa5s.save", color="#fff"))
                    save_pat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    save_pat_btn.setStyleSheet(
                        "QPushButton { background: #27ae60; color: #ffffff; border: none;"
                        " border-radius: 6px; padding: 6px 16px; font-size: 12px; font-weight: bold; }"
                        "QPushButton:hover { background: #219a52; }"
                    )
                    save_pat_btn.clicked.connect(self._save_patterns)
                    btn_row.addWidget(save_pat_btn)

            copy_btn = QPushButton("  复制为自定义")
            copy_btn.setIcon(qta.icon("fa5s.copy", color="#1a1a1a"))
            copy_btn.setStyleSheet(_RuleCardWidget_btn_style())
            copy_btn.clicked.connect(lambda: (self.copy_requested.emit(rule), self.close_and_cleanup()))
            btn_row.addWidget(copy_btn)
        else:
            edit_btn = QPushButton("  编辑")
            edit_btn.setIcon(qta.icon("fa5s.edit", color="#1a1a1a"))
            edit_btn.setStyleSheet(_RuleCardWidget_btn_style())
            edit_btn.clicked.connect(lambda: (self.edit_requested.emit(rule), self.close_and_cleanup()))
            btn_row.addWidget(edit_btn)

            copy_btn = QPushButton("  复制")
            copy_btn.setIcon(qta.icon("fa5s.copy", color="#4a90d9"))
            copy_btn.setStyleSheet(_RuleCardWidget_btn_secondary())
            copy_btn.clicked.connect(lambda: (self.copy_requested.emit(rule), self.close_and_cleanup()))
            btn_row.addWidget(copy_btn)

            del_btn = QPushButton("  删除")
            del_btn.setIcon(qta.icon("fa5s.trash-alt", color="#e17055"))
            del_btn.setStyleSheet(_RuleCardWidget_btn_secondary())
            del_btn.clicked.connect(lambda: (self.delete_requested.emit(rule), self.close_and_cleanup()))
            btn_row.addWidget(del_btn)

        root.addLayout(btn_row)

    def close_and_cleanup(self):
        RuleCardWidget._active_overlay = None
        self.close()
        self.deleteLater()

    def _save_keywords(self):
        if not hasattr(self, '_kw_widget') or not hasattr(self, '_kw_path'):
            return
        new_kws = self._kw_widget.get_keywords()
        fm = _load_feature_mapping()
        _save_keywords_to_path(fm, self._kw_path, new_kws)
        _save_feature_mapping(fm)
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("已保存")
        box.setText(f"关键词已更新，共 {len(new_kws)} 个，立即生效。")
        box.setStyleSheet(
            "QMessageBox { background: #ffffff; }"
            "QMessageBox QLabel { color: #1a1a1a; background: transparent; }"
            "QPushButton { background: #e0e0e0; color: #1a1a1a; border: none;"
            " border-radius: 6px; padding: 6px 18px; }"
        )
        box.exec()

    def _save_patterns(self):
        if not hasattr(self, '_pattern_widgets') or not hasattr(self, '_pat_kw_path'):
            return
        new_patterns = {}
        for val_name, w in self._pattern_widgets.items():
            kws = w.get_keywords()
            if kws:
                new_patterns[val_name] = kws
        fm = _load_feature_mapping()
        _save_patterns_to_path(fm, self._pat_kw_path, new_patterns)
        _save_feature_mapping(fm)
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("已保存")
        total = sum(len(v) for v in new_patterns.values())
        box.setText(f"匹配模式已更新，共 {len(new_patterns)} 组 {total} 个模式词，立即生效。")
        box.setStyleSheet(
            "QMessageBox { background: #ffffff; }"
            "QMessageBox QLabel { color: #1a1a1a; background: transparent; }"
            "QPushButton { background: #e0e0e0; color: #1a1a1a; border: none;"
            " border-radius: 6px; padding: 6px 18px; }"
        )
        box.exec()

    def mousePressEvent(self, event):
        """点击遮罩区域关闭浮层。"""
        # 检查点击是否在卡片区域外
        for child in self.children():
            if isinstance(child, QWidget) and child.objectName() == "detailCard":
                if child.geometry().contains(event.position().toPoint()):
                    return  # 点在卡片内，不关闭
        self.close_and_cleanup()


def _RuleCardWidget_btn_style():
    return (
        "QPushButton { background: #e0e0e0; color: #1a1a1a; border: none; "
        "border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
        "QPushButton:hover { background: #d5d5d5; }"
        "QPushButton:pressed { background: #cccccc; }"
    )


def _RuleCardWidget_btn_secondary():
    return (
        "QPushButton { background: transparent; color: #888888; border: 1px solid #dcdcdc; "
        "border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
        "QPushButton:hover { background: #f0f0f0; }"
    )


class KeywordListWidget(QWidget):
    """可增删的关键词列表组件：每行一个关键词 + 删除按钮，底部添加按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[QLineEdit] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._rows_layout = layout
        # 底部添加按钮
        self._add_btn = QPushButton("＋ 添加关键词")
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet(
            "QPushButton { background: #4a90d9; color: #ffffff; border: none;"
            " border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background: #357abd; }"
            "QPushButton:pressed { background: #2c6aa0; }"
        )
        self._add_btn.clicked.connect(lambda: self._add_row(""))
        layout.addWidget(self._add_btn)
        # 默认一行
        self._add_row("")

    def _add_row(self, text: str = "") -> None:
        row = QHBoxLayout()
        row.setSpacing(4)
        inp = QLineEdit()
        inp.setText(text)
        inp.setPlaceholderText("触发关键词")
        inp.setStyleSheet(
            "QLineEdit { background: #ffffff; border: 1px solid #dcdcdc;"
            " border-radius: 6px; padding: 5px 10px; font-size: 12px; }"
        )
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(28, 28)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #e17055; border: none;"
            " font-size: 14px; }"
            "QPushButton:hover { color: #d63031; }"
        )
        idx = len(self._rows)
        del_btn.clicked.connect(lambda _, i=idx: self._del_row(i))
        row.addWidget(inp, 1)
        row.addWidget(del_btn)
        # 插入到添加按钮之前
        self._rows_layout.insertLayout(self._rows_layout.count() - 1, row)
        self._rows.append(inp)

    def _del_row(self, idx: int) -> None:
        if idx >= len(self._rows):
            return
        inp = self._rows.pop(idx)
        # 移除对应的布局行
        item = self._rows_layout.takeAt(idx)
        if item and item.layout():
            layout = item.layout()
            while layout.count():
                w = layout.takeAt(0).widget()
                if w and w is not inp:
                    w.deleteLater()
            inp.deleteLater()
        # 重新绑定剩余删除按钮的索引
        self._rebind_del_buttons()

    def _rebind_del_buttons(self) -> None:
        """删除行后重新绑定删除按钮的索引。"""
        for i in range(self._rows_layout.count() - 1):
            item = self._rows_layout.itemAt(i)
            if not item or not item.layout():
                continue
            hlayout = item.layout()
            # 第二个 widget 是删除按钮
            if hlayout.count() >= 2:
                del_btn = hlayout.itemAt(1).widget()
                if isinstance(del_btn, QPushButton):
                    del_btn.clicked.disconnect()
                    del_btn.clicked.connect(lambda _, i=i: self._del_row(i))

    def set_keywords(self, keywords) -> None:
        """设置关键词列表（接受 list 或逗号分隔字符串）。"""
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        elif keywords is None:
            keywords = []
        # 清空现有行
        while self._rows:
            self._del_row(0)
        if not keywords:
            self._add_row("")
        else:
            for kw in keywords:
                self._add_row(kw)

    def get_keywords(self) -> list[str]:
        return [inp.text().strip() for inp in self._rows if inp.text().strip()]


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
        self._keywords_input = KeywordListWidget()
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
            elif item.layout():
                layout = item.layout()
                while layout.count():
                    child = layout.takeAt(0)
                    cw = child.widget()
                    if cw:
                        cw.deleteLater()

        # 关闭已有浮层
        RuleCardWidget._active_overlay = None

        # ── 内置规则：按文件分组 ──
        title = QLabel(f"📋 内置规则（共 {len(ALL_RULES)} 条）")
        title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1a1a1a; "
            "padding: 6px 0; background: transparent;"
        )
        self._list_layout.addWidget(title)

        # 保持顺序的分组
        from collections import OrderedDict
        file_groups: OrderedDict[str, list[dict]] = OrderedDict()
        for rule in ALL_RULES:
            f = rule.get("file", "其他")
            file_groups.setdefault(f, []).append(rule)

        # 文件名 → 图标 + 显示名
        _FILE_META = {
            "build_config.txt":              ("📄", "build_config.txt"),
            "overlay/.../ctv_data.xml":      ("📋", "ctv_data.xml"),
            "configs/ctvsetting.xml":        ("⚙️", "ctvsetting.xml"),
            "configs/db.ini":                ("📊", "db.ini"),
            "ctvbuild.prop":                 ("📝", "ctvbuild.prop"),
            "etc/whiteList.conf":            ("📃", "whiteList.conf"),
            "configs/CtvLanguage.ini":       ("🌐", "CtvLanguage.ini"),
            "build_ctv_app.txt":             ("📦", "build_ctv_app.txt"),
        }

        for file_key, rules in file_groups.items():
            icon, display_name = _FILE_META.get(file_key, ("📄", file_key))

            # 文件分组标题
            group_header = QLabel(f"{icon}  {display_name}  ({len(rules)} 条)")
            group_header.setStyleSheet(
                "font-size: 12px; font-weight: bold; color: #555; "
                "padding: 8px 4px 2px 4px; background: transparent;"
                " border-bottom: 1px solid #e8e8e8;"
            )
            self._list_layout.addWidget(group_header)

            # 卡片网格
            flow = FlowLayout(margin=0, h_spacing=10, v_spacing=10)
            for rule in rules:
                card = RuleCardWidget(rule, is_builtin=True)
                card.copy_requested.connect(self._on_copy_builtin)
                flow.addWidget(card)
            self._list_layout.addWidget(_FlowLayoutContainer(flow))

        # ── 自定义规则 ──
        custom_rules = load_rules()
        spacer = QLabel("")
        spacer.setFixedHeight(6)
        spacer.setStyleSheet("background: transparent;")
        self._list_layout.addWidget(spacer)

        custom_title = QLabel(f"✏️ 自定义规则（共 {len(custom_rules)} 条）")
        custom_title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1a1a1a; "
            "padding: 6px 0; background: transparent;"
        )
        self._list_layout.addWidget(custom_title)

        add_btn = QPushButton("  添加自定义规则")
        add_btn.setIcon(qta.icon("fa5s.plus-circle", color="#1a1a1a"))
        add_btn.setStyleSheet(self._btn_style())
        add_btn.clicked.connect(self._on_add)
        self._list_layout.addWidget(add_btn)

        if custom_rules:
            # 自定义规则也按 rule_type 分组
            type_groups: OrderedDict[str, list[dict]] = OrderedDict()
            for rule in custom_rules:
                t = rule.get("rule_type", "other")
                type_groups.setdefault(t, []).append(rule)

            for rtype, rules in type_groups.items():
                label = _get_type_label(rtype)
                icon_name, icon_color = _get_rule_icon(rtype)

                group_header = QLabel(f"  {label}  ({len(rules)} 条)")
                group_header.setStyleSheet(
                    "font-size: 12px; font-weight: bold; color: #555; "
                    "padding: 8px 4px 2px 4px; background: transparent;"
                    " border-bottom: 1px solid #e8e8e8;"
                )
                self._list_layout.addWidget(group_header)

                flow = FlowLayout(margin=0, h_spacing=10, v_spacing=10)
                for rule in rules:
                    card = RuleCardWidget(rule, is_builtin=False)
                    card.copy_requested.connect(self._on_copy_custom)
                    card.edit_requested.connect(self._on_edit)
                    card.delete_requested.connect(self._on_delete)
                    flow.addWidget(card)
                self._list_layout.addWidget(_FlowLayoutContainer(flow))
        else:
            no_custom = QLabel("暂无自定义规则。点击「复制」内置规则可快速创建。")
            no_custom.setStyleSheet(
                "color: #999; font-size: 12px; padding: 10px; background: transparent;"
            )
            self._list_layout.addWidget(no_custom)

        self._list_layout.addStretch()

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
        self._keywords_input.set_keywords([])
        self._type_combo.setCurrentIndex(0)
        self._on_type_changed(0)
        self._form_group.setVisible(True)

    def _on_edit(self, rule: dict):
        self._editing_rule = rule
        self._form_group.setTitle("编辑自定义规则")
        self._name_input.setText(rule.get("name", ""))
        self._keywords_input.set_keywords(rule.get("keywords", []))
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
        keywords = self._keywords_input.get_keywords()
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
        self._keywords_input.set_keywords(rule.get("trigger", ""))
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

    def _on_copy_custom(self, rule: dict):
        """复制自定义规则：带出全部字段，名称加「副本」，存为新规则。"""
        self._editing_rule = None  # 清空 id，作为新增
        self._form_group.setTitle("复制规则（可修改后保存）")
        self._name_input.setText(rule.get("name", "") + " 副本")
        self._keywords_input.set_keywords(rule.get("keywords", []))
        rtype = rule.get("rule_type", "")
        self._type_combo.blockSignals(True)
        idx = self._type_combo.findData(rtype)
        self._type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._type_combo.blockSignals(False)
        self._on_type_changed(idx if idx >= 0 else 0)
        params = rule.get("params", {})
        for key, inp in self._params_inputs.items():
            val = params.get(key, "")
            if isinstance(val, bool):
                val = "true" if val else "false"
            inp.setText(str(val) if val != "" else "")
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
