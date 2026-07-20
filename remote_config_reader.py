"""远程配置读取器 — 从 SSH 服务器读取并解析各配置文件的当前值。"""
from __future__ import annotations

import re
from typing import Optional

from config.logging_setup import get_logger
from customer_project.remote_fs import RemotePath


# 文件相对路径
_PATHS = {
    "build_config":  "build_config.txt",
    "db_ini":        "configs/db.ini",
    "prop":          "ctvbuild.prop",
    "ctv_data":      "overlay/cultraview/common/apps/CtvMiddleware/CultraviewTvService/res/raw/ctv_data.xml",
    "ctv_setting":   "configs/ctvsetting.xml",
    "whitelist":     "etc/whiteList.conf",
    "preinstall":    "build_ctv_app.txt",
    "language":      "configs/CtvLanguage.ini",
}


class RemoteConfigReader:
    """从远程服务器读取配置文件并解析当前值。"""

    def __init__(self, ssh_client, source_path: str) -> None:
        self._ssh = ssh_client
        self._base = RemotePath(ssh_client, source_path)
        self._logger = get_logger()
        self._cache: dict[str, str] = {}  # 文件内容缓存

    def _read(self, file_key: str) -> Optional[str]:
        """读取文件内容（带缓存，自动尝试多种编码）。"""
        if file_key in self._cache:
            return self._cache[file_key]
        rel = _PATHS.get(file_key)
        if not rel:
            return None
        path = self._base / rel
        try:
            if not path.exists():
                return None
            # 尝试多种编码
            for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
                try:
                    content = path.read_text(encoding=enc)
                    self._cache[file_key] = content
                    return content
                except (UnicodeDecodeError, UnicodeError):
                    continue
            # 最后用 latin-1（永远不会失败）
            content = path.read_text(encoding="latin-1")
            self._cache[file_key] = content
            return content
        except Exception as e:
            self._logger.warning("读取 %s 失败: %s", rel, e)
            return None

    # ── build_config.txt ──

    def read_build_config(self, keys: list[str]) -> dict[str, str]:
        """读取 build_config.txt 中指定 key 的值。"""
        content = self._read("build_config")
        if not content:
            return {}
        result = {}
        for key in keys:
            m = re.search(rf'^\s*{re.escape(key)}\s*=\s*(.+?)$', content, re.MULTILINE)
            if m:
                result[key] = m.group(1).strip()
        return result

    # ── db.ini ──

    def read_db_ini(self, keys: list[str]) -> dict[str, str]:
        """读取 db.ini 中指定 key 的值（去掉注释部分）。"""
        content = self._read("db_ini")
        if not content:
            return {}
        result = {}
        for key in keys:
            m = re.search(rf'^\s*{re.escape(key)}\s*=\s*(.+?)$', content, re.MULTILINE)
            if m:
                val = m.group(1).strip()
                # 去掉 ;## 注释
                if ";##" in val:
                    val = val[:val.index(";##")].strip()
                if ";" in val:
                    val = val[:val.index(";")].strip()
                result[key] = val
        return result

    # ── ctvbuild.prop ──

    def read_prop(self, keys: list[str]) -> dict[str, str]:
        """读取 ctvbuild.prop 中指定 key 的值。"""
        content = self._read("prop")
        if not content:
            return {}
        result = {}
        for key in keys:
            m = re.search(rf'^{re.escape(key)}=(.*)$', content, re.MULTILINE)
            if m:
                result[key] = m.group(1).strip()
        return result

    # ── ctv_data.xml ──

    def read_ctv_data(self, names: list[str]) -> dict[str, str]:
        """读取 ctv_data.xml 中指定 data 节点的 value。"""
        content = self._read("ctv_data")
        if not content:
            return {}
        result = {}
        for name in names:
            m = re.search(rf'name="{re.escape(name)}"\s+(?:value|item)="([^"]*)"', content)
            if m:
                result[name] = m.group(1).strip()
        return result

    # ── 白平衡（FacColorTemp_*_nature）──

    def read_color_temp(self) -> Optional[str]:
        """读取白平衡行的前6个值（R,G,B,R_O,G_O,B_O）。"""
        content = self._read("db_ini")
        if not content:
            return None
        for line in content.splitlines():
            if "FacColorTemp" in line and "_nature" in line and "=" in line:
                val_part = line.split("=", 1)[1].strip()
                if ";" in val_part:
                    val_part = val_part[:val_part.index(";")].strip()
                return val_part  # 如 "274,256,292,256,256,256"
        return None

    # ── Gain（SatGain/HueGain/BriGain）──

    def read_gain(self, gain_name: str) -> Optional[str]:
        """读取 PQ_*_{gain_name} 行的前7个值。"""
        content = self._read("db_ini")
        if not content:
            return None
        for line in content.splitlines():
            if gain_name in line and "=" in line:
                val_part = line.split("=", 1)[1].strip()
                if ";" in val_part:
                    val_part = val_part[:val_part.index(";")].strip()
                # 取前7个值
                vals = [v.strip() for v in val_part.split(",")]
                return ",".join(vals[:7])
        return None

    # ── ctvsetting.xml ──

    def read_ctv_setting(self, en_names: list[str]) -> dict[str, str]:
        """读取 ctvsetting.xml 中指定菜单项的 enable 值。"""
        content = self._read("ctv_setting")
        if not content:
            return {}
        result = {}
        for name in en_names:
            m = re.search(rf'name="{re.escape(name)}"[^>]*enable="([^"]*)"', content)
            if m:
                result[name] = m.group(1).strip()
        return result

    # ── whiteList.conf ──

    def read_whitelist_packages(self) -> list[str]:
        """读取白名单中的所有包名。"""
        content = self._read("whitelist")
        if not content:
            return []
        # 按逗号/换行分割，去掉空白和续行符
        raw = content.replace("\\\n", "").replace("\n", ",")
        pkgs = [p.strip() for p in raw.split(",") if p.strip() and not p.strip().startswith("#")]
        return pkgs

    # ── build_ctv_app.txt ──

    def read_preinstall(self, app: str) -> Optional[str]:
        """读取预装应用状态。返回 Y/n/None。"""
        content = self._read("preinstall")
        if not content:
            return None
        m = re.search(rf'^\s*{re.escape(app)}\s*=\s*(.+?)$', content, re.MULTILINE)
        if m:
            return m.group(1).strip().upper()
        return None

    # ── CountryList（从 ctv_data.xml 读取）──

    def read_country_list(self) -> list[str]:
        """读取 CountryList 中的国家码列表。"""
        content = self._read("ctv_data")
        if not content:
            return []
        m = re.search(r'name="CountryList"\s+item="([^"]+)"', content)
        if m:
            return [c.strip() for c in m.group(1).split(",")]
        return []

    # ── CtvLanguage.ini ──

    def read_language_first(self) -> Optional[str]:
        """读取当前默认语言（第一行有效语言）。"""
        content = self._read("language")
        if not content:
            return None
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            return line  # CSV 格式: code,name,...
        return None
