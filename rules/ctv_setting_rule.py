from __future__ import annotations

import re
from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


CTV_SETTING_RELATIVE = "configs/ctvsetting.xml"


class CtvSettingRule(BaseRule):
    """修改 ctvsetting.xml 中指定菜单项的 enable 属性。

    支持精确匹配和前缀匹配两种模式。
    """

    def __init__(self, name: str, enable: str, prefix_match: bool = False) -> None:
        self.name = name
        self.enable = enable
        self.prefix_match = prefix_match

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / CTV_SETTING_RELATIVE
        if not target.exists():
            return changed

        content = target.read_text(encoding="utf-8")

        if self.prefix_match:
            modified = self._modify_prefix(content)
        else:
            modified = self._modify_exact(content)

        if modified != content:
            target.write_text(modified, encoding="utf-8")
            changed.append(target)

        return changed

    def _modify_exact(self, content: str) -> str:
        pattern = rf'(name="{re.escape(self.name)}"\s+[^>]*?enable=")[^"]*(")'
        return re.sub(pattern, rf'\g<1>{self.enable}\g<2>', content)

    def _modify_prefix(self, content: str) -> str:
        """匹配所有 name 以此前缀开头的 Item。"""
        pattern = rf'(name="{re.escape(self.name)}[^"]*"\s+[^>]*?enable=")[^"]*(")'
        return re.sub(pattern, rf'\g<1>{self.enable}\g<2>', content)
