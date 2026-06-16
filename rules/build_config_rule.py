from __future__ import annotations

import re
from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


class BuildConfigRule(BaseRule):
    """修改某个配置文件中的键值对。

    支持两种模式:
    - value: 直接替换整行值
    - value_part: 替换类似 "600/900" 中 "/" 前的部分
    """

    def __init__(self, file: str, key: str, new_value: str, mode: str = "value") -> None:
        self.file = file
        self.key = key
        self.new_value = new_value
        self.mode = mode

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / self.file

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
            if line.strip().startswith(self.key):
                new_lines.append(self._modify_line(line))
            else:
                new_lines.append(line)

        return "".join(new_lines)

    def _modify_line(self, line: str) -> str:
        eq_match = re.match(r'(\s*' + re.escape(self.key) + r'\s*=\s*)(.+)', line)
        if not eq_match:
            return line

        prefix = eq_match.group(1)
        value_part = eq_match.group(2)

        if self.mode == "value_part":
            new_value_part = re.sub(r'^\d+', self.new_value, value_part)
        else:
            new_value_part = self.new_value + "\n"

        if line.endswith("\n") and not new_value_part.endswith("\n"):
            new_value_part += "\n"

        return prefix + new_value_part
