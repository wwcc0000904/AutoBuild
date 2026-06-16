from __future__ import annotations

from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


class PropRule(BaseRule):
    """修改 .prop 文件中的键值对。

    格式: key=value
    key 和 value 之间只有一个 =，没有固定空格数。
    保留原有格式，只替换值。
    """

    def __init__(self, file: str, key: str, value: str) -> None:
        self.file = file
        self.key = key
        self.value = value

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
            stripped = line.strip()
            if stripped.startswith(self.key):
                new_lines.append(self._replace_value(line))
            else:
                new_lines.append(line)

        return "".join(new_lines)

    def _replace_value(self, line: str) -> str:
        if "=" in line:
            before, _ = line.split("=", 1)
            return f"{before}={self.value}\n"
        return line
