from __future__ import annotations

import re
from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


DB_INI_RELATIVE = "configs/db.ini"


class NlaRule(BaseRule):
    """修改 NlaInfo 非线性参数。

    支持两种模式:
    - single: 修改某个位置的单个值（默认 position=2 中间值）
    - full: 替换整行所有值

    用法:
        NlaRule("brightness", "205")              # 改中间值
        NlaRule("brightness", "205", position=2)  # 改中间值
        NlaRule.full("brightness", ["0","128","205","328","500"])  # 全行替换
    """

    def __init__(self, param: str, value: str, position: int = 2) -> None:
        self.param = param
        self.value = value
        self.position = position
        self._full_values: list[str] | None = None

    @classmethod
    def full(cls, param: str, values: list[str]) -> "NlaRule":
        """全行替换模式。"""
        rule = cls(param, values[0] if values else "0")
        rule._full_values = values
        return rule

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / DB_INI_RELATIVE
        if not target.exists():
            return changed

        content = target.read_text(encoding="utf-8")
        modified = self._modify_content(content)

        if modified != content:
            target.write_text(modified, encoding="utf-8")
            changed.append(target)

        return changed

    def _modify_content(self, content: str) -> str:
        lines = content.splitlines(keepends=True)
        new_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"NlaInfo_{self.param}"):
                new_lines.append(self._replace_value(line))
            else:
                new_lines.append(line)

        return "".join(new_lines)

    def _replace_value(self, line: str) -> str:
        # NlaInfo_brightness = 0,128,256,328,500;
        match = re.match(r'(NlaInfo_\w+\s*=\s*)([^;]+);', line)
        if not match:
            return line

        prefix = match.group(1)

        if self._full_values is not None:
            # 全行替换
            return f"{prefix}{','.join(self._full_values)};\n"
        else:
            # 替换单个位置
            values_str = match.group(2)
            values = [v.strip() for v in values_str.split(",")]
            if self.position < len(values):
                values[self.position] = self.value
            return f"{prefix}{','.join(values)};\n"
