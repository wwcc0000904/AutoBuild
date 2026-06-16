from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from rules.base_rule import BaseRule


CTV_DATA_RELATIVE = "overlay/cultraview/common/apps/CtvMiddleware/CultraviewTvService/res/raw/ctv_data.xml"


class CountryListRule(BaseRule):
    """将 CountryList 中的指定国家代码移到第一项，并去重。

    如果指定代码不在当前列表中，则不做修改，通过返回信息告知调用方。
    """

    def __init__(self, country_code: str) -> None:
        self.country_code = country_code.upper()

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / CTV_DATA_RELATIVE
        if not target.exists():
            return changed

        content = target.read_text(encoding="utf-8")
        match = re.search(r'(name="CountryList"\s+item=")([^"]+)(")', content)
        if not match:
            return changed

        current_items = [i.strip() for i in match.group(2).split(",")]

        if self.country_code not in current_items:
            return changed  # 列表中没有该国家，不做修改

        prefix = match.group(1)
        suffix = match.group(3)

        new_items = [self.country_code] + [i for i in current_items if i.upper() != self.country_code]
        new_items_str = ", ".join(new_items)

        new_content = content[:match.start()] + f'{prefix}{new_items_str}{suffix}' + content[match.end():]

        if new_content != content:
            target.write_text(new_content, encoding="utf-8")
            changed.append(target)

        return changed

    @staticmethod
    def check_country_exists(project_root: Path, country_code: str) -> bool:
        """检查国家代码是否已在 CountryList 中。"""
        target = project_root / CTV_DATA_RELATIVE
        if not target.exists():
            return False
        content = target.read_text(encoding="utf-8")
        match = re.search(r'name="CountryList"\s+item="([^"]+)"', content)
        if not match:
            return False
        items = [i.strip() for i in match.group(1).split(",")]
        return country_code.upper() in [i.upper() for i in items]
