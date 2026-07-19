from __future__ import annotations

import re
from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


DB_INI_RELATIVE = "configs/db.ini"


class GainRule(BaseRule):
    """批量修改 PQ_*_{name} 行的前 7 个值，后 2 个保留不变。

    适用于 SatGain、HueGain、BriGain 等同类参数。
    """

    def __init__(self, name: str, values: list[str]) -> None:
        self.name = name
        self.values = values
        self._new_prefix = ",".join(values)

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / DB_INI_RELATIVE
        if not target.exists():
            return changed

        content = target.read_text(encoding="utf-8")

        safe_name = re.escape(self.name)
        modified = re.sub(
            rf'(PQ_\w+_{safe_name}\s*=\s*)([\d,;-]+)',
            lambda m: self._replace_line(m),
            content,
        )

        if modified != content:
            target.write_text(modified, encoding="utf-8")
            changed.append(target)

        return changed

    def _replace_line(self, m: re.Match) -> str:
        prefix = m.group(1)
        all_values = m.group(2).rstrip(";").split(",")
        tail = all_values[-2:] if len(all_values) >= 2 else all_values
        # 不加 \n，原行的 \n 会保留
        return f"{prefix}{self._new_prefix},{','.join(tail)};"
