from __future__ import annotations

import re
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
        self.confirmed: list[tuple[str, str, str]] = []

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
        self.confirmed = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(self.key):
                new_line = self._replace_value(line)
                new_lines.append(new_line)
                if new_line == line:
                    self.confirmed.append((self.file, self.key, str(self.value)))
            else:
                new_lines.append(line)

        return "".join(new_lines)

    def _replace_value(self, line: str) -> str:
        if "=" in line:
            before, after = line.split("=", 1)
            # 保留原行尾换行符，避免把 \r\n 误转成 \n
            m = re.match(r'([^\r\n]*)(\r?\n)?$', after)
            old_value = m.group(1) if m else after
            line_ending = m.group(2) or "" if m else ""
            if old_value.strip() == str(self.value).strip():
                return line  # 值没变，原样返回
            return f"{before}={self.value}{line_ending}"
        return line
