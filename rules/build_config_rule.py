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
        # 值已是目标值、未触发写入的配置项：(file, key, final_value)
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
            if line.strip().startswith(self.key):
                new_line = self._modify_line(line)
                new_lines.append(new_line)
                # 值没变时记录确认项，让用户看到最终值
                if new_line == line:
                    m = re.match(r'\s*' + re.escape(self.key) + r'\s*=\s*([^\r\n]*)', new_line)
                    if m:
                        self.confirmed.append((self.file, self.key, m.group(1).strip()))
            else:
                new_lines.append(line)

        return "".join(new_lines)

    def _modify_line(self, line: str) -> str:
        # 用 [^\r\n]* 匹配值（避免吃掉 \r），用 (\r?\n)? 捕获行尾换行符
        eq_match = re.match(r'(\s*' + re.escape(self.key) + r'\s*=\s*)([^\r\n]*)(\r?\n)?$', line)
        if not eq_match:
            return line

        prefix = eq_match.group(1)
        value_part = eq_match.group(2)
        line_ending = eq_match.group(3) or ""

        if self.mode == "value_part":
            new_value_part = re.sub(r'^\d+', self.new_value, value_part)
        else:
            new_value_part = self.new_value

        if new_value_part == value_part:
            # 值没变，原样返回（保留原换行符，避免误判为已修改）
            return line

        return prefix + new_value_part + line_ending
