from __future__ import annotations

import re
from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


DB_INI_RELATIVE = "configs/db.ini"


class ColorTempRule(BaseRule):
    """批量修改 db.ini 中所有 nature 色温行。

    支持两种模式:
    - 3 值模式: 只改 R/G/B Gain（默认）
    - 6 值模式: 改 R/G/B Gain + R/G/B Offset

    用法:
        ColorTempRule("274", "256", "292")        # 前3值
        ColorTempRule("274", "256", "292", "256", "256", "256")  # 前6值
    """

    def __init__(self, *values: str) -> None:
        if len(values) not in (3, 6):
            raise ValueError(f"ColorTempRule 需要 3 或 6 个值，收到 {len(values)}")
        self.values = list(values)
        self._new_value = ",".join(values)

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / DB_INI_RELATIVE
        if not target.exists():
            return changed

        content = target.read_text(encoding="utf-8")
        n = len(self.values)

        # 替换前 n 个数字
        pattern = r'(FacColorTemp_\w+_nature\s*=\s*)' + r'\d+,' * (n - 1) + r'\d+'
        modified = re.sub(
            pattern,
            lambda m: m.group(1) + self._new_value,
            content,
        )

        if modified != content:
            target.write_text(modified, encoding="utf-8")
            changed.append(target)

        return changed
