from __future__ import annotations

from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


class WhitelistRule(BaseRule):
    """管理 whiteList.conf 中的包名。

    支持追加和删除包名。
    如果包名已存在，追加操作不重复添加。
    """

    def __init__(self, package: str, action: str = "add") -> None:
        self.package = package
        self.action = action  # "add" 或 "remove"

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / "etc" / "whiteList.conf"
        if not target.exists():
            return changed

        content = target.read_text(encoding="utf-8")

        if self.action == "add":
            new_content = self._add_package(content)
        elif self.action == "remove":
            new_content = self._remove_package(content)
        else:
            return changed

        if new_content != content:
            target.write_text(new_content, encoding="utf-8")
            changed.append(target)

        return changed

    def _add_package(self, content: str) -> str:
        if self.package in content:
            return content
        # 追加到最后一行（保持缩进格式）
        indent = "                  "
        new_line = f"{indent}{self.package},\\"
        # 在最后一个反斜杠行后面追加
        lines = content.splitlines(keepends=True)
        # 找到最后一行以反斜杠结尾的行
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].rstrip().endswith(",\\"):
                # 在它后面插入
                lines.insert(i + 1, new_line + "\n")
                return "".join(lines)
        return content + new_line + "\n"

    def _remove_package(self, content: str) -> str:
        lines = content.splitlines(keepends=True)
        new_lines = [l for l in lines if self.package not in l]
        return "".join(new_lines)
