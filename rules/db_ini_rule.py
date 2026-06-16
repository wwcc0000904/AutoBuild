from __future__ import annotations

from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


class DbIniRule(BaseRule):
    """修改 db.ini 中的键值对。

    格式: Key = value;##注释
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
            before, after = line.split("=", 1)
            # 保留后面的注释（分号及以后内容）
            if ";" in after:
                comment = after.split(";", 1)[1]
                return f"{before}= {self.value};{comment}"
            else:
                return f"{before}= {self.value}\n"
        return line
