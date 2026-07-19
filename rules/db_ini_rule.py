from __future__ import annotations

import re
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
            # 保留后面的注释（分号及以后内容）
            if ";" in after:
                value_part, comment = after.split(";", 1)
                # comment 里可能含行尾换行符，单独分离出来
                cm = re.match(r'([^\r\n]*)(\r?\n)?$', comment)
                line_ending = cm.group(2) or "" if cm else ""
                if value_part.strip() == str(self.value).strip():
                    return line
                return f"{before}= {self.value};{cm.group(1) if cm else comment}{line_ending}"
            else:
                m = re.match(r'([^\r\n]*)(\r?\n)?$', after)
                old_value = m.group(1) if m else after
                line_ending = m.group(2) or "" if m else ""
                if old_value.strip() == str(self.value).strip():
                    return line
                return f"{before}= {self.value}{line_ending}"
        return line
